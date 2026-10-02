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

def make_ref_material(name,base,roughness=0.55,metallic=0.0,noise_scale=0.0,noise_strength=0.0):
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes=True
    nt=mat.node_tree
    bsdf=nt.nodes.get("Principled BSDF") if nt else None
    if not bsdf:
        return mat
    bsdf.inputs["Base Color"].default_value=(*base,1.0)
    bsdf.inputs["Roughness"].default_value=roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value=metallic
    if noise_scale>0.0:
        noise=nt.nodes.new("ShaderNodeTexNoise")
        noise.name=name+"_NOISE"
        noise.inputs["Scale"].default_value=noise_scale
        noise.inputs["Detail"].default_value=5.5
        noise.inputs["Roughness"].default_value=0.72
        bump=nt.nodes.new("ShaderNodeBump")
        bump.name=name+"_BUMP"
        bump.inputs["Strength"].default_value=noise_strength
        bump.inputs["Distance"].default_value=0.12
        nt.links.new(noise.outputs["Fac"],bump.inputs["Height"])
        normal=bsdf.inputs.get("Normal")
        if normal:
            nt.links.new(bump.outputs["Normal"],normal)
    return mat

ALTAR_STONE=make_ref_material("SANCTUM_REF_ALTAR_STONE",(0.115,0.095,0.078),0.42,0.0,5.8,0.24)
ALTAR_WOOD=make_ref_material("SANCTUM_REF_ALTAR_WOOD",(0.055,0.024,0.014),0.38,0.0,4.2,0.16)
ALTAR_CLOTH=make_ref_material("SANCTUM_REF_ALTAR_CLOTH",(0.19,0.015,0.022),0.62,0.0,9.5,0.08)
ALTAR_GOLD=make_ref_material("SANCTUM_REF_ALTAR_GOLD",(0.54,0.27,0.055),0.28,0.72,0.0,0.0)
ALTAR_PAPER=make_ref_material("SANCTUM_REF_ALTAR_PAPER",(0.72,0.62,0.46),0.76,0.0,7.5,0.05)
ALTAR_CANDLE=make_ref_material("SANCTUM_REF_ALTAR_CANDLE",(0.88,0.66,0.34),0.64,0.0,10.0,0.05)
ALTAR_IRON=make_ref_material("SANCTUM_REF_ALTAR_IRON",(0.035,0.029,0.025),0.31,0.72,3.0,0.10)

def add_cylinder(name,location,radius,depth,mat,role="hero_altar_detail",collision=False,vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=location)
    obj=bpy.context.object
    obj.name=name
    if mat:
        obj.data.materials.append(mat)
    obj["xziel_role"]=role
    obj["xziel_collision"]=bool(collision)
    return obj

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

# Reference-driven altar assembly. The new photo reads as a three-step
# stone dais with a dark Gothic timber altar, burgundy frontal, gold cross,
# open book and dense candle clusters. Keep it compact in the apse so gameplay
# clearance and the proven multilevel navigation surfaces stay untouched.
hero=[]

step_specs=[
    ("LOW",4.90,2.75,0.18,-0.98,0.09),
    ("MID",4.30,2.28,0.18,-0.71,0.27),
    ("TOP",3.72,1.82,0.18,-0.47,0.45),
]
for label,w,d,h,yoff,zoff in step_specs:
    hero.append(add_box(
        f"SANCTUM_HERO_ALTAR_STEP_{label}",
        (ic.x,altar_y+yoff,floor_z+zoff),
        (w,d,h),
        ALTAR_STONE,"hero_altar_step",True
    ))

wood_base=add_box(
    "SANCTUM_HERO_ALTAR_WOOD_BASE",
    (ic.x,altar_y+0.05,floor_z+0.93),
    (3.42,1.28,0.92),
    ALTAR_WOOD,"hero_altar_wood",True
)
hero.append(wood_base)

# Deep carved-looking rails/posts give the silhouette weight from the entrance.
for sign in (-1.0,1.0):
    hero.append(add_box(
        f"SANCTUM_HERO_ALTAR_POST_{'L' if sign<0 else 'R'}",
        (ic.x+sign*1.48,altar_y-0.02,floor_z+1.02),
        (0.24,1.42,1.12),
        ALTAR_WOOD,"hero_altar_wood",True
    ))
    hero.append(add_box(
        f"SANCTUM_HERO_ALTAR_FINIAL_{'L' if sign<0 else 'R'}",
        (ic.x+sign*1.48,altar_y-0.28,floor_z+1.67),
        (0.18,0.24,0.34),
        ALTAR_WOOD,"hero_altar_detail",False
    ))

# Re-skin the authored slab as the heavy dark top from the reference.
if slab.data.materials:
    slab.data.materials.clear()
