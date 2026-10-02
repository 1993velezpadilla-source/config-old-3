import bpy
import json
import math
import os
import runpy
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_HERO_ALTAR_OUT","sanctum-hero-altar-probe"))
OUT.mkdir(parents=True,exist_ok=True)
RUINS_BLEND=Path(os.environ["SANCTUM_RUINS_BLEND"])

# Start from the latest proven three-floor + industrial undercroft stack.
state=runpy.run_path("tools/sanctum_v2/dress_sanctum_industrial_undercroft.py")
scene=state["scene"]
vertical_state=state["state"]
ic=state["ic"]
hy=state["hy"]
floor_z=state["floor_z"]
lower_z=state["lower_z"]
upper_z=state["upper_z"]
base_export=list(state["export_objects"])
mesh_stats=state["mesh_stats"]
ensure_camera=state["ensure_camera"]

half_l=vertical_state["half_l"]
xmin=vertical_state["xmin"]; xmax=vertical_state["xmax"]
ymin=vertical_state["ymin"]; ymax=vertical_state["ymax"]
STONE=vertical_state["STONE"]
add_box=vertical_state["add_box"]

def fail(msg):
    raise SystemExit("SANCTUM_HERO_ALTAR_FAIL: "+msg)

def append_object(source_name,new_name):
    with bpy.data.libraries.load(str(RUINS_BLEND),link=False) as (src,dst):
        if source_name not in src.objects:
            fail(f"missing ruins object {source_name}")
        dst.objects=[source_name]
    obj=dst.objects[0]
    obj.name=new_name
    scene.collection.objects.link(obj)
    return obj

def world_bounds(obj):
    pts=[obj.matrix_world@Vector(c) for c in obj.bound_box]
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def place_bottom_center(obj,target,scale=1.0,rotation_z=0.0,role="hero_altar"):
    obj.location=(0,0,0)
    obj.rotation_euler=(0,0,rotation_z)
    obj.scale=(scale,scale,scale)
    obj.hide_render=False
    obj.hide_viewport=False
    bpy.context.view_layer.update()
    mn,mx=world_bounds(obj)
    bottom_center=Vector(((mn.x+mx.x)*0.5,(mn.y+mx.y)*0.5,mn.z))
    obj.location += Vector(target)-bottom_center
    bpy.context.view_layer.update()
    obj["xziel_role"]=role
    obj["source_pack"]="OpenGameArt 3TD Fantasy Ruins"
    obj["source_license"]="CC0"
    return obj

apse_src=append_object("TempleRuinTwo300","SANCTUM_HERO_APSE_RUIN")
slab_src=append_object("Object.001","SANCTUM_HERO_ALTAR_SLAB")

# The apse sits at the far end of the nave, behind the active combat loop but
# clearly visible from spawn/pews. Keep the existing Gothic arch as a backdrop.
apse_y=ic.y+half_l*0.60
apse=place_bottom_center(
    apse_src,
    (ic.x,apse_y,floor_z),
    scale=0.42,
    rotation_z=0.0,
    role="hero_apse"
)

# A long authored stone slab becomes the altar table top.
altar_y=ic.y+half_l*0.48
slab=place_bottom_center(
    slab_src,
    (ic.x,altar_y,floor_z+1.02),
    scale=0.55,
    rotation_z=math.radians(90),
    role="hero_altar_slab"
)

# Two simple stone supports use the same authored stone material family; the
# focal visual surfaces remain the CC0 ruin meshes above.
support_a=add_box(
    "SANCTUM_HERO_ALTAR_SUPPORT_L",
    (ic.x-1.25,altar_y,floor_z+0.50),
    (0.62,0.78,1.0),
    STONE,"hero_altar_support",True
)
support_b=add_box(
    "SANCTUM_HERO_ALTAR_SUPPORT_R",
    (ic.x+1.25,altar_y,floor_z+0.50),
    (0.62,0.78,1.0),
    STONE,"hero_altar_support",True
)

hero=[apse,slab,support_a,support_b]

