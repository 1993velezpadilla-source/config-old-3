import bpy
import json
import math
import os
import runpy
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_ENRICH_OUT","sanctum-enriched-probe"))
OUT.mkdir(parents=True,exist_ok=True)
BENCH_BLEND=Path(os.environ["SANCTUM_BENCH_BLEND"])
CANDLE_BLEND=Path(os.environ["SANCTUM_CANDLE_BLEND"])

# Build the already-gated cathedral + CC0 interior + Gothic dressing first.
state=runpy.run_path("tools/sanctum_v2/dress_sanctum_with_cc0_gothic.py")
scene=bpy.context.scene
walkability=state["walkability_with_dressing"]
mesh_stats=state["mesh_stats"]
# The base stage owns SANCTUM_DRESS_OUT; redirect only the reused render helper\n# so enriched evidence lands in the enriched artifact directory.\nrender_view.__globals__["DRESS_OUT"]=OUT\nensure_camera=state["ensure_camera"]
export_dressed=state["export_dressed"]
inner_after=state["inner_after"]
base_walk=state["walk"]
base_export=list(state["export_objects"])
ic=Vector(inner_after["center"])
isz=Vector(inner_after["size"])
floor_z=Vector(inner_after["min"]).z + 0.12
half_w=isz.x*0.5
half_l=isz.y*0.5

def fail(msg):
    raise SystemExit(f"SANCTUM_ENRICH_FAIL: {msg}")

def append_object(blend_path,name):
    with bpy.data.libraries.load(str(blend_path),link=False) as (src,dst):
        if name not in src.objects:
            fail(f"{name} missing from {blend_path}")
        dst.objects=[name]
    obj=dst.objects[0]
    scene.collection.objects.link(obj)
    return obj

def bottom_z(obj):
    return min((obj.matrix_world @ Vector(c)).z for c in obj.bound_box)

def place_copy(template,name,location,rotation_z=0.0,scale=1.0):
    obj=template.copy()
    obj.data=template.data
    obj.name=name
    obj.hide_render=False
    obj.hide_viewport=False
    scene.collection.objects.link(obj)
    obj.rotation_euler=(0.0,0.0,rotation_z)
    obj.scale=(scale,scale,scale)
    obj.location=Vector(location)
    bpy.context.view_layer.update()
    dz=floor_z-bottom_z(obj)
    obj.location.z += dz
    obj["xziel_role"]="church_prop"
    obj["source_pack"]="OpenGameArt AnyRPG CC0"
    return obj

# Detailed wooden bench: closest useful authored CC0 approximation to a pew.
bench_template=append_object(BENCH_BLEND,"BenchWoodOld")
bench_template.name="SANCTUM_PEW_TEMPLATE"
bench_template.hide_render=True
bench_template.hide_viewport=True

pews=[]
row_fracs=(-0.26,-0.16,-0.06,0.04,0.14)
x_offset=min(2.25,half_w*0.27)
for row,frac in enumerate(row_fracs,1):
    y=ic.y+isz.y*frac
    for side,sign in (("L",-1.0),("R",1.0)):
        pews.append(place_copy(
            bench_template,
            f"SANCTUM_PEW_{row}_{side}",
            (ic.x+sign*x_offset,y,floor_z),
            rotation_z=0.0,
            scale=1.0,
        ))

# Build one authored candle cluster from the center stand + candle + wick.
candle_parts=[]
for source_name in ("CandleStand","Candle","Wicka"):
    candle_parts.append(append_object(CANDLE_BLEND,source_name))

for o in bpy.context.selected_objects:
    o.select_set(False)
for o in candle_parts:
    o.hide_render=False
    o.hide_viewport=False
    o.select_set(True)
bpy.context.view_layer.objects.active=candle_parts[0]
bpy.ops.object.join()
candle_template=bpy.context.view_layer.objects.active
candle_template.name="SANCTUM_CANDLE_TEMPLATE"
bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY",center="BOUNDS")
candle_template.hide_render=True
candle_template.hide_viewport=True

candles=[]
candle_targets=[
    (-3.7,0.60),(-2.4,0.68),(2.4,0.68),(3.7,0.60),
    (-4.8,0.36),(4.8,0.36),
]
for idx,(xoff,yfrac) in enumerate(candle_targets,1):
    candles.append(place_copy(
        candle_template,
        f"SANCTUM_CANDLE_{idx:02d}",
        (ic.x+xoff,ic.y+half_l*yfrac,floor_z),
        rotation_z=0.0,
        scale=1.35,
    ))

# Small warm preview lights stay render-only; they are not selected for GLB export.
preview_lights=[]
for idx,obj in enumerate(candles,1):
    ld=bpy.data.lights.new(f"SANCTUM_CANDLE_LIGHT_{idx:02d}_DATA","POINT")
    ld.energy=55.0
    ld.color=(1.0,0.44,0.16)
    ld.shadow_soft_size=0.65
    lo=bpy.data.objects.new(f"SANCTUM_CANDLE_LIGHT_{idx:02d}",ld)
    scene.collection.objects.link(lo)
    lo.location=obj.location+Vector((0,0,0.75))
    preview_lights.append(lo)