slab.data.materials.append(ALTAR_WOOD)
hero.append(slab)

cloth=add_box(
    "SANCTUM_HERO_ALTAR_BURGUNDY_FRONTAL",
    (ic.x,altar_y-0.655,floor_z+1.03),
    (1.42,0.035,0.92),
    ALTAR_CLOTH,"hero_altar_detail",False
)
hero.append(cloth)
hero.append(add_box(
    "SANCTUM_HERO_ALTAR_GOLD_CROSS_V",
    (ic.x,altar_y-0.678,floor_z+1.03),
    (0.105,0.025,0.58),
    ALTAR_GOLD,"hero_altar_detail",False
))
hero.append(add_box(
    "SANCTUM_HERO_ALTAR_GOLD_CROSS_H",
    (ic.x,altar_y-0.680,floor_z+1.10),
    (0.42,0.025,0.095),
    ALTAR_GOLD,"hero_altar_detail",False
))

# Open book: two leaves pitched slightly away from the spine.
book_z=floor_z+1.63
for sign in (-1.0,1.0):
    page=add_box(
        f"SANCTUM_HERO_ALTAR_BOOK_{'L' if sign<0 else 'R'}",
        (ic.x+sign*0.23,altar_y-0.06,book_z),
        (0.48,0.56,0.035),
        ALTAR_PAPER,"hero_altar_detail",False
    )
    page.rotation_euler.y=math.radians(sign*8.0)
    hero.append(page)

# Two dark iron candelabra groups plus warm wax candles.
candle_x=(-1.18,-0.76,0.76,1.18)
for idx,xoff in enumerate(candle_x,1):
    base=add_cylinder(
        f"SANCTUM_HERO_ALTAR_CANDLE_BASE_{idx}",
        (ic.x+xoff,altar_y-0.02,floor_z+1.62),
        0.105,0.14,ALTAR_IRON,"hero_altar_detail",False,24
    )
    stem=add_cylinder(
        f"SANCTUM_HERO_ALTAR_CANDLE_STEM_{idx}",
        (ic.x+xoff,altar_y-0.02,floor_z+1.91),
        0.055,0.50,ALTAR_IRON,"hero_altar_detail",False,20
    )
    wax=add_cylinder(
        f"SANCTUM_HERO_ALTAR_CANDLE_WAX_{idx}",
        (ic.x+xoff,altar_y-0.02,floor_z+2.23),
        0.075,0.34,ALTAR_CANDLE,"hero_altar_detail",False,20
    )
    hero.extend([base,stem,wax])

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

altar_target=Vector((ic.x,altar_y,floor_z+1.42))
# Warm candle/altar key against a restrained cool stained-glass rim.
add_area("SANCTUM_ALTAR_KEY",
         (ic.x-3.8,altar_y-2.4,floor_z+4.6),920,4.2,(1.0,0.38,0.12),altar_target)
add_area("SANCTUM_ALTAR_RIM",
         (ic.x+3.2,apse_y+0.8,floor_z+5.9),540,3.2,(0.16,0.30,0.58),altar_target)

# Local candle glows are proof-only; geometry remains in the GLB.
for idx,xoff in enumerate(candle_x,1):
    ld=bpy.data.lights.new(f"SANCTUM_HERO_CANDLE_GLOW_{idx}_DATA","POINT")
    ld.energy=52.0
    ld.color=(1.0,0.29,0.06)
    ld.shadow_soft_size=0.42
    lo=bpy.data.objects.new(f"SANCTUM_HERO_CANDLE_GLOW_{idx}",ld)
    scene.collection.objects.link(lo)
    lo.location=Vector((ic.x+xoff,altar_y-0.02,floor_z+2.42))

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
    bg.inputs["Strength"].default_value=0.125

cam=ensure_camera(scene)
# Raised player-view requested for the entrance match.
eye=floor_z+1.88
cam.data.lens=31.0

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
           (ic.x,ic.y-hy*0.70,eye),
           (ic.x,altar_y,floor_z+1.72)),
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
    "stage":"hero-altar-reference-v2",
    "source":"OpenGameArt 3TD Fantasy Ruins Pack",
    "license":"CC0",
    "source_sha256":os.environ.get("SANCTUM_RUINS_SHA256",""),
    "source_objects":["TempleRuinTwo300","Object.001"],
    "hero_objects":[o.name for o in hero],\n    "hero_camera":{"eye_height_m":1.88,"lens_mm":31.0,"view":"raised_main_door_reference_match"},\n    "reference_materials":["dark_worn_stone","dark_gothic_wood","burgundy_cloth","aged_gold","warm_wax","black_iron"],
    "apse_scale":0.42,
    "altar_slab_scale":0.55,\n    "altar_step_count":3,\n    "altar_candle_count":4,
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
