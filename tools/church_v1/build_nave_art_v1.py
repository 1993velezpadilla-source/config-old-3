import bpy
import math
import os
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("CHURCH_V1_OUT", ROOT / "church_v1/out"))
OUT.mkdir(parents=True, exist_ok=True)

# Fresh scene.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

art = bpy.data.collections.new("ART_PROTOTYPE_V1__MAIN_NAVE")
bpy.context.scene.collection.children.link(art)

def move_to(obj):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    art.objects.link(obj)
    obj["xziel_stage"] = "art_prototype_v1"

def mat_principled(name, base, rough=0.65, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    return m

def mat_procedural_stone():
    m = mat_principled("PBR_STONE_PROCEDURAL_V1", (0.16,0.17,0.18), 0.82, 0.0)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 4.0
    noise.inputs["Detail"].default_value = 7.0
    noise.inputs["Roughness"].default_value = 0.75
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.055,0.06,0.065,1)
    ramp.color_ramp.elements[1].color = (0.28,0.29,0.30,1)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.28
    bump.inputs["Distance"].default_value = 0.12
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m

def mat_procedural_wood():
    m = mat_principled("PBR_OLD_WOOD_PROCEDURAL_V1", (0.12,0.045,0.018), 0.58, 0.0)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 5.0
    noise.inputs["Roughness"].default_value = 0.68
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.025,0.008,0.003,1)
    ramp.color_ramp.elements[1].color = (0.22,0.07,0.018,1)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.08
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m

STONE = mat_procedural_stone()
WOOD = mat_procedural_wood()
IRON = mat_principled("PBR_IRON_PROCEDURAL_V1", (0.035,0.04,0.045), 0.38, 0.72)
BRASS = mat_principled("PBR_BRASS_PROCEDURAL_V1", (0.28,0.12,0.025), 0.32, 0.75)
WAX = mat_principled("PBR_WAX_PROCEDURAL_V1", (0.58,0.46,0.26), 0.48, 0.0)

def stained_material(name, color):
    m = mat_principled(name, color, 0.22, 0.0)
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*color,1.0)
        bsdf.inputs["Emission Strength"].default_value = 0.65
    elif "Emission" in bsdf.inputs:
        bsdf.inputs["Emission"].default_value = (*color,1.0)
    return m

GLASS_RED = stained_material("GLASS_STAINED_RED", (0.34,0.015,0.02))
GLASS_BLUE = stained_material("GLASS_STAINED_BLUE", (0.015,0.05,0.30))
GLASS_AMBER = stained_material("GLASS_STAINED_AMBER", (0.40,0.18,0.02))

def add_cube(name, loc, dims, material, bevel=0.06):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        mod = o.modifiers.new("EDGE_BEVEL", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=mod.name)
    o.data.materials.append(material)
    move_to(o)
    return o

def add_cylinder(name, loc, radius, depth, material, vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    move_to(o)
    return o

def add_curve(name, points, radius, material, resolution=4):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = resolution
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points)-1)
    for bp, p in zip(spline.bezier_points, points):
        bp.co = p
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    art.objects.link(obj)
    obj.data.materials.append(material)
    obj["xziel_stage"] = "art_prototype_v1"
    return obj

# Nave floor and raised altar.
add_cube("NAVE_FLOOR", (0,0,-0.18), (18.4,30.4,0.36), STONE, 0.10)
add_cube("ALTAR_DAIS_LOW", (0,11.6,0.16), (8.2,5.0,0.32), STONE, 0.10)
add_cube("ALTAR_DAIS_HIGH", (0,12.8,0.42), (5.8,2.6,0.34), STONE, 0.10)

# Wall bays: leave window gaps rather than one flat wall.
bay_centers = [-11.5,-7.5,-3.5,0.5,4.5,8.5]
for side in (-1,1):
    x = side * 9.0
    for i,y in enumerate(bay_centers):
        # Buttress/piers between windows.
        add_cube(f"SIDE_PIER_{side}_{i}", (x,y,3.6), (0.85,1.0,7.2), STONE, 0.09)
        # lower stone dado under window
        add_cube(f"SIDE_DADO_{side}_{i}", (x,y+1.75,1.0), (0.55,2.5,2.0), STONE, 0.07)
    # continuous upper wall band
    add_cube(f"SIDE_UPPER_BAND_{side}", (x,0,8.7), (0.55,30.0,1.25), STONE, 0.08)

