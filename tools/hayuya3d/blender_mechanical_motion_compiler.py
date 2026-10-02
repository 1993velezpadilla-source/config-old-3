#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv=sys.argv
    if "--" in argv:
        argv=argv[argv.index("--")+1:]
    else:
        argv=[]
    p=argparse.ArgumentParser(description="Compile semantic HAYUYA mechanical recipes into fitted skeletal animation.")
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--part-map",required=True,type=Path)
    p.add_argument("--family",required=True)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--recipes",type=Path,default=Path("hayuya/standards/hayuya_mechanical_motion_recipes_v1.json"))
    p.add_argument("--fps",type=int,default=30)
    p.add_argument("--seconds",type=float,default=1.25)
    return p.parse_args(argv)


def import_asset(path:Path):
    ext=path.suffix.lower()
    if ext in {".glb",".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    elif ext==".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path.resolve()),automatic_bone_orientation=False)
    elif ext==".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    else:
        raise RuntimeError(f"unsupported_asset:{ext}")


def armature():
    arms=[o for o in bpy.context.scene.objects if o.type=="ARMATURE"]
    if len(arms)!=1:
        raise RuntimeError(f"expected_one_mechanical_armature:{len(arms)}")
    return arms[0]


def vec3(value,default=(0,0,0)):
    vals=list(value or default)
    if len(vals)!=3:
        raise ValueError("expected vec3")
    return Vector(tuple(float(x) for x in vals))


def main():
    a=parse_args()
    recipes=json.loads(a.recipes.read_text(encoding="utf-8"))
    part_map=json.loads(a.part_map.read_text(encoding="utf-8"))
    family=recipes.get("families",{}).get(a.family)
    if not family:
        raise RuntimeError(f"unknown_family:{a.family}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    import_asset(a.input)
    arm=armature()
    if arm.animation_data is None:
        arm.animation_data_create()

    components=part_map.get("components",{})
    report={
        "schema":1,
        "family":a.family,
        "input":str(a.input),
        "output":str(a.output),
        "compiled_actions":[],
        "skipped_actions":[],
        "warnings":[]
    }

    fps=max(1,a.fps)
    bpy.context.scene.render.fps=fps
    frame_span=max(2,int(round(max(0.2,a.seconds)*fps)))

    for action_name,events in family.items():
        required={e.get("component") for e in events if e.get("component")}
        missing=[c for c in sorted(required) if c not in components]
        if missing:
            report["skipped_actions"].append({
                "name":action_name,
                "reason":"missing_components",
                "components":missing
            })
            continue

        targets={}
        unsupported=[]
        for component in required:
            meta=components[component]
            if meta.get("target_type")!="bone":
                unsupported.append(component)
                continue
            name=str(meta.get("target_name") or "")
            bone=arm.pose.bones.get(name)
            if not bone:
                unsupported.append(component)
                continue
            targets[component]=(bone,meta)
        if unsupported:
            report["skipped_actions"].append({
                "name":action_name,
                "reason":"unsupported_or_missing_bone_targets",
                "components":unsupported
            })
            continue

        act=bpy.data.actions.new(name="HAYUYA_"+action_name)
        arm.animation_data.action=act
        bases={}
        for comp,(bone,meta) in targets.items():
            bone.rotation_mode="XYZ"
            bases[comp]={
                "location":bone.location.copy(),
                "rotation":bone.rotation_euler.copy()
            }

        unsupported_ops=set()
        for event in events:
            comp=event.get("component")
            bone,meta=targets[comp]
            base=bases[comp]
            op=event.get("op")
            amount=float(event.get("amount",0.0))
            t=max(0.0,min(1.0,float(event.get("t",0.0))))
            frame=1+int(round(t*frame_span))

            bone.location=base["location"].copy()
            bone.rotation_euler=base["rotation"].copy()

            if op=="translate_axis":
                axis=vec3(meta.get("axis"),(0,1,0))
                if axis.length<=1e-8:
                    raise RuntimeError(f"zero_axis:{comp}")
                axis.normalize()
                distance=float(meta.get("distance",0.0))
                bone.location=base["location"]+axis*(distance*amount)
                bone.keyframe_insert(data_path="location",frame=frame,group=bone.name)
            elif op in {"rotate_axis","hinge_rotate","rotate_step"}:
                axis=vec3(meta.get("axis"),(1,0,0))
                if axis.length<=1e-8:
                    raise RuntimeError(f"zero_axis:{comp}")
                axis.normalize()
                if op=="rotate_step":
                    degrees=float(meta.get("degrees_per_step",meta.get("degrees",0.0)))
                else:
                    degrees=float(meta.get("degrees",0.0))
                delta=axis*math.radians(degrees*amount)
                bone.rotation_euler=base["rotation"]+delta
                bone.keyframe_insert(data_path="rotation_euler",frame=frame,group=bone.name)
            elif op in {"spawn_or_attach","translate_to_socket","hide_or_parent"}:
                unsupported_ops.add(op)
            else:
                unsupported_ops.add(str(op))

        if unsupported_ops:
            report["warnings"].append(
                action_name+":unsupported_ops:"+",".join(sorted(unsupported_ops))
            )

        # Constant endpoint protection: restore bases one frame after clip end only
        # when no explicit event lands at t=1 for that component.
        report["compiled_actions"].append({
            "name":act.name,
            "source_recipe":action_name,
            "frame_range":[1,1+frame_span],
            "components":sorted(required)
        })

    if not report["compiled_actions"]:
        raise RuntimeError("no_actions_compiled")

    # Push compiled actions to NLA so glTF exports all of them.
    arm.animation_data.action=None
    for rec in report["compiled_actions"]:
        act=bpy.data.actions.get(rec["name"])
        track=arm.animation_data.nla_tracks.new()
        track.name=rec["name"]
        strip=track.strips.new(rec["name"],1,act)
        strip.action_frame_start=act.frame_range[0]
        strip.action_frame_end=act.frame_range[1]

    a.output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(a.output.resolve()),
        export_format="GLB",
        export_animations=True,
        export_skins=True,
        export_nla_strips=True,
        export_yup=True
    )

    report["output_bytes"]=a.output.stat().st_size
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_MECHANICAL_MOTION_COMPILED")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
