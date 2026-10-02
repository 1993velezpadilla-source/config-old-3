#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path


def safe_copy(src: Path, dst: Path):
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    return True


def main() -> int:
    p=argparse.ArgumentParser(description="Build a self-contained HAYUYA game-ready asset package from a saved editor recipe.")
    p.add_argument("--recipe",required=True,type=Path)
    p.add_argument("--model",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--repo-root",type=Path,default=Path("."))
    p.add_argument("--animation-gate",type=Path)
    args=p.parse_args()

    recipe=json.loads(args.recipe.read_text(encoding="utf-8"))
    job_id=str(recipe["job_id"])
    root=args.out/job_id
    if root.exists():
        shutil.rmtree(root)
    (root/"asset").mkdir(parents=True)
    (root/"audio").mkdir(parents=True)
    (root/"docs").mkdir(parents=True)

    safe_copy(args.model,root/"asset"/"model.glb")

    model_dir=args.repo_root/"hayuya"/"models"/job_id
    safe_copy(model_dir/"manifest.json",root/"asset"/"manifest.json")
    safe_copy(model_dir/"rig_gate.json",root/"asset"/"rig_gate.json")
    safe_copy(model_dir/"quality_gate.json",root/"asset"/"quality_gate.json")
    safe_copy(model_dir/"animation_gate.json",root/"asset"/"animation_gate.json")
    safe_copy(model_dir/"auto_motion_plan.json",root/"asset"/"auto_motion_plan.json")

    # Keep the exact editor recipe beside the exported character.
    (root/"hayuya_recipe.json").write_text(json.dumps(recipe,indent=2)+"\n",encoding="utf-8")

    # Runtime-friendly profile: selected IDs are stable; labels are presentation.
    selected=recipe.get("selected",{})
    profile={
        "schema":2,
        "job_id":job_id,
        "asset_profile":recipe.get("asset_profile","auto"),
        "motion_profile":recipe.get("motion_profile","auto"),
        "skeleton_type":recipe.get("skeleton_type","hayuya_humanoid_v1"),
        "animations":selected.get("animations",[]),
        "real_mocap":selected.get("real_mocap",[]),
        "weapon_animations":selected.get("weapon_animations",[]),
        "procedural_motion":selected.get("procedural_motion",[]),
        "audio":selected.get("audio",[]),
        "addons":selected.get("addons",[]),
    }
    (root/"asset_profile.json").write_text(json.dumps(profile,indent=2)+"\n",encoding="utf-8")
    # Backwards compatibility for existing Xziel character importers.
    (root/"character_profile.json").write_text(json.dumps(profile,indent=2)+"\n",encoding="utf-8")

    copied_audio=[]
    unresolved_audio=[]
    for item in profile["audio"]:
        for raw in item.get("files") or []:
            src=args.repo_root/raw
            dst=root/"audio"/Path(raw).name
            if safe_copy(src,dst):
                copied_audio.append(str(dst.relative_to(root)))
            else:
                unresolved_audio.append(raw)
        directory=item.get("directory")
        if directory:
            src=args.repo_root/directory
            dst=root/"audio"/Path(directory).name
            if safe_copy(src,dst):
                copied_audio.append(str(dst.relative_to(root)))
            else:
                unresolved_audio.append(directory)

    # Copy project audio provenance/policy when available.
    safe_copy(args.repo_root/"docs"/"audio"/"XZIEL_HORROR_AUDIO_SOURCES.md",root/"docs"/"XZIEL_HORROR_AUDIO_SOURCES.md")
    safe_copy(args.repo_root/"hayuya"/"standards"/"hayuya_humanoid_v1.json",root/"docs"/"hayuya_humanoid_v1.json")
    safe_copy(args.repo_root/"hayuya"/"standards"/"hayuya_preview_pack_v1.json",root/"docs"/"hayuya_preview_pack_v1.json")
    safe_copy(args.repo_root/"hayuya"/"standards"/"hayuya_asset_profiles_v1.json",root/"docs"/"hayuya_asset_profiles_v1.json")
    safe_copy(args.repo_root/"hayuya"/"standards"/"hayuya_weapon_animation_v1.json",root/"docs"/"hayuya_weapon_animation_v1.json")

    local_animation_sources=sorted({
        str(x.get("source"))
        for x in profile["animations"]
        if x.get("availability") in (None,"local") and x.get("clip") and x.get("source")
    })
    mixed_animation_sources=len(local_animation_sources)>1
    unresolved_animations=[
        x for x in profile["animations"]
        if x.get("availability") not in (None,"local")
    ]
    unresolved_mocap=[
        x for x in profile["real_mocap"]
        if x.get("availability") not in (None,"local")
    ]

    selected_local_clips=sorted({
        str(x.get("clip")) for x in profile["animations"]
        if x.get("availability") in (None,"local") and x.get("clip")
    })
    animation_qa={}
    if args.animation_gate and args.animation_gate.exists():
        animation_qa=json.loads(args.animation_gate.read_text(encoding="utf-8"))
    else:
        # Existing banks are accepted only if the model manifest explicitly
        # records Rig QA v2 and the selected source bank was marked safe.
        manifest_path=model_dir/"manifest.json"
        if manifest_path.exists():
            manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
            banks=manifest.get("animation_banks") or {}
            source=local_animation_sources[0] if len(local_animation_sources)==1 else ""
            bank=banks.get(source) or {}
            if int(bank.get("rig_quality_version") or 0)>=2 and bank.get("quality_passed") is True:
                animation_qa={
                    "schema":2,
                    "source":"manifest_safe_bank",
                    "compatible_clips":bank.get("clips") or [],
                    "passed":True,
                }
    compatible_clips={str(x) for x in animation_qa.get("compatible_clips") or []}
    unsafe_selected_clips=sorted(set(selected_local_clips)-compatible_clips) if selected_local_clips else []
    missing_animation_qa=bool(selected_local_clips) and not bool(animation_qa)

    unresolved_weapon=[
        x for x in profile["weapon_animations"]
        if x.get("availability") not in (None,"local")
    ]
    weapon_profile=profile["asset_profile"]=="weapon.firearm"
    weapon_items=profile["weapon_animations"]
    # Conservative rule: firearm package cannot call itself game-ready merely
    # because a template was selected. It must be explicitly marked compatible
    # by the mechanical family/component gate or be absent.
    unresolved_weapon_compat=[
        x for x in weapon_items
        if weapon_profile and not bool(x.get("compatibility_passed",False))
    ]
    incompatible_motion=[
        x for x in profile["procedural_motion"]
        if profile["asset_profile"] not in ("auto",*(x.get("profiles") or []))
    ]

    auto_plan={}
    auto_plan_path=model_dir/"auto_motion_plan.json"
    if profile["motion_profile"]=="hayuya_auto" and auto_plan_path.exists():
        auto_plan=json.loads(auto_plan_path.read_text(encoding="utf-8"))
    unresolved_auto_motion=False
    if profile["motion_profile"]=="hayuya_auto":
        status=str(auto_plan.get("status") or "")
        unresolved_auto_motion=status in {
            "",
            "needs_family_confirmation",
            "needs_component_fit",
            "needs_creature_rig",
            "needs_part_fit",
        }

    build={
        "schema":1,
        "job_id":job_id,
        "model":str(args.model),
        "asset_profile":profile["asset_profile"],
        "motion_profile":profile["motion_profile"],
        "copied_audio":copied_audio,
        "unresolved_audio":unresolved_audio,
        "selected_animation_sources":local_animation_sources,
        "mixed_animation_sources":mixed_animation_sources,
        "unresolved_animation_retarget":unresolved_animations,
        "unresolved_external_mocap":unresolved_mocap,
        "selected_local_clips":selected_local_clips,
        "animation_qa":animation_qa,
        "unsafe_selected_clips":unsafe_selected_clips,
        "missing_animation_qa":missing_animation_qa,
        "unresolved_weapon_assets":unresolved_weapon,
        "unresolved_weapon_compatibility":unresolved_weapon_compat,
        "incompatible_procedural_motion":incompatible_motion,
        "auto_motion_plan":auto_plan,
        "unresolved_auto_motion":unresolved_auto_motion,
        "game_ready":not unresolved_audio and not mixed_animation_sources and not unresolved_animations and not unresolved_mocap and not unsafe_selected_clips and not missing_animation_qa and not unresolved_weapon and not unresolved_weapon_compat and not incompatible_motion and not unresolved_auto_motion,
        "notes":[
            "Local skeletal animations are game-ready only when the selected clip names pass deformation QA.",
            "External mocap is never silently bundled without an ingested/licensed local source.",
            "Gameplay state/motion mapping remains explicit in asset_profile.json.",
            "Firearm animation compatibility is fail-closed: family/mechanical proof is required before game-ready.",
            "Foliage and mechanical motion can remain runtime metadata when shader/engine motion is superior to baked skeletal animation.",
            "HAYUYA Auto is fail-closed: unresolved family/part-fit/rig stages prevent GAME READY until self-evaluation finishes."
        ]
    }
    (root/"BUILD.json").write_text(json.dumps(build,indent=2)+"\n",encoding="utf-8")

    zip_path=args.out/f"{job_id}-hayuya-package.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                z.write(path,path.relative_to(args.out))

    print("HAYUYA_PACKAGE_PASS")
    print(json.dumps({
        "job_id":job_id,
        "zip":str(zip_path),
        "zip_bytes":zip_path.stat().st_size,
        "game_ready":build["game_ready"],
        "animation_sources":local_animation_sources,
        "mixed_animation_sources":mixed_animation_sources,
        "unresolved_animation_retarget":len(unresolved_animations),
        "unresolved_external_mocap":len(unresolved_mocap),
        "unsafe_selected_clips":unsafe_selected_clips,
        "missing_animation_qa":missing_animation_qa,
        "audio_items":len(copied_audio),
        "weapon_items":len(profile["weapon_animations"]),
        "motion_fx":len(profile["procedural_motion"]),
        "unresolved_weapon_compatibility":len(unresolved_weapon_compat),
        "unresolved_auto_motion":unresolved_auto_motion
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
