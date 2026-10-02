import bpy
import json
import math
import os
import runpy
from pathlib import Path
from mathutils import Vector

VERT_OUT=Path(os.environ.get("SANCTUM_VERTICAL_OUT","sanctum-vertical-probe"))
VERT_OUT.mkdir(parents=True,exist_ok=True)
LAYOUT_PATH=Path(os.environ.get("SANCTUM_VERTICAL_LAYOUT","docs/sanctum-vertical-layout.v1.json"))
layout=json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))

# Build on the last proven playable/art pass.
state=runpy.run_path("tools/sanctum_v2/enrich_sanctum_cc0_props.py")
scene=state["scene"]
inner_after=state["inner_after"]
mesh_stats=state["mesh_stats"]
ensure_camera=state["ensure_camera"]
base_export=list(state["export_objects"])

ic=Vector(inner_after["center"])
isz=Vector(inner_after["size"])
imn=Vector(inner_after["min"])
floor_z=imn.z+0.12
half_w=isz.x*0.5
half_l=isz.y*0.5

def fail(msg):
    raise SystemExit(f"SANCTUM_VERTICAL_FAIL: {msg}")

def material(name,fallback=None):
    mat=bpy.data.materials.get(name)
    if mat is None and fallback:
        mat=bpy.data.materials.get(fallback)
    if mat is None:
        mat=bpy.data.materials.new(f"SANCTUM_{name}")
        mat.diffuse_color=(0.18,0.18,0.18,1.0)
    return mat

# Reference-driven PBR family shared by nave, pews, altar and new runtime
# geometry.  This changes only shading/materials; authored navigation topology
# remains exactly the same.
refmat=runpy.run_path("tools/sanctum_v2/reference_materials.py")
REF=refmat["material_set"]()
STONE=REF["stone"]
FLOOR=REF["floor"]
WOOD=REF["wood_h"]
METAL=material("Metal","RustedMetal")

