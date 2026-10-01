import bpy
import json
import os
from pathlib import Path
from mathutils import Vector

OUT = Path(os.environ.get("SANCTUM_RUINS_OUT", "sanctum-ruins-probe"))
OUT.mkdir(parents=True, exist_ok=True)

KEYWORDS = (
    "arch", "pillar", "column", "wall", "foundation", "rail",
    "ruin", "window", "door", "temple", "cathedral", "church", "stone"
)

def fail(msg):
    raise SystemExit(f"SANCTUM_RUINS_FAIL: {msg}")

def evaluated_stats(obj):
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

def score(item):
    n=item["name"].lower()
    kw=sum(1 for k in KEYWORDS if k in n)
    return (kw, item["polygons"])

def ensure_camera(scene):
    data=bpy.data.cameras.get("SANCTUM_RUINS_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_RUINS_CAMERA_DATA")
    cam=bpy.data.objects.get("SANCTUM_RUINS_CAMERA") or bpy.data.objects.new("SANCTUM_RUINS_CAMERA",data)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    scene.camera=cam
    cam.data.lens=45
    cam.data.clip_start=0.03
    cam.data.clip_end=5000
    return cam

def point(cam,target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def render_object(scene,cam,obj,item,index):
    for o in scene.objects:
        if hasattr(o,"hide_render"):
            o.hide_render = o != obj
    obj.hide_render=False

    center=Vector(item["center"])
    size=Vector(item["size"])
    ext=max(size.x,size.y,size.z,0.5)
    cam.location=center+Vector((ext*1.15,-ext*1.15,ext*0.75))
    point(cam,center+Vector((0,0,size.z*0.08)))
    safe="".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in obj.name)[:80]
    name=f"{index:02d}-{safe}.png"
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)
    p=OUT/name
    if not p.is_file() or p.stat().st_size<2000:
        fail(f"render failed for {obj.name}")
    return {"name":name,"object":obj.name,"bytes":p.stat().st_size}

scene=bpy.context.scene
meshes=[o for o in scene.objects if o.type=="MESH"]
if not meshes:
    fail("no mesh objects")

items=[]
for obj in meshes:
    s=evaluated_stats(obj)
    if s:
        items.append(s)

items.sort(key=score, reverse=True)
selected_items=items[:12]
selected_names={x["name"] for x in selected_items}
selected=[bpy.data.objects[n] for n in selected_names if n in bpy.data.objects]

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
        renders.append(render_object(scene,cam,obj,item,idx))

for o in scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=False

for o in bpy.context.selected_objects:
    o.select_set(False)
for o in selected:
    o.select_set(True)
if selected:
    bpy.context.view_layer.objects.active=selected[0]

glb=OUT/"cc0-gothic-ruins-selected-kit.glb"
bpy.ops.export_scene.gltf(
    filepath=str(glb),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
)

report={
    "status":"PASS",
    "source":"3TD Fantasy Ruins Pack for Blender",
    "license":"CC0",
    "source_url":"https://opengameart.org/content/3td-fantasy-ruins-pack-for-blender",
    "source_file_url":"https://opengameart.org/sites/default/files/fantasy_ruins_pack_for_blender.blend",
    "source_sha256":os.environ.get("SANCTUM_RUINS_SHA256",""),
    "blender_version":bpy.app.version_string,
    "mesh_object_count":len(items),
    "materials":sorted({m for x in items for m in x["materials"]}),
    "objects":items,
    "selected":selected_items,
    "renders":renders,
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size if glb.is_file() else 0,
}
(OUT/"ruins-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_RUINS_PROBE_PASS")
print(json.dumps({
    "mesh_object_count":len(items),
    "selected":[x["name"] for x in selected_items],
    "selected_polygons":[x["polygons"] for x in selected_items],
    "glb_bytes":report["glb_bytes"],
},indent=2))

# Workflow trigger marker: Gothic ruins probe v1
