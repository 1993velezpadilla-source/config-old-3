#!/usr/bin/env python3
"""Offline test: render real source vs mobile LOD silhouette, no invented assets."""
import bpy,math
from pathlib import Path
from mathutils import Vector
out=Path("tripo-fidelity");out.mkdir(exist_ok=True)
def reset():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
def bbox(obj):
    verts=[obj.matrix_world@Vector(v) for v in obj.bound_box]
    lo=Vector(tuple(min(v[i] for v in verts) for i in range(3)))
    hi=Vector(tuple(max(v[i] for v in verts) for i in range(3)))
    return (lo+hi)*0.5,hi-lo
def configure_camera(obj):
    scene=bpy.context.scene
    center,ext=bbox(obj)
    cam_data=bpy.data.cameras.new("fidelity_camera")
    cam=bpy.data.objects.new("fidelity_camera",cam_data)
    scene.collection.objects.link(cam)
    cam.data.type="ORTHO"
    cam.data.ortho_scale=max(ext)*1.85
    camera_direction=Vector((1.3,-2.8,1.45)).normalized()
    cam.location=center+camera_direction*max(ext)*3
    direction=center-cam.location
    cam.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
    scene.camera=cam
    scene.render.engine="BLENDER_WORKBENCH"
    scene.display.shading.light="STUDIO"
    scene.display.shading.color_type="SINGLE"
    scene.display.shading.single_color=(0.76,0.55,0.30)
    scene.display.shading.show_cavity=True
    scene.display.shading.cavity_type="BOTH"
    scene.render.resolution_x=960
    scene.render.resolution_y=680
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    return cam
for kind,ratio in (("bench",0.016),("altar",0.028)):
    for version in ("source","mobile"):
        reset()
        bpy.ops.import_scene.gltf(filepath=str((Path("xogot/assets/environment/church")/(kind+".glb")).resolve()))
        obj=next(o for o in bpy.context.scene.objects if o.type=="MESH")
        if version=="mobile":
            m=obj.modifiers.new("mobile_lod","DECIMATE");m.ratio=ratio
            bpy.context.view_layer.objects.active=obj
            obj.select_set(True)
            bpy.ops.object.modifier_apply(modifier=m.name)
        print("FIDE_SOURCE",kind,version,"triangles",len(obj.data.polygons),"vertices",len(obj.data.vertices))
        configure_camera(obj)
        bpy.context.scene.render.filepath=str((out/(kind+"_"+version+".png")).resolve())
        bpy.ops.render.render(write_still=True)
        print("FIDE_RENDER_DONE",kind,version)
