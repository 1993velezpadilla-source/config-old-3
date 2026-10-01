import bpy
import json
import os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_LANDMARK_OUT","sanctum-landmark-probe"))
OUT.mkdir(parents=True,exist_ok=True)
PACK=os.environ.get("SANCTUM_LANDMARK_PACK","unknown")
LICENSE=os.environ.get("SANCTUM_LANDMARK_LICENSE","CC0")
SHA=os.environ.get("SANCTUM_LANDMARK_SHA256","")
REQUESTED=[x.strip() for x in os.environ.get("SANCTUM_LANDMARK_OBJECTS","").split(",") if x.strip()]

def fail(msg):
    raise SystemExit(f"SANCTUM_LANDMARK_PROBE_FAIL: {msg}")

if LICENSE!="CC0":
    fail(f"unexpected license {LICENSE}")
if len(SHA)!=64:
    fail("missing source sha256")
if not REQUESTED:
    fail("no requested objects")

scene=bpy.context.scene
deps=bpy.context.evaluated_depsgraph_get()

def object_stats(obj):
    ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh()
    try:
        pts=[ev.matrix_world @ v.co for v in mesh.vertices]
        if not pts:
            fail(f"{obj.name} has no vertices")
        mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
        mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
        return {
            "name":obj.name,
            "vertices":len(mesh.vertices),
            "polygons":len(mesh.polygons),
            "min":list(mn),
            "max":list(mx),
            "center":list((mn+mx)*0.5),
            "size":list(mx-mn),
            "materials":[slot.material.name for slot in obj.material_slots if slot.material],
        }
    finally:
        ev.to_mesh_clear()

selected=[]
stats=[]
for name in REQUESTED:
    obj=bpy.data.objects.get(name)
    if obj is None or obj.type!="MESH":
        fail(f"requested mesh missing: {name}")
    selected.append(obj)
    stats.append(object_stats(obj))

data=bpy.data.cameras.new("SANCTUM_LANDMARK_CAMERA_DATA")
cam=bpy.data.objects.new("SANCTUM_LANDMARK_CAMERA",data)
scene.collection.objects.link(cam)
scene.camera=cam
cam.data.lens=52
cam.data.clip_start=0.03
cam.data.clip_end=10000

scene.render.engine="BLENDER_WORKBENCH"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=720
scene.render.resolution_y=450
scene.render.resolution_percentage=100

renders=[]
for idx,(obj,item) in enumerate(zip(selected,stats),1):
    for o in scene.objects:
        if hasattr(o,"hide_render"):
            o.hide_render=(o!=obj)
    obj.hide_render=False
    center=Vector(item["center"])
    size=Vector(item["size"])
    ext=max(size.x,size.y,size.z,0.25)
    cam.location=center+Vector((ext*1.15,-ext*1.25,ext*0.75))
    cam.rotation_euler=(center-cam.location).to_track_quat("-Z","Y").to_euler()
    safe="".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in obj.name)
    p=OUT/f"{idx:02d}-{safe}.png"
    scene.render.filepath=str(p)
    bpy.ops.render.render(write_still=True)
    if not p.is_file() or p.stat().st_size<2000:
        fail(f"render failed: {obj.name}")
    renders.append({"name":p.name,"object":obj.name,"bytes":p.stat().st_size})

for o in scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=False
for o in bpy.context.selected_objects:
    o.select_set(False)
for o in selected:
    o.select_set(True)
bpy.context.view_layer.objects.active=selected[0]

glb=OUT/f"{PACK}-landmarks.glb"
bpy.ops.export_scene.gltf(filepath=str(glb),export_format="GLB",use_selection=True,export_apply=True)
if not glb.is_file() or glb.stat().st_size<1000:
    fail("landmark glb export failed")

report={
    "status":"PASS",
    "pack":PACK,
    "license":LICENSE,
    "source_sha256":SHA,
    "objects":stats,
    "renders":renders,
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size,
    "blender_version":bpy.app.version_string,
}
(OUT/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_LANDMARK_PROBE_PASS")
print(json.dumps({
    "pack":PACK,
    "objects":[x["name"] for x in stats],
    "polygons":sum(x["polygons"] for x in stats),
    "glb_bytes":report["glb_bytes"],
},indent=2))
