import bpy
import json
import math
import os
import runpy
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_INDUSTRIAL_DRESS_OUT","sanctum-industrial-dressed-probe"))
OUT.mkdir(parents=True,exist_ok=True)
INDUSTRIAL_BLEND=Path(os.environ["SANCTUM_INDUSTRIAL_BLEND"])

state=runpy.run_path("tools/sanctum_v2/build_sanctum_vertical_blockout.py")
scene=state["scene"]
mesh_stats=state["mesh_stats"]
ensure_camera=state["ensure_camera"]
ic=state["ic"]
hx=state["hx"]
hy=state["hy"]
bx0=state["bx0"]
bx1=state["bx1"]
by0=state["by0"]
by1=state["by1"]
lower_z=state["lower_z"]
floor_z=state["floor_z"]
upper_z=state["upper_z"]
base_export=list(state["export_objects"])

def fail(msg):
    raise SystemExit(f"SANCTUM_INDUSTRIAL_DRESS_FAIL: {msg}")

def append_object(name):
    with bpy.data.libraries.load(str(INDUSTRIAL_BLEND),link=False) as (src,dst):
        if name not in src.objects:
            fail(f"missing industrial object {name}")
        dst.objects=[name]
    obj=dst.objects[0]
    scene.collection.objects.link(obj)
    obj.name="XZIEL_INDUSTRIAL_SRC_"+name
    return obj

def normalize_source(obj):
    obj.hide_render=False
    obj.hide_viewport=False
    # Preserve authored mesh/materials while removing the source scene's
    # world-placement offset. The source pack stores objects far apart.
    obj.location=(0.0,0.0,0.0)
    bpy.context.view_layer.update()
    return obj

