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

# Same reference-driven PBR library used by the floor and new pews.
refmat=runpy.run_path("tools/sanctum_v2/reference_materials.py")
REF=refmat["material_set"]()
ref_group_fit=runpy.run_path("tools/sanctum_v2/reference_group_fit.py")
REF_SILHOUETTES=json.loads(Path("docs/sanctum-reference-silhouettes.v1.json").read_text(encoding="utf-8"))
fit_object_group_to_silhouettes=ref_group_fit["fit_object_group_to_silhouettes"]
count_group_violations=ref_group_fit["count_group_violations"]
ALTAR_STONE=REF["stone"]
ALTAR_WOOD=REF["wood_h"]
ALTAR_WOOD_V=REF["wood_v"]
ALTAR_CLOTH=REF["cloth"]
ALTAR_GOLD=REF["gold"]
ALTAR_CANDLE=REF["wax"]
ALTAR_IRON=REF["iron"]

# Page material remains deliberately matte/aged so the book does not glow.
ALTAR_PAPER=bpy.data.materials.get("SANCTUM_REF_ALTAR_PAPER") or bpy.data.materials.new("SANCTUM_REF_ALTAR_PAPER")
ALTAR_PAPER.use_nodes=True
paper_bsdf=ALTAR_PAPER.node_tree.nodes.get("Principled BSDF")
if paper_bsdf:
    paper_bsdf.inputs["Base Color"].default_value=(0.68,0.57,0.42,1.0)
    paper_bsdf.inputs["Roughness"].default_value=0.78

def add_cylinder(name,location,radius,depth,mat,role="hero_altar_detail",collision=False,vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=location)
    obj=bpy.context.object
    obj.name=name
    if mat:
        obj.data.materials.append(mat)
    obj["xziel_role"]=role
    obj["xziel_collision"]=bool(collision)
    return obj

def add_segment(name,a,b,radius,mat,role="hero_altar_detail"):
    a=Vector(a); b=Vector(b)
    d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=14,radius=radius,depth=d.length,location=(a+b)*0.5)
    obj=bpy.context.object
    obj.name=name
    obj.rotation_euler=d.to_track_quat("Z","Y").to_euler()
    obj.data.materials.append(mat)
    obj["xziel_role"]=role
    obj["xziel_collision"]=False
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

def fit_bottom_center_to_box(obj,target,target_size,rotation_z=0.0,role="hero_backdrop"):
    """Fit authored source geometry into a target world-space box without decimation.

    The ruins pack objects carry very large authored dimensions.  Earlier code
    applied a blind 0.42 scalar, which left the apse ~28 m wide and outside the
    Sanctum nave envelope.  This preserves every source vertex/material while
    fitting only its world transform to the actual apse bay.
    """
    obj.location=(0,0,0)
    obj.rotation_euler=(0,0,rotation_z)
    obj.scale=(1,1,1)
    obj.hide_render=False
    obj.hide_viewport=False
    bpy.context.view_layer.update()
    mn,mx=world_bounds(obj)
    size=mx-mn
    tx,ty,tz=[float(v) for v in target_size]
    sx=tx/max(size.x,1e-6)
    sy=ty/max(size.y,1e-6)
    sz=tz/max(size.z,1e-6)
    obj.scale=(sx,sy,sz)
    bpy.context.view_layer.update()
    mn,mx=world_bounds(obj)
    bottom_center=Vector(((mn.x+mx.x)*0.5,(mn.y+mx.y)*0.5,mn.z))
    obj.location += Vector(target)-bottom_center
    bpy.context.view_layer.update()
    obj["xziel_role"]=role
    obj["source_pack"]="OpenGameArt 3TD Fantasy Ruins"
    obj["source_license"]="CC0"
    obj["reference_fit"]="apse_target_box"
    obj["reference_target_size_m"]=[tx,ty,tz]
    return obj

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
apse_target_size=(
    (xmax-xmin)*0.86,
    max(2.4,half_l*0.23),
    8.4,
)
apse=fit_bottom_center_to_box(
    apse_src,
    (ic.x,apse_y,floor_z),
    apse_target_size,
    rotation_z=0.0,
    role="hero_apse"
)
apse_bounds=[list(v) for v in world_bounds(apse)]

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
# Keep the authored CC0 apse in both export and safety validation.
hero=[apse]

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
# Gold cloth edging from the supplied closeup: narrow aged trim, not bright UI gold.
cloth_y=altar_y-0.686
for idx,(cx,cz,sx,sz) in enumerate([
    (ic.x, floor_z+1.48, 1.48,0.035),
    (ic.x, floor_z+0.58, 1.48,0.035),
    (ic.x-0.72,floor_z+1.03,0.035,0.92),
    (ic.x+0.72,floor_z+1.03,0.035,0.92),
]):
    hero.append(add_box(
        f"SANCTUM_HERO_ALTAR_CLOTH_TRIM_{idx}",
        (cx,cloth_y,cz),(sx,0.018,sz),ALTAR_GOLD,"hero_altar_detail",False
    ))

