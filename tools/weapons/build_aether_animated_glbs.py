#!/usr/bin/env python3
"""Merge mapped Aether WaW skeletal GLBs with their ActorX PSA animations in Blender.

Run inside Blender:
  blender --background --python build_aether_animated_glbs.py -- <artifact_root> <output_root>
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import bpy

MAPPING = {
    "1911": "colt",
    "357": "357",
    "Arisaka": "arisaka",
    "BAR": "bar",
    "Browning": "browning",
    "DoubleBarrel": "doublebarrel",
    "DP28": "dp28",
    "FG42": "fg42",
    "Gewehr": "gewehr",
    "Kar98k": "kar98k",
    "M1Carbine": "m1a1",
    "M1Garand": "m1",
    "MG42": "mg42",
    "MosinNagant": "mosin",
    "MP40": "mp40",
    "Nambu": "nambu",
    "PPSH": "ppsh",
    "PTRS": "ptrs",
    "SawedOffDB": "sawnoff",
    "Springfield": "springfield",
    "STG44": "stg",
    "Stielhand": "stielhand",
    "SVT40": "svt40",
    "Thompson": "thompson",
    "TrenchGun": "trench",
    "TT33": "tt33",
    "Type100": "type100",
    "Type99": "type99",
    "Walther": "walther",
}

PREFERRED = {
    "TrenchGun": "viewmodel_usa_trenchgun_rifle.glb",
}


def argv_after_double_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1:]


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.actions,
        bpy.data.armatures,
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
    ):
        for block in list(datablocks):
            try:
                datablocks.remove(block)
            except Exception:
                pass


def choose_glb(folder: Path, source_name: str) -> Path:
    candidates = sorted(folder.glob("*.glb"))
    if not candidates:
        raise RuntimeError(f"No GLB in {folder}")
    pref = PREFERRED.get(source_name)
    if pref and (folder / pref).is_file():
        return folder / pref
    view = [p for p in candidates if "viewmodel" in p.name.lower()]
    return view[0] if view else candidates[0]


def glb_stats(path: Path) -> dict:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise RuntimeError(f"Not GLB: {path}")
    json_len, json_type = struct.unpack_from("<II", data, 12)
    if json_type != 0x4E4F534A:
        raise RuntimeError(f"Missing GLB JSON chunk: {path}")
    doc = json.loads(data[20:20 + json_len].rstrip(b" \t\r\n\0"))
    return {
        "meshes": len(doc.get("meshes", [])),
        "skins": len(doc.get("skins", [])),
        "animations": len(doc.get("animations", [])),
        "materials": len(doc.get("materials", [])),
        "images": len(doc.get("images", [])),
        "textures": len(doc.get("textures", [])),
        "nodes": len(doc.get("nodes", [])),
        "animation_names": [str(a.get("name", "")) for a in doc.get("animations", [])],
    }


def export_animated_glb(path: Path) -> None:
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
        kwargs["export_animation_mode"] = "ACTIONS"
    elif "export_all_actions" in props:
        kwargs["export_all_actions"] = True
    if "export_force_sampling" in props:
        kwargs["export_force_sampling"] = True
    if "export_nla_strips" in props:
        kwargs["export_nla_strips"] = False
    result = bpy.ops.export_scene.gltf(**kwargs)
    if "FINISHED" not in result:
        raise RuntimeError(f"GLTF export failed: {result}")


def main() -> int:
    args = argv_after_double_dash()
    if len(args) != 3:
        raise SystemExit(
            "usage: blender --background --python build_aether_animated_glbs.py "
            "-- <artifact_root> <addon_parent> <output_root>"
        )
    artifact_root = Path(args[0]).resolve()
    addon_parent = Path(args[1]).resolve()
    output_root = Path(args[2]).resolve()

    sys.path.insert(0, str(addon_parent))
    wheels = sorted((addon_parent / "io_scene_psk_psa" / "wheels").glob("psk_psa_py-*.whl"))
    if not wheels:
        raise SystemExit(f"Bundled psk_psa_py wheel missing under {addon_parent}")
    # Wheels are ZIP-importable; adding the bundled wheel to sys.path avoids
    # mutating Blender's embedded Python installation on the CI runner.
    sys.path.insert(0, str(wheels[-1]))
    import psk_psa_py  # type: ignore
    print("XZOGOT_PSK_PSA_PY_READY", getattr(psk_psa_py, "__file__", "wheel"))
    import io_scene_psk_psa  # type: ignore
    io_scene_psk_psa.register()

    mesh_root = artifact_root / "recovered-export" / "ProjectAether" / "Content" / "Assets" / "Weapons" / "waw"
    actorx_root = artifact_root / "recovered-actorx"
    if not mesh_root.is_dir():
        raise SystemExit(f"mesh root missing: {mesh_root}")
    if not actorx_root.is_dir():
        raise SystemExit(f"ActorX root missing: {actorx_root}")

    report = []
    for source_name, runtime_id in MAPPING.items():
        clear_scene()
        folder = mesh_root / source_name
        source_glb = choose_glb(folder, source_name)
        bpy.ops.import_scene.gltf(filepath=str(source_glb))

        armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
        if not armatures:
            raise RuntimeError(f"{runtime_id}: imported GLB has no armature")
        armature = max(armatures, key=lambda o: len(o.data.bones))
        bpy.context.view_layer.objects.active = armature
        armature.select_set(True)

        source_token = source_name.lower()
        psas = sorted(
            p for p in actorx_root.rglob("*.psa")
            if f"/{source_token}/" in p.as_posix().lower()
        )
        if not psas:
            raise RuntimeError(f"{runtime_id}: no PSA animations found for {source_name}")

        before = set(bpy.data.actions.keys())
        import_failures = []
        for psa in psas:
            bpy.context.view_layer.objects.active = armature
            armature.select_set(True)
            try:
                result = bpy.ops.psa.import_all(
                    filepath=str(psa),
                    should_convert_to_samples=True,
                )
                if "FINISHED" not in result:
                    import_failures.append(f"{psa.name}:{result}")
            except Exception as exc:
                import_failures.append(f"{psa.name}:{exc}")

        new_actions = sorted(set(bpy.data.actions.keys()) - before)
        if not new_actions:
            raise RuntimeError(
                f"{runtime_id}: PSA files were present but no Blender Actions imported; "
                f"failures={import_failures[:5]}"
            )
        for action_name in new_actions:
            bpy.data.actions[action_name].use_fake_user = True

        out_dir = output_root / runtime_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_glb = out_dir / "viewmodel.glb"
        export_animated_glb(out_glb)
        stats = glb_stats(out_glb)
        if stats["meshes"] < 1 or stats["skins"] < 1 or stats["animations"] < 1:
            raise RuntimeError(f"{runtime_id}: invalid animated GLB stats {stats}")

        row = {
            "source_dir": source_name,
            "runtime_id": runtime_id,
            "source_glb": source_glb.name,
            "psa_files": len(psas),
            "actions_imported": len(new_actions),
            "import_failures": import_failures,
            "output": str(out_glb),
            **stats,
        }
        report.append(row)
        print(
            "XZOGOT_ANIMATED_WEAPON_GREEN",
            runtime_id,
            "psa=", len(psas),
            "actions=", len(new_actions),
            "glb_anims=", stats["animations"],
            "images=", stats["images"],
        )

    if len(report) != 29:
        raise RuntimeError(f"Expected 29 animated weapons, got {len(report)}")
    if sum(int(r["animations"]) for r in report) < 50:
        raise RuntimeError("Animation coverage unexpectedly low")

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "animated-inventory.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "id": "aether_waw_animated_weapon_inventory_v1",
                "weapon_count": len(report),
                "weapons": report,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print("XZOGOT_29_ANIMATED_REAL_WEAPONS_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
