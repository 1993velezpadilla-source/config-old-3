#!/usr/bin/env python3
"""Godot 4.6 Meridian 2.0 source scene A/B, not a BO3 T7 extractor.

Execute with Blender >=4.5:
 blender --background --factory-startup --python THIS_SCRIPT -- \
     --scene /path/to/nacht-static-scene.json \
     --mesh-root /path/to/meshes_glb \
     --meridian-parent /tmp/meridian-src --out /tmp/nacht-meridian-ab

Native mesh/actor matrices MUST be present. Never create fake meshes in
production. --fixture explicitly creates diagnostic geometry only.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import mathutils


def parse_args():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--mesh-root", type=Path)
    parser.add_argument("--meridian-parent", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fixture", action="store_true",
                        help="SYNTHETIC CI geometry only, NEVER a shipping map")
    parser.add_argument("--max-instances", type=int, default=0)
    return parser.parse_args(args)


def as_matrix(row):
    if not isinstance(row, list) or len(row) != 16:
        raise ValueError("source matrixRowMajor missing: refuse default identity")
    vals = [float(x) for x in row]
    if not all(math.isfinite(x) for x in vals):
        raise ValueError("nonfinite source matrix")
    if any(abs(vals[i]) > 1e-5 for i in (12, 13, 14)) or abs(vals[15] - 1) > 1e-5:
        raise ValueError("source matrix incompatible with 4x4 affine")
    return mathutils.Matrix((vals[0:4], vals[4:8], vals[8:12], vals[12:16]))


def read_scene(path, is_fixture):
    raw = path.read_bytes()
    scene = json.loads(raw)
    if scene.get("schemaVersion") != 1 or scene.get("format") != "xziel_visual_scene_v1":
        raise ValueError("unrecognized Unreal-to-XZIEL source scene schema")
    coord = scene.get("coordinateSystem", {})
    if coord.get("matrixConvention") != "row_major_column_vector_T_R_S":
        raise ValueError("source matrix semantics absent; no axis guesses")
    if not is_fixture and not scene.get("summary", {}).get("ready"):
        raise ValueError("real Unreal scene source authority is not ready")
    if not scene.get("meshes") or not scene.get("instances"):
        raise ValueError("native source mesh instances absent")
    return scene, hashlib.sha256(raw).hexdigest()


def make_mesh_fixture():
    bpy.ops.mesh.primitive_cube_add(size=0.5)
    obj = bpy.context.object
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    return mesh


def import_exact_native_mesh(path):
    if not path.is_file() or path.stat().st_size <= 20:
        raise ValueError("missing source-native GLB: " + str(path))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    created = list(set(bpy.data.objects) - before)
    meshes = [o for o in created if o.type == "MESH"]
    if not meshes:
        raise ValueError("original mesh GLB contains no usable surfaces " + str(path))
    # glTF loader may wrap chunk meshes in nodes: fail if nonidentity transforms
    # until glTF frame conversion is independently proven against source bounds.
    unexpected = [o.name for o in meshes if
                  any(abs(float(v) - (1. if k in (0,5,10,15) else 0.)) > 1e-4
                      for k, v in enumerate(sum((list(r) for r in o.matrix_world), [])))]
    if unexpected:
        raise ValueError("source GLB imported with nonidentity chunk transform: " + str(unexpected))
    # XZMS-generated GLBs explicitly say xziel_basis_preserved=true. Their
    # POSITION data is XZIEL Z-UP, whereas glTF normatively describes Y-UP.
    # Blender's importer rotates Y-UP -> Blender Z-UP, silently rotating the
    # nonstandard but source-faithful vertex payload. Undo Blender's known
    # glTF axis conversion ONCE for these positively identified bridge GLBs.
    # Not a per-prop tweak. Exact raw source world-vertex AABB acceptance
    # independently verifies this contract at every actor (separate gate).
    import struct
    raw = path.read_bytes()
    if raw[:4] != b"glTF":
        raise ValueError("source GLB magic missing " + str(path))
    json_len, json_typ = struct.unpack_from("<II", raw, 12)
    if json_typ != 0x4E4F534A:
        raise ValueError("source GLB JSON missing " + str(path))
    source_doc = json.loads(raw[20:20 + json_len])
    if source_doc.get("extras", {}).get("xziel_basis_preserved") is not True:
        raise ValueError("unknown native glTF axis convention; refuse silent correction")
    restore_xziel_z_up = mathutils.Matrix.Rotation(-math.pi / 2, 4, "X")
    result = [o.data for o in meshes]
    for mesh in result:
        mesh.transform(restore_xziel_z_up)
        mesh.update()
    print("XZOGOT_NATIVE_XZIEL_GLB_AXIS_CONTRACT",
          path.name, "source_Z_UP_preserved=true",
          "Blender_glTF_YUP_to_ZUP_undone_once=true",
          "mesh_chunks=", len(result))
    for o in created:
        bpy.data.objects.remove(o, do_unlink=True)
    return result


def main():
    opts = parse_args()
    scene, source_sha = read_scene(opts.scene, opts.fixture)
    if opts.fixture:
        if opts.mesh_root:
            raise ValueError("cannot mix synthetic CI geometry and source mesh files")
    elif not opts.mesh_root or not opts.mesh_root.is_dir():
        raise ValueError("source GLB directory required. Never substitute sample cubes")
    if opts.max_instances < 0:
        raise ValueError("negative instances limit")
    opts.out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    # Actual CUE4Parse extractor output: UE centimeters -> X,-Y,Z in meters.
    # Existing Xogot runtime rotates XZIEL +X -> Godot -Z, +Y -> -X, +Z -> +Y.
    # Meridian exports Blender +Z-up via glTF Y-up; Blender +90deg about Z
    # is the conjugate of that proven runtime transform.
    root = bpy.data.objects.new("XZIEL_Nacht_Source_Basis", None)
    bpy.context.scene.collection.objects.link(root)
    root.rotation_euler = (0.0, 0.0, math.pi / 2)
    root["source_basis"] = "XZIEL_X-minusY_Zup_to_Blender_before_Godot"
    template = {}
    meshes = {int(item["index"]): item for item in scene["meshes"]}
    rows = scene["instances"]
    if opts.max_instances:
        rows = rows[:opts.max_instances]
    expected = {}
    for row in rows:
        iid = str(row["instanceId"])
        if iid in expected:
            raise ValueError("source instance IDs duplicated " + iid)
        idx = int(row["meshIndex"])
        if idx not in meshes:
            raise ValueError("referenced source meshIndex missing " + str(idx))
        if idx not in template:
            mesh = meshes[idx]
            if opts.fixture:
                template[idx] = [make_mesh_fixture()]
            else:
                runtime_file = str(mesh["runtimeFile"])
                # Source runtime mesh path is the XZMS; independently converted
                # Godot-safe GLB has same stem per xzms_to_glb.py.
                name = Path(runtime_file).stem + ".glb"
                template[idx] = import_exact_native_mesh(opts.mesh_root / name)
        mat = as_matrix(row["matrixRowMajor"])
        actor = bpy.data.objects.new(iid, None)
        bpy.context.scene.collection.objects.link(actor)
        actor.parent = root
        actor.matrix_local = mat
        actor["source_component_path"] = str(row.get("sourceComponentPath", ""))
        actor["source_instance_id"] = iid
        actor["source_mesh_index"] = idx
        for part, data in enumerate(template[idx]):
            child = bpy.data.objects.new(iid + "_chunk_%03d" % part, data)
            bpy.context.scene.collection.objects.link(child)
            child.parent = actor
        xyz = mat.translation
        expected[iid] = {
            "xz_position_m": [xyz.x, xyz.y, xyz.z],
            "expected_godot_position_m": [-xyz.y, xyz.z, -xyz.x],
            "mesh_index": idx,
            "source_component_path": str(row.get("sourceComponentPath", "")),
        }
    if len(expected) != len(rows):
        raise ValueError("source instance count mismatch")

    # Real third-party Blender-to-Godot adapter; no approximation or homegrown
    # faux-Meridian scene writer. Pinned commit and version from CI.
    parent = opts.meridian_parent.resolve()
    sys.path.insert(0, str(parent))
    # In background --factory-startup Blender does not enumerate arbitrary
    # folders appended to sys.path as installed addons. Explicitly register
    # pinned Meridian source modules; the class registry is the authority,
    # not User Preferences' list of persistent enabled addons.
    import Meridian
    try:
        Meridian.register()
    except Exception as exc:
        raise RuntimeError("Meridian 2.0 register failed: " + repr(exc))
    if not hasattr(bpy.types.Scene, "MX_SceneProperties"):
        raise RuntimeError("Meridian real Scene properties were not registered")
    props = bpy.context.scene.MX_SceneProperties
    props.mx_godot_project_path = str(opts.out.resolve() / "godot")
    props.mx_export_scene_name = "Nacht_Source_Bridge_Probe"
    props.mx_renderer = "MOBILE"
    props.mx_platform = "DESKTOP"
    props.mx_export_format = "GLB"
    props.mx_export_animations = False
    props.mx_export_custom_properties = True
    # No GUI editor/headless hidden subprocess. CI runs Godot separately.
    prefs = bpy.context.preferences.addons.get("Meridian")
    if prefs is not None:
        prefs.preferences.godot_path = ""
    bpy.ops.wm.save_as_mainfile(filepath=str(opts.out.resolve() / "nacht_bridge.blend"))
    start = bpy.ops.mx.initialize_project()
    if "FINISHED" not in start:
        raise RuntimeError("Meridian initialize_project failed " + str(start))
    result = bpy.ops.mx.compile()
    if "FINISHED" not in result:
        raise RuntimeError("Meridian compile failed " + str(result))
    p = Path(props.mx_godot_project_path)
    files = [p / "project.godot", p / "scenes/main.tscn",
             p / "scenes/Nacht_Source_Bridge_Probe.tscn",
             p / "assets/meshes/Nacht_Source_Bridge_Probe.glb"]
    if any(not q.is_file() or q.stat().st_size == 0 for q in files):
        raise RuntimeError("Meridian missing generated Godot files: " + str(files))
    report = {
        "authority": "synthetic_test_fixture_ONLY" if opts.fixture else "UE4.21 source JSON GLB geometry",
        "source_sha256": source_sha,
        "source_instance_count": len(scene["instances"]),
        "exported_instance_count": len(rows),
        "exported_mesh_references": len(template),
        "coordinate_source": "XZIEL X,-Y,Z Z-up meters",
        "godot_scene": "scenes/main.tscn",
        "source_world_positions": expected,
        "made_up_source_objects": bool(opts.fixture),
        "manual_per_object_pose_offsets": 0,
        "original_bo3_t7_map_proven": False,
    }
    (opts.out / "source-equivalence.json").write_text(json.dumps(report, indent=2)+"\n")
    print("XZOGOT_NACHT_MERIDIAN_REAL_ADDON_COMPILE_GREEN",
          "test_fixture=", opts.fixture, "objects=", len(expected),
          "native_mesh_types=", len(template))
    print("XZOGOT_NACHT_NOT_ORIGINAL_BO3_T7", source_sha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
