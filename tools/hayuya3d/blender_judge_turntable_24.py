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
    argv=argv[argv.index("--")+1:] if "--" in argv else []
    p=argparse.ArgumentParser(description="Render HAYUYA 24-view factual turntable in Blender.")
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--size",type=int,default=768)
    p.add_argument("--face-size",type=int,default=768)
    p.add_argument(
        "--preflight-only",
        action="store_true",
        help="Render only semantic-front body + face evidence for fast AAA rejection.",
    )
    return p.parse_args(argv)


def load_asset(path:Path):
    ext=path.suffix.lower()
    if ext in {".glb",".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    elif ext==".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path.resolve()),automatic_bone_orientation=False)
    elif ext==".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    else:
        raise RuntimeError(f"unsupported:{ext}")


def world_bounds(meshes):
    pts=[]
    for obj in meshes:
        for c in obj.bound_box:
            pts.append(obj.matrix_world @ Vector(c))
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx


def look_at(obj,target):
    obj.rotation_euler=(target-obj.location).to_track_quat("-Z","Y").to_euler()


def add_area(location,target,energy,size):
    bpy.ops.object.light_add(type="AREA",location=location)
    light=bpy.context.object
    light.data.energy=energy
    light.data.size=size
    look_at(light,target)


def set_resolution(scene,size:int):
    scene.render.resolution_x=size
    scene.render.resolution_y=size
    scene.render.resolution_percentage=100


def render(scene,cam,path:Path,target:Vector,offset:Vector,scale:float,size:int):
    cam.location=target+offset
    look_at(cam,target)
    cam.data.ortho_scale=scale
    set_resolution(scene,size)
    scene.render.filepath=str(path.resolve())
    bpy.ops.render.render(write_still=True)


def main():
    a=parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_asset(a.input)
    meshes=[o for o in bpy.context.scene.objects if o.type=="MESH" and not o.hide_render]
    if not meshes:
        raise RuntimeError("no_meshes")

    mn,mx=world_bounds(meshes)
    center=(mn+mx)*0.5
    ext=mx-mn
    radius=max(float(ext.x),float(ext.y),float(ext.z))*0.72
    radius=max(radius,0.5)

    # Remove imported lights/cameras; preserve meshes/materials/armatures exactly.
    for obj in list(bpy.context.scene.objects):
        if obj.type in {"CAMERA","LIGHT"}:
            bpy.data.objects.remove(obj,do_unlink=True)

    scene=bpy.context.scene
    # Blender 4.x exposes render engines as enum values, not bpy.types attrs.
    # Prefer Eevee Next and only fall back for genuinely older Blender builds.
    try:
        scene.render.engine="BLENDER_EEVEE_NEXT"
    except Exception:
        scene.render.engine="BLENDER_EEVEE"
    scene.render.image_settings.file_format="PNG"
    scene.render.film_transparent=False
    scene.world=bpy.data.worlds.new("HAYUYA_Judge_World") if scene.world is None else scene.world
    scene.world.color=(0.035,0.035,0.04)
    try:
        scene.view_settings.look="AgX - Medium High Contrast"
    except Exception:
        pass

    bpy.ops.object.camera_add()
    cam=bpy.context.object
    scene.camera=cam
    cam.data.type="ORTHO"
    cam.data.clip_start=0.01
    cam.data.clip_end=max(100.0,radius*20.0)

    add_area(center+Vector((-2.2*radius,2.6*radius,2.4*radius)),center,850,4.0*radius)
    add_area(center+Vector((2.4*radius,1.2*radius,1.0*radius)),center,480,3.0*radius)
    add_area(center+Vector((0.0,-2.0*radius,2.8*radius)),center,650,3.0*radius)

    out=a.output_dir
    full_dir=out/"turntable"
    face_dir=out/"faces"
    full_dir.mkdir(parents=True,exist_ok=True)
    face_dir.mkdir(parents=True,exist_ok=True)

    # HAYUYA generated GLBs import into Blender facing -Y. Empirically,
    # index 12 / 180 deg is the semantic front for current character exports.
    full_scale=max(float(ext.x),float(ext.y),float(ext.z))*1.08
    full_scale=max(full_scale,0.35)
    head_target=center.copy()
    # Character face evidence lives near the top of the body bounds. The old
    # 0.82 / 0.30 framing centered too low and frequently clipped the forehead
    # while wasting most of the crop on shoulders/chest. Keep this generic:
    # target the upper humanoid region and preserve extra lateral room for
    # hoods, hair, helmets and horns.
    head_target.z=mn.z+ext.z*0.895
    head_scale=max(
        float(ext.z)*0.24,
        float(ext.x)*0.58,
        float(ext.y)*0.58,
        0.18,
    )

    full=[]
    faces=[]
    # Judge v4 consumes only the front/quarter neighborhood for face evidence.
    # Render those angles FIRST so dense 2M Hero runs expose useful evidence
    # immediately and preserve the highest-value frames even if a runner dies.
    face_indices={8,9,10,11,12,13,14,15,16}
    priority=[12,13,14,15,16,8,9,10,11]
    render_order=(
        [12]
        if a.preflight_only
        else priority+[i for i in range(24) if i not in set(priority)]
    )
    distance=3.2*radius
    full_by_index={}
    face_by_index={}
    for index in render_order:
        deg=index*15
        rad=math.radians(deg)
        # 0 deg = +Y rear, 90 = +X side, 180 = -Y semantic front.
        offset=Vector((math.sin(rad)*distance,math.cos(rad)*distance,0.02*radius))
        fp=full_dir/f"{index:02d}_{deg:03d}.png"
        print(f"HAYUYA_BLENDER_RENDER full index={index} deg={deg}",flush=True)
        render(scene,cam,fp,center,offset,full_scale,a.size)
        full_by_index[index]=str(fp)
        if index in face_indices:
            hp=face_dir/f"{index:02d}_{deg:03d}.png"
            print(f"HAYUYA_BLENDER_RENDER face index={index} deg={deg}",flush=True)
            render(scene,cam,hp,head_target,offset,head_scale,a.face_size)
            face_by_index[index]=str(hp)

    # Manifest remains canonical turntable order for full Judge evidence.
    # Preflight intentionally emits only semantic front.
    if a.preflight_only:
        full=[full_by_index[12]]
        faces=[face_by_index[12]]
        manifest_face_indices=[12]
    else:
        full=[full_by_index[i] for i in range(24)]
        faces=[face_by_index[i] for i in sorted(face_indices)]
        manifest_face_indices=sorted(face_indices)

    manifest={
        "schema":1,
        "source":str(a.input),
        "renderer":"blender-eevee-24view-material-faithful-v1",
        "front_convention":"-Y after Blender glTF import; index 12 / 180 deg",
        "bounds":{
            "min":[float(x) for x in mn],
            "max":[float(x) for x in mx],
            "extents":[float(x) for x in ext],
        },
        "turntable":full,
        "faces":faces,
        "face_indices":manifest_face_indices,
        "preflight_only":bool(a.preflight_only),
    }
    (out/"blender_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(
        "HAYUYA_BLENDER_PREFLIGHT" if a.preflight_only else "HAYUYA_BLENDER_24VIEW",
        json.dumps(manifest),
    )


if __name__=="__main__":
    main()
