import bpy, json, os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_INDUSTRIAL_PROBE_OUT","sanctum-industrial-probe"))
OUT.mkdir(parents=True,exist_ok=True)
SOURCE_SHA=os.environ.get("SANCTUM_INDUSTRIAL_SHA256","")

NAMES=[
    "tank_control_panel_mat",
    "tank_2_mat",
    "vent_mat",
    "pipe_05",
    "pipe_07",
    "wall_thing_mat",
]

def fail(msg):
    raise SystemExit("SANCTUM_INDUSTRIAL_PROBE_FAIL: "+msg)

def stats(obj):
    deps=bpy.context.evaluated_depsgraph_get()
    ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh()
    try:
        pts=[ev.matrix_world@v.co for v in mesh.vertices]
        mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
        mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
        return {
            "name":obj.name,
            "vertices":len(mesh.vertices),
            "polygons":len(mesh.polygons),
            "min":list(mn),"max":list(mx),
            "center":list((mn+mx)*0.5),
            "size":list(mx-mn),
            "materials":[s.material.name for s in obj.material_slots if s.material],
        }
    finally:
        ev.to_mesh_clear()

missing=[n for n in NAMES if bpy.data.objects.get(n) is None]
if missing:
    fail("missing objects "+repr(missing))
if len(SOURCE_SHA)!=64:
    fail("missing source SHA256")

scene=bpy.context.scene
scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=720
scene.render.resolution_y=480
scene.render.resolution_percentage=100
if scene.world is None:
    scene.world=bpy.data.worlds.new("SANCTUM_INDUSTRIAL_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.025,0.03,0.04,1)
    bg.inputs["Strength"].default_value=0.35

cam_data=bpy.data.cameras.new("SANCTUM_INDUSTRIAL_CAM_DATA")
cam=bpy.data.objects.new("SANCTUM_INDUSTRIAL_CAM",cam_data)
scene.collection.objects.link(cam)
scene.camera=cam
cam.data.lens=52

ld=bpy.data.lights.new("SANCTUM_INDUSTRIAL_KEY_DATA","AREA")
ld.energy=1100
ld.shape="DISK"
ld.size=5.0
light=bpy.data.objects.new("SANCTUM_INDUSTRIAL_KEY",ld)
scene.collection.objects.link(light)

items=[]
renders=[]
for idx,name in enumerate(NAMES,1):
    obj=bpy.data.objects[name]
    item=stats(obj)
    items.append(item)

    for o in scene.objects:
        if hasattr(o,"hide_render"):
            o.hide_render=(o not in {obj,light,cam})
    obj.hide_render=False

    center=Vector(item["center"])
    size=Vector(item["size"])
    ext=max(size.x,size.y,size.z,0.5)
    cam.location=center+Vector((ext*1.25,-ext*1.45,ext*0.80))
    cam.rotation_euler=(center-cam.location).to_track_quat("-Z","Y").to_euler()
    light.location=center+Vector((ext*0.6,-ext*0.4,ext*1.5))
    light.rotation_euler=(center-light.location).to_track_quat("-Z","Y").to_euler()

    safe=name.replace(" ","_")
    filename=f"{idx:02d}-{safe}.png"
    scene.render.filepath=str(OUT/filename)
    bpy.ops.render.render(write_still=True)
    p=OUT/filename
    if not p.is_file() or p.stat().st_size<3000:
        fail("render failed "+name)
    renders.append({"name":filename,"object":name,"bytes":p.stat().st_size})

report={
    "status":"PASS",
    "source":"OpenGameArt PBR Industrial Asset Pack by a52",
    "license":"CC0",
    "source_sha256":SOURCE_SHA,
    "selected":items,
    "renders":renders,
}
(OUT/"industrial-probe-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_INDUSTRIAL_SELECTED_PROBE_PASS")
print(json.dumps({"objects":[x["name"] for x in items],"renders":len(renders)},indent=2))
