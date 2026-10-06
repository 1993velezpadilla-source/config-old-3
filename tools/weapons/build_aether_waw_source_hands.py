#!/usr/bin/env python3
"""Build per-weapon WaW/T4 first-person hand GLBs from recovered Project Aether source.

The base mesh/skeleton must be the exact T4 Marine viewhands exported from:
  /Game/Assets/Viewmodels/Viewhands/T4/Marine/viewmodel_usa_marine_arms

Each runtime weapon receives only its own recovered:
  /Game/Assets/Weapons/WAW/<weapon>/Anims/Hands/*.psa

No weapon-specific pose offsets are authored here. ActorX translations are converted
from Unreal centimeters to the meter-space GLB once, at import.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import bpy


RUNTIME_TO_SOURCE = {
    "colt": "1911",
    "357": "357",
    "arisaka": "Arisaka",
    "bar": "BAR",
    "browning": "Browning",
    "doublebarrel": "DoubleBarrel",
    "dp28": "DP28",
    "fg42": "FG42",
    "gewehr": "Gewehr",
    "kar98k": "Kar98k",
    "m1a1": "M1Carbine",
    "m1": "M1Garand",
    "mg42": "MG42",
    "mp40": "MP40",
    "mosin": "MosinNagant",
    "nambu": "Nambu",
    "ppsh": "PPSH",
    "ptrs": "PTRS",
    "springfield": "Springfield",
    "stg": "STG44",
    "svt40": "SVT40",
    "thompson": "Thompson",
    "trench": "TrenchGun",
    "tt33": "TT33",
    "type100": "Type100",
    "type99": "Type99",
    "walther": "Walther",
}

SOURCE_PENDING = {"sawnoff": "SawedOffDB"}

CORE_TOKENS = {
    "idle": ("idle", "hold"),
    "fire": ("fire", "shoot"),
    "reload": ("reload", "rechamber"),
    "equip": ("equip", "raise", "pullout", "bringout", "bring_out", "first_raise"),
}


def args_after_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1:]


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blocks in (
        bpy.data.actions,
        bpy.data.armatures,
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
    ):
        for block in list(blocks):
            try:
                blocks.remove(block)
            except Exception:
                pass


def purge_imported_animation() -> None:
    for obj in [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]:
        if obj.animation_data is not None:
            obj.animation_data_clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def bind_actions_to_nla(armature, action_names: list[str]) -> list[str]:
    anim = armature.animation_data_create()
    bound: list[str] = []
    for name in action_names:
        action = bpy.data.actions.get(name)
        if action is None:
            continue
        action.use_fake_user = True
        track = anim.nla_tracks.new()
        track.name = "PSA_" + name
        start = int(round(float(action.frame_range[0])))
        strip = track.strips.new(name, start, action)
        strip.name = name
        bound.append(name)
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
    return json.loads(data[20:20 + n].rstrip(b" \t\r\n\0"))


def source_psas(actorx_root: Path, source_dir: str) -> list[Path]:
    needle = f"/weapons/waw/{source_dir.lower()}/anims/hands/"
    return sorted(
        p for p in actorx_root.rglob("*.psa")
        if needle in p.as_posix().lower()
    )


def core_role_report(action_names: list[str]) -> dict[str, bool]:
    lower = [name.lower() for name in action_names]
    return {
        role: any(any(token in name for token in tokens) for name in lower)
        for role, tokens in CORE_TOKENS.items()
    }


def build_one(
    base_hands: Path,
    actorx_root: Path,
    output_root: Path,
    runtime_id: str,
    source_dir: str,
) -> dict:
    clear_scene()
    suffix = base_hands.suffix.lower()
    if suffix in {".psk", ".pskx"}:
        result = bpy.ops.psk.import_file(
            filepath=str(base_hands),
            components="ALL",
            # ActorX mesh/skeleton uses UE centimeters. Keep PSA translations
            # in the same source unit system and scale the complete rig once.
            scale=0.01,
        )
        if "FINISHED" not in result:
            raise RuntimeError(f"{runtime_id}: T4 Marine PSK import failed: {result}")
        psa_translation_scale = 1.0
        source_mesh_scale = 0.01
        base_kind = "actorx_psk"
    elif suffix == ".glb":
        bpy.ops.import_scene.gltf(filepath=str(base_hands))
        psa_translation_scale = 0.01
        source_mesh_scale = 1.0
        base_kind = "gltf"
    else:
        raise RuntimeError(f"{runtime_id}: unsupported T4 hands base {base_hands}")

    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError(f"{runtime_id}: T4 Marine hands source has no armature")
    armature = max(armatures, key=lambda o: len(o.data.bones))
    purge_imported_animation()

    bone_names = {b.name for b in armature.data.bones}
    required = {"tag_weapon"}
    missing_required = sorted(required - bone_names)
    if missing_required:
        raise RuntimeError(
            f"{runtime_id}: exact T4 Marine hands missing required bones {missing_required}"
        )

    psas = source_psas(actorx_root, source_dir)
    if not psas:
        raise RuntimeError(f"{runtime_id}: no Hands PSA source found for {source_dir}")

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
                translation_scale=psa_translation_scale,
            )
            if "FINISHED" not in result:
                failures.append(f"{psa.name}:{result}")
        except Exception as exc:
            failures.append(f"{psa.name}:{exc!r}")

    actions = sorted(set(bpy.data.actions.keys()) - before)
    if not actions:
        raise RuntimeError(
            f"{runtime_id}: no hand Actions imported; failures={failures[:6]}"
        )

    roles = core_role_report(actions)
    missing_roles = sorted(role for role, ready in roles.items() if not ready)
    if missing_roles:
        raise RuntimeError(
            f"{runtime_id}: source hands missing core roles {missing_roles}; "
            f"actions={actions}"
        )

    bound = bind_actions_to_nla(armature, actions)
    if len(bound) != len(actions):
        raise RuntimeError(
            f"{runtime_id}: only {len(bound)}/{len(actions)} Actions bound to NLA"
        )

    out_dir = output_root / runtime_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "viewhands.glb"
    export_glb(output)

    doc = glb_document(output)
    animation_names = [str(a.get("name", "")) for a in doc.get("animations", [])]
    if len(doc.get("meshes", [])) < 1:
        raise RuntimeError(f"{runtime_id}: exported hands lost mesh")
    if len(doc.get("skins", [])) < 1:
        raise RuntimeError(f"{runtime_id}: exported hands lost skin")
    if len(animation_names) < 4:
        raise RuntimeError(
            f"{runtime_id}: exported hands has too few animations {animation_names}"
        )

    report = {
        "runtime_id": runtime_id,
        "source_dir": source_dir,
        "base_hands_source": "T4/Marine/viewmodel_usa_marine_arms",
        "source_psa_count": len(psas),
        "source_psas": [p.name for p in psas],
        "actions_imported": actions,
        "actions_exported": animation_names,
        "core_roles": roles,
        "import_failures": failures,
        "armature_bones": len(bone_names),
        "has_tag_view": "tag_view" in bone_names,
        "has_tag_ads": "tag_ads" in bone_names,
        "has_tag_weapon": "tag_weapon" in bone_names,
        "has_tag_camera": "tag_camera" in bone_names,
        "base_hands_kind": base_kind,
        "source_mesh_scale": source_mesh_scale,
        "translation_scale": psa_translation_scale,
        "translation_units": (
            "ActorX mesh+PSA remain in matching UE centimeters; complete rig object scale=0.01"
            if base_kind == "actorx_psk"
            else "ActorX UE cm -> existing GLB meters"
        ),
        "output": output.as_posix(),
        "output_bytes": output.stat().st_size,
    }
    (out_dir / "animation-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "XZOGOT_WAW_SOURCE_HANDS_GREEN",
        runtime_id,
        source_dir,
        len(psas),
        len(animation_names),
        len(bone_names),
    )
    return report


def main() -> int:
    args = args_after_dash()
    if len(args) != 5:
        raise SystemExit(
            "usage: blender --background --python build_aether_waw_source_hands.py -- "
            "<t4_marine_hands.psk|pskx|glb> <actorx_root> <addon_parent> "
            "<psk_psa_py_target> <output_root>"
        )

    base_hands = Path(args[0]).resolve()
    actorx_root = Path(args[1]).resolve()
    addon_parent = Path(args[2]).resolve()
    psk_target = Path(args[3]).resolve()
    output_root = Path(args[4]).resolve()

    if not base_hands.is_file():
        raise SystemExit(f"T4 Marine hands source missing: {base_hands}")
    if not actorx_root.is_dir():
        raise SystemExit(f"ActorX source root missing: {actorx_root}")
    if not (psk_target / "psk_psa_py" / "__init__.py").is_file():
        raise SystemExit(f"psk_psa_py missing: {psk_target}")

    sys.path.insert(0, str(psk_target))
    sys.path.insert(0, str(addon_parent))
    import psk_psa_py  # noqa: F401
    import io_scene_psk_psa
    io_scene_psk_psa.register()

    reports: list[dict] = []
    for runtime_id, source_dir in RUNTIME_TO_SOURCE.items():
        reports.append(
            build_one(base_hands, actorx_root, output_root, runtime_id, source_dir)
        )

    inventory = {
        "schema": 1,
        "source": "Project Aether UE5.7 T4 Marine viewhands + WaW per-weapon Hands PSA",
        "built_weapon_count": len(reports),
        "expected_weapon_count": 27,
        "source_pending": SOURCE_PENDING,
        "source_units_policy": "PSK base preferred: mesh+PSA remain matched in UE cm, complete rig scaled to meters once.",
        "weapons": reports,
    }
    if len(reports) != 27:
        raise RuntimeError(f"Expected 27 hands packages, built {len(reports)}")

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )
    print("XZOGOT_WAW_27_SOURCE_HANDS_GREEN", len(reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
