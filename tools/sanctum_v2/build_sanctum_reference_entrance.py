import bpy
import json
import math
import os
import runpy
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

OUT=Path(os.environ.get("SANCTUM_REFERENCE_ENTRANCE_OUT","sanctum-reference-entrance-probe"))
OUT.mkdir(parents=True,exist_ok=True)
TARGET_PATH=Path(os.environ.get("SANCTUM_ENTRANCE_TARGET","docs/sanctum-entrance-reference-target.v1.json"))
target=json.loads(TARGET_PATH.read_text(encoding="utf-8"))

# Start from the latest proven multilevel + industrial/PBR stack.
state=runpy.run_path("tools/sanctum_v2/dress_sanctum_industrial_undercroft.py")
scene=state["scene"]
vertical=state["state"]
ic=state["ic"]
hy=state["hy"]
floor_z=state["floor_z"]
lower_z=state["lower_z"]
upper_z=state["upper_z"]
base_export=list(state["export_objects"])
mesh_stats=state["mesh_stats"]
ensure_camera=state["ensure_camera"]

half_l=vertical["half_l"]
xmin=vertical["xmin"]; xmax=vertical["xmax"]
ymin=vertical["ymin"]; ymax=vertical["ymax"]
STONE=vertical["STONE"]
add_box=vertical["add_box"]

def fail(msg):
    raise SystemExit("SANCTUM_REFERENCE_ENTRANCE_FAIL: "+msg)

def principled(mat):
    mat.use_nodes=True
    return mat.node_tree.nodes.get("Principled BSDF")

def new_material(name,base,roughness=0.45,metallic=0.0):
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    bsdf=principled(mat)
    if bsdf:
        bsdf.inputs["Base Color"].default_value=(*base,1.0)
        bsdf.inputs["Roughness"].default_value=roughness
        bsdf.inputs["Metallic"].default_value=metallic
    return mat

