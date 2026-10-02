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
render_view=state["render_dress_view"]
# The base stage owns SANCTUM_DRESS_OUT; redirect only the reused render helper
# so enriched evidence lands in the enriched artifact directory.
render_view.__globals__["DRESS_OUT"]=OUT
ensure_camera=state["ensure_camera"]
export_dressed=state["export_dressed"]
inner_after=state["inner_after"]
base_walk=state["walk"]
base_export=list(state["export_objects"])

# Shared reference-driven PBR set.  This keeps pew/altar/floor materials in the
# same authored visual family instead of letting props look like pasted assets.
refmat=runpy.run_path("tools/sanctum_v2/reference_materials.py")
REF=refmat["material_set"]()
ref_fit=runpy.run_path("tools/sanctum_v2/reference_silhouette_fit.py")
REF_PROFILES=ref_fit["load_profiles"]()
fit_object_to_silhouettes=ref_fit["fit_object_to_silhouettes"]
gameplay_floor=state.get("gameplay_floor")
if gameplay_floor is not None and gameplay_floor.type=="MESH":
    gameplay_floor.data.materials.clear()
    gameplay_floor.data.materials.append(REF["floor"])
    gameplay_floor["material_source"]="Sanctum reference board / procedural PBR v2"

# Upgrade only materials that are explicitly named as glass/window materials.
# This avoids flattening the existing church art while giving true window
# surfaces the blue/red/gold stained-glass response from the reference board.
stained_glass_slots=0
for obj in base_export:
    if obj.type!="MESH":
        continue
    for slot in obj.material_slots:
        mat=slot.material
        if mat is None:
            continue
        n=mat.name.lower()
        if "glass" in n or "window" in n or "vitra" in n:
            slot.material=REF["glass"]
            stained_glass_slots += 1

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
    obj["source_pack"]=template.get("source_pack","OpenGameArt AnyRPG CC0")
    if template.get("source_license"):
        obj["source_license"]=template.get("source_license")
    return obj

# Reference-built Gothic pew.  The previous BenchWoodOld was technically
# valid but too thin/simple compared with the supplied all-angle model sheet.
# Build one heavier authored template: square posts, wide feet, thick seat/back,
# pointed Gothic relief and a real hymn-book rack, then instance it for rows.
def _box_piece(name,loc,size,mat,bevel=0.018):
    bpy.ops.mesh.primitive_cube_add(size=1.0,location=loc)
    o=bpy.context.object
    o.name=name
    o.dimensions=Vector(size)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mat)
    if bevel>0:
        mod=o.modifiers.new("SANCTUM_EDGE_SOFTEN","BEVEL")
        mod.width=bevel
        mod.segments=2
        bpy.context.view_layer.objects.active=o
        o.select_set(True)
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        finally:
            o.select_set(False)
    return o

def _tube_segment(name,a,b,radius,mat):
    a=Vector(a); b=Vector(b)
    d=b-a
    length=d.length
    mid=(a+b)*0.5
    bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=radius,depth=length,location=mid)
    o=bpy.context.object
    o.name=name
    o.rotation_euler=d.to_track_quat("Z","Y").to_euler()
    o.data.materials.append(mat)
    return o

