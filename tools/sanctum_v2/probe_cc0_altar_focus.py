import bpy, json, os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_ALTAR_FOCUS_OUT","sanctum-altar-focus"))
OUT.mkdir(parents=True,exist_ok=True)
SHA=os.environ.get("SANCTUM_ALTAR_SHA256","")

SELECTED=[
    "altar",
    "Cross",
    "bible.000",
    "bible.002",
    "candle",
    "candle.001",
    "candle.002",
    "candle.003",
]

def fail(msg):
    raise SystemExit("SANCTUM_ALTAR_FOCUS_FAIL: "+msg)

missing=[n for n in SELECTED if bpy.data.objects.get(n) is None]
if missing:
    fail("missing "+repr(missing))
if len(SHA)!=64:
    fail("missing source SHA256")

scene=bpy.context.scene
objs=[bpy.data.objects[n] for n in SELECTED]

def bounds(objects):
    pts=[]
    for o in objects:
        pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

mn,mx=bounds(objs)
center=(mn+mx)*0.5
size=mx-mn

# Hide everything except the authored altar cluster.
for o in scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=o not in objs

scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=840
scene.render.resolution_y=620
scene.render.resolution_percentage=100

if scene.world is None:
    scene.world=bpy.data.worlds.new("SANCTUM_ALTAR_FOCUS_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.018,0.015,0.012,1.0)
    bg.inputs["Strength"].default_value=0.35

cam_data=bpy.data.cameras.new("SANCTUM_ALTAR_FOCUS_CAM_DATA")
cam=bpy.data.objects.new("SANCTUM_ALTAR_FOCUS_CAM",cam_data)
scene.collection.objects.link(cam)
scene.camera=cam
cam.data.lens=55
cam.data.clip_start=0.03
cam.data.clip_end=2000

def point(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

# Warm key and cool rim for material readability only.
for name,loc,energy,color,size_light in [
    ("ALTAR_KEY",center+Vector((-size.x*0.55,-size.y*0.75,size.z*0.55)),1300,(1.0,0.58,0.26),5.0),
    ("ALTAR_RIM",center+Vector((size.x*0.55,size.y*0.20,size.z*0.85)),750,(0.25,0.38,0.65),4.0),
]:
    ld=bpy.data.lights.new(name+"_DATA","AREA")
    ld.energy=energy
    ld.shape="DISK"
    ld.size=size_light
    ld.color=color
    lo=bpy.data.objects.new(name,ld)
    scene.collection.objects.link(lo)
    lo.location=loc
    point(lo,center)

def render(name,pos,look):
    cam.location=Vector(pos)
    point(cam,look)
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)
    p=OUT/name
    if not p.is_file() or p.stat().st_size<5000:
        fail("render failed "+name)
    return {"name":name,"bytes":p.stat().st_size}

dist=max(size.x,size.y,size.z)*1.10
renders=[
    render("01-altar-front.png",
           center+Vector((0,-dist*1.15,size.z*0.05)),
           center+Vector((0,0,size.z*0.05))),
    render("02-altar-three-quarter.png",
           center+Vector((dist*0.78,-dist*0.90,size.z*0.12)),
           center+Vector((0,0,size.z*0.03))),
    render("03-altar-cross-low.png",
           center+Vector((-dist*0.58,-dist*0.82,-size.z*0.12)),
           center+Vector((0,0,size.z*0.18))),
]

# Export only the authored cluster so it can be tested directly in Sanctum.
for o in bpy.context.selected_objects:
    o.select_set(False)
for o in objs:
    o.hide_viewport=False
    o.hide_render=False
    o.select_set(True)
bpy.context.view_layer.objects.active=objs[0]

glb=OUT/"altar-cluster.glb"
bpy.ops.export_scene.gltf(
    filepath=str(glb),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
)
if not glb.is_file() or glb.stat().st_size<1000:
    fail("GLB export failed")

report={
    "status":"PASS",
    "source":"OpenGameArt Church",
    "license":"CC0",
    "source_sha256":SHA,
    "objects":SELECTED,
    "bounds":{"min":list(mn),"max":list(mx),"center":list(center),"size":list(size)},
    "renders":renders,
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size,
}
(OUT/"altar-focus-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_ALTAR_FOCUS_PASS")
print(json.dumps({
    "objects":SELECTED,
    "size":list(size),
    "glb_bytes":report["glb_bytes"],
},indent=2))