def simple_material(name,color,emission=0.0):
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value=(*color,1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value=0.55
        if emission>0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value=(*color,1.0)
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value=(*color,1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value=emission
    return mat

AD_PANEL=simple_material("SANCTUM_AD_PANEL",(0.03,0.04,0.05),0.15)
AD_FRAME=simple_material("SANCTUM_AD_FRAME",(0.20,0.13,0.07),0.0)
DEBUG_POWER=simple_material("SANCTUM_POWER_PROXY",(0.42,0.08,0.03),0.05)

def add_box(name,center,size,mat,role="architecture",collision=True):
    bpy.ops.mesh.primitive_cube_add(size=1.0,location=center)
    obj=bpy.context.object
    obj.name=name
    obj.dimensions=Vector(size)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if mat is not None:
        obj.data.materials.append(mat)
    obj["xziel_role"]=role
    obj["xziel_collision"]=bool(collision)
    return obj

def add_ramp_y(name,x,y_center,z_low,z_high,run_m,width,high_toward_positive_y,mat):
    rise=z_high-z_low
    slope_len=math.sqrt(run_m*run_m+rise*rise)
    angle=math.atan2(rise,run_m)
    if not high_toward_positive_y:
        angle=-angle
    thickness=0.20
    center_z=(z_low+z_high)*0.5-(thickness*0.5*math.cos(abs(angle)))
    obj=add_box(name,(x,y_center,center_z),(width,slope_len,thickness),mat,role="walkable_ramp",collision=True)
    obj.rotation_euler.x=angle
    obj["xziel_rise_m"]=rise
    obj["xziel_run_m"]=run_m
    return obj

def add_wall(name,center,size):
    return add_box(name,center,size,STONE,role="undercroft_wall",collision=True)

def add_ad_frame(prefix,center,normal_axis,size_xy,surface_id):
    width,height=size_xy
    pieces=[]
    if normal_axis=="X":
        panel=add_box(f"SANCTUM_AD_{prefix}_PANEL",center,(0.05,width,height),AD_PANEL,"ad_surface",False)
        bar_t=0.09
        y,z=center[1],center[2]
        x=center[0]
        pieces.extend([
            panel,
            add_box(f"SANCTUM_AD_{prefix}_FRAME_L",(x,y-width*0.5-bar_t*0.5,z),(0.08,bar_t,height+0.18),AD_FRAME,"ad_frame",False),
            add_box(f"SANCTUM_AD_{prefix}_FRAME_R",(x,y+width*0.5+bar_t*0.5,z),(0.08,bar_t,height+0.18),AD_FRAME,"ad_frame",False),
            add_box(f"SANCTUM_AD_{prefix}_FRAME_T",(x,y,z+height*0.5+bar_t*0.5),(0.08,width+0.18,bar_t),AD_FRAME,"ad_frame",False),
            add_box(f"SANCTUM_AD_{prefix}_FRAME_B",(x,y,z-height*0.5-bar_t*0.5),(0.08,width+0.18,bar_t),AD_FRAME,"ad_frame",False),
        ])
    else:
        panel=add_box(f"SANCTUM_AD_{prefix}_PANEL",center,(width,0.05,height),AD_PANEL,"ad_surface",False)
        bar_t=0.09
        x,z=center[0],center[2]
        y=center[1]
        pieces.extend([
            panel,
            add_box(f"SANCTUM_AD_{prefix}_FRAME_L",(x-width*0.5-bar_t*0.5,y,z),(bar_t,0.08,height+0.18),AD_FRAME,"ad_frame",False),
            add_box(f"SANCTUM_AD_{prefix}_FRAME_R",(x+width*0.5+bar_t*0.5,y,z),(bar_t,0.08,height+0.18),AD_FRAME,"ad_frame",False),
            add_box(f"SANCTUM_AD_{prefix}_FRAME_T",(x,y,z+height*0.5+bar_t*0.5),(width+0.18,0.08,bar_t),AD_FRAME,"ad_frame",False),
            add_box(f"SANCTUM_AD_{prefix}_FRAME_B",(x,y,z-height*0.5-bar_t*0.5),(width+0.18,0.08,bar_t),AD_FRAME,"ad_frame",False),
        ])
    for obj in pieces:
        obj["xziel_ad_surface_id"]=surface_id
        obj["xziel_world_space_only"]=True
    return pieces

# Replace the single gameplay quad with a thicker walkable floor containing
# two authored openings for the undercroft routes.
old_floor=bpy.data.objects.get("SANCTUM_GAMEPLAY_FLOOR")
if old_floor:
    old_floor.hide_render=True
    old_floor.hide_viewport=True
base_export=[o for o in base_export if o.name!="SANCTUM_GAMEPLAY_FLOOR"]

hx=isz.x*0.40
hy=isz.y*0.39
xmin,xmax=ic.x-hx,ic.x+hx
ymin,ymax=ic.y-hy,ic.y+hy
floor_thickness=0.18

hole_w=max(1.9,min(2.35,hx*0.34))
hole_len=max(5.8,min(6.8,hy*0.55))
# Inset ramp openings from the side shell. The original 0.55 m inset
# left each opening ~18.6 cm through the undercroft side wall.
left_x0=xmin+1.00
left_x1=left_x0+hole_w
# Keep the west undercroft ramp fully inside the service-room shell.
# The old -0.44 fraction crossed the south perimeter wall by ~2 m.
left_y0=ic.y-hy*0.27
left_y1=left_y0+hole_len
right_x1=xmax-1.00
right_x0=right_x1-hole_w
right_y1=ic.y+hy*0.44
right_y0=right_y1-hole_len

floor_parts=[]
def floor_box(name,x0,x1,y0,y1):
    if x1-x0<0.15 or y1-y0<0.15:
        return None
    obj=add_box(name,((x0+x1)*0.5,(y0+y1)*0.5,floor_z-floor_thickness*0.5),(x1-x0,y1-y0,floor_thickness),FLOOR,"walkable_floor",True)
    floor_parts.append(obj)
    return obj

# Three vertical strips plus hole-band caps.
floor_box("SANCTUM_MAIN_FLOOR_LEFT",xmin,left_x0,ymin,ymax)
floor_box("SANCTUM_MAIN_FLOOR_CENTER_LEFT",left_x1,right_x0,ymin,ymax)
floor_box("SANCTUM_MAIN_FLOOR_RIGHT",right_x1,xmax,ymin,ymax)
floor_box("SANCTUM_MAIN_FLOOR_LEFT_HOLE_BEFORE",left_x0,left_x1,ymin,left_y0)
floor_box("SANCTUM_MAIN_FLOOR_LEFT_HOLE_AFTER",left_x0,left_x1,left_y1,ymax)
floor_box("SANCTUM_MAIN_FLOOR_RIGHT_HOLE_BEFORE",right_x0,right_x1,ymin,right_y0)
floor_box("SANCTUM_MAIN_FLOOR_RIGHT_HOLE_AFTER",right_x0,right_x1,right_y1,ymax)

# FLOOR +1: two side galleries joined at the rear. The inner edge intentionally
# has no continuous railing so a player can bail into the nave rather than camp.
upper_z=floor_z+3.80
gallery_t=0.24
gallery_w=1.85
# Keep the gallery inside the proven nave clearance envelope instead of
# pinning it against the CC0 masonry. This avoids wall/pillar interpenetration.
gallery_x=half_w*0.50
gallery_y0=ic.y-hy*0.42
gallery_y1=ic.y+hy*0.38
gallery_len=gallery_y1-gallery_y0
vertical_meshes=[]
for side,sign in (("WEST",-1.0),("EAST",1.0)):
    vertical_meshes.append(add_box(
        f"SANCTUM_UPPER_{side}_WALKWAY",
        (ic.x+sign*gallery_x,(gallery_y0+gallery_y1)*0.5,upper_z-gallery_t*0.5),
        (gallery_w,gallery_len,gallery_t),
        WOOD,"upper_walkway",True
    ))
bridge_width=gallery_x*2+gallery_w
vertical_meshes.append(add_box(
    "SANCTUM_UPPER_REAR_BRIDGE",
    (ic.x,gallery_y0+1.0,upper_z-gallery_t*0.5),
    (bridge_width,2.0,gallery_t),
    WOOD,"upper_walkway",True
))

# Outer guards plus segmented nave-facing rails. Each side retains one
# deliberate bailout gap so the high ground never becomes a permanent camp.
rail_h=1.05
for side,sign in (("WEST",-1.0),("EAST",1.0)):
    x_outer=ic.x+sign*(gallery_x+gallery_w*0.5)
    vertical_meshes.append(add_box(
        f"SANCTUM_UPPER_{side}_OUTER_GUARD",
        (x_outer,(gallery_y0+gallery_y1)*0.5,upper_z+rail_h*0.5),
        (0.12,gallery_len,rail_h),
        WOOD,"upper_guard",True
    ))

    x_inner=ic.x+sign*(gallery_x-gallery_w*0.5)
    gap_center=ic.y + (-1.35 if side=="WEST" else 1.35)
    gap_half=1.05
    seg_a0,seg_a1=gallery_y0,gap_center-gap_half
    seg_b0,seg_b1=gap_center+gap_half,gallery_y1
    if seg_a1-seg_a0>0.5:
        vertical_meshes.append(add_box(
            f"SANCTUM_UPPER_{side}_INNER_GUARD_A",
            (x_inner,(seg_a0+seg_a1)*0.5,upper_z+rail_h*0.5),
            (0.10,seg_a1-seg_a0,rail_h),
            WOOD,"upper_guard",True
        ))
    if seg_b1-seg_b0>0.5:
        vertical_meshes.append(add_box(
            f"SANCTUM_UPPER_{side}_INNER_GUARD_B",
            (x_inner,(seg_b0+seg_b1)*0.5,upper_z+rail_h*0.5),
            (0.10,seg_b1-seg_b0,rail_h),
            WOOD,"upper_guard",True
        ))

upper_run=6.6
upper_ramp_w=max(1.45,min(1.75,gallery_w*0.82))
vertical_meshes.append(add_ramp_y(
    "SANCTUM_UPPER_RAMP_WEST",
    ic.x-gallery_x,
    gallery_y0-upper_run*0.5,
    floor_z,
    upper_z,
    upper_run,
    upper_ramp_w,
    True,
    WOOD
))
vertical_meshes.append(add_ramp_y(
    "SANCTUM_UPPER_RAMP_EAST",
    ic.x+gallery_x,
    gallery_y1+upper_run*0.5,
    floor_z,
    upper_z,
    upper_run,
    upper_ramp_w,
    False,
    WOOD
))

# FLOOR -1: service undercroft. A central boiler mass forces a two-sided loop.
lower_z=floor_z-3.60
bx0=ic.x-hx*0.90
bx1=ic.x+hx*0.90
by0=ic.y-hy*0.28
by1=ic.y+hy*0.56

# Topology invariant: both authored undercroft ramp openings must live inside
# the continuous perimeter shell. Fail before rendering if a future edit
# pushes a ramp through a solid wall.
topology_margin=0.08
for opening_name,(ox0,ox1,oy0,oy1) in {
    "west":(left_x0,left_x1,left_y0,left_y1),
    "east":(right_x0,right_x1,right_y0,right_y1),
}.items():
    if ox0 < bx0-topology_margin or ox1 > bx1+topology_margin:
        fail(f"{opening_name} undercroft ramp crosses X perimeter")
    if oy0 < by0-topology_margin or oy1 > by1+topology_margin:
        fail(
            f"{opening_name} undercroft ramp crosses Y perimeter: "
            f"[{oy0:.3f},{oy1:.3f}] vs room [{by0:.3f},{by1:.3f}]"
        )

basement_t=0.25
vertical_meshes.append(add_box(
    "SANCTUM_UNDERCROFT_FLOOR",
    ((bx0+bx1)*0.5,(by0+by1)*0.5,lower_z-basement_t*0.5),
    (bx1-bx0,by1-by0,basement_t),
    STONE,"undercroft_floor",True
))
# Meet the underside of the segmented nave floor so the undercroft reads as
# an actual room rather than a dark box with a floating gap above its walls.
wall_h=(floor_z-floor_thickness)-lower_z
vertical_meshes.extend([
    add_wall("SANCTUM_UNDERCROFT_WALL_WEST",(bx0,(by0+by1)*0.5,lower_z+wall_h*0.5),(0.22,by1-by0,wall_h)),
    add_wall("SANCTUM_UNDERCROFT_WALL_EAST",(bx1,(by0+by1)*0.5,lower_z+wall_h*0.5),(0.22,by1-by0,wall_h)),
    add_wall("SANCTUM_UNDERCROFT_WALL_SOUTH",((bx0+bx1)*0.5,by0,lower_z+wall_h*0.5),(bx1-bx0,0.22,wall_h)),
    add_wall("SANCTUM_UNDERCROFT_WALL_NORTH",((bx0+bx1)*0.5,by1,lower_z+wall_h*0.5),(bx1-bx0,0.22,wall_h)),
])
boiler=add_box(
    "SANCTUM_BOILER_CORE",
    (ic.x,ic.y+hy*0.12,lower_z+1.15),
    (3.0,3.8,2.30),
    METAL,"boiler_core",True
)
vertical_meshes.append(boiler)

left_hole_center_y=(left_y0+left_y1)*0.5
right_hole_center_y=(right_y0+right_y1)*0.5
vertical_meshes.append(add_ramp_y(
    "SANCTUM_UNDERCROFT_RAMP_WEST",
    (left_x0+left_x1)*0.5,
    left_hole_center_y,
    lower_z,
    floor_z,
    left_y1-left_y0,
    hole_w*0.82,
    True,
    STONE
))
vertical_meshes.append(add_ramp_y(
    "SANCTUM_UNDERCROFT_RAMP_EAST_SHORTCUT",
    (right_x0+right_x1)*0.5,
    right_hole_center_y,
    lower_z,
    floor_z,
    right_y1-right_y0,
    hole_w*0.82,
    False,
    STONE
))

# Runtime/gameplay proxies.
power_proxy=add_box(
    "SANCTUM_POWER_SWITCH_PROXY",
    (bx0+0.45,ic.y+hy*0.26,lower_z+1.05),
    (0.30,0.55,0.70),
    DEBUG_POWER,"power_switch_proxy",False
)
power_proxy["xziel_entity_id"]="power_switch"

# Diegetic ad surfaces. Anchor them to the proven *interior* gameplay
# bounds, not the larger fitted-source half-width. The older placement used
# half_w and landed behind the masonry, so the proof camera saw only stone.
ad_nave_west_pos=(xmin+0.18,ic.y-hy*0.08,floor_z+1.75)
ad_gallery_east_pos=(xmax-0.18,ic.y+hy*0.10,upper_z+1.40)
ad_radio_pos=(bx1-1.0,ic.y+hy*0.22,lower_z+0.35)

# Hard gate: world-space creatives must be visibly reachable from the authored
# interior side of the map. Never silently export a sponsor surface behind wall.
if not (xmin <= ad_nave_west_pos[0] <= xmax):
    fail(f"nave ad frame outside gameplay X bounds: {ad_nave_west_pos[0]:.3f}")
if not (xmin <= ad_gallery_east_pos[0] <= xmax):
    fail(f"gallery ad frame outside gameplay X bounds: {ad_gallery_east_pos[0]:.3f}")

ad_meshes=[]
ad_meshes.extend(add_ad_frame(
    "NAVE_WEST",
    ad_nave_west_pos,
    "X",(1.60,0.90),"ad_frame_nave_west"
))
ad_meshes.extend(add_ad_frame(
    "GALLERY_EAST",
    ad_gallery_east_pos,
    "X",(1.40,0.80),"ad_frame_gallery_east"
))
radio=add_box(
    "SANCTUM_AD_RADIO_UNDERCROFT",
    ad_radio_pos,
    (0.58,0.34,0.42),
    METAL,"spatial_radio_ad",False
)
radio["xziel_ad_surface_id"]="radio_ad_undercroft"
radio["xziel_audio_radius_m"]=7.5
radio["xziel_max_clip_seconds"]=15
ad_meshes.append(radio)

# Gameplay markers remain sidecar-authoritative rather than collision geometry.
def world_from_fraction(floor_id,fx,fy,z_extra=0.0):
    if floor_id=="floor_minus_1":
        z=lower_z+z_extra
        return [ic.x+fx*(bx1-bx0)*0.5,ic.y+fy*(by1-by0)*0.5,z]
    if floor_id=="floor_1":
        z=upper_z+z_extra
        return [ic.x+fx*hx,ic.y+fy*hy,z]
    return [ic.x+fx*hx,ic.y+fy*hy,floor_z+z_extra]

entities=[]
for spec in layout.get("gameplay_entities",[]):
    fx,fy=spec["anchor_fraction"]
    entities.append({
        **spec,
        "world_position":world_from_fraction(spec["floor"],float(fx),float(fy),0.35),
    })

ad_manifest={
    "schema_version":1,
    "map_id":layout["map_id"],
    "policy":layout["ad_system"]["principles"],
    "content_adapter_state":"house_or_direct_sponsor_only_until_provider_policy_adapter",
    "placements":[
        {
            **p,
            "world_position":(
                list(ad_nave_west_pos) if p["id"]=="ad_frame_nave_west"
                else list(ad_gallery_east_pos) if p["id"]=="ad_frame_gallery_east"
                else list(ad_radio_pos)
            )
        }
        for p in layout["ad_system"]["placements"]
    ],
}
(VERT_OUT/"sanctum-ad-surfaces.json").write_text(json.dumps(ad_manifest,indent=2),encoding="utf-8")

gameplay_manifest={
    "schema_version":1,
    "map_id":layout["map_id"],
    "floor_heights_m":{"undercroft":lower_z,"nave":floor_z,"gallery":upper_z},
    "connections":layout["connections"],
    "entities":entities,
    "authoritative_design":"docs/sanctum-vertical-layout.v1.json",
}
(VERT_OUT/"sanctum-gameplay-entities.json").write_text(json.dumps(gameplay_manifest,indent=2),encoding="utf-8")

# Material/night blockout proof.
scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=960
scene.render.resolution_y=600
scene.render.resolution_percentage=100
if scene.world is None:
    scene.world=bpy.data.worlds.new("SANCTUM_VERTICAL_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.004,0.006,0.012,1.0)
    bg.inputs["Strength"].default_value=0.22

# Add a few proof-only lights; not exported to runtime GLB.
proof_lights=[]
def point_light(name,location,energy,color,cast_shadow=True):
    ld=bpy.data.lights.new(name+"_DATA","POINT")
    ld.energy=energy
    ld.color=color
    ld.shadow_soft_size=0.75
    ld.use_shadow=bool(cast_shadow)
    lo=bpy.data.objects.new(name,ld)
    scene.collection.objects.link(lo)
    lo.location=Vector(location)
    proof_lights.append(lo)

point_light("SANCTUM_PROOF_UPPER_LIGHT",(ic.x,gallery_y0+2.0,upper_z+1.8),260,(0.28,0.42,0.68))
point_light("SANCTUM_PROOF_UNDERCROFT_LIGHT",(ic.x,ic.y+hy*0.12,lower_z+1.6),220,(0.80,0.20,0.06))
# Warm nave pools + restrained cool altar/window fill. Proof-only; runtime light
# authoring remains separate from navigation/collision.
for idx,frac in enumerate((-0.42,-0.18,0.08,0.34),1):
    y=ic.y+hy*frac
    point_light(f"SANCTUM_PROOF_NAVE_WARM_L_{idx}",(ic.x-hx*0.58,y,floor_z+2.3),150,(1.0,0.31,0.08),False)
    point_light(f"SANCTUM_PROOF_NAVE_WARM_R_{idx}",(ic.x+hx*0.58,y,floor_z+2.3),150,(1.0,0.31,0.08),False)
point_light("SANCTUM_PROOF_ALTAR_COOL",(ic.x,ic.y+hy*0.62,floor_z+5.2),300,(0.20,0.34,0.66),False)

cam=ensure_camera(scene)
eye=1.88
cam.data.lens=31.0
def point(cam,target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def render(name,pos,look):
    cam.location=Vector(pos)
    point(cam,look)
    scene.render.filepath=str(VERT_OUT/name)
    bpy.ops.render.render(write_still=True)
    p=VERT_OUT/name
    if not p.is_file() or p.stat().st_size<4000:
        fail(f"proof render failed {name}")
    return {"name":name,"bytes":p.stat().st_size}

renders=[
    render("01-nave-sees-upper-gallery.png",
           (ic.x,ic.y-hy*0.76,floor_z+eye),
           (ic.x,ic.y+hy*0.58,floor_z+1.72)),
    render("02-upper-gallery-player-view.png",
           (ic.x-gallery_x+0.25,gallery_y0+2.6,upper_z+eye),
           (ic.x+gallery_x-0.25,ic.y+0.25,upper_z+1.05)),
    render("03-upper-east-bailout.png",
           (ic.x+gallery_x-0.25,ic.y+1.35,upper_z+eye),
           (ic.x,ic.y+hy*0.05,floor_z+0.8)),
    render("04-undercroft-power-loop.png",
           (ic.x-4.2,by0+1.3,lower_z+eye),
           (ic.x,ic.y+hy*0.12,lower_z+1.1)),
    render("05-undercroft-shortcut.png",
           (ic.x+3.2,by1-1.4,lower_z+eye),
           ((right_x0+right_x1)*0.5,right_hole_center_y,floor_z+0.5)),
    render("06-diegetic-ad-frame.png",
           (ic.x-hx*0.55,ic.y-hy*0.08,floor_z+eye),
           Vector(ad_nave_west_pos)),
]

export_objects=[
    *base_export,
    *floor_parts,
    *vertical_meshes,
    power_proxy,
    *ad_meshes,
]
# Deduplicate object references while preserving order.
seen=set()
export_objects=[o for o in export_objects if o and not (o.name in seen or seen.add(o.name))]

for obj in bpy.context.selected_objects:
    obj.select_set(False)
for obj in export_objects:
    if obj.type=="MESH":
        obj.hide_render=False
        obj.hide_viewport=False
        obj.select_set(True)
if not export_objects:
    fail("no export objects")
bpy.context.view_layer.objects.active=next(o for o in export_objects if o.type=="MESH")

glb=VERT_OUT/"sanctum-vertical-blockout.glb"
bpy.ops.export_scene.gltf(
    filepath=str(glb),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_extras=True,
)
if not glb.is_file() or glb.stat().st_size<1000000:
    fail("vertical GLB export failed")

stats=mesh_stats([o for o in export_objects if o.type=="MESH"])
report={
    "status":"PASS",
    "stage":"vertical-gameplay-blockout-v1",
    "integration_status":"PLAYABLE_BLOCKOUT_REQUIRES_RUNTIME_PORTAL_TEST",
    "design_layout":str(LAYOUT_PATH),
    "floor_heights_m":{"undercroft":lower_z,"nave":floor_z,"gallery":upper_z},
    "vertical_span_m":upper_z-lower_z,
    "main_floor_bounds":[[xmin,ymin,floor_z],[xmax,ymax,floor_z]],
    "undercroft_bounds":[[bx0,by0,lower_z],[bx1,by1,lower_z+wall_h]],
    "gallery":{"x_offset":gallery_x,"y0":gallery_y0,"y1":gallery_y1,"width":gallery_w},
    "floor_openings":{
        "west":[left_x0,left_x1,left_y0,left_y1],
        "east":[right_x0,right_x1,right_y0,right_y1],
    },
    "connections":[
        "SANCTUM_UPPER_RAMP_WEST",
        "SANCTUM_UPPER_RAMP_EAST",
        "SANCTUM_UNDERCROFT_RAMP_WEST",
        "SANCTUM_UNDERCROFT_RAMP_EAST_SHORTCUT",
    ],
    "ad_surface_count":3,
    "ad_manifest":"sanctum-ad-surfaces.json",
    "gameplay_manifest":"sanctum-gameplay-entities.json",
    "proof_camera":{"eye_height_m":eye,"lens_mm":31.0,"primary_view":"raised_main_door"},
    "renders":renders,
    "stats":stats,
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size,
}
(VERT_OUT/"vertical-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")

print("SANCTUM_VERTICAL_BLOCKOUT_PASS")
print(json.dumps({
    "floor_heights_m":report["floor_heights_m"],
    "vertical_span_m":report["vertical_span_m"],
    "connections":len(report["connections"]),
    "ad_surface_count":report["ad_surface_count"],
    "vertices":stats["vertices"],
    "polygons":stats["polygons"],
    "glb_bytes":report["glb_bytes"],
},indent=2))
