#!/usr/bin/env python3
"""Merge mapped Aether WaW skeletal GLBs with their ActorX PSA animations in Blender.

Run inside Blender:
  blender --background --python build_aether_animated_glbs.py -- <artifact_root> <addon_parent> <psk_psa_py_target> <output_root>
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

# Aether does not ship a dedicated SawedOffDB PSA folder, but the mesh shares
# the functional double-barrel joint layout (j_gun/tag_barrels/tag_extractor/
# tag_shell1/tag_shell2/tag_flash/tag_grip/tag_brass/tag_lever). Reuse those
# source clips instead of fabricating animations.
PSA_SOURCE_OVERRIDE = {
    "SawedOffDB": "DoubleBarrel",
}

# Projectile-only source: animation belongs to the player's hand/throw action,
# not to the grenade mesh itself.
THROWABLE_STATIC = {"Stielhand"}


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


def bind_actions_to_armature_nla(armature, action_names: list[str]) -> list[str]:
    """Attach imported PSA actions to the weapon armature so glTF can see them."""
    anim = armature.animation_data_create()
    # The importer intentionally creates Actions without applying them.  glTF
    # ACTIONS mode can therefore skip them.  Give each real PSA action its own
    # NLA track on the actual weapon skeleton.
    bound = []
    for action_name in action_names:
        action = bpy.data.actions.get(action_name)
        if action is None:
            continue
        try:
            track = anim.nla_tracks.new()
            track.name = "PSA_" + action_name
            start = int(round(float(action.frame_range[0])))
            strip = track.strips.new(action_name, start, action)
            strip.name = action_name
            bound.append(action_name)
        except Exception as exc:
            print("XZOGOT_PSA_NLA_BIND_FAIL", armature.name, action_name, repr(exc))
    if not bound:
        raise RuntimeError(f"{armature.name}: no imported PSA Actions could be bound to NLA")
    print("XZOGOT_PSA_NLA_BOUND", armature.name, len(bound), bound[:8])
    return bound


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
        # Imported PSA clips are explicitly attached as NLA tracks above.
        mode_prop = bpy.ops.export_scene.gltf.get_rna_type().properties["export_animation_mode"]
        modes = {item.identifier for item in mode_prop.enum_items}
        if "NLA_TRACKS" in modes:
            kwargs["export_animation_mode"] = "NLA_TRACKS"
        elif "ACTIONS" in modes:
            kwargs["export_animation_mode"] = "ACTIONS"
        else:
            raise RuntimeError(f"No usable glTF animation mode; available={sorted(modes)}")
        print("XZOGOT_GLTF_ANIMATION_MODE", kwargs["export_animation_mode"])
    elif "export_all_actions" in props:
        kwargs["export_all_actions"] = True
    if "export_force_sampling" in props:
        kwargs["export_force_sampling"] = True
    if "export_nla_strips" in props:
        kwargs["export_nla_strips"] = True
    result = bpy.ops.export_scene.gltf(**kwargs)
    if "FINISHED" not in result:
        raise RuntimeError(f"GLTF export failed: {result}")



def repair_actorx_psa_animation_axes_in_glb(path: Path) -> dict[str, int]:
    """Reconcile GLTF-native skinned bone rest axes with ActorX PSA Action keys.

    The original UE-exported glTF bind joints are (x,z,-y), while PSA import
    onto that GLB armature currently bakes its keyed translations in (x,y,z).
    This misorients slide/magazine/reload bones (and most ADS iron sights).
    Verified directly from original Colt1911Idle.psa BONENAMES/ANIMKEYS and
    Colt1911.glb: all 14 local joints align after X -90-degree conversion,
    from 0.0258 m baseline RMS bind discrepancy to numerical zero.

    Apply the same proper change of basis to both translations and rotations
    in glTF animation outputs; NEVER touch the original mesh, bind poses,
    inverseBindMatrices, animation timing, scalar stats, or source hand rigs.
    This is a native conversion of the entire source actorx animation, not
    a frame-dependent/gun-specific invented position offset.
    """
    payload = bytearray(path.read_bytes())
    if payload[:4] != b"glTF" or len(payload) != struct.unpack_from("<I", payload, 8)[0]:
        raise RuntimeError(f"{path}: invalid source GLB header")
    chunks = []
    offset = 12
    while offset + 8 <= len(payload):
        chunk_length, kind = struct.unpack_from("<II", payload, offset)
        start = offset + 8
        if start + chunk_length > len(payload):
            raise RuntimeError(f"{path}: corrupt source GLB chunk boundaries")
        chunks.append((kind, start, chunk_length))
        offset = start + chunk_length
    if offset != len(payload):
        raise RuntimeError(f"{path}: invalid GLB chunk remainder")
    json_chunks = [ch for ch in chunks if ch[0] == 0x4E4F534A]
    bin_chunks = [ch for ch in chunks if ch[0] == 0x004E4942]
    if len(json_chunks) != 1 or len(bin_chunks) != 1:
        raise RuntimeError(f"{path}: expected one JSON and BIN chunk")
    _, start_json, len_json = json_chunks[0]
    _, start_bin, len_bin = bin_chunks[0]
    doc = json.loads(payload[start_json:start_json + len_json].rstrip(bytes((32, 9, 13, 10, 0))))
    joint_nodes = set()
    for skin in doc.get("skins", []):
        joint_nodes.update(skin.get("joints", []))
    if not joint_nodes or not doc.get("animations"):
        raise RuntimeError(f"{path}: source animation or skin joint map missing")

    changed: set[tuple[int, str]] = set()
    sample_total = 0
    channel_total = 0
    translation_total = 0
    rotation_total = 0
    for animation in doc["animations"]:
        samplers = animation.get("samplers", [])
        for channel in animation.get("channels", []):
            target = channel.get("target", {})
            component = target.get("path")
            if target.get("node") not in joint_nodes or component not in ("translation", "rotation"):
                continue
            sampler = samplers[channel["sampler"]]
            accessor_index = int(sampler["output"])
            key = (accessor_index, component)
            if key in changed:
                continue
            changed.add(key)
            accessor = doc["accessors"][accessor_index]
            kind = "VEC3" if component == "translation" else "VEC4"
            if accessor.get("componentType") != 5126 or accessor.get("type") != kind or "sparse" in accessor:
                raise RuntimeError(f"{path}: unsafe ActorX output accessor {key}: {accessor}")
            view = doc["bufferViews"][accessor["bufferView"]]
            if int(view.get("buffer", 0)) != 0:
                raise RuntimeError(f"{path}: non-GLB animation buffer {key}")
            width = 3 if component == "translation" else 4
            stride = int(view.get("byteStride", width * 4))
            if stride < width * 4 or stride % 4:
                raise RuntimeError(f"{path}: unsafe animation stride {stride} for {key}")
            start = start_bin + int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
            if accessor["count"] < 1 or start + (accessor["count"] - 1) * stride + width * 4 > start_bin + len_bin:
                raise RuntimeError(f"{path}: source PSA output out of BIN bounds {key}")
            for idx in range(int(accessor["count"])):
                at = start + idx * stride
                if component == "translation":
                    x, y, z = struct.unpack_from("<3f", payload, at)
                    # glTF rest coordinate system: proper R_x(-90): (x,z,-y).
                    struct.pack_into("<3f", payload, at, x, z, -y)
                    translation_total += 1
                else:
                    x, y, z, w = struct.unpack_from("<4f", payload, at)
                    # q' = R_x(-90) q R_x(+90): rotate quaternion's vector,
                    # preserve scalar; valid also for cubic-spline tangents.
                    struct.pack_into("<4f", payload, at, x, z, -y, w)
                    rotation_total += 1
                sample_total += 1
            channel_total += 1
    if not translation_total or not rotation_total:
        raise RuntimeError(f"{path}: no native skinned gun translations/rotations repaired")
    # The entire original GLB layout, bone bindings and key times are byte-
    # identical except the intended source Action output float samples.
    path.write_bytes(payload)
    print("XZOGOT_ACTORX_GLTF_BONE_AXES_REPAIRED", path.name,
          "channels=", channel_total,
          "translation_samples=", translation_total,
          "rotation_samples=", rotation_total,
          "skinned_bones=", len(joint_nodes))
    return {"channels": channel_total, "translation_samples": translation_total,
            "rotation_samples": rotation_total, "skinned_bones": len(joint_nodes)}


def main() -> int:
    args = argv_after_double_dash()
    if len(args) != 4:
        raise SystemExit(
            "usage: blender --background --python build_aether_animated_glbs.py "
            "-- <artifact_root> <addon_parent> <psk_psa_py_target> <output_root>"
        )
    artifact_root = Path(args[0]).resolve()
    addon_parent = Path(args[1]).resolve()
    psk_psa_py_target = Path(args[2]).resolve()
    output_root = Path(args[3]).resolve()

    if not (psk_psa_py_target / "psk_psa_py" / "__init__.py").is_file():
        raise SystemExit(f"Installed psk_psa_py package missing: {psk_psa_py_target}")
    sys.path.insert(0, str(psk_psa_py_target))
    sys.path.insert(0, str(addon_parent))
    import psk_psa_py  # type: ignore
    print("XZOGOT_PSK_PSA_PY_READY", getattr(psk_psa_py, "__file__", "installed"))
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

        psa_source = PSA_SOURCE_OVERRIDE.get(source_name, source_name)
        source_token = psa_source.lower()
        psas = sorted(
            p for p in actorx_root.rglob("*.psa")
            if f"/{source_token}/" in p.as_posix().lower()
        )

        out_dir = output_root / runtime_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_glb = out_dir / "viewmodel.glb"

        if source_name in THROWABLE_STATIC:
            # Preserve the recovered real skinned projectile mesh exactly. Its
            # animation is authored on the player's hands/throw state.
            out_glb.write_bytes(source_glb.read_bytes())
            stats = glb_stats(out_glb)
            if stats["meshes"] < 1 or stats["skins"] < 1:
                raise RuntimeError(f"{runtime_id}: invalid throwable GLB stats {stats}")
            new_actions = []
            import_failures = []
            animation_mode = "throwable_static_mesh"
        else:
            if not psas:
                raise RuntimeError(
                    f"{runtime_id}: no PSA animations found for {source_name} "
                    f"(PSA source {psa_source})"
                )

            # Sawed-off and full double barrel share the same functional joints;
            # only their root skeleton node label differs. Rename that one root
            # locally so the inherited DoubleBarrel PSA can bind cleanly.
            if source_name == "SawedOffDB":
                roots = [b for b in armature.data.bones if b.parent is None]
                if roots:
                    roots[0].name = "viewmodel_usa_double_barrel_LOD0_skel"

            before = set(bpy.data.actions.keys())
            import_failures = []
            for psa in psas:
                bpy.context.view_layer.objects.active = armature
                armature.select_set(True)
                try:
                    result = bpy.ops.psa.import_all(
                        filepath=str(psa),
                        should_convert_to_samples=True,
                        # Source ActorX PSA bone translations are UE centimeters;
                        # recovered Aether GLB armatures and meshes are meters.
                        # Without 0.01, source idle clips move many weapon joints
                        # 10-100 meters (28-gun Godot geometry gate measured 98m).
                        # The upstream PSA importer documents this exact parameter.
                        translation_scale=0.01,
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
            bound_actions = bind_actions_to_armature_nla(armature, new_actions)
            if len(bound_actions) != len(new_actions):
                raise RuntimeError(
                    f"{runtime_id}: only {len(bound_actions)}/{len(new_actions)} PSA Actions bound to NLA"
                )

            export_animated_glb(out_glb)
            axis_report = repair_actorx_psa_animation_axes_in_glb(out_glb)
            stats = glb_stats(out_glb)
            if stats["meshes"] < 1 or stats["skins"] < 1 or stats["animations"] < 1:
                raise RuntimeError(f"{runtime_id}: invalid animated GLB stats {stats}")
            animation_mode = "embedded_psa_actions"

        row = {
            "source_dir": source_name,
            "runtime_id": runtime_id,
            "source_glb": source_glb.name,
            "psa_source": psa_source,
            "psa_files": len(psas),
            "psa_translation_scale": 0.01 if animation_mode == "embedded_psa_actions" else None,
            "psa_to_gltf_axes": "x,z,-y" if animation_mode == "embedded_psa_actions" else None,
            "actions_imported": len(new_actions),
            "actions_nla_bound": len(new_actions) if animation_mode == "embedded_psa_actions" else 0,
            "import_failures": import_failures,
            "animation_mode": animation_mode,
            "output": str(out_glb),
            **stats,
        }
        report.append(row)
        print(
            "XZOGOT_WEAPON_ASSET_GREEN",
            runtime_id,
            "mode=", animation_mode,
            "psa=", len(psas),
            "actions=", len(new_actions),
            "glb_anims=", stats["animations"],
            "images=", stats["images"],
        )

    if len(report) != 29:
        raise RuntimeError(f"Expected 29 recovered Aether assets, got {len(report)}")
    animated = [r for r in report if r["animation_mode"] == "embedded_psa_actions"]
    throwables = [r for r in report if r["animation_mode"] == "throwable_static_mesh"]
    if len(animated) != 28 or len(throwables) != 1:
        raise RuntimeError(
            f"Expected 28 animated firearms + 1 throwable; got {len(animated)} + {len(throwables)}"
        )
    if sum(int(r["animations"]) for r in animated) < 50:
        raise RuntimeError("Animation coverage unexpectedly low")

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "animated-inventory.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "id": "aether_waw_animated_weapon_inventory_v1",
                "weapon_count": len(report),
                "animated_weapon_count": len(animated),
                "throwable_count": len(throwables),
                "weapons": report,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print("XZOGOT_28_ANIMATED_FIREARMS_1_THROWABLE_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
