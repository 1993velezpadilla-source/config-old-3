#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
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
    selected=None
    promoted=False
    if eligible:
        # Lowest profile error wins. Exact ties prefer the untouched multi-view
        # baseline so a challenger must provide measurable evidence to replace it.
        eligible.sort(
            key=lambda row:(
                float(row["median_profile_error"]),
                float(row["p90_profile_error"]),
                0 if row["name"]=="multiview_base" else 1,
                row["name"],
            )
        )
        selected=eligible[0]
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
            "fail_closed":True,
        },
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