bpy.context.view_layer.update()

# Gameplay gate: props must preserve at least 88% of the already-approved
# dressed-map player-clearance samples.
prop_walk=walkability(scene,inner_after)

def key(p):
    return (round(float(p[0]),5),round(float(p[1]),5))
base_points={key(p) for p in base_walk["walkable_points"]}
prop_points={key(p) for p in prop_walk["walkable_points"]}
retained=base_points & prop_points
retention=len(retained)/len(base_points) if base_points else 0.0

# Explicitly protect the central aisle: no prop may sit within this strip.
aisle_half_width=1.0
aisle_intruders=[]
for obj in [*pews,*candles]:
    xs=[(obj.matrix_world @ Vector(c)).x for c in obj.bound_box]
    if min(xs) < ic.x+aisle_half_width and max(xs) > ic.x-aisle_half_width:
        aisle_intruders.append(obj.name)

if aisle_intruders:
    fail(f"central aisle intrusion: {aisle_intruders}")
if retention < 0.88:
    fail(f"prop dressing preserves only {retention:.3f} of approved clearance")

# Render actual enriched nave at player height.
scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=960
scene.render.resolution_y=600
scene.render.resolution_percentage=100
if scene.world is None:
    scene.world=bpy.data.worlds.new("SANCTUM_ENRICH_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.004,0.006,0.012,1.0)
    bg.inputs["Strength"].default_value=0.18

cam=ensure_camera(scene)
eye=floor_z+1.72

def render_enriched_view(scene, cam, name, pos, look):
    cam.location=Vector(pos)
    cam.rotation_euler=(Vector(look)-cam.location).to_track_quat("-Z","Y").to_euler()
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)
    p=OUT/name
    if not p.is_file() or p.stat().st_size < 4000:
        fail(f"render failed: {name}")
    return {"name":name,"bytes":p.stat().st_size}

views=[
    ("01-enriched-nave-forward.png",
     Vector((ic.x,ic.y-half_l*0.74,eye)),
     Vector((ic.x,ic.y+half_l*0.50,eye+0.7))),
    ("02-enriched-nave-reverse.png",
     Vector((ic.x,ic.y+half_l*0.58,eye)),
     Vector((ic.x,ic.y-half_l*0.60,eye+0.4))),
    ("03-enriched-left-pews.png",
     Vector((ic.x-0.55,ic.y-half_l*0.40,eye)),
     Vector((ic.x-2.2,ic.y+half_l*0.12,eye+0.3))),
    ("04-enriched-altar-candles.png",
     Vector((ic.x,ic.y+half_l*0.25,eye)),
     Vector((ic.x,ic.y+half_l*0.72,eye+1.0))),
]
renders=[render_enriched_view(scene,cam,*v) for v in views]

export_objects=[*base_export,*pews,*candles]
glb=OUT/"sanctum-enriched-cathedral-interior.glb"
for obj in bpy.context.selected_objects:
    obj.select_set(False)
for obj in export_objects:
    if obj.type=="MESH":
        obj.select_set(True)
bpy.context.view_layer.objects.active=export_objects[0]
bpy.ops.export_scene.gltf(filepath=str(glb),export_format="GLB",use_selection=True,export_apply=True)
if not glb.is_file() or glb.stat().st_size < 1000000:
    fail("enriched GLB export failed")

stats=mesh_stats(export_objects)
report={
    "status":"PASS",
    "license_policy":"MIT outer + CC0 interior/dressing/props",
    "bench_source":"https://opengameart.org/content/medieval-benches",
    "bench_source_sha256":os.environ.get("SANCTUM_BENCH_SHA256",""),
    "candle_source":"https://opengameart.org/content/medieval-candles",
    "candle_source_sha256":os.environ.get("SANCTUM_CANDLE_SHA256",""),
    "pew_source_object":"BenchWoodOld",
    "candle_source_objects":["CandleStand","Candle","Wicka"],
    "pew_count":len(pews),
    "candle_count":len(candles),
    "base_walkable_points":len(base_points),
    "retained_walkable_points":len(retained),
    "walkability_retention_ratio":retention,
    "central_aisle_half_width":aisle_half_width,
    "central_aisle_intruders":aisle_intruders,
    "renders":renders,
    "stats":stats,
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size,
}
(OUT/"enriched-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_ENRICHED_CC0_PROPS_PASS")
print(json.dumps({
    "pews":len(pews),"candles":len(candles),
    "retention":retention,"vertices":stats["vertices"],
    "polygons":stats["polygons"],"glb_bytes":glb.stat().st_size,
},indent=2))
