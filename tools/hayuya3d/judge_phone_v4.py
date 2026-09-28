#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from gameprep import build_turntable
from judge_v4 import JudgeV4Thresholds, run_judge_v4


IMAGE_EXTS={".png",".jpg",".jpeg",".webp"}


def _images(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [
        path for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    ]


def _is_character(manifest: dict) -> bool:
    values=[
        manifest.get("asset_profile"),
        (manifest.get("asset") or {}).get("profile"),
        manifest.get("mode"),
    ]
    text=" ".join(str(x or "").lower() for x in values)
    return any(token in text for token in (
        "character","humanoid","creature","monster","zombie","undead","human"
    ))


def _resolved_render_path(value:str)->Path:
    path=Path(value)
    return path if path.is_absolute() else (Path.cwd()/path).resolve()


def _run_front_preflight(
    final_glb:Path,
    out_dir:Path,
    source_images:list[Path],
    detail_images:list[Path],
    python_executable:str,
)->dict|None:
    blender=shutil.which("blender")
    if not blender:
        return None

    script=Path(__file__).with_name("blender_judge_turntable_24.py")
    face_worker=Path(__file__).with_name("judge_v4_face_worker.py")
    root=out_dir/"front_preflight"
    render_root=root/"blender"
    render_root.mkdir(parents=True,exist_ok=True)
    log_path=root/"blender.log"
    cmd=[
        blender,
        "--python-exit-code","1",
        "-b",
        "--python",str(script),
        "--",
        "--input",str(final_glb),
        "--output-dir",str(render_root),
        "--size","512",
        "--face-size","768",
        "--preflight-only",
    ]
    try:
        proc=subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=900,
            check=False,
        )
        output=proc.stdout or ""
    except subprocess.TimeoutExpired as exc:
        output=exc.stdout or ""
        if isinstance(output,bytes):
            output=output.decode("utf-8","replace")
        log_path.write_text(output,encoding="utf-8")
        return {
            "schema":1,
            "passed":False,
            "reasons":["front_preflight_blender_timeout"],
            "render_root":str(render_root),
        }
    log_path.write_text(output,encoding="utf-8")
    if proc.returncode!=0:
        return {
            "schema":1,
            "passed":False,
            "reasons":[f"front_preflight_blender_exit:{proc.returncode}"],
            "render_root":str(render_root),
        }

    manifest_path=render_root/"blender_manifest.json"
    if not manifest_path.is_file():
        return {
            "schema":1,
            "passed":False,
            "reasons":["front_preflight_manifest_missing"],
            "render_root":str(render_root),
        }
    render_manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    faces=[
        _resolved_render_path(str(x))
        for x in (render_manifest.get("faces") or [])
    ]
    if len(faces)!=1 or not faces[0].is_file():
        return {
            "schema":1,
            "passed":False,
            "reasons":[f"front_preflight_face_count:{len(faces)}!=1"],
            "render_root":str(render_root),
        }

    face_json=root/"face_landmarks.json"
    face_log=root/"face_landmarks.log"
    worker=[
        python_executable,
        str(face_worker),
    ]
    for src in [*source_images,*detail_images]:
        worker.extend(["--source",str(src)])
    worker.extend(["--candidate",str(faces[0]),"--output",str(face_json)])
    try:
        face_proc=subprocess.run(
            worker,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
            check=False,
        )
        face_log.write_text(face_proc.stdout or "",encoding="utf-8")
    except subprocess.TimeoutExpired:
        return {
            "schema":1,
            "passed":False,
            "reasons":["front_preflight_face_worker_timeout"],
            "render_root":str(render_root),
            "front_face":str(faces[0]),
        }
    if face_proc.returncode!=0 or not face_json.is_file():
        return {
            "schema":1,
            "passed":False,
            "reasons":[f"front_preflight_face_worker_exit:{face_proc.returncode}"],
            "render_root":str(render_root),
            "front_face":str(faces[0]),
        }

    face_report=json.loads(face_json.read_text(encoding="utf-8"))
    thresholds=JudgeV4Thresholds()
    reasons=[]
    if face_report.get("face_expected_from_source"):
        detected=int(face_report.get("candidate_detected") or 0)
        total=max(1,int(face_report.get("candidate_total") or 0))
        if detected<1:
            reasons.append("front_face_not_detected")
        fraction=detected/total
        if fraction<thresholds.face_candidate_detection_fraction_min:
            reasons.append(
                f"front_face_detection_coverage:{fraction:.3f}<"
                f"{thresholds.face_candidate_detection_fraction_min:.3f}"
            )
        med=face_report.get("median_profile_error")
        if med is None or float(med)>thresholds.face_profile_median_error_max:
            reasons.append(
                f"front_face_geometry_median_error:{med}>"
                f"{thresholds.face_profile_median_error_max}"
            )
        p90=face_report.get("p90_profile_error")
        if p90 is None or float(p90)>thresholds.face_profile_p90_error_max:
            reasons.append(
                f"front_face_geometry_p90_error:{p90}>"
                f"{thresholds.face_profile_p90_error_max}"
            )

    report={
        "schema":1,
        "passed":not reasons,
        "reasons":reasons,
        "front_face":str(faces[0]),
        "renderer":render_manifest.get("renderer"),
        "face_landmarks":face_report,
    }
    (root/"preflight.json").write_text(
        json.dumps(report,indent=2)+"\n",
        encoding="utf-8",
    )
    print(
        "HAYUYA_JUDGE_V4_FRONT_PREFLIGHT "
        +json.dumps(report,separators=(",",":"))
    )
    return report


