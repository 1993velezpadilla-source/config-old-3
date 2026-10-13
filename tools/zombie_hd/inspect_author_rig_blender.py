#!/usr/bin/env python3
"""Blender headless audit of the real authored Hotstrike rigged FBX.

Produces mesh/rig/UV/scale facts, never a fake Quake model or asset dump.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def analyze(fbx):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), use_anim=True)
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not meshes:
        raise RuntimeError("No importable authored zombie mesh from FBX")
    all_points = []
    results = []
    for obj in meshes:
        ob = obj.data
        ob.calc_loop_triangles()
        coords = [obj.matrix_world @ p.co for p in ob.vertices]
        all_points.extend(coords)
        results.append({
            "name": obj.name,
            "vertices": len(ob.vertices),
            "triangles": len(ob.loop_triangles),
            "uv_layers": [u.name for u in ob.uv_layers],
            "material_names": [m.name for m in ob.materials if m],
            "vertex_groups": len(obj.vertex_groups),
            "bound_armature": [
                m.object.name for m in obj.modifiers
                if m.type == "ARMATURE" and m.object is not None
            ],
        })
    mins = [min(p[i] for p in all_points) for i in range(3)]
    maxs = [max(p[i] for p in all_points) for i in range(3)]
    arm_info = [
        {"name": a.name,
         "bones": len(a.data.bones),
         "bone_names": [b.name for b in a.data.bones],
         "world_scale": [float(v) for v in a.scale],
         "root_bones": [b.name for b in a.data.bones if b.parent is None]}
        for a in armatures
    ]
    return {
        "origin": "Hotstrike Studio free SZombie rigged author FBX",
        "mesh": results,
        "mesh_vertices_total": sum(x["vertices"] for x in results),
        "triangles_total": sum(x["triangles"] for x in results),
        "armatures": arm_info,
        "bounds_world": {"min": mins, "max": maxs,
                         "size_xyz": [maxs[i]-mins[i] for i in range(3)]},
        "actions_in_free_source": sorted(a.name for a in bpy.data.actions),
        "images_declared": sorted(img.name for img in bpy.data.images),
        "next": "Retarget verified source to native zfull.mdl actions; verify render/headshots on device",
        "status": "REAL_SOURCE_FBX_PARSED_NOT_YET_GAME_READY",
    }


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--fbx", required=True, type=Path)
    a.add_argument("--output", required=True, type=Path)
    opts = a.parse_args(sys.argv[sys.argv.index("--")+1:])
    report = analyze(opts.fbx.resolve())
    assert report["triangles_total"] >= 4500, "FBX is unexpectedly low detail"
    assert report["armatures"] and any(x["bones"] > 10 for x in report["armatures"]), "No usable humanoid rig"
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(report, indent=2)+"\n")
    print("XZIEL_GENUINE_HOTSTRIKE_FBX_AUDIT", json.dumps(report))


if __name__ == "__main__":
    main()
