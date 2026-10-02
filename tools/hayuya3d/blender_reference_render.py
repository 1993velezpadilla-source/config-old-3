#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    p=argparse.ArgumentParser(description="Render a clean HAYUYA reference image from a 3D asset.")
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--size",type=int,default=1024)
    p.add_argument("--view",choices=["front","side","rear","top"],default="front")
    p.add_argument(
        "--frame",
        choices=["full","head","upper","lower"],
        default="full",
        help="semantic framing crop; head keeps facial anatomy large enough for detector QA",
    )
    return p.parse_args(argv)


def load_asset(path:Path):
    ext=path.suffix.lower()
    if ext==".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    elif ext==".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path.resolve()),automatic_bone_orientation=False)
    elif ext in {".glb",".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    elif ext==".obj":
        try:
            bpy.ops.wm.obj_import(filepath=str(path.resolve()))
        except Exception:
            bpy.ops.import_scene.obj(filepath=str(path.resolve()))
    else:
        raise RuntimeError(f"unsupported:{ext}")


def bounds(meshes):
    pts=[]
    for obj in meshes:
        for c in obj.bound_box:
            pts.append(obj.matrix_world @ Vector(c))
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx


def look_at(obj,target):
    direction=target-obj.location
    obj.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()


def main():
    a=parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_asset(a.input)
    meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
    if not meshes:
        raise RuntimeError("no_meshes")

    mn,mx=bounds(meshes)
    center=(mn+mx)*0.5
    ext=mx-mn
    radius=max(ext.x,ext.y,ext.z)*0.72
    radius=max(radius,0.5)

    frame_center=center.copy()
    if a.frame=="head":
        frame_center.z=mn.z+ext.z*0.84
        frame_scale=max(
            ext.z*0.38,
            ext.x*0.28,
            ext.y*0.28,
            0.25,
        )
    elif a.frame=="upper":
        frame_center.z=mn.z+ext.z*0.68
        frame_scale=max(
            ext.z*0.66,
            ext.x*0.82,
            ext.y*0.82,
            0.4,
        )
    elif a.frame=="lower":
        frame_center.z=mn.z+ext.z*0.28
        frame_scale=max(
            ext.z*0.58,
            ext.x*0.74,
            ext.y*0.74,
            0.4,
        )
    else:
        frame_scale=max(ext.x,ext.y,ext.z)*1.35

    scene=bpy.context.scene
    scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=a.size
    scene.render.resolution_y=a.size
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.film_transparent=False
    scene.world.color=(0.02,0.02,0.025)

    bpy.ops.object.camera_add()
    cam=bpy.context.object
    scene.camera=cam
    offsets={
        "front":Vector((0,-3.2*radius,0)),
        "rear":Vector((0,3.2*radius,0)),
        "side":Vector((3.2*radius,0,0)),
        "top":Vector((0,0,3.2*radius)),
    }
    cam.location=frame_center+offsets[a.view]
    look_at(cam,frame_center)
    cam.data.type="ORTHO"
    cam.data.ortho_scale=frame_scale

    for loc,energy,size in [
        (frame_center+Vector((-2*radius,-2*radius,2*radius)),900,4*radius),
        (frame_center+Vector((2*radius,-1*radius,0.5*radius)),500,3*radius),
        (frame_center+Vector((0,1.5*radius,2.5*radius)),650,3*radius),
    ]:
        bpy.ops.object.light_add(type="AREA",location=loc)
        light=bpy.context.object
        light.data.energy=energy
        light.data.size=size
        look_at(light,frame_center)

    a.output.parent.mkdir(parents=True,exist_ok=True)
    scene.render.filepath=str(a.output.resolve())
    bpy.ops.render.render(write_still=True)
    print(
        "HAYUYA_REFERENCE_RENDER",
        a.output,
        f"view={a.view}",
        f"frame={a.frame}",
    )


if __name__=="__main__":
    main()
