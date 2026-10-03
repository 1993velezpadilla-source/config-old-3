#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
from pathlib import Path


FACE_COVERAGE_MIN=0.60
FACE_MEDIAN_MAX=0.22
FACE_P90_MAX=0.35


def _run(command:list[str])->dict:
    proc=subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "returncode":int(proc.returncode),
        "stdout":proc.stdout[-12000:],
        "stderr":proc.stderr[-12000:],
    }


def _candidate_sources(root:Path)->list[Path]:
    sources=[]
    for folder in (root/"prepared_views",root/"prepared_details"):
        if folder.is_dir():
            sources.extend(sorted(folder.glob("*.png")))
            sources.extend(sorted(folder.glob("*.jpg")))
            sources.extend(sorted(folder.glob("*.jpeg")))
            sources.extend(sorted(folder.glob("*.webp")))
    # Preserve order while removing duplicates.
    seen=set()
    unique=[]
    for path in sources:
        key=str(path.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique



def _dreamsim_face_distances(
    source_paths:list[Path],
    rows:list[dict],
)->dict:
    """Add source-grounded perceptual face distance without weakening hard gates."""
    if not source_paths:
        return {"ready":False,"reason":"no_detected_face_sources"}

    try:
        import torch
        from PIL import Image
        from dreamsim import dreamsim
        from judge_v4_face_worker import _crop_top_subject

        device="cuda" if torch.cuda.is_available() else "cpu"
        model,preprocess=dreamsim(pretrained=True,device=device)
        model.eval()

        prepared_sources=[]
        for path in source_paths:
            if not path.is_file():
                continue
            image=_crop_top_subject(Image.open(path).convert("RGB"))
            prepared_sources.append((
                path,
                preprocess(image).to(device),
            ))
        if not prepared_sources:
            return {"ready":False,"reason":"face_source_files_missing"}

        scored=0
        with torch.inference_mode():
            for row in rows:
                render_raw=row.get("render_face")
                if not render_raw:
                    continue
                render_path=Path(render_raw)
                if not render_path.is_file():
                    continue
                candidate=_crop_top_subject(
                    Image.open(render_path).convert("RGB")
                )
                candidate_tensor=preprocess(candidate).to(device)
                distances=[]
                source_scores=[]
                for source_path,source_tensor in prepared_sources:
                    distance=float(
                        model(source_tensor,candidate_tensor)
                        .detach().cpu().item()
                    )
                    if not (distance==distance):
                        continue
                    distances.append(distance)
                    source_scores.append({
                        "source":str(source_path),
                        "distance":round(distance,6),
                    })
                if not distances:
                    continue
                source_scores.sort(key=lambda item:item["distance"])
                row["dreamsim_face_mean_distance"]=round(
                    float(statistics.mean(distances)),6
                )
                row["dreamsim_face_median_distance"]=round(
                    float(statistics.median(distances)),6
                )
                row["dreamsim_face_best_distance"]=round(
                    float(min(distances)),6
                )
                row["dreamsim_face_best_source"]=source_scores[0]["source"]
                row["dreamsim_face_sources"]=source_scores
                scored+=1

        return {
            "ready":scored>0,
            "device":device,
            "model":"DreamSim",
            "source_count":len(prepared_sources),
            "candidate_count":scored,
            "selection_metric":"dreamsim_face_median_distance",
        }
    except Exception as exc:
        return {
            "ready":False,
            "reason":f"{type(exc).__name__}:{exc}",
        }


def _rank_eligible(eligible:list[dict],dreamsim_ready:bool)->list[dict]:
    """Rank only candidates that already passed the existing facial hard gates."""
    if dreamsim_ready:
        usable=[
            row for row in eligible
            if row.get("dreamsim_face_median_distance") is not None
        ]
        if len(usable)==len(eligible) and usable:
            return sorted(
                eligible,
                key=lambda row:(
                    float(row["dreamsim_face_median_distance"]),
                    float(row["median_profile_error"]),
                    float(row["p90_profile_error"]),
                    0 if row["name"]=="multiview_base" else 1,
                    row["name"],
                ),
            )
    return sorted(
        eligible,
        key=lambda row:(
            float(row["median_profile_error"]),
            float(row["p90_profile_error"]),
            0 if row["name"]=="multiview_base" else 1,
            row["name"],
        ),
    )

def main()->int:
    p=argparse.ArgumentParser(
        description="Render and select a HAYUYA facial geometry challenger."
    )
    p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--blender",default="blender")
    p.add_argument("--python",default=sys.executable)
    p.add_argument(
        "--renderer",
        type=Path,
        default=Path("tools/hayuya3d/blender_judge_turntable_24.py"),
    )
    p.add_argument(
        "--face-worker",
        type=Path,
        default=Path("tools/hayuya3d/judge_v4_face_worker.py"),
    )
    a=p.parse_args()

    root=a.output_root
    manifest_path=root/"face_geometry_candidates.json"
    report_path=root/"face_geometry_tournament.json"
    if not manifest_path.is_file():
        report={
            "schema":1,
            "attempted":False,
            "reason":"candidate_manifest_missing",
            "selected":None,
            "promoted":False,
        }
        report_path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print("HAYUYA_FACE_GEOMETRY_TOURNAMENT "+json.dumps(report,separators=(",",":")))
        return 0

    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    master=Path(manifest["master"])
    sources=_candidate_sources(root)
    candidates=[
        row for row in manifest.get("candidates",[])
        if row.get("hard_gate_passed") and Path(row.get("path","")).is_file()
    ]

    tournament_dir=root/"face_geometry_tournament"
    tournament_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    detected_source_faces={}

    for index,row in enumerate(candidates):
        name=str(row.get("name") or f"candidate_{index:02d}")
        path=Path(row["path"])
        render_dir=tournament_dir/f"{index:02d}_{name}"
        render_cmd=[
            str(a.blender),
            "--background",
            "--python-exit-code","1",
            "--python",str(a.renderer),
            "--",
            "--input",str(path),
            "--output-dir",str(render_dir),
            "--preflight-only",
            "--size","768",
            "--face-size","768",
        ]
        render=_run(render_cmd)
        candidate_face=render_dir/"faces"/"12_180.png"
        candidate_report=render_dir/"face_report.json"
        face_cmd=[
            str(a.python),
            str(a.face_worker),
        ]
        for source in sources:
            face_cmd.extend(["--source",str(source)])
        face_cmd.extend([
            "--candidate",str(candidate_face),
            "--output",str(candidate_report),
        ])

        face_run=None
        face_report=None
        if render["returncode"]==0 and candidate_face.is_file():
            face_run=_run(face_cmd)
            if face_run["returncode"]==0 and candidate_report.is_file():
                face_report=json.loads(candidate_report.read_text(encoding="utf-8"))
                for source_row in face_report.get("source",[]):
                    raw_source=source_row.get("path")
                    if raw_source:
                        source_path=Path(raw_source)
                        detected_source_faces[str(source_path)]=source_path

        detected=int((face_report or {}).get("candidate_detected",0) or 0)
        total=int((face_report or {}).get("candidate_total",1) or 1)
        coverage=float(detected)/float(max(total,1))
        median=(face_report or {}).get("median_profile_error")
        p90=(face_report or {}).get("p90_profile_error")
        expected=bool((face_report or {}).get("face_expected_from_source",True))
        eligible=bool(
            expected
            and coverage>=FACE_COVERAGE_MIN
            and median is not None
            and p90 is not None
            and float(median)<=FACE_MEDIAN_MAX
            and float(p90)<=FACE_P90_MAX
        )
        rows.append({
            "name":name,
            "path":str(path),
            "kind":row.get("kind"),
            "eligible":eligible,
            "face_expected_from_source":expected,
            "candidate_detected":detected,
            "candidate_total":total,
            "coverage":round(coverage,6),
            "median_profile_error":median,
            "p90_profile_error":p90,
            "render_face":str(candidate_face) if candidate_face.is_file() else None,
            "render_returncode":render["returncode"],
            "face_returncode":(
                face_run["returncode"] if face_run is not None else None
            ),
            "render_stderr":render["stderr"] if render["returncode"] else "",
            "face_stderr":(
                face_run["stderr"]
                if face_run is not None and face_run["returncode"]
                else ""
            ),
        })

    eligible=[row for row in rows if row["eligible"]]

    # Perceptual fidelity is evaluated only after the existing facial hard gates.
    # Normalize sources to the upper subject/head before DreamSim comparison so
    # full-body framing and background cannot dominate facial selection.
    detected=list(detected_source_faces.values())
    detail_detected=[
        path for path in detected
        if "prepared_details" in path.parts
    ]
    fidelity_sources=detail_detected or detected
    dreamsim=_dreamsim_face_distances(fidelity_sources,rows)
    ranked=_rank_eligible(eligible,bool(dreamsim.get("ready")))

    selected=None
    promoted=False
    if ranked:
        selected=ranked[0]
        selected_path=Path(selected["path"])
        if selected_path.resolve()!=master.resolve():
            master.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(selected_path,master)
            promoted=True

    report={
        "schema":1,
        "attempted":True,
        "policy":{
            "face_detection_coverage_min":FACE_COVERAGE_MIN,
            "median_profile_error_max":FACE_MEDIAN_MAX,
            "p90_profile_error_max":FACE_P90_MAX,
            "tie_break":"prefer_multiview_base",
            "selection_order":(
                "hard_face_gates_then_dreamsim_then_landmarks"
                if dreamsim.get("ready")
                else "hard_face_gates_then_landmarks"
            ),
            "fail_closed":True,
        },
        "dreamsim":dreamsim,
        "fidelity_sources":[str(path) for path in fidelity_sources],
        "source_count":len(sources),
        "candidate_count":len(rows),
        "eligible_count":len(eligible),
        "selected":selected,
        "promoted":promoted,
        "master":str(master),
        "candidates":rows,
    }
    report_path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(
        "HAYUYA_FACE_GEOMETRY_TOURNAMENT "
        +json.dumps(report,separators=(",",":"))
    )
    return 0


if __name__=="__main__":
    raise SystemExit(main())