def make_dark_oak():
    mat=bpy.data.materials.get("SANCTUM_REF_DARK_OAK") or bpy.data.materials.new("SANCTUM_REF_DARK_OAK")
    mat.use_nodes=True
    nt=mat.node_tree
    nt.nodes.clear()
    out=nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf=nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex=nt.nodes.new("ShaderNodeTexCoord")
    mapping=nt.nodes.new("ShaderNodeMapping")
    noise=nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value=5.5
    noise.inputs["Detail"].default_value=7.0
    noise.inputs["Roughness"].default_value=0.72
    sep=nt.nodes.new("ShaderNodeSeparateXYZ")
    wave=nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type="BANDS"; wave.bands_direction="X"
    wave.inputs["Scale"].default_value=8.0
    wave.inputs["Distortion"].default_value=5.0
    wave.inputs["Detail"].default_value=5.0
    mix=nt.nodes.new("ShaderNodeMixRGB"); mix.blend_type="MULTIPLY"; mix.inputs[0].default_value=0.62
    ramp=nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color=(0.025,0.008,0.003,1)
    ramp.color_ramp.elements[1].color=(0.25,0.075,0.018,1)
    bump=nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value=0.22; bump.inputs["Distance"].default_value=0.09
    nt.links.new(tex.outputs["Generated"],mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"],noise.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"],wave.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"],mix.inputs[1])
    nt.links.new(wave.outputs["Color"],mix.inputs[2])
    nt.links.new(mix.outputs["Color"],ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"],bsdf.inputs["Base Color"])
    nt.links.new(noise.outputs["Fac"],bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value=0.38
    nt.links.new(bsdf.outputs["BSDF"],out.inputs["Surface"])
    return mat

def make_cloth():
    mat=new_material("SANCTUM_REF_BURGUNDY",(0.18,0.008,0.012),0.64,0.0)
    nt=mat.node_tree; bsdf=nt.nodes.get("Principled BSDF")
    tex=nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value=55.0; tex.inputs["Detail"].default_value=2.0
    bump=nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value=0.10; bump.inputs["Distance"].default_value=0.025
    nt.links.new(tex.outputs["Fac"],bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    return mat

def make_wet_floor():
    mat=bpy.data.materials.get("SANCTUM_REF_WET_FLAGSTONE") or bpy.data.materials.new("SANCTUM_REF_WET_FLAGSTONE")
    mat.use_nodes=True
    nt=mat.node_tree
    nt.nodes.clear()
    out=nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf=nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex=nt.nodes.new("ShaderNodeTexCoord")
    mapping=nt.nodes.new("ShaderNodeMapping")
    brick=nt.nodes.new("ShaderNodeTexBrick")
    brick.inputs["Color1"].default_value=(0.055,0.043,0.035,1)
    brick.inputs["Color2"].default_value=(0.16,0.11,0.075,1)
    brick.inputs["Mortar"].default_value=(0.012,0.010,0.009,1)
    brick.inputs["Scale"].default_value=4.2
    brick.inputs["Mortar Size"].default_value=0.035
    brick.offset=0.0
    noise=nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value=2.4
    noise.inputs["Detail"].default_value=7.0
    noise.inputs["Roughness"].default_value=0.75
    mix=nt.nodes.new("ShaderNodeMixRGB"); mix.blend_type="MULTIPLY"; mix.inputs[0].default_value=0.56
    rough_ramp=nt.nodes.new("ShaderNodeValToRGB")
    rough_ramp.color_ramp.elements[0].position=0.34
    rough_ramp.color_ramp.elements[0].color=(0.13,0.13,0.13,1)
    rough_ramp.color_ramp.elements[1].position=0.67
    rough_ramp.color_ramp.elements[1].color=(0.56,0.56,0.56,1)
    bump=nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value=0.30; bump.inputs["Distance"].default_value=0.10
    nt.links.new(tex.outputs["Generated"],mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"],brick.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"],noise.inputs["Vector"])
    nt.links.new(brick.outputs["Color"],mix.inputs[1])
    nt.links.new(noise.outputs["Fac"],mix.inputs[2])
    nt.links.new(mix.outputs["Color"],bsdf.inputs["Base Color"])
    nt.links.new(noise.outputs["Fac"],rough_ramp.inputs["Fac"])
    nt.links.new(rough_ramp.outputs["Color"],bsdf.inputs["Roughness"])
    nt.links.new(brick.outputs["Fac"],bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"],out.inputs["Surface"])
    return mat

def make_stained_glass():
    mat=bpy.data.materials.get("SANCTUM_REF_STAINED_GLASS") or bpy.data.materials.new("SANCTUM_REF_STAINED_GLASS")
    mat.use_nodes=True
    nt=mat.node_tree
    nt.nodes.clear()
    out=nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf=nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex=nt.nodes.new("ShaderNodeTexCoord")
    vor=nt.nodes.new("ShaderNodeTexVoronoi"); vor.feature="F1"; vor.distance="EUCLIDEAN"; vor.inputs["Scale"].default_value=10.0
    edge=nt.nodes.new("ShaderNodeTexVoronoi"); edge.feature="DISTANCE_TO_EDGE"; edge.inputs["Scale"].default_value=10.0
    edge_ramp=nt.nodes.new("ShaderNodeValToRGB")
    edge_ramp.color_ramp.elements[0].position=0.018
    edge_ramp.color_ramp.elements[0].color=(0.005,0.004,0.004,1)
    edge_ramp.color_ramp.elements[1].position=0.045
    edge_ramp.color_ramp.elements[1].color=(1,1,1,1)
    hue=nt.nodes.new("ShaderNodeHueSaturation"); hue.inputs["Saturation"].default_value=1.35; hue.inputs["Value"].default_value=0.85
    mult=nt.nodes.new("ShaderNodeMixRGB"); mult.blend_type="MULTIPLY"; mult.inputs[0].default_value=1.0
    nt.links.new(tex.outputs["Generated"],vor.inputs["Vector"])
    nt.links.new(tex.outputs["Generated"],edge.inputs["Vector"])
    nt.links.new(vor.outputs["Color"],hue.inputs["Color"])
    nt.links.new(edge.outputs["Distance"],edge_ramp.inputs["Fac"])
    nt.links.new(hue.outputs["Color"],mult.inputs[1])
    nt.links.new(edge_ramp.outputs["Color"],mult.inputs[2])
    nt.links.new(mult.outputs["Color"],bsdf.inputs["Base Color"])
    if "Emission Color" in bsdf.inputs:
        nt.links.new(mult.outputs["Color"],bsdf.inputs["Emission Color"])
    elif "Emission" in bsdf.inputs:
        nt.links.new(mult.outputs["Color"],bsdf.inputs["Emission"])
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value=1.8
    bsdf.inputs["Roughness"].default_value=0.22
    nt.links.new(bsdf.outputs["BSDF"],out.inputs["Surface"])
    return mat

OAK=make_dark_oak()
BURGUNDY=make_cloth()
GOLD=new_material("SANCTUM_REF_GOLD",(0.42,0.20,0.035),0.25,0.82)
WET_STONE=make_wet_floor()
GLASS=make_stained_glass()

def bevel(obj,amount=0.05,segments=3):
    if obj.type!="MESH":
        return obj
    mod=obj.modifiers.new("SANCTUM_REF_BEVEL","BEVEL")
    mod.width=amount
    mod.segments=segments
    mod.limit_method="ANGLE"
    bpy.context.view_layer.objects.active=obj
    obj.select_set(True)
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception:
        pass
    obj.select_set(False)
    return obj

def box(name,center,size,mat,role="hero_reference",collision=True,bev=0.035):
    obj=add_box(name,center,size,mat,role,collision)
    if bev>0:
        bevel(obj,bev,3)
    return obj

def curve_frame(name,points,mat,bevel_depth=0.035,role="altar_detail"):
    data=bpy.data.curves.new(name+"_CURVE","CURVE")
    data.dimensions="3D"
    data.resolution_u=2
    data.bevel_depth=bevel_depth
    data.bevel_resolution=3
    spline=data.splines.new("POLY")
    spline.points.add(len(points)-1)
    for p,co in zip(spline.points,points):
        p.co=(*co,1.0)
    obj=bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj["xziel_role"]=role
    obj["xziel_collision"]=False
    # Convert to mesh so glTF receives explicit geometry.
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True); bpy.context.view_layer.objects.active=obj
    bpy.ops.object.convert(target="MESH")
    return bpy.context.view_layer.objects.active

def pointed_arch_points(cx,y,z0,width,height):
    w=width*0.5
    shoulder=z0+height*0.52
    apex=z0+height
    return [
        (cx-w,y,z0),
        (cx-w,y,shoulder),
        (cx-w*0.78,y,shoulder+height*0.12),
        (cx-w*0.45,y,shoulder+height*0.28),
        (cx,y,apex),
        (cx+w*0.45,y,shoulder+height*0.28),
        (cx+w*0.78,y,shoulder+height*0.12),
        (cx+w,y,shoulder),
        (cx+w,y,z0),
    ]

# Replace the plain proof look of the main nave floor with a wet worn flagstone PBR material.
for obj in scene.objects:
    if obj.type=="MESH" and (obj.name.startswith("SANCTUM_MAIN_FLOOR_") or obj.name=="SANCTUM_GAMEPLAY_FLOOR"):
        obj.data.materials.clear()
        obj.data.materials.append(WET_STONE)

# Procedural Gothic altar from the user's orthographic reference sheet.
altar_y=ic.y+half_l*0.49
step_z=floor_z
altar=[]
step_specs=[
    (6.1,2.25,0.18),
    (5.72,1.92,0.18),
    (5.34,1.62,0.18),
]
acc=0.0
for i,(w,d,h) in enumerate(step_specs,1):
    o=box(f"SANCTUM_REF_ALTAR_STEP_{i}",(ic.x,altar_y,step_z+acc+h*0.5),(w,d,h),STONE,"hero_altar_step",True,0.025)
    altar.append(o); acc+=h

body_bottom=step_z+acc
body_h=1.22
body_d=1.02
body_w=4.92
body=box("SANCTUM_REF_ALTAR_BODY",(ic.x,altar_y,body_bottom+body_h*0.5),(body_w,body_d,body_h),OAK,"hero_altar_body",True,0.055)
altar.append(body)

# Side towers, posts and top cornice.
for sign in (-1,1):
    x=ic.x+sign*2.12
    altar.append(box(f"SANCTUM_REF_ALTAR_SIDE_{'L' if sign<0 else 'R'}",(x,altar_y,body_bottom+0.66),(0.78,1.20,1.32),OAK,"hero_altar_body",True,0.055))
    for px in (ic.x+sign*1.72,ic.x+sign*2.46):
        altar.append(box(f"SANCTUM_REF_ALTAR_POST_{len(altar):02d}",(px,altar_y-body_d*0.48-0.03,body_bottom+0.72),(0.20,0.22,1.44),OAK,"hero_altar_detail",False,0.03))
        altar.append(box(f"SANCTUM_REF_ALTAR_CAP_{len(altar):02d}",(px,altar_y-body_d*0.48-0.03,body_bottom+1.48),(0.31,0.29,0.12),OAK,"hero_altar_detail",False,0.025))
altar.append(box("SANCTUM_REF_ALTAR_CORNICE",(ic.x,altar_y,body_bottom+1.37),(5.34,1.19,0.22),OAK,"hero_altar_detail",False,0.04))

# Pointed Gothic panel tracery on the front face.
front_y=altar_y-body_d*0.51-0.04
for x in (ic.x-2.08,ic.x-1.25,ic.x+1.25,ic.x+2.08):
    altar.append(curve_frame(
        f"SANCTUM_REF_ALTAR_ARCH_{len(altar):02d}",
        pointed_arch_points(x,front_y,body_bottom+0.20,0.58,0.86),
        GOLD,0.026,"hero_altar_carving"
    ))

# Burgundy frontal cloth and gold cross.
cloth=box("SANCTUM_REF_ALTAR_CLOTH",(ic.x,front_y-0.035,body_bottom+0.74),(1.70,0.045,1.08),BURGUNDY,"hero_altar_cloth",False,0.015)
altar.append(cloth)
altar.append(box("SANCTUM_REF_ALTAR_GOLD_CROSS_V",(ic.x,front_y-0.066,body_bottom+0.76),(0.075,0.035,0.47),GOLD,"hero_altar_detail",False,0.01))
altar.append(box("SANCTUM_REF_ALTAR_GOLD_CROSS_H",(ic.x,front_y-0.067,body_bottom+0.82),(0.31,0.035,0.075),GOLD,"hero_altar_detail",False,0.01))

top_z=body_bottom+1.52

# Tall altar cross behind the book/candles.
cross_y=altar_y+0.10
altar.append(box("SANCTUM_REF_ALTAR_CROSS_V",(ic.x,cross_y,top_z+0.96),(0.12,0.12,1.82),GOLD,"hero_altar_detail",False,0.018))
altar.append(box("SANCTUM_REF_ALTAR_CROSS_H",(ic.x,cross_y,top_z+1.15),(0.88,0.12,0.12),GOLD,"hero_altar_detail",False,0.018))
altar.append(box("SANCTUM_REF_ALTAR_CROSS_BASE",(ic.x,cross_y,top_z+0.08),(0.52,0.38,0.16),OAK,"hero_altar_detail",False,0.025))

# Open book proxy: two page blocks on a small dark stand.
PAGE=new_material("SANCTUM_REF_PAGES",(0.72,0.60,0.43),0.67,0.0)
book_l=box("SANCTUM_REF_ALTAR_BOOK_L",(ic.x-0.23,altar_y-0.22,top_z+0.13),(0.44,0.36,0.055),PAGE,"hero_altar_detail",False,0.012)
book_r=box("SANCTUM_REF_ALTAR_BOOK_R",(ic.x+0.23,altar_y-0.22,top_z+0.13),(0.44,0.36,0.055),PAGE,"hero_altar_detail",False,0.012)
book_l.rotation_euler.y=math.radians(-8); book_r.rotation_euler.y=math.radians(8)
altar.extend([book_l,book_r])

# Candles on the altar top, cloned from the already-verified CC0 candle template.
candle_template=bpy.data.objects.get("SANCTUM_CANDLE_TEMPLATE")
altar_candles=[]
if candle_template:
    for idx,(xoff,yoff,scale) in enumerate([
        (-2.15,-0.10,0.70),(-1.82,0.00,0.85),(-1.48,-0.08,0.72),
        (-0.92,0.04,0.60),(0.92,0.04,0.60),
        (1.48,-0.08,0.72),(1.82,0.00,0.85),(2.15,-0.10,0.70),
    ],1):
        obj=candle_template.copy(); obj.data=candle_template.data
        obj.name=f"SANCTUM_ALTAR_CANDLE_{idx:02d}"
        scene.collection.objects.link(obj)
        obj.hide_render=False; obj.hide_viewport=False; obj.hide_set(False)
        obj.scale=(scale,scale,scale)
        obj.location=(ic.x+xoff,altar_y+yoff,top_z+0.03)
        # Drop bottom onto altar top.
        bpy.context.view_layer.update()
        pts=[obj.matrix_world@Vector(c) for c in obj.bound_box]
        obj.location.z += top_z-min(p.z for p in pts)
        obj["xziel_role"]="hero_altar_candle"
        obj["source_license"]="CC0"
        altar_candles.append(obj)

altar.extend(altar_candles)

# Stained-glass apse: five tall upper lancets + three lower lancets.
def make_lancet(name,cx,y,z0,width,height):
    verts=[
        (cx-width*0.5,y,z0),
        (cx+width*0.5,y,z0),
        (cx+width*0.5,y,z0+height*0.77),
        (cx,y,z0+height),
        (cx-width*0.5,y,z0+height*0.77),
    ]
    mesh=bpy.data.meshes.new(name+"_MESH")
    mesh.from_pydata(verts,[],[(0,1,2,3,4)])
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(obj)
    obj.data.materials.append(GLASS)
    obj["xziel_role"]="stained_glass"
    obj["xziel_collision"]=False
    frame=curve_frame(name+"_FRAME",pointed_arch_points(cx,y-0.025,z0,width,height),GOLD,0.035,"stained_glass_frame")
    return [obj,frame]

glass=[]
glass_y=min(ymax-0.20,ic.y+half_l*0.64)
for i,xoff in enumerate((-3.15,-1.58,0.0,1.58,3.15),1):
    glass.extend(make_lancet(f"SANCTUM_STAINED_UPPER_{i}",ic.x+xoff,glass_y,floor_z+4.15,1.08,4.75))
for i,xoff in enumerate((-2.25,0.0,2.25),1):
    glass.extend(make_lancet(f"SANCTUM_STAINED_LOWER_{i}",ic.x+xoff,glass_y-0.03,floor_z+2.05,0.98,1.88))

# Safety: altar remains in the far end-zone; preserve the main training loop.
for obj in altar:
    if obj.type!="MESH":
        continue
    pts=[obj.matrix_world@Vector(c) for c in obj.bound_box]
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    if mn.x < xmin-0.10 or mx.x > xmax+0.10:
        fail(f"altar crosses nave X envelope: {obj.name}")
    if mn.y < ic.y+hy*0.17:
        fail(f"altar intrudes primary nave loop: {obj.name} minY={mn.y:.3f}")
    if mx.y > ymax+1.25:
        fail(f"altar extends beyond apse envelope: {obj.name} maxY={mx.y:.3f}")

# Lighting tuned to the supplied reference: warm candle layers + cool glass.
def point_light(name,loc,energy,color,radius=0.55):
    ld=bpy.data.lights.new(name+"_DATA","POINT")
    ld.energy=energy; ld.color=color; ld.shadow_soft_size=radius
    o=bpy.data.objects.new(name,ld); scene.collection.objects.link(o); o.location=Vector(loc)
    return o

for idx,xoff in enumerate((-2.3,-1.55,-0.7,0.7,1.55,2.3),1):
    point_light(f"SANCTUM_REF_ALTAR_WARM_{idx}",(ic.x+xoff,altar_y-0.35,top_z+0.55),95,(1.0,0.34,0.08),0.42)

for idx,(yfrac,energy) in enumerate(((-0.30,75),(-0.05,85),(0.18,90)),1):
    y=ic.y+hy*yfrac
    point_light(f"SANCTUM_REF_AISLE_L_{idx}",(ic.x-3.35,y,floor_z+1.45),energy,(1.0,0.31,0.055),0.65)
    point_light(f"SANCTUM_REF_AISLE_R_{idx}",(ic.x+3.35,y,floor_z+1.45),energy,(1.0,0.31,0.055),0.65)

# Cool fill from the apse windows.
ld=bpy.data.lights.new("SANCTUM_REF_GLASS_FILL_DATA","AREA")
ld.energy=780; ld.shape="RECTANGLE"; ld.size=7.5; ld.color=(0.16,0.32,0.72)
lo=bpy.data.objects.new("SANCTUM_REF_GLASS_FILL",ld); scene.collection.objects.link(lo)
lo.location=(ic.x,glass_y-0.35,floor_z+7.3)
lo.rotation_euler=(math.radians(90),0,0)

scene.render.engine="BLENDER_EEVEE"
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=960
scene.render.resolution_y=720
scene.render.resolution_percentage=100
if scene.world is None:
    scene.world=bpy.data.worlds.new("SANCTUM_REFERENCE_WORLD")
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value=(0.0025,0.0035,0.006,1)
    bg.inputs["Strength"].default_value=0.12

cam=ensure_camera(scene)
cam.data.lens=float(target["camera"]["lens_mm_initial"])
cam.data.sensor_width=36.0
eye=floor_z+float(target["camera"]["eye_height_m"])
entrance_y=ymin+0.58
pitch=math.radians(float(target["camera"]["pitch_up_degrees_initial"]))
distance=max(1.0,altar_y-entrance_y)
look_z=eye+math.tan(pitch)*distance
cam.location=Vector((ic.x,entrance_y,eye))
cam.rotation_euler=(Vector((ic.x,altar_y,look_z))-cam.location).to_track_quat("-Z","Y").to_euler()

def screen_bbox(objects):
    xs=[]; ys=[]
    for obj in objects:
        if obj.type!="MESH":
            continue
        for c in obj.bound_box:
            p=world_to_camera_view(scene,cam,obj.matrix_world@Vector(c))
            if p.z>0:
                xs.append(float(p.x)); ys.append(float(p.y))
    if not xs:
        fail("no projected points for screen bbox")
    return [min(xs),min(ys),max(xs),max(ys)]

altar_bbox=screen_bbox(altar)
altar_center=((altar_bbox[0]+altar_bbox[2])*0.5,(altar_bbox[1]+altar_bbox[3])*0.5)
altar_width=altar_bbox[2]-altar_bbox[0]
glass_bbox=screen_bbox(glass)

left_pews=[o for o in scene.objects if o.type=="MESH" and o.name.startswith("SANCTUM_PEW_") and o.name.endswith("_L")]
right_pews=[o for o in scene.objects if o.type=="MESH" and o.name.startswith("SANCTUM_PEW_") and o.name.endswith("_R")]
if not left_pews or not right_pews:
    fail("verified pew banks missing")
left_bbox=screen_bbox(left_pews); right_bbox=screen_bbox(right_pews)
left_c=(left_bbox[0]+left_bbox[2])*0.5
right_c=(right_bbox[0]+right_bbox[2])*0.5
pew_mirror_error=abs((1.0-left_c)-right_c)

# Convert target altar bbox from top-origin to Blender bottom-origin.
tb=target["composition"]["altar_bbox_top_origin_norm"]
target_altar_center=( (tb[0]+tb[2])*0.5, 1.0-(tb[1]+tb[3])*0.5 )
xtol=float(target["hard_gates"]["altar_screen_center_x_error_max"])
ytol=float(target["hard_gates"]["altar_screen_center_y_error_max"])
wr=target["composition"]["altar_width_range_norm"]

if abs(cam.location.x-ic.x)>float(target["hard_gates"]["camera_center_offset_m_max"]):
    fail("entrance camera is not centered on nave")
if abs(altar_center[0]-target_altar_center[0])>xtol:
    fail(f"altar screen X mismatch: {altar_center[0]:.3f} target {target_altar_center[0]:.3f}")
if abs(altar_center[1]-target_altar_center[1])>ytol:
    fail(f"altar screen Y mismatch: {altar_center[1]:.3f} target {target_altar_center[1]:.3f}")
if not (float(wr[0])<=altar_width<=float(wr[1])):
    fail(f"altar screen width mismatch: {altar_width:.3f} target {wr}")
if pew_mirror_error>float(target["hard_gates"]["pew_mirror_screen_error_max"]):
    fail(f"pew banks not screen-symmetric: {pew_mirror_error:.3f}")
if (glass_bbox[0]+glass_bbox[2])*0.5 < 0.43 or (glass_bbox[0]+glass_bbox[2])*0.5 > 0.57:
    fail("stained-glass group not centered")
if glass_bbox[3] < 0.78:
    fail(f"stained glass does not dominate upper frame: ymax={glass_bbox[3]:.3f}")

scene.render.filepath=str(OUT/"00-front-door-reference-match.png")
bpy.ops.render.render(write_still=True)
proof=OUT/"00-front-door-reference-match.png"
if not proof.is_file() or proof.stat().st_size<12000:
    fail("front-door reference proof render failed")

# Two supporting proof views.
def point_at(pos,target_pos):
    cam.location=Vector(pos)
    cam.rotation_euler=(Vector(target_pos)-cam.location).to_track_quat("-Z","Y").to_euler()

renders=[{"name":proof.name,"bytes":proof.stat().st_size}]
point_at((ic.x-3.7,altar_y-4.8,floor_z+1.82),(ic.x,altar_y,floor_z+1.25))
scene.render.filepath=str(OUT/"01-reference-altar-detail.png"); bpy.ops.render.render(write_still=True)
renders.append({"name":"01-reference-altar-detail.png","bytes":(OUT/"01-reference-altar-detail.png").stat().st_size})
point_at((ic.x,ic.y-hy*0.20,floor_z+1.80),(ic.x,glass_y,floor_z+6.1))
scene.render.filepath=str(OUT/"02-reference-stained-glass.png"); bpy.ops.render.render(write_still=True)
renders.append({"name":"02-reference-stained-glass.png","bytes":(OUT/"02-reference-stained-glass.png").stat().st_size})

# Restore entrance camera for report/export proof metadata.
cam.location=Vector((ic.x,entrance_y,eye))
cam.rotation_euler=(Vector((ic.x,altar_y,look_z))-cam.location).to_track_quat("-Z","Y").to_euler()

export_objects=[*base_export,*altar,*glass]
seen=set(); export_objects=[o for o in export_objects if o and not (o.name in seen or seen.add(o.name))]
for o in bpy.context.selected_objects:
    o.select_set(False)
for o in export_objects:
    if o.type=="MESH":
        o.hide_viewport=False; o.hide_render=False; o.select_set(True)
bpy.context.view_layer.objects.active=next(o for o in export_objects if o.type=="MESH")

glb=OUT/"sanctum-reference-entrance.glb"
bpy.ops.export_scene.gltf(
    filepath=str(glb),export_format="GLB",use_selection=True,export_apply=True,export_extras=True
)
if not glb.is_file() or glb.stat().st_size<1000000:
    fail("reference entrance GLB export failed")

stats=mesh_stats([o for o in export_objects if o.type=="MESH"])
report={
    "status":"PASS",
    "stage":"front-door-reference-match-v1",
    "target":str(TARGET_PATH),
    "source_image_stored_in_repo":False,
    "camera":{
        "position":list(cam.location),
        "lens_mm":cam.data.lens,
        "eye_height_m":float(target["camera"]["eye_height_m"]),
        "pitch_up_degrees":float(target["camera"]["pitch_up_degrees_initial"]),
        "look_z":look_z,
    },
    "composition":{
        "altar_bbox_bottom_origin":altar_bbox,
        "altar_center_bottom_origin":altar_center,
        "altar_width_norm":altar_width,
        "target_altar_center_bottom_origin":target_altar_center,
        "stained_glass_bbox_bottom_origin":glass_bbox,
        "left_pew_bbox":left_bbox,
        "right_pew_bbox":right_bbox,
        "pew_mirror_error":pew_mirror_error,
    },
    "geometry":{
        "altar_objects":len(altar),
        "stained_glass_objects":len(glass),
        "pew_count":len(left_pews)+len(right_pews),
    },
    "renders":renders,
    "stats":stats,
    "glb":glb.name,
    "glb_bytes":glb.stat().st_size,
}
(OUT/"reference-entrance-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_REFERENCE_ENTRANCE_PASS")
print(json.dumps({
    "camera":report["camera"],
    "composition":report["composition"],
    "geometry":report["geometry"],
    "vertices":stats["vertices"],
    "polygons":stats["polygons"],
    "glb_bytes":report["glb_bytes"],
},indent=2))