# Safety: hero altar stays in the apse end-zone and cannot consume the central
# training loop or leave the playable shell.
for obj in hero:
    mn,mx=world_bounds(obj)
    if mn.x < xmin-0.15 or mx.x > xmax+0.15:
        fail(f"{obj.name} crosses nave X envelope: {list(mn)} {list(mx)}")
    if mn.y < ic.y+hy*0.18:
        fail(f"{obj.name} intrudes primary nave loop: minY={mn.y:.3f}")
    if mx.y > ymax+1.5:
        fail(f"{obj.name} extends too far beyond apse shell: maxY={mx.y:.3f}")

# Proof-only lighting. Do not add these to export_objects.
def add_area(name,loc,energy,size_m,color,target):
    ld=bpy.data.lights.new(name+"_DATA","AREA")
    ld.energy=energy
    ld.shape="DISK"
    ld.size=size_m
    ld.color=color
    lo=bpy.data.objects.new(name,ld)
    scene.collection.objects.link(lo)
    lo.location=Vector(loc)
    lo.rotation_euler=(Vector(target)-lo.location).to_track_quat("-Z","Y").to_euler()

altar_target=Vector((ic.x,altar_y,floor_z+1.2))
add_area("SANCTUM_ALTAR_KEY",
         (ic.x-4.0,altar_y-3.0,floor_z+5.2),1150,4.5,(1.0,0.48,0.20),altar_target)
add_area("SANCTUM_ALTAR_RIM",
         (ic.x+3.5,apse_y+1.0,floor_z+5.8),750,3.5,(0.22,0.38,0.72),altar_target)

scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=960
scene.render.resolution_y=600
scene.render.resolution_percentage=100

if scene.world is None:
    scene.world=bpy.data.worlds.new("SANCTUM_HERO_ALTAR_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.004,0.005,0.009,1)
    bg.inputs["Strength"].default_value=0.18

cam=ensure_camera(scene)
eye=floor_z+1.84

def point(cam,target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def render(name,pos,look):
    cam.location=Vector(pos)
    point(cam,look)
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)
    p=OUT/name
    if not p.is_file() or p.stat().st_size<6000:
        fail(f"proof render failed {name}")
    return {"name":name,"bytes":p.stat().st_size}

renders=[
    render("01-hero-altar-from-nave.png",
           (ic.x,ic.y-hy*0.48,eye),
           (ic.x,altar_y,floor_z+1.35)),
    render("02-hero-altar-mid-nave.png",
           (ic.x-1.0,ic.y+hy*0.05,eye),
           (ic.x,altar_y,floor_z+1.55)),
    render("03-hero-altar-three-quarter.png",
           (ic.x-4.0,altar_y-4.0,eye+0.25),
           (ic.x,altar_y,floor_z+1.20)),
    render("04-hero-altar-side.png",
           (ic.x+4.0,altar_y-2.5,eye+0.15),
           (ic.x,apse_y,floor_z+1.25)),
]

export_objects=[*base_export,*hero]
seen=set()
export_objects=[o for o in export_objects if o and not (o.name in seen or seen.add(o.name))]

for obj in bpy.context.selected_objects:
    obj.select_set(False)
for obj in export_objects:
    if obj.type=="MESH":
        obj.hide_viewport=False
        obj.hide_render=False
        obj.select_set(True)
bpy.context.view_layer.objects.active=next(o for o in export_objects if o.type=="MESH")

glb=OUT/"sanctum-hero-altar.glb"
bpy.ops.export_scene.gltf(
    filepath=str(glb),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_extras=True,
)
if not glb.is_file() or glb.stat().st_size<1000000:
    fail("hero altar GLB export failed")

stats=mesh_stats([o for o in export_objects if o.type=="MESH"])
report={
    "status":"PASS",
    "stage":"hero-altar-v1",
    "source":"OpenGameArt 3TD Fantasy Ruins Pack",
    "license":"CC0",
    "source_sha256":os.environ.get("SANCTUM_RUINS_SHA256",""),
    "source_objects":["TempleRuinTwo300","Object.001"],
    "hero_objects":[o.name for o in hero],
    "apse_scale":0.42,
    "altar_slab_scale":0.55,
    "apse_y":apse_y,
    "altar_y":altar_y,
    "renders":renders,
    "stats":stats,
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size,
}
(OUT/"hero-altar-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_HERO_ALTAR_PASS")
print(json.dumps({
    "objects":report["hero_objects"],
    "vertices":stats["vertices"],
    "polygons":stats["polygons"],
    "glb_bytes":report["glb_bytes"],
},indent=2))