# South entry wall and north apse wall.
add_cube("ENTRY_WALL_L", (-5.3,-15.0,3.4), (7.5,0.55,6.8), STONE, 0.08)
add_cube("ENTRY_WALL_R", (5.3,-15.0,3.4), (7.5,0.55,6.8), STONE, 0.08)
add_cube("ENTRY_LINTEL", (0,-15.0,7.8), (4.4,0.55,2.0), STONE, 0.08)
add_cube("APSE_BACK", (0,15.0,4.8), (18.0,0.6,9.6), STONE, 0.10)

# Compound Gothic columns down the nave.
column_y = [-10,-6,-2,2,6,10]
for side in (-1,1):
    x = side * 6.1
    for idx,y in enumerate(column_y):
        add_cylinder(f"COL_BASE_{side}_{idx}", (x,y,0.28), 0.68, 0.56, STONE, 28)
        add_cylinder(f"COL_SHAFT_{side}_{idx}", (x,y,3.35), 0.42, 6.1, STONE, 28)
        for a in range(4):
            ang = a * math.pi/2
            sx = x + math.cos(ang)*0.43
            sy = y + math.sin(ang)*0.43
            add_cylinder(f"COL_CLUSTER_{side}_{idx}_{a}", (sx,sy,3.2), 0.13, 5.8, STONE, 16)
        add_cube(f"COL_CAP_{side}_{idx}", (x,y,6.52), (1.4,1.4,0.32), STONE, 0.12)
        add_cube(f"COL_ABACUS_{side}_{idx}", (x,y,6.78), (1.05,1.05,0.22), STONE, 0.08)

# Pointed arcade arches along both sides: two quadratic-like Bezier segments.
for side in (-1,1):
    x = side * 6.1
    for i in range(len(column_y)-1):
        y0 = column_y[i]
        y1 = column_y[i+1]
        mid = (y0+y1)/2
        points = [
            (x, y0, 6.75),
            (x, mid-0.8, 8.1),
            (x, mid, 9.15),
            (x, mid+0.8, 8.1),
            (x, y1, 6.75),
        ]
        add_curve(f"ARCADE_{side}_{i}", points, 0.18, STONE)

# Transverse pointed ribs span the nave at each bay.
for idx,y in enumerate(column_y):
    pts = [
        (-6.1,y,6.8),
        (-3.5,y,8.8),
        (0,y,10.8),
        (3.5,y,8.8),
        (6.1,y,6.8),
    ]
    add_curve(f"VAULT_RIB_{idx}", pts, 0.16, STONE)

# Longitudinal ridge and secondary ribs.
add_curve("VAULT_RIDGE", [(0,-11,10.8),(0,0,11.05),(0,11,10.8)], 0.13, STONE)
for x in (-3.15,3.15):
    add_curve(f"VAULT_LONG_{x}", [(x,-11,8.9),(x,0,9.25),(x,11,8.9)], 0.10, STONE)

# Dark ceiling planes behind ribs.
ceiling = mat_principled("CEILING_DARK_STONE", (0.055,0.06,0.065), 0.9, 0.0)
roof_l = add_cube("CEILING_SLOPE_L", (-4.45,0,9.25), (9.4,29.5,0.26), ceiling, 0.04)
roof_l.rotation_euler[1] = math.radians(-18)
roof_r = add_cube("CEILING_SLOPE_R", (4.45,0,9.25), (9.4,29.5,0.26), ceiling, 0.04)
roof_r.rotation_euler[1] = math.radians(18)

