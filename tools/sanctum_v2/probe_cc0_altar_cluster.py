import bpy, json, os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_ALTAR_CLUSTER_OUT","sanctum-altar-cluster"))
OUT.mkdir(parents=True,exist_ok=True)
SHA=os.environ.get("SANCTUM_ALTAR_SHA256","")

KEEP=[
    "altar",
    "Cross",
    "candle","candle.001","candle.002","candle.003",
    "bible.000","bible.002",
    "Cylinder.015",
]

def fail(msg):
    raise SystemExit("SANCTUM_ALTAR_CLUSTER_FAIL: "+msg)

missing=[n for n in KEEP if bpy.data.objects.get(n) is None]
if missing:
    fail("missing "+repr(missing))
if len(SHA)!=64:
    fail("missing source sha")

scene=bpy.context.scene
keep_objs=[bpy.data.objects[n] for n in KEEP]
for o in scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=o not in keep_objs

pts=[]
for obj in keep_objs:
    pts.extend(obj.matrix_world @ Vector(c) for c in obj.bound_box)
mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
center=(mn+mx)*0.5
size=mx-mn

scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=960
scene.render.resolution_y=600
scene.render.resolution_percentage=100
if scene.world is None:
    scene.world=bpy.data.worlds.new("ALTAR_CLUSTER_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.006,0.006,0.008,1)
    bg.inputs["Strength"].default_value=0.16

cam_data=bpy.data.cameras.new("ALTAR_CLUSTER_CAMERA_DATA")
cam=bpy.data.objects.new("ALTAR_CLUSTER_CAMERA",cam_data)
scene.collection.objects.link(cam)
scene.camera=cam
cam.data.lens=54

def add_area(name,loc,energy,size_m,color):
    ld=bpy.data.lights.new(name+"_DATA","AREA")
    ld.energy=energy
    ld.shape="DISK"
    ld.size=size_m
    ld.color=color
    lo=bpy.data.objects.new(name,ld)
    scene.collection.objects.link(lo)
    lo.location=Vector(loc)
    lo.rotation_euler=(center-lo.location).to_track_quat("-Z","Y").to_euler()
    return lo

add_area("ALTAR_KEY",center+Vector((0,-size.y*0.85,size.z*0.35)),1300,max(4.0,size.x*0.45),(1.0,0.58,0.28))
add_area("ALTAR_FILL",center+Vector((size.x*0.45,-size.y*0.25,size.z*0.60)),700,max(3.0,size.x*0.30),(0.30,0.42,0.72))

def point(target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def render(name,loc,target):
    cam.location=Vector(loc)
    point(target)
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)
    p=OUT/name
    if not p.is_file() or p.stat().st_size<5000:
        fail("render failed "+name)
    return {"name":name,"bytes":p.stat().st_size}

front=center+Vector((0,-max(10.0,size.y*1.35),size.z*0.05))
left=center+Vector((-max(8.0,size.x*0.65),-max(8.0,size.y*0.90),size.z*0.10))
low=center+Vector((0,-max(7.0,size.y*0.90),-size.z*0.18))

renders=[
    render("01-altar-front.png",front,center+Vector((0,0,size.z*0.05))),
    render("02-altar-left.png",left,center+Vector((0,0,size.z*0.02))),
    render("03-altar-low.png",low,center+Vector((0,0,size.z*0.12))),
]

report={
    "status":"PASS",
    "source":"OpenGameArt Church-0",
    "license":"CC0",
    "source_sha256":SHA,
    "objects":KEEP,
    "bounds":{"min":list(mn),"max":list(mx),"center":list(center),"size":list(size)},
    "renders":renders,
}
(OUT/"altar-cluster-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_ALTAR_CLUSTER_PASS")
print(json.dumps({"objects":KEEP,"size":list(size),"renders":len(renders)},indent=2))
