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
from judge_v4 import run_judge_v4


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
    proc=subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=1200,
        check=False,
    )
    log_path.parent.mkdir(parents=True,exist_ok=True)
    log_path.write_text(proc.stdout or "",encoding="utf-8")
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
    requested=(0,1,2,3,4,20,21,22,23)
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
