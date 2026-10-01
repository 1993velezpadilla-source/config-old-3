import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_V2_INTERIOR_AUDIT_OUT","sanctum-v2-interior-source-audit"))
OUT.mkdir(parents=True,exist_ok=True)

KEYWORDS=("pew","bench","altar","pulpit","chair","table","candle","lamp","torch","chandelier","door","stair","rail","organ","cross")

def world_bbox(objs):
    pts=[]
    for o in objs:
        if o.type!="MESH":
            continue
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    if not pts:
        raise SystemExit("No mesh geometry in CC0 church interior source")
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def point(cam,target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

scene=bpy.context.scene
mesh_objs=[o for o in scene.objects if o.type=="MESH"]
mn,mx=world_bbox(mesh_objs)
center=(mn+mx)*0.5
size=mx-mn
ext=max(size.x,size.y,size.z)

inventory=[]
matches=[]
for o in scene.objects:
    rec={
        "name":o.name,
        "type":o.type,
        "materials":[m.name for m in getattr(o.data,"materials",[]) if m] if getattr(o,"data",None) else [],
    }
    if o.type=="MESH":
        rec["vertices"]=len(o.data.vertices)
        rec["polygons"]=len(o.data.polygons)
    inventory.append(rec)
    n=o.name.lower()
    if any(k in n for k in KEYWORDS):
        matches.append(rec)

# Audit render: source geometry untouched, Workbench studio lighting.
scene.render.engine="BLENDER_WORKBENCH"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=1280
scene.render.resolution_y=800
scene.render.resolution_percentage=100

cam_data=bpy.data.cameras.new("SANCTUM_V2_CC0_AUDIT_CAM_DATA")
cam=bpy.data.objects.new("SANCTUM_V2_CC0_AUDIT_CAM",cam_data)
scene.collection.objects.link(cam)
scene.camera=cam
cam.data.lens=42

z=mn.z+max(size.z*0.12,1.6)
views=[
    ("01-overview-a.png",center+Vector((ext*0.85,-ext*0.85,ext*0.45)),center),
    ("02-overview-b.png",center+Vector((-ext*0.85,ext*0.85,ext*0.45)),center),
    ("03-interior-long-a.png",Vector((center.x,center.y-size.y*0.28,z)),Vector((center.x,center.y+size.y*0.25,z+size.z*0.06))),
    ("04-interior-long-b.png",Vector((center.x,center.y+size.y*0.28,z)),Vector((center.x,center.y-size.y*0.25,z+size.z*0.06))),
]
for name,pos,look in views:
    cam.location=pos
    point(cam,look)
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)

report={
    "source":"OpenGameArt Medieval Church Interior",
    "author":"AnyRPG",
    "license":"CC0",
    "source_url":"https://opengameart.org/content/medieval-church-interior",
    "mesh_object_count":len(mesh_objs),
    "bbox":{"min":list(mn),"max":list(mx),"size":list(size)},
    "keyword_matches":matches,
    "inventory":inventory,
    "renders":[v[0] for v in views],
}
(OUT/"cc0-church-interior-audit.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_V2_CC0_INTERIOR_AUDIT_OK")
print(json.dumps({"mesh_object_count":len(mesh_objs),"keyword_matches":matches},indent=2))
