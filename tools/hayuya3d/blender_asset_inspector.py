#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import bpy


def args():
    argv=sys.argv
    if "--" in argv:
        argv=argv[argv.index("--")+1:]
    else:
        argv=[]
    p=argparse.ArgumentParser(description="Inspect arbitrary 3D assets for HAYUYA.")
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--json",required=True,type=Path)
    return p.parse_args(argv)


def import_asset(path: Path):
    ext=path.suffix.lower()
    if ext in {".glb",".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    elif ext==".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path.resolve()),automatic_bone_orientation=False)
    elif ext==".obj":
        try:
            bpy.ops.wm.obj_import(filepath=str(path.resolve()))
        except Exception:
            bpy.ops.import_scene.obj(filepath=str(path.resolve()))
    elif ext==".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    else:
        raise RuntimeError(f"unsupported_asset:{ext}")


def main():
    a=args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import_asset(a.input)

    objects=list(bpy.data.objects)
    meshes=[o for o in objects if o.type=="MESH"]
    arms=[o for o in objects if o.type=="ARMATURE"]
    empties=[o for o in objects if o.type=="EMPTY"]
    actions=sorted({x.name for x in bpy.data.actions})
    bones=sorted({b.name for arm in arms for b in arm.data.bones})
    mesh_names=[o.name for o in meshes]
    material_names=sorted({slot.material.name for o in meshes for slot in o.material_slots if slot.material})
    shape_keys=sorted({
        kb.name for o in meshes if o.data.shape_keys
        for kb in o.data.shape_keys.key_blocks
        if kb.name!="Basis"
    })

    vertex_count=sum(len(o.data.vertices) for o in meshes)
    polygon_count=sum(len(o.data.polygons) for o in meshes)

    report={
        "schema":1,
        "input":str(a.input),
        "object_count":len(objects),
        "mesh_count":len(meshes),
        "armature_count":len(arms),
        "empty_count":len(empties),
        "vertices":vertex_count,
        "polygons":polygon_count,
        "mesh_names":mesh_names,
        "armatures":[{"name":arm.name,"bones":[b.name for b in arm.data.bones]} for arm in arms],
        "bone_names":bones,
        "actions":actions,
        "action_count":len(actions),
        "materials":material_names,
        "shape_keys":shape_keys,
        "animation_capable":bool(actions or arms or shape_keys),
    }
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_ASSET_INSPECT",json.dumps({
        "meshes":len(meshes),"armatures":len(arms),"actions":len(actions),
        "vertices":vertex_count,"polygons":polygon_count
    },separators=(",",":")))
    print(json.dumps(report,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
