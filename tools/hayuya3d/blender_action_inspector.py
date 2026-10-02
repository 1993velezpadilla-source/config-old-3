#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import bpy

BONE_RE = re.compile(r'pose\.bones\["([^"]+)"\]')

def parse_args():
    argv=sys.argv
    if "--" in argv:
        argv=argv[argv.index("--")+1:]
    else:
        argv=[]
    p=argparse.ArgumentParser(description="Inspect which mechanical bones/channels each Blender action actually moves.")
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--json",required=True,type=Path)
    return p.parse_args(argv)

def load_asset(path:Path):
    ext=path.suffix.lower()
    if ext==".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    elif ext==".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path.resolve()),automatic_bone_orientation=False)
    elif ext in {".glb",".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    else:
        raise RuntimeError(f"unsupported_asset:{ext}")

def keyframe_delta(curve):
    pts=list(curve.keyframe_points)
    if len(pts)<2:
        return 0.0
    vals=[float(p.co[1]) for p in pts]
    return max(vals)-min(vals)

def main():
    a=parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_asset(a.input)

    actions=[]
    for action in sorted(bpy.data.actions,key=lambda x:x.name.lower()):
        bones={}
        object_channels=[]
        for fc in action.fcurves:
            delta=keyframe_delta(fc)
            if delta<=1e-8:
                continue
            m=BONE_RE.search(fc.data_path or "")
            item={
                "path":fc.data_path,
                "array_index":int(fc.array_index),
                "keyframes":len(fc.keyframe_points),
                "value_delta":round(delta,8),
            }
            if m:
                bones.setdefault(m.group(1),[]).append(item)
            else:
                object_channels.append(item)
        start,end=action.frame_range
        actions.append({
            "name":action.name,
            "frame_range":[float(start),float(end)],
            "animated_bones":sorted(bones),
            "bone_channels":bones,
            "object_channels":object_channels,
            "mechanical_motion_present":bool(bones or object_channels),
        })

    report={
        "schema":1,
        "input":str(a.input),
        "armatures":[
            {"name":o.name,"bones":[b.name for b in o.data.bones]}
            for o in bpy.context.scene.objects if o.type=="ARMATURE"
        ],
        "actions":actions,
        "action_count":len(actions),
    }
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_ACTION_INSPECT",json.dumps({
        "actions":len(actions),
        "moving_actions":sum(1 for x in actions if x["mechanical_motion_present"])
    },separators=(",",":")))
    print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
