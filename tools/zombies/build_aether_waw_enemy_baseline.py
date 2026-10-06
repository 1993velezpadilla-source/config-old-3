#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import bpy

ZOMBIE_ROLES = {
    "idle": ("idle",),
    "walk": ("walk",),
    "run": ("run",),
    "sprint": ("sprint",),
    "attack": ("attack",),
    "death": ("death",),
    "traverse": ("traverse", "climb"),
}
DOG_ROLES = {
    "idle": ("idle",),
    "trot": ("trot",),
    "run": ("run",),
    "attack": ("attack",),
    "death": ("death",),
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


def glb_document(path: Path) -> dict:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise RuntimeError(f"Not GLB: {path}")
    off = 12
    while off + 8 <= len(data):
        n, kind = struct.unpack_from("<II", data, off)
        off += 8
        if kind == 0x4E4F534A:
            return json.loads(data[off:off+n].rstrip(b" \t\r\n\0"))
        off += n
    raise RuntimeError(f"GLB JSON missing: {path}")


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
        kwargs["export_animation_mode"] = (
            "NLA_TRACKS" if "NLA_TRACKS" in modes else "ACTIONS"
        )
    elif "export_all_actions" in props:
        kwargs["export_all_actions"] = True
    if "export_force_sampling" in props:
        kwargs["export_force_sampling"] = True
    if "export_nla_strips" in props:
        kwargs["export_nla_strips"] = True
    result = bpy.ops.export_scene.gltf(**kwargs)
    if "FINISHED" not in result:
        raise RuntimeError(f"glTF export failed: {result}")


def bind_actions(armature, names: list[str]) -> None:
    anim = armature.animation_data_create()
    for name in names:
        action = bpy.data.actions.get(name)
        if action is None:
            continue
        action.use_fake_user = True
        track = anim.nla_tracks.new()
        track.name = "PSA_" + name
        start = int(round(float(action.frame_range[0])))
        strip = track.strips.new(name, start, action)
        strip.name = name


def role_report(names: list[str], rules: dict[str, tuple[str, ...]]) -> dict[str, bool]:
    lower = [n.lower() for n in names]
    return {
        role: any(any(token in name for token in tokens) for name in lower)
        for role, tokens in rules.items()
    }


def build(
    base_glb: Path,
    psas: list[Path],
    output: Path,
    rules: dict[str, tuple[str, ...]],
    source_id: str,
) -> dict:
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(base_glb))
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError(f"{source_id}: base GLB has no armature")
    armature = max(armatures, key=lambda o: len(o.data.bones))

    for obj in armatures:
        if obj.animation_data is not None:
            obj.animation_data_clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)

    before = set(bpy.data.actions.keys())
    failures: list[str] = []
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    for psa in psas:
        try:
            result = bpy.ops.psa.import_all(
                filepath=str(psa),
                should_convert_to_samples=True,
                translation_scale=0.01,
            )
            if "FINISHED" not in result:
                failures.append(f"{psa.name}:{result}")
        except Exception as exc:
            failures.append(f"{psa.name}:{exc!r}")

    actions = sorted(set(bpy.data.actions.keys()) - before)
    if not actions:
        raise RuntimeError(f"{source_id}: no PSA actions imported; {failures[:8]}")
    roles = role_report(actions, rules)
    missing = [k for k, ready in roles.items() if not ready]
    if missing:
        raise RuntimeError(f"{source_id}: missing required roles {missing}")

    bind_actions(armature, actions)
    output.parent.mkdir(parents=True, exist_ok=True)
    export_glb(output)
    doc = glb_document(output)
    exported = [str(a.get("name", "")) for a in doc.get("animations", [])]
    if not doc.get("meshes") or not doc.get("skins") or not exported:
        raise RuntimeError(f"{source_id}: animated export lost mesh/skin/anims")

    report = {
        "source_id": source_id,
        "base_glb": base_glb.as_posix(),
        "base_bones": len(armature.data.bones),
        "source_psa_count": len(psas),
        "actions_imported": actions,
        "actions_exported": exported,
        "roles": roles,
        "import_failures": failures,
        "translation_scale": 0.01,
        "translation_units": "ActorX UE cm -> GLB meters",
        "output": output.as_posix(),
        "output_bytes": output.stat().st_size,
    }
    output.with_suffix(".report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "XZOGOT_SOURCE_ENEMY_BUILD_GREEN",
        source_id,
        "bones=", len(armature.data.bones),
        "psa=", len(psas),
        "exported=", len(exported),
    )
    return report


def main() -> int:
    args = args_after_dash()
    if len(args) != 5:
        raise SystemExit(
            "usage: blender --background --python build_aether_waw_enemy_baseline.py -- "
            "<source_first_root> <addon_parent> <psk_psa_py_target> <output_root> <report.json>"
        )
    source = Path(args[0]).resolve()
    addon_parent = Path(args[1]).resolve()
    psk_target = Path(args[2]).resolve()
    out = Path(args[3]).resolve()
    report_path = Path(args[4]).resolve()

    sys.path.insert(0, str(psk_target))
    sys.path.insert(0, str(addon_parent))
    import psk_psa_py  # noqa: F401
    import io_scene_psk_psa
    io_scene_psk_psa.register()

    content = source / "source-first-export/ProjectAether/Content"
    actorx = source / "source-first-actorx/ProjectAether/Content"

    zombie_anim_root = actorx / "FirstPerson/Blueprints/Zombies/Resources/Anims/waw"
    zombie_psas = sorted(
        p for p in zombie_anim_root.rglob("*.psa")
        if "_Montage" not in p.name
    )
    if len(zombie_psas) < 30:
        raise RuntimeError(f"WaW zombie PSA set too small: {len(zombie_psas)}")

    body_root = content / "FirstPerson/Blueprints/Zombies/Resources/Models/Bodies/waw"
    variants = {
        "honorgd": body_root / "honorgd/char_ger_honorgd_body1_1_Merged_Merged.glb",
        "sumpf": body_root / "sumpf/char_jap_impinf_body5z_1_Merged_Merged.glb",
    }

    reports = []
    for variant, glb in variants.items():
        if not glb.is_file():
            raise RuntimeError(f"source zombie body missing: {glb}")
        reports.append(
            build(glb, zombie_psas, out / variant / "zombie.glb", ZOMBIE_ROLES, variant)
        )

    dog_root = content / "FirstPerson/Blueprints/Zombies/Other/zombie_wolf"
    dog_glb = dog_root / "zombie_wolf.glb"
    dog_actorx = actorx / "FirstPerson/Blueprints/Zombies/Other/zombie_wolf"
    dog_psas = sorted(
        p for p in dog_actorx.rglob("*.psa")
        if "_Montage" not in p.name
    )
    if not dog_glb.is_file() or len(dog_psas) < 5:
        raise RuntimeError(
            f"hellhound source incomplete glb={dog_glb.is_file()} psa={len(dog_psas)}"
        )
    reports.append(
        build(dog_glb, dog_psas, out / "hellhound" / "hellhound.glb", DOG_ROLES, "hellhound")
    )

    payload = {
        "schema": 1,
        "source": "Project Aether UE5.7 source-first enemy baseline",
        "zombie_variants": ["honorgd", "sumpf"],
        "hellhound": "hellhound",
        "crawler_animation_status": "source_pending_nacht_lane",
        "reports": reports,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("XZOGOT_SOURCE_ENEMY_BASELINE_GREEN", len(reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
