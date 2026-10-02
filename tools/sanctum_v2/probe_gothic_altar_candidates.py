import bpy, json, os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_GOTHIC_ALTAR_PROBE_OUT","sanctum-gothic-altar-candidates"))
OUT.mkdir(parents=True,exist_ok=True)
SHA=os.environ.get("SANCTUM_RUINS_SHA256","")
NAMES=["TempleRuinTwo300","SpeakingStonesOne300","Object","Object.001","Object.004","Object.002"]

def fail(msg): raise SystemExit("SANCTUM_GOTHIC_ALTAR_CANDIDATE_FAIL: "+msg)

missing=[n for n in NAMES if bpy.data.objects.get(n) is None]
if missing: fail("missing "+repr(missing))
if len(SHA)!=64: fail("missing source sha")

scene=bpy.context.scene
scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=720
scene.render.resolution_y=480
scene.render.resolution_percentage=100
if scene.world is None: scene.world=bpy.data.worlds.new("GOTHIC_ALTAR_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.025,0.025,0.03,1)
    bg.inputs["Strength"].default_value=0.35

cam_data=bpy.data.cameras.new("GOTHIC_ALTAR_CAM_DATA")
cam=bpy.data.objects.new("GOTHIC_ALTAR_CAM",cam_data)
scene.collection.objects.link(cam)
scene.camera=cam
cam.data.lens=50

ld=bpy.data.lights.new("GOTHIC_ALTAR_KEY_DATA","AREA")
ld.energy=1100
ld.shape="DISK"
ld.size=6
light=bpy.data.objects.new("GOTHIC_ALTAR_KEY",ld)
scene.collection.objects.link(light)

def bounds(obj):
    pts=[obj.matrix_world@Vector(c) for c in obj.bound_box]
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def point(o,target): o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler()

items=[]; renders=[]
for idx,name in enumerate(NAMES,1):
    obj=bpy.data.objects[name]
    mn,mx=bounds(obj); center=(mn+mx)*0.5; size=mx-mn
    for o in scene.objects:
        if hasattr(o,"hide_render"):
            o.hide_render=o not in {obj,cam,light}
    obj.hide_render=False
    ext=max(size.x,size.y,size.z,0.5)
    cam.location=center+Vector((ext*1.0,-ext*1.45,ext*0.72))
    point(cam,center+Vector((0,0,size.z*0.08)))
    light.location=center+Vector((-ext*0.5,-ext*0.5,ext*1.4))
    point(light,center)
    fn=f"{idx:02d}-{name.replace('.','_')}.png"
    scene.render.filepath=str(OUT/fn)
    bpy.ops.render.render(write_still=True)
    p=OUT/fn
    if not p.is_file() or p.stat().st_size<4000: fail("render failed "+name)
    item={
        "name":name,
        "vertices":len(obj.data.vertices),
        "polygons":len(obj.data.polygons),
        "size":list(size),
        "materials":[s.material.name for s in obj.material_slots if s.material],
    }
    items.append(item)
    renders.append({"name":fn,"object":name,"bytes":p.stat().st_size})

report={"status":"PASS","license":"CC0","source_sha256":SHA,"candidates":items,"renders":renders}
(OUT/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_GOTHIC_ALTAR_CANDIDATES_PASS")
print(json.dumps({"objects":NAMES},indent=2))