# Gothic window proxies with stained panes and stone pointed frames.
window_y = [-9.5,-5.5,-1.5,2.5,6.5,10.5]
glass_cycle = [GLASS_BLUE, GLASS_RED, GLASS_AMBER]
for side in (-1,1):
    x = side * 8.70
    for i,y in enumerate(window_y):
        g = add_cube(f"STAINED_GLASS_{side}_{i}", (x,y,4.85), (0.06,2.25,4.3), glass_cycle[i%3], 0.0)
        # vertical mullion
        add_cube(f"WINDOW_MULLION_{side}_{i}", (x - side*0.05,y,4.85), (0.10,0.12,4.15), IRON, 0.02)
        # arch frame is in Y-Z plane at constant X
        pts = [
            (x-side*0.12,y-1.15,6.15),
            (x-side*0.12,y-0.75,6.85),
            (x-side*0.12,y,7.55),
            (x-side*0.12,y+0.75,6.85),
            (x-side*0.12,y+1.15,6.15),
        ]
        add_curve(f"WINDOW_ARCH_{side}_{i}", pts, 0.12, STONE)

# Pews: two banks, central aisle.
for row,y in enumerate([-10.0,-7.8,-5.6,-3.4,-1.2,1.0,3.2,5.4,7.6]):
    for side in (-1,1):
        x = side * 3.45
        add_cube(f"PEW_SEAT_{row}_{side}", (x,y,0.72), (4.8,0.72,0.18), WOOD, 0.08)
        back = add_cube(f"PEW_BACK_{row}_{side}", (x,y+0.30,1.42), (4.8,0.16,1.35), WOOD, 0.07)
        back.rotation_euler[0] = math.radians(-7)
        for lx in (-2.15,2.15):
            add_cube(f"PEW_LEG_{row}_{side}_{lx}", (x+lx,y,0.36), (0.18,0.55,0.72), WOOD, 0.04)

# Altar, reredos, cross and candles.
add_cube("ALTAR_TABLE", (0,12.4,1.25), (4.1,1.25,1.35), STONE, 0.12)
add_cube("ALTAR_FRONT_PANEL", (0,11.74,1.28), (3.2,0.12,0.95), BRASS, 0.04)
add_cube("REREDOS_CENTER", (0,14.52,4.5), (5.8,0.55,6.7), STONE, 0.14)
add_cube("REREDOS_LEFT", (-4.6,14.58,3.3), (2.8,0.45,4.3), STONE, 0.12)
add_cube("REREDOS_RIGHT", (4.6,14.58,3.3), (2.8,0.45,4.3), STONE, 0.12)
add_cube("ALTAR_CROSS_V", (0,14.15,5.35), (0.36,0.24,2.8), BRASS, 0.04)
add_cube("ALTAR_CROSS_H", (0,14.12,5.72), (1.75,0.24,0.36), BRASS, 0.04)

for i,x in enumerate((-1.45,-0.75,0.75,1.45)):
    add_cylinder(f"CANDLE_{i}", (x,11.95,2.16), 0.08, 0.62, WAX, 16)
    bpy.ops.object.light_add(type="POINT", location=(x,11.85,2.62))
    lamp=bpy.context.object
    lamp.name=f"CANDLE_LIGHT_{i}"
    lamp.data.energy=42
    lamp.data.color=(1.0,0.48,0.15)
    lamp.data.shadow_soft_size=0.55

# Hanging chandelier / central focal detail.
add_cylinder("CHANDELIER_STEM", (0,0,7.65), 0.06, 3.2, IRON, 16)
add_cylinder("CHANDELIER_RING", (0,0,6.12), 1.05, 0.10, IRON, 32)
for i in range(8):
    a = i * math.tau/8
    x,y = math.cos(a)*0.94, math.sin(a)*0.94
    add_cylinder(f"CHANDELIER_CANDLE_{i}", (x,y,6.38), 0.045, 0.34, WAX, 12)
    bpy.ops.object.light_add(type="POINT", location=(x,y,6.62))
    l=bpy.context.object
    l.data.energy=28
    l.data.color=(1.0,0.42,0.12)
    l.data.shadow_soft_size=0.38

# Entry doors.
door_mat = mat_principled("PBR_DARK_DOOR_WOOD", (0.045,0.012,0.006), 0.48, 0.0)
add_cube("ENTRY_DOOR_L", (-1.15,-15.22,2.75), (2.15,0.30,5.5), door_mat, 0.10)
add_cube("ENTRY_DOOR_R", (1.15,-15.22,2.75), (2.15,0.30,5.5), door_mat, 0.10)

