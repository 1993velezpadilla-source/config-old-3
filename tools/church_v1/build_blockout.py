import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(os.environ.get("CHURCH_V1_SPEC", ROOT / "church_v1/spec/church_v1.json"))
OUT = Path(os.environ.get("CHURCH_V1_OUT", ROOT / "church_v1/out"))
OUT.mkdir(parents=True, exist_ok=True)

spec = json.loads(SPEC.read_text(encoding="utf-8"))

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

blockout = bpy.data.collections.new("BLOCKOUT_ONLY__NOT_FINAL_ART")
bpy.context.scene.collection.children.link(blockout)

def move_to(obj, collection):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)

def add_box(name, center, dims, role, zone):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj["xziel_stage"] = "blockout"
    obj["xziel_role"] = role
    obj["xziel_zone"] = zone
    move_to(obj, blockout)
    return obj

FLOOR_THICKNESS = 0.24
WALL_THICKNESS = 0.30
zone_by_id = {z["id"]: z for z in spec["zones"]}

for z in spec["zones"]:
    cx, cy, _ = z["center"]
    sx, sy, sz = z["size"]
    floor_z = z["floorZ"]

    add_box(
        f"BLOCKOUT_{z['id']}_floor",
        (cx, cy, floor_z - FLOOR_THICKNESS * 0.5),
        (sx, sy, FLOOR_THICKNESS),
        "floor",
        z["id"],
    )

    wall_h = max(3.5, min(sz, 12.0))
    wz = floor_z + wall_h * 0.5
    add_box(f"BLOCKOUT_{z['id']}_wall_w", (cx - sx/2, cy, wz), (WALL_THICKNESS, sy, wall_h), "wall", z["id"])
    add_box(f"BLOCKOUT_{z['id']}_wall_e", (cx + sx/2, cy, wz), (WALL_THICKNESS, sy, wall_h), "wall", z["id"])
    add_box(f"BLOCKOUT_{z['id']}_wall_s", (cx, cy - sy/2, wz), (sx, WALL_THICKNESS, wall_h), "wall", z["id"])
    add_box(f"BLOCKOUT_{z['id']}_wall_n", (cx, cy + sy/2, wz), (sx, WALL_THICKNESS, wall_h), "wall", z["id"])

for a, b in spec["connections"]:
    za, zb = zone_by_id[a], zone_by_id[b]
    pa = Vector((za["center"][0], za["center"][1], za["floorZ"] + 1.0))
    pb = Vector((zb["center"][0], zb["center"][1], zb["floorZ"] + 1.0))
    d = pb - pa
    mid = (pa + pb) * 0.5
    length = max(d.length, 0.1)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=mid)
    obj = bpy.context.object
    obj.name = f"BLOCKOUT_ROUTE_{a}__{b}"
    obj.dimensions = (2.2, length, 2.2)
    yaw = math.atan2(d.y, d.x) - math.pi/2
    horiz = max(math.hypot(d.x, d.y), 0.001)
    pitch = math.atan2(d.z, horiz)
    obj.rotation_euler = (pitch, 0, yaw)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj["xziel_stage"] = "blockout"
    obj["xziel_role"] = "route"
    move_to(obj, blockout)

def make_mat(name, rgba):
    m = bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m

m_floor = make_mat("BLOCKOUT_FLOOR", (0.16,0.17,0.18,1))
m_wall = make_mat("BLOCKOUT_WALL", (0.36,0.37,0.39,1))
m_route = make_mat("BLOCKOUT_ROUTE", (0.30,0.16,0.10,1))

for obj in blockout.objects:
    if obj.type != "MESH":
        continue
    role = obj.get("xziel_role")
    obj.data.materials.append(m_floor if role=="floor" else m_route if role=="route" else m_wall)

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.025,0.03,0.04,1)
    bg.inputs["Strength"].default_value = 0.35

bpy.ops.object.light_add(type="AREA", location=(0,-4,20))
key = bpy.context.object
key.data.energy = 1800
key.data.size = 18

bpy.ops.object.light_add(type="AREA", location=(12,10,8))
fill = bpy.context.object
fill.data.energy = 900
fill.data.size = 10

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100

def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def render(name, location, target, lens=35):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.data.lens = lens
    look_at(cam, target)
    scene.camera = cam
    scene.render.filepath = str(OUT / name)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)

render("blockout_top_3q.png", (48,-52,58), (0,3,0), 42)
render("blockout_player_nave.png", (0,-11,1.62), (0,8,2.1), 30)
render("blockout_crypt.png", (9,10,-3.2), (3,18,-3.4), 32)

bpy.ops.object.select_all(action="DESELECT")
for obj in blockout.objects:
    if obj.type == "MESH":
        obj.select_set(True)
mesh_objs = [o for o in blockout.objects if o.type == "MESH"]
if mesh_objs:
    bpy.context.view_layer.objects.active = mesh_objs[0]
    bpy.ops.export_scene.gltf(
        filepath=str(OUT / "church_v1_blockout.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )

report = {
    "stage": "BLOCKOUT_ONLY",
    "shippingAllowed": False,
    "zones": [z["id"] for z in spec["zones"]],
    "connections": spec["connections"],
    "meshObjects": len(mesh_objs),
    "note": "Spatial/gameplay blockout only. Final art must pass validate_final_art.py."
}
(OUT / "blockout_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "church_v1_blockout.blend"))
print("CHURCH_V1_BLOCKOUT_OK", json.dumps(report))