def _build_blender_evidence(final_glb:Path,out_dir:Path):
    blender=shutil.which("blender")
    if not blender:
        return None

    script=Path(__file__).with_name("blender_judge_turntable_24.py")
    render_root=out_dir/"blender_evidence"
    log_path=out_dir/"blender_evidence.log"
    render_root.mkdir(parents=True,exist_ok=True)
    cmd=[
        blender,
        "--python-exit-code","1",
        "-b",
        "--python",str(script),
        "--",
        "--input",str(final_glb),
        "--output-dir",str(render_root),
        "--size","640",
        "--face-size","768",
    ]
    try:
        proc=subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=4200,
            check=False,
        )
        output=proc.stdout or ""
    except subprocess.TimeoutExpired as exc:
        output=exc.stdout or ""
        if isinstance(output,bytes):
            output=output.decode("utf-8","replace")
        log_path.parent.mkdir(parents=True,exist_ok=True)
        log_path.write_text(output,encoding="utf-8")
        raise RuntimeError(
            "Blender Judge evidence render timed out after 4200s; "
            "partial evidence preserved at "+str(render_root)
        ) from exc
    log_path.parent.mkdir(parents=True,exist_ok=True)
    log_path.write_text(output,encoding="utf-8")
    if proc.returncode!=0:
        raise RuntimeError(
            "Blender Judge evidence render failed; see "
            +str(log_path)
        )

    manifest_path=render_root/"blender_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("Blender Judge evidence manifest missing")
    render_manifest=json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    turns=[
        _resolved_render_path(str(value))
        for value in (render_manifest.get("turntable") or [])
    ]
    all_faces=[
        _resolved_render_path(str(value))
        for value in (render_manifest.get("faces") or [])
    ]
    if len(turns)!=24 or not all(path.is_file() for path in turns):
        raise RuntimeError(
            f"Blender Judge turntable incomplete: {len(turns)}/24"
        )
    # Canonical Judge order is front,+15,+30,+45,+60,-60,-45,-30,-15.
    # HAYUYA GLBs face -Y in Blender, so semantic front is index 12 (180 deg).
    requested=(12,13,14,15,16,8,9,10,11)
    rendered_face_indices=[
        int(value)
        for value in (render_manifest.get("face_indices") or [])
    ]
    if rendered_face_indices:
        face_by_index={
            index:path
            for index,path in zip(rendered_face_indices,all_faces)
        }
        face_frames=[
            face_by_index[index]
            for index in requested
            if index in face_by_index and face_by_index[index].is_file()
        ]
    else:
        # Backward compatibility with older manifests that emitted all 24
        # face angles in turntable index order.
        face_frames=[
            all_faces[index]
            for index in requested
            if index<len(all_faces) and all_faces[index].is_file()
        ]
    if len(face_frames)!=len(requested):
        raise RuntimeError(
            "Blender Judge dedicated face evidence incomplete: "
            f"{len(face_frames)}/{len(requested)}"
        )
    return turns,face_frames,render_manifest


