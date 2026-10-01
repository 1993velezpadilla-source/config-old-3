import bpy
import json
import os
from pathlib import Path
from mathutils import Vector

OUT = Path(os.environ.get("SANCTUM_PROP_OUT", "sanctum-prop-probe"))
OUT.mkdir(parents=True, exist_ok=True)
PACK = os.environ.get("SANCTUM_PROP_PACK", "unknown")
LICENSE = os.environ.get("SANCTUM_PROP_LICENSE", "CC0")
SOURCE_URL = os.environ.get("SANCTUM_PROP_SOURCE_URL", "")
SOURCE_FILE_URL = os.environ.get("SANCTUM_PROP_SOURCE_FILE_URL", "")
SOURCE_SHA256 = os.environ.get("SANCTUM_PROP_SHA256", "")

def fail(msg):
    raise SystemExit(f"SANCTUM_PROP_PROBE_FAIL: {msg}")

def stats(obj):
    deps=bpy.context.evaluated_depsgraph_get()
    ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh()
    try:
        pts=[ev.matrix_world @ v.co for v in mesh.vertices]
        if not pts:
            return None
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

def ensure_camera(scene):
    data=bpy.data.cameras.get("SANCTUM_PROP_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_PROP_CAMERA_DATA")
    cam=bpy.data.objects.get("SANCTUM_PROP_CAMERA") or bpy.data.objects.new("SANCTUM_PROP_CAMERA",data)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    scene.camera=cam
    cam.data.lens=50
    cam.data.clip_start=0.03
    cam.data.clip_end=5000
    return cam

def point(cam,target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def render_item(scene,cam,obj,item,index):
    for o in scene.objects:
        if hasattr(o,"hide_render"):
            o.hide_render=(o != obj)
    obj.hide_render=False
    center=Vector(item["center"])
    size=Vector(item["size"])
    ext=max(size.x,size.y,size.z,0.3)
    cam.location=center+Vector((ext*1.20,-ext*1.20,ext*0.75))
    point(cam,center+Vector((0,0,size.z*0.08)))
    safe="".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in obj.name)[:80]
    name=f"{index:02d}-{safe}.png"
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)
    p=OUT/name
    if not p.is_file() or p.stat().st_size < 1500:
        fail(f"render failed for {obj.name}")
    return {"name":name,"object":obj.name,"bytes":p.stat().st_size}

scene=bpy.context.scene
mesh_objects=[o for o in scene.objects if o.type=="MESH"]
items=[s for o in mesh_objects if (s:=stats(o))]
if not items:
    fail("no mesh objects")

# Prefer meaningful non-trivial objects, but keep the inventory complete.
items.sort(key=lambda x:(x["polygons"],x["vertices"]), reverse=True)
selected_items=items[:min(16,len(items))]

scene.render.engine="BLENDER_WORKBENCH"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=640
scene.render.resolution_y=400
scene.render.resolution_percentage=100
cam=ensure_camera(scene)

renders=[]
for idx,item in enumerate(selected_items,1):
    obj=bpy.data.objects.get(item["name"])
    if obj:
        renders.append(render_item(scene,cam,obj,item,idx))

for o in scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=False

selected=[]
for item in selected_items:
    obj=bpy.data.objects.get(item["name"])
    if obj:
        selected.append(obj)
for o in bpy.context.selected_objects:
    o.select_set(False)
for o in selected:
    o.select_set(True)
if selected:
    bpy.context.view_layer.objects.active=selected[0]

glb=OUT/f"{PACK}-selected.glb"
bpy.ops.export_scene.gltf(filepath=str(glb),export_format="GLB",use_selection=True,export_apply=True)

report={
    "status":"PASS",
    "pack":PACK,
    "license":LICENSE,
    "source_url":SOURCE_URL,
    "source_file_url":SOURCE_FILE_URL,
    "source_sha256":SOURCE_SHA256,
    "blender_version":bpy.app.version_string,
    "mesh_object_count":len(items),
    "materials":sorted({m for x in items for m in x["materials"]}),
    "objects":items,
    "selected":selected_items,
    "renders":renders,
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size if glb.is_file() else 0,
}
(OUT/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_PROP_PROBE_PASS")
print(json.dumps({
    "pack":PACK,
    "mesh_object_count":len(items),
    "selected":[x["name"] for x in selected_items],
    "glb_bytes":report["glb_bytes"],
},indent=2))