def build_reference_pew_template():
    parts=[]
    W=3.45
    # Main horizontal timbers.
    parts += [
        _box_piece("PEW_SEAT",(0.0,0.00,0.49),(W,0.62,0.11),REF["wood_h"],0.025),
        _box_piece("PEW_BACK",(0.0,-0.31,1.02),(W,0.12,0.82),REF["wood_h"],0.024),
        _box_piece("PEW_TOP_RAIL",(0.0,-0.31,1.45),(W+0.12,0.16,0.12),REF["wood_h"],0.025),
        _box_piece("PEW_FRONT_APRON",(0.0,0.24,0.33),(W,0.10,0.28),REF["wood_h"],0.020),
        _box_piece("PEW_RACK",(0.0,-0.46,0.84),(W-0.44,0.16,0.35),REF["wood_h"],0.016),
        _box_piece("PEW_RACK_LIP",(0.0,-0.56,0.67),(W-0.34,0.10,0.10),REF["wood_h"],0.014),
    ]
    # Heavy Gothic end posts/panels and stepped feet/caps.
    for side,sign in (("L",-1.0),("R",1.0)):
        x=sign*(W*0.5+0.09)
        parts += [
            _box_piece(f"PEW_{side}_END",(x,0.0,0.77),(0.24,0.82,1.54),REF["wood_v"],0.028),
            _box_piece(f"PEW_{side}_FOOT",(x,0.0,0.09),(0.38,0.94,0.18),REF["wood_h"],0.024),
            _box_piece(f"PEW_{side}_BASE",(x,0.0,0.22),(0.32,0.88,0.12),REF["wood_h"],0.022),
            _box_piece(f"PEW_{side}_CAP",(x,0.0,1.50),(0.38,0.92,0.16),REF["wood_h"],0.024),
        ]
        # Raised pointed-arch relief on the outside face, matching the reference.
        xf=x+sign*0.128
        for idx,(a,b) in enumerate([
            ((xf,-0.27,0.36),(xf,-0.27,1.00)),
            ((xf, 0.27,0.36),(xf, 0.27,1.00)),
            ((xf,-0.27,1.00),(xf,0.0,1.29)),
            ((xf, 0.27,1.00),(xf,0.0,1.29)),
            ((xf,-0.20,0.38),(xf,0.0,0.62)),
            ((xf, 0.20,0.38),(xf,0.0,0.62)),
        ]):
            parts.append(_tube_segment(f"PEW_{side}_GOTHIC_{idx}",a,b,0.028,REF["wood_v"]))
    # Hymn books: muted black/burgundy volumes visible from the rear rack.
    book_mats=[]
    for idx,col in enumerate(((0.050,0.020,0.018,1.0),(0.19,0.025,0.028,1.0),(0.035,0.033,0.030,1.0))):
        m=bpy.data.materials.get(f"SANCTUM_HYMN_{idx}") or bpy.data.materials.new(f"SANCTUM_HYMN_{idx}")
        m.diffuse_color=col
        book_mats.append(m)
    for i,x in enumerate((-1.00,-0.50,0.0,0.50,1.00)):
        parts.append(_box_piece(f"PEW_BOOK_{i}",(x,-0.58,0.88),(0.28,0.07,0.34),book_mats[i%3],0.008))

    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join()
    o=bpy.context.view_layer.objects.active
    o.name="SANCTUM_PEW_REFERENCE_TEMPLATE"
    # Project the authored template into the traced front+side visual hull.
    # This is the "draw over the photo" constraint: outer geometry must match
    # both supplied orthographic silhouettes before we instance it.
    pew_profile=REF_PROFILES["pew"]
    fit_stats=fit_object_to_silhouettes(
        o,
        pew_profile["front"]["points"],
        pew_profile["side_left"]["points"],
        pew_profile["target_dimensions_m"],
    )
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY",center="BOUNDS")
    o["xziel_role"]="church_prop"
    o["reference_fit_vertices"]=fit_stats["vertices"]
    o["reference_fit_changed_components"]=fit_stats["changed"]
    o["source_pack"]="User Sanctum pew reference / procedural reconstruction"
    o["source_license"]="original_xziel_reference_reconstruction"
    o.hide_render=True
    o.hide_viewport=True
    return o

bench_template=build_reference_pew_template()

pews=[]
row_fracs=(-0.26,-0.16,-0.06,0.04,0.14)
# Wider/heavier than the old benches while preserving the proven central aisle.
# Full reference width is preserved. Move the heavier pews into the side-bay
# footprint (where pillars already consume clearance) instead of shrinking them
# or weakening the 0.88 walkability gate.
x_offset=min(max(3.00,half_w*0.50),half_w-1.85)
for row,frac in enumerate(row_fracs,1):
    y=ic.y+isz.y*frac
    for side,sign in (("L",-1.0),("R",1.0)):
        p=place_copy(
            bench_template,
            f"SANCTUM_PEW_{row}_{side}",
            (ic.x+sign*x_offset,y,floor_z),
            rotation_z=0.0,
            scale=1.0,
        )
        p["reference_model"]="docs/sanctum-reference-materials.v2.json#model_targets.pew"
        pews.append(p)

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
# Keep all nave proofs at the new requested player-view height.
eye=floor_z+1.88
cam.data.lens=31.0

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
    "license_policy":"MIT outer + CC0 architecture/dressing/candles + original XZIEL reference-reconstructed pews",
    "bench_source":"user Sanctum pew all-angle reference / original procedural reconstruction",
    "bench_source_sha256":"",
    "reference_material_profile":"docs/sanctum-reference-materials.v2.json",
    "reference_silhouette_profile":"docs/sanctum-reference-silhouettes.v1.json",
    "pew_reference_fit_method":"dual_silhouette_vertex_clamp",
    "stained_glass_slots_upgraded":stained_glass_slots,
    "candle_source":"https://opengameart.org/content/medieval-candles",
    "candle_source_sha256":os.environ.get("SANCTUM_CANDLE_SHA256",""),
    "pew_source_object":"SANCTUM_PEW_REFERENCE_TEMPLATE",
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