# Lighting: cold moon shafts + warm practicals.
world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.003,0.006,0.014,1)
bg.inputs["Strength"].default_value = 0.11

for side in (-1,1):
    for i,y in enumerate((-7.5,0.5,8.5)):
        bpy.ops.object.light_add(type="AREA", location=(side*7.6,y,5.2))
        l=bpy.context.object
        l.data.energy=520
        l.data.shape="RECTANGLE"
        l.data.size=3.4
        l.data.size_y=5.2
        l.data.color=(0.12,0.23,0.55)
        l.rotation_euler=(0, math.radians(90 if side<0 else -90), 0)

for y in (-8,-2,4,10):
    bpy.ops.object.light_add(type="POINT", location=(0,y,3.4))
    l=bpy.context.object
    l.data.energy=120
    l.data.color=(1.0,0.28,0.08)
    l.data.shadow_soft_size=1.2

# Slight altar emphasis.
bpy.ops.object.light_add(type="AREA", location=(0,10.0,7.6))
altar_key=bpy.context.object
altar_key.data.energy=620
altar_key.data.color=(0.55,0.12,0.05)
altar_key.data.size=4.0
altar_key.rotation_euler=(math.radians(18),0,0)

# Ground mist using a large volume cube.
fog_mat=bpy.data.materials.new("NAVE_FOG")
fog_mat.use_nodes=True
fog_mat.node_tree.nodes.clear()
out=fog_mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
vol=fog_mat.node_tree.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value=0.018
vol.inputs["Color"].default_value=(0.035,0.045,0.07,1)
fog_mat.node_tree.links.new(vol.outputs["Volume"],out.inputs["Volume"])
fog=add_cube("NAVE_VOLUME", (0,0,3.8), (17.4,29.0,7.2), fog_mat, 0.0)
fog.display_type="WIRE"

scene=bpy.context.scene
scene.render.engine="BLENDER_EEVEE"
scene.render.resolution_x=1600
scene.render.resolution_y=900
scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"
scene.render.film_transparent=False
scene.render.filepath=str(OUT/"nave_art_v1_player.png")

# Eevee volumetrics/settings when available.
if hasattr(scene, "eevee"):
    pass

def look_at(obj,target):
    direction=Vector(target)-obj.location
    obj.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()

# Player-eye hero view from entry.
bpy.ops.object.camera_add(location=(0,-12.7,1.62))
cam=bpy.context.object
cam.data.lens=28
look_at(cam,(0,10.5,3.0))
scene.camera=cam
bpy.ops.render.render(write_still=True)

# Side player view to inspect columns/windows.
cam.location=(-3.8,-5.0,1.62)
cam.data.lens=31
look_at(cam,(3.8,5.2,4.6))
scene.render.filepath=str(OUT/"nave_art_v1_side.png")
bpy.ops.render.render(write_still=True)

# Export the art prototype as a separate GLB. It is not final shipping art.
bpy.data.objects.remove(cam, do_unlink=True)
bpy.ops.object.select_all(action="DESELECT")
meshes=[o for o in art.objects if o.type=="MESH" and o.name!="NAVE_VOLUME"]
for o in meshes:
    o.select_set(True)
if meshes:
    bpy.context.view_layer.objects.active=meshes[0]
    bpy.ops.export_scene.gltf(
        filepath=str(OUT/"church_v1_nave_art_prototype.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )

triangles=0
for o in meshes:
    o.data.calc_loop_triangles()
    triangles += len(o.data.loop_triangles)

report={
    "stage":"ART_PROTOTYPE_V1",
    "shippingAllowed":False,
    "meshObjects":len(meshes),
    "triangles":triangles,
    "materials":len({m for o in meshes for m in o.data.materials if m}),
    "features":[
        "compound columns",
        "pointed arcades",
        "vault ribs",
        "stained-glass proxies",
        "pews",
        "altar",
        "chandelier",
        "warm/cold lighting",
        "volumetric atmosphere"
    ]
}
(OUT/"nave_art_v1_report.json").write_text(__import__("json").dumps(report,indent=2),encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"church_v1_nave_art_v1.blend"))
print("CHURCH_V1_NAVE_ART_PROTOTYPE_OK",report)
