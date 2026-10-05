#!/usr/bin/env python3
"""Build source-authored Legacy first-person hands with real MP40 hand PSA actions.

The mesh is the recovered Project Aether BO2/Legacy Richtofen viewhands staged in
xogot/assets/weapons/aether_waw_hands/legacy_richtofen/viewhands.glb.
Animations come only from the mapped Aether WaW MP40 Hands ActorX PSA export.
Missing non-matching PSA bones are intentionally ignored by io_scene_psk_psa;
all matching Legacy deform/tag bones are animated.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import bpy


CORE_TOKENS = {
    "idle": ("idle",),
    "fire": ("fire", "shoot"),
    "reload": ("reload",),
    "equip": ("equip", "raise", "pullout"),
}


def args_after_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1:]


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blocks in (bpy.data.actions, bpy.data.armatures, bpy.data.meshes):
        for block in list(blocks):
            try:
                blocks.remove(block)
            except Exception:
                pass


def bind_actions_to_nla(armature, action_names: list[str]) -> list[str]:
    anim = armature.animation_data_create()
    bound: list[str] = []
    for name in action_names:
        action = bpy.data.actions.get(name)
        if action is None:
            continue
        track = anim.nla_tracks.new()
        track.name = "PSA_" + name
        start = int(round(float(action.frame_range[0])))
        strip = track.strips.new(name, start, action)
        strip.name = name
        bound.append(name)
    if not bound:
        raise RuntimeError("No source hand PSA actions bound to Legacy armature")
    return bound


def export_glb(path: Path) -> None:
    props = set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys())
    kwargs = {
        "filepath": str(path),
        "export_format": "GLB",
        "export_animations": True,
        "export_skins": True,
    }
    if "export_materials" in props:
        kwargs["export_materials"] = "EXPORT"
    if "export_animation_mode" in props:
        modes = {
            item.identifier
            for item in bpy.ops.export_scene.gltf.get_rna_type().properties[
                "export_animation_mode"
            ].enum_items
        }
        if "NLA_TRACKS" in modes:
            kwargs["export_animation_mode"] = "NLA_TRACKS"
        elif "ACTIONS" in modes:
            kwargs["export_animation_mode"] = "ACTIONS"
        else:
            raise RuntimeError(f"No usable glTF animation mode: {sorted(modes)}")
    elif "export_all_actions" in props:
        kwargs["export_all_actions"] = True
    if "export_force_sampling" in props:
        kwargs["export_force_sampling"] = True
    if "export_nla_strips" in props:
        kwargs["export_nla_strips"] = True
    result = bpy.ops.export_scene.gltf(**kwargs)
    if "FINISHED" not in result:
        raise RuntimeError(f"glTF export failed: {result}")


def glb_document(path: Path) -> dict:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise RuntimeError(f"Not GLB: {path}")
    n, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A:
        raise RuntimeError(f"Missing JSON chunk: {path}")
    return json.loads(data[20:20+n].rstrip(b" \t\r\n\0"))


def main() -> int:
    args = args_after_dash()
    if len(args) != 5:
        raise SystemExit(
            "usage: blender --background --python build_aether_legacy_hands_glb.py -- "
            "<base_hands.glb> <actorx_root> <addon_parent> <psk_psa_py_target> <output.glb>"
        )
    base_glb = Path(args[0]).resolve()
    actorx_root = Path(args[1]).resolve()
    addon_parent = Path(args[2]).resolve()
    psk_target = Path(args[3]).resolve()
    output = Path(args[4]).resolve()

    if not base_glb.is_file():
        raise SystemExit(f"Legacy hands GLB missing: {base_glb}")
    if not actorx_root.is_dir():
        raise SystemExit(f"ActorX root missing: {actorx_root}")
    if not (psk_target / "psk_psa_py" / "__init__.py").is_file():
        raise SystemExit(f"psk_psa_py missing: {psk_target}")

    sys.path.insert(0, str(psk_target))
    sys.path.insert(0, str(addon_parent))
    import psk_psa_py  # noqa: F401
    import io_scene_psk_psa
    io_scene_psk_psa.register()

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(base_glb))
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("Legacy hands GLB has no armature")
    armature = max(armatures, key=lambda o: len(o.data.bones))

    # The staged GLB may itself be the output of an earlier animation build.
    # Never layer newly corrected PSA actions on top of stale imported NLA/actions:
    # that previously let the old 100x-centimeter HandIdleMP40 survive while the
    # corrected 0.01-scale action was imported under a suffixed name.
    for obj in armatures:
        if obj.animation_data is not None:
            obj.animation_data_clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
    if len(bpy.data.actions) != 0:
        raise RuntimeError("Failed to clear stale viewhands actions before PSA import")

    bone_names = {b.name for b in armature.data.bones}
    required_tags = {
        "RootBone", "tag_view", "tag_ads", "tag_torso",
        "tag_weapon", "tag_camera", "j_wrist_le", "j_wrist_ri",
    }
    missing_tags = sorted(required_tags - bone_names)
    if missing_tags:
        raise RuntimeError(f"Legacy hands missing required tags: {missing_tags}")

    psas = sorted(
        p for p in actorx_root.rglob("*.psa")
        if "/mp40/anims/hands/" in p.as_posix().lower()
    )
    if not psas:
        raise RuntimeError("No MP40 Hands PSA files found in mapped Aether ActorX artifact")

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    before = set(bpy.data.actions.keys())
    failures: list[str] = []
    for psa in psas:
        bpy.context.view_layer.objects.active = armature
        armature.select_set(True)
        try:
            result = bpy.ops.psa.import_all(
                filepath=str(psa),
                should_convert_to_samples=True,
                # ActorX/Unreal PSA translations are authored in centimeters.
                # The recovered Aether glTF/GLB mesh is already meters. The
                # maintained importer defaults to 1.0, so omitting this made
                # every animated translation 100x too large and pushed the
                # first-person rig outside the camera frustum.
                translation_scale=0.01,
            )
            if "FINISHED" not in result:
                failures.append(f"{psa.name}:{result}")
        except Exception as exc:
            failures.append(f"{psa.name}:{exc!r}")

    actions = sorted(set(bpy.data.actions.keys()) - before)
    if not actions:
        raise RuntimeError(f"No MP40 hand Actions imported; failures={failures[:8]}")
    for name in actions:
        bpy.data.actions[name].use_fake_user = True

    lower_names = [n.lower() for n in actions]
    missing_roles = [
        role for role, tokens in CORE_TOKENS.items()
        if not any(any(token in name for token in tokens) for name in lower_names)
    ]
    if missing_roles:
        raise RuntimeError(
            f"Legacy hands missing core source animation roles {missing_roles}; actions={actions}"
        )

    bound = bind_actions_to_nla(armature, actions)
    if len(bound) != len(actions):
        raise RuntimeError(f"Only {len(bound)}/{len(actions)} hand Actions bound")

    output.parent.mkdir(parents=True, exist_ok=True)
    export_glb(output)
    doc = glb_document(output)
    animation_names = [str(a.get("name", "")) for a in doc.get("animations", [])]
    if len(doc.get("meshes", [])) < 1 or len(doc.get("skins", [])) < 1:
        raise RuntimeError("Animated Legacy hands GLB lost mesh/skin")
    if len(animation_names) < 4:
        raise RuntimeError(f"Animated Legacy hands has too few Actions: {animation_names}")

    report = {
        "schema": 1,
        "source": "Project Aether UE5.7 BO2 Legacy Richtofen viewhands + WaW MP40 Hands PSA",
        "psa_files": [p.name for p in psas],
        "actions_imported": actions,
        "actions_exported": animation_names,
        "import_warnings_or_failures": failures,
        "armature_bones": len(bone_names),
        "required_tags": sorted(required_tags),
        "translation_scale": 0.01,
        "translation_units": "ActorX UE cm -> GLB meters",
        "stale_base_actions_cleared": True,
        "output_bytes": output.stat().st_size,
    }
    output.with_suffix(".animation-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("XZOGOT_LEGACY_HANDS_ANIMATION_GREEN", len(animation_names), output.stat().st_size)
    print("XZOGOT_LEGACY_HANDS_CORE_ROLES_GREEN", ",".join(sorted(CORE_TOKENS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