def main()->int:
    p=argparse.ArgumentParser(
        description=(
            "Mandatory CPU-capable HAYUYA visual pre-approval. "
            "Uses Judge v4 core tier before Hub persistence."
        )
    )
    p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--python",default=sys.executable)
    p.add_argument("--force-character",action="store_true")
    a=p.parse_args()

    root=a.output_root
    manifest_path=root/"manifest.json"
    final_glb=root/"hayuya_final.glb"
    if not manifest_path.is_file():
        raise SystemExit("manifest missing before Judge v4 core")
    if not final_glb.is_file():
        raise SystemExit("final GLB missing before Judge v4 core")

    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    character=a.force_character or _is_character(manifest)
    if not character:
        manifest["judge_v4_core"]={
            "schema":4,
            "applicable":False,
            "passed":True,
            "reason":"non-character asset",
        }
        manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
        print("HAYUYA_JUDGE_V4_CORE_SKIPPED non-character")
        return 0

    source_images=_images(root/"prepared_views")
    detail_images=_images(root/"prepared_details")
    if not source_images:
        raise SystemExit("Judge v4 core requires prepared source images")

    judge_root=root/"judge_v4_core"

    # Render semantic front first and reject obvious face/anatomy failures
    # before spending tens of minutes on a 24-view 2M-triangle turntable.
    preflight=_run_front_preflight(
        final_glb,
        judge_root,
        source_images,
        detail_images,
        a.python,
    )
    if preflight is not None:
        manifest["judge_v4_front_preflight"]=preflight
        if not preflight.get("passed",False):
            reasons=list(preflight.get("reasons") or ["front_preflight_failed"])
            manifest["visual_approval"]={
                "schema":1,
                "state":"rejected",
                "production_approved":False,
                "core_passed":False,
                "pro_required":True,
                "hard_fail_reasons":reasons,
                "note":(
                    "Fast semantic-front gate rejected the candidate before "
                    "full 24-view evidence. This prevents visibly melted or "
                    "anatomically invalid Hero candidates from reaching Hub."
                ),
            }
            manifest_path.write_text(
                json.dumps(manifest,indent=2)+"\n",
                encoding="utf-8",
            )
            print(
                "HAYUYA_JUDGE_V4_FRONT_PREFLIGHT_REJECT "
                +json.dumps(reasons,separators=(",",":")),
                file=sys.stderr,
            )
            return 2

    faithful=_build_blender_evidence(final_glb,judge_root)
    face_frames=[]
    if faithful is not None:
        turntable,face_frames,render_manifest=faithful
        print(
            "HAYUYA_JUDGE_V4_RENDERER "
            +str(render_manifest.get("renderer") or "blender")
            +" full=24 face="+str(len(face_frames))
        )
    else:
        # Portable developer fallback only. CI installs Blender before Judge so
        # production character acceptance never relies on sparse face sampling.
        turntable_dir=judge_root/"turntable_cpu_fallback"
        turntable=[
            Path(path) for path in build_turntable(
                final_glb,
                turntable_dir,
                anchor_view=None,
            )
        ]
        print(
            "::warning::Blender unavailable; using legacy CPU Judge renderer. "
            "This path may reject dense meshes but can never production-approve."
        )

    report=run_judge_v4(
        final_glb=final_glb,
        source_images=source_images,
        detail_images=detail_images,
        turntable_frames=turntable,
        candidate_face_frames=face_frames,
        out_dir=judge_root,
        policy="required",
        python_executable=a.python,
        tier="core",
    )
    manifest["judge_v4_core"]=asdict(report)
    manifest["visual_approval"]={
        "schema":1,
        "state":"core_pass" if report.passed else "rejected",
        "production_approved":False,
        "core_passed":bool(report.passed),
        "pro_required":True,
        "hard_fail_reasons":list(report.hard_fail_reasons),
        "note":(
            "Core is the mandatory CPU pre-screen only. It can reject but can "
            "never production-approve a character. Monster/Ultra production "
            "approval requires authoritative Judge v5 on the HAYUYA GPU worker."
        ),
    }
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(
        "HAYUYA_JUDGE_V4_CORE "
        f"passed={str(bool(report.passed)).lower()} "
        f"hard_failures={len(report.hard_fail_reasons)}"
    )
    if not report.passed:
        print("\n".join(report.hard_fail_reasons[:32]),file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