def world_bounds(obj):
    pts=[obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def place_copy(template,name,target_bottom_center,scale=1.0,rotation_z=0.0,role="industrial_prop"):
    obj=template.copy()
    obj.data=template.data
    obj.name=name
    scene.collection.objects.link(obj)
    # Copies inherit the hidden state of the source template. Explicitly
    # re-enable authored instances so proof renders and final export see them.
    obj.hide_render=False
    obj.hide_viewport=False
    obj.hide_set(False)
    obj.location=(0.0,0.0,0.0)
    obj.rotation_euler=(0.0,0.0,rotation_z)
    obj.scale=(scale,scale,scale)
    bpy.context.view_layer.update()

    mn,mx=world_bounds(obj)
    current_bottom_center=Vector(((mn.x+mx.x)*0.5,(mn.y+mx.y)*0.5,mn.z))
    obj.location += Vector(target_bottom_center)-current_bottom_center
    bpy.context.view_layer.update()

    obj["xziel_role"]=role
    obj["source_pack"]="OpenGameArt PBR Industrial Asset Pack by a52"
    obj["source_license"]="CC0"
    return obj

def enrich_boiler_materials(obj, seed=0):
    """Layer deterministic grime, wet roughness breakup and micro-bump over CC0 PBR."""
    if obj.type!="MESH":
        return
    for slot_i,slot in enumerate(obj.material_slots):
        src=slot.material
        if src is None:
            continue
        mat=src.copy()
        mat.name=f"{src.name}_SANCTUM_GRIME_{seed}_{slot_i}"
        mat.use_nodes=True
        nt=mat.node_tree
        bsdf=nt.nodes.get("Principled BSDF") if nt else None
        if bsdf is None:
            slot.material=mat
            continue

        noise=nt.nodes.new("ShaderNodeTexNoise")
        noise.name=f"SANCTUM_GRIME_NOISE_{seed}_{slot_i}"
        noise.inputs["Scale"].default_value=2.35 + seed*0.21
        noise.inputs["Detail"].default_value=6.0
        noise.inputs["Roughness"].default_value=0.72

        ramp=nt.nodes.new("ShaderNodeValToRGB")
        ramp.name=f"SANCTUM_GRIME_MASK_{seed}_{slot_i}"
        ramp.color_ramp.elements[0].position=0.46
        ramp.color_ramp.elements[0].color=(0.0,0.0,0.0,1.0)
        ramp.color_ramp.elements[1].position=0.74
        ramp.color_ramp.elements[1].color=(0.58,0.58,0.58,1.0)
        nt.links.new(noise.outputs["Fac"],ramp.inputs["Fac"])

        # Dark oily/grimy deposits over the authored albedo without replacing it.
        mix=nt.nodes.new("ShaderNodeMixRGB")
        mix.blend_type="MULTIPLY"
        mix.inputs[2].default_value=(0.20,0.13,0.075,1.0)
        nt.links.new(ramp.outputs["Color"],mix.inputs[0])
        base=bsdf.inputs.get("Base Color")
        if base:
            if base.is_linked:
                old=base.links[0]
                from_socket=old.from_socket
                nt.links.remove(old)
                nt.links.new(from_socket,mix.inputs[1])
            else:
                mix.inputs[1].default_value=base.default_value
            nt.links.new(mix.outputs["Color"],base)

        # Wet/oily patches selectively lower roughness; dry metal stays authored.
        rough=bsdf.inputs.get("Roughness")
        if rough:
            mapr=nt.nodes.new("ShaderNodeMapRange")
            mapr.inputs["From Min"].default_value=0.0
            mapr.inputs["From Max"].default_value=1.0
            mapr.inputs["To Min"].default_value=1.0
            mapr.inputs["To Max"].default_value=0.46
            nt.links.new(noise.outputs["Fac"],mapr.inputs["Value"])
            mult=nt.nodes.new("ShaderNodeMath")
            mult.operation="MULTIPLY"
            if rough.is_linked:
                old=rough.links[0]
                from_socket=old.from_socket
                nt.links.remove(old)
                nt.links.new(from_socket,mult.inputs[0])
            else:
                mult.inputs[0].default_value=float(rough.default_value)
            nt.links.new(mapr.outputs["Result"],mult.inputs[1])
            nt.links.new(mult.outputs[0],rough)

        # Fine pitting/grit layered over any authored normal map.
        bump=nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value=0.17
        bump.inputs["Distance"].default_value=0.11
        nt.links.new(noise.outputs["Fac"],bump.inputs["Height"])
        normal=bsdf.inputs.get("Normal")
        if normal:
            if normal.is_linked:
                old=normal.links[0]
                from_socket=old.from_socket
                nt.links.remove(old)
                nt.links.new(from_socket,bump.inputs["Normal"])
            nt.links.new(bump.outputs["Normal"],normal)
        slot.material=mat

# Remove the blockout boiler from the final authored/export set.
boiler=bpy.data.objects.get("SANCTUM_BOILER_CORE")
if boiler:
    boiler.hide_render=True
    boiler.hide_viewport=True
base_export=[o for o in base_export if o.name!="SANCTUM_BOILER_CORE"]

tank_src=normalize_source(append_object("tank_2_mat"))
pipe5_src=normalize_source(append_object("pipe_05"))
pipe7_src=normalize_source(append_object("pipe_07"))
vent_src=normalize_source(append_object("vent_mat"))

for src in (tank_src,pipe5_src,pipe7_src,vent_src):
    src.hide_render=True
    src.hide_viewport=True

# Two compact vertical tanks make a readable boiler landmark without consuming
# the left/right combat loop around the room.
tank_scale=0.34
center_y=ic.y+hy*0.12
industrial=[]
industrial.append(place_copy(
    tank_src,"SANCTUM_BOILER_TANK_WEST",
    (ic.x-0.78,center_y,lower_z),
    scale=tank_scale,
    rotation_z=math.radians(90),
    role="boiler_tank"
))
industrial.append(place_copy(
    tank_src,"SANCTUM_BOILER_TANK_EAST",
    (ic.x+0.78,center_y,lower_z),
    scale=tank_scale,
    rotation_z=math.radians(90),
    role="boiler_tank"
))

# Pipe modules live above/behind the tanks so they read as machinery without
# narrowing the player lane at chest height.
industrial.append(place_copy(
    pipe5_src,"SANCTUM_BOILER_PIPE_OVERHEAD_A",
    (ic.x,center_y+0.95,lower_z+2.42),
    scale=0.62,
    rotation_z=math.radians(90),
    role="boiler_pipe"
))
industrial.append(place_copy(
    pipe7_src,"SANCTUM_BOILER_PIPE_OVERHEAD_B",
    (ic.x,center_y-1.05,lower_z+2.50),
    scale=0.72,
    rotation_z=math.radians(90),
    role="boiler_pipe"
))

# Vent mounted to the south wall, centered between the two lateral ramp
# envelopes. The east-wall placement became unsafe after the ramps were inset.
industrial.append(place_copy(
    vent_src,"SANCTUM_UNDERCROFT_VENT_SOUTH",
    (ic.x,by0+0.16,lower_z+1.25),
    scale=0.80,
    rotation_z=0.0,
    role="vent"
))

# Material pass from the new reference: less pale, more oily/grimy surface breakup.
for idx,obj in enumerate(industrial,1):
    enrich_boiler_materials(obj,idx)

# Basic geometric safety envelope: props must stay away from the two ramp
# openings and preserve broad west/east loop lanes.
ramp_boxes=[
    (state["left_x0"]-0.35,state["left_x1"]+0.35,state["left_y0"]-0.35,state["left_y1"]+0.35),
    (state["right_x0"]-0.35,state["right_x1"]+0.35,state["right_y0"]-0.35,state["right_y1"]+0.35),
]
intrusions=[]
for obj in industrial:
    mn,mx=world_bounds(obj)
    for x0,x1,y0,y1 in ramp_boxes:
        if mx.x>x0 and mn.x<x1 and mx.y>y0 and mn.y<y1 and mn.z<floor_z+0.35:
            intrusions.append(obj.name)
            break
if intrusions:
    fail(f"industrial props intrude ramp safety envelopes: {intrusions}")

# Proof lighting.
def point_light(name,location,energy,color):
    ld=bpy.data.lights.new(name+"_DATA","POINT")
    ld.energy=energy
    ld.color=color
    ld.shadow_soft_size=0.65
    lo=bpy.data.objects.new(name,ld)
    scene.collection.objects.link(lo)
    lo.location=Vector(location)
    return lo

point_light("SANCTUM_BOILER_WARM_A",(ic.x-1.8,center_y,lower_z+1.7),470,(1.0,0.43,0.12))
point_light("SANCTUM_BOILER_WARM_B",(ic.x+1.8,center_y+0.5,lower_z+1.5),310,(0.92,0.34,0.10))
point_light("SANCTUM_BOILER_COOL_FILL",(ic.x,by0+1.1,lower_z+2.0),190,(0.16,0.22,0.34))
point_light("SANCTUM_BOILER_TANK_RIM",(ic.x,center_y-2.2,lower_z+2.2),225,(0.18,0.27,0.42))

# Proof-only overhead area light so the PBR machinery can actually be inspected
# in CI renders. This light is not part of export_objects and never ships.
def area_light(name,location,energy,size,color):
    ld=bpy.data.lights.new(name+"_DATA","AREA")
    ld.energy=energy
    ld.shape="DISK"
    ld.size=size
    ld.color=color
    lo=bpy.data.objects.new(name,ld)
    scene.collection.objects.link(lo)
    lo.location=Vector(location)
    lo.rotation_euler=(0.0,0.0,0.0)
    return lo

area_light(
    "SANCTUM_BOILER_PROOF_OVERHEAD",
    (ic.x,center_y,lower_z+2.75),
    760,
    4.6,
    (0.68,0.60,0.48),
)

scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=960
scene.render.resolution_y=600
scene.render.resolution_percentage=100
if scene.world is None:
    scene.world=bpy.data.worlds.new("SANCTUM_INDUSTRIAL_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.003,0.004,0.006,1)
    bg.inputs["Strength"].default_value=0.15

cam=ensure_camera(scene)
eye=1.82
def point(cam,target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def render(name,pos,look):
    cam.location=Vector(pos)
    point(cam,look)
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)
    p=OUT/name
    if not p.is_file() or p.stat().st_size<5000:
        fail(f"render failed {name}")
    return {"name":name,"bytes":p.stat().st_size}

# Keep proof cameras inside the central clear lane, away from the west/east
# ramp footprints. Earlier views were technically valid but the ramps occluded
# the hero machinery, making a GREEN art pass impossible to judge visually.
renders=[
    render("01-undercroft-boiler-entry.png",
           (ic.x,by0+1.25,lower_z+eye),
           (ic.x,center_y,lower_z+1.20)),
    render("02-undercroft-boiler-loop-west.png",
           (ic.x-2.75,center_y+1.15,lower_z+eye),
           (ic.x-0.55,center_y,lower_z+1.20)),
    render("03-undercroft-boiler-loop-east.png",
           (ic.x+2.75,center_y+1.15,lower_z+eye),
           (ic.x+0.55,center_y,lower_z+1.20)),
    render("04-undercroft-power-route.png",
           (ic.x,by1-1.20,lower_z+eye),
           (ic.x,center_y,lower_z+1.35)),
]

export_objects=[*base_export,*industrial]
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

glb=OUT/"sanctum-vertical-industrial.glb"
bpy.ops.export_scene.gltf(
    filepath=str(glb),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_extras=True,
)
if not glb.is_file() or glb.stat().st_size<1000000:
    fail("industrial GLB export failed")

stats=mesh_stats([o for o in export_objects if o.type=="MESH"])
report={
    "status":"PASS",
    "source":"OpenGameArt PBR Industrial Asset Pack by a52",
    "license":"CC0",
    "source_sha256":os.environ.get("SANCTUM_INDUSTRIAL_SHA256",""),
    "replaced_blockout":"SANCTUM_BOILER_CORE",
    "industrial_objects":[o.name for o in industrial],
    "tank_scale":tank_scale,
    "ramp_intrusions":intrusions,
    "renders":renders,
    "stats":stats,
    "floor_heights_m":{"undercroft":lower_z,"nave":floor_z,"gallery":upper_z},
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size,
}
(OUT/"industrial-dressed-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_INDUSTRIAL_DRESS_PASS")
print(json.dumps({
    "objects":report["industrial_objects"],
    "ramp_intrusions":intrusions,
    "vertices":stats["vertices"],
    "polygons":stats["polygons"],
    "glb_bytes":report["glb_bytes"],
},indent=2))