# Three pointed Gothic relief panels across the timber front. The center is
# partially covered by the frontal; side panels remain clearly readable.
for panel_i,xoff in enumerate((-1.02,0.0,1.02),1):
    x=ic.x+xoff
    y=altar_y-0.665
    z0=floor_z+0.65
    z1=floor_z+1.15
    apex=floor_z+1.36
    for seg_i,(a,b) in enumerate([
        ((x-0.27,y,z0),(x-0.27,y,z1)),
        ((x+0.27,y,z0),(x+0.27,y,z1)),
        ((x-0.27,y,z1),(x,y,apex)),
        ((x+0.27,y,z1),(x,y,apex)),
    ]):
        hero.append(add_segment(
            f"SANCTUM_HERO_ALTAR_GOTHIC_{panel_i}_{seg_i}",a,b,0.024,ALTAR_WOOD_V
        ))

# Raised corner pilasters and stepped top/base rails add the all-angle weight
# visible in the reference model rather than reading as one plain cube.
for sign in (-1.0,1.0):
    x=ic.x+sign*1.60
    hero.append(add_box(
        f"SANCTUM_HERO_ALTAR_FRONT_PILASTER_{'L' if sign<0 else 'R'}",
        (x,altar_y-0.62,floor_z+1.02),(0.20,0.16,1.16),ALTAR_WOOD_V,"hero_altar_detail",False
    ))
    hero.append(add_box(
        f"SANCTUM_HERO_ALTAR_PILASTER_CAP_{'L' if sign<0 else 'R'}",
        (x,altar_y-0.62,floor_z+1.62),(0.32,0.24,0.10),ALTAR_WOOD,"hero_altar_detail",False
    ))
hero.append(add_box(
    "SANCTUM_HERO_ALTAR_FRONT_TOP_TRIM",
    (ic.x,altar_y-0.63,floor_z+1.56),(3.52,0.16,0.11),ALTAR_WOOD,"hero_altar_detail",False
))
hero.append(add_box(
    "SANCTUM_HERO_ALTAR_FRONT_BASE_TRIM",
    (ic.x,altar_y-0.63,floor_z+0.51),(3.52,0.18,0.13),ALTAR_WOOD,"hero_altar_detail",False
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
candle_x=(-1.28,-0.98,-0.68,-0.38,0.38,0.68,0.98,1.28)
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

# Central altar cross, built as aged metal geometry so it reads from the nave.
cross_z=floor_z+2.28
hero.append(add_cylinder(
    "SANCTUM_HERO_ALTAR_TOP_CROSS_STEM",
    (ic.x,altar_y+0.03,cross_z),0.035,1.15,ALTAR_GOLD,"hero_altar_detail",False,18
))
hero.append(add_segment(
    "SANCTUM_HERO_ALTAR_TOP_CROSS_BAR",
    (ic.x-0.34,altar_y+0.03,cross_z+0.18),
    (ic.x+0.34,altar_y+0.03,cross_z+0.18),
    0.035,ALTAR_GOLD
))
hero.append(add_cylinder(
    "SANCTUM_HERO_ALTAR_TOP_CROSS_BASE",
    (ic.x,altar_y+0.03,floor_z+1.69),0.16,0.10,ALTAR_IRON,"hero_altar_detail",False,24
))

# Lock the actual altar carcass to the traced front + side silhouettes.
# Decorative candles/book/top cross are intentionally excluded so their vertical
# detail remains faithful to the reference sheet rather than being squashed into
# the body outline.
altar_profile=REF_SILHOUETTES["altar"]
body_exclude=("CANDLE","BOOK","TOP_CROSS","APSE_RUIN")
altar_body_fit=[o for o in hero if not any(token in o.name for token in body_exclude)]
altar_fit=fit_object_group_to_silhouettes(
    altar_body_fit,
    altar_profile["front_body"]["points"],
    altar_profile["side_left"]["points"],
    altar_profile["body_dimensions_m"],
    anchor_xy=(ic.x,altar_y),
    ground_z=floor_z,
)
altar_fit_audit=count_group_violations(
    altar_body_fit,
    altar_profile["front_body"]["points"],
    altar_profile["side_left"]["points"],
    altar_profile["body_dimensions_m"],
    anchor_xy=(ic.x,altar_y),
    ground_z=floor_z,
)
if altar_fit_audit["violations"]!=0:
    fail(f"altar body escaped reference cage: {altar_fit_audit}")

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
    "stage":"hero-altar-reference-v3",
    "source":"OpenGameArt 3TD Fantasy Ruins Pack",
    "license":"CC0",
    "source_sha256":os.environ.get("SANCTUM_RUINS_SHA256",""),
    "source_objects":["TempleRuinTwo300","Object.001"],
    "hero_objects":[o.name for o in hero],
    "hero_camera":{"eye_height_m":1.88,"lens_mm":31.0,"view":"raised_main_door_reference_match"},
    "reference_material_profile":"docs/sanctum-reference-materials.v2.json",
    "reference_silhouette_profile":"docs/sanctum-reference-silhouettes.v1.json",
    "altar_reference_fit":altar_fit,
    "altar_reference_fit_audit":altar_fit_audit,
    "reference_materials":["wet_dark_stone","aged_masonry","dark_gothic_wood","burgundy_cloth","aged_gold","warm_wax","black_iron"],
    "apse_fit":"target_box_no_decimation",
    "apse_target_size_m":list(apse_target_size),
    "apse_bounds":apse_bounds,
    "altar_slab_scale":0.55,
    "altar_step_count":3,
    "altar_candle_count":8,
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
