import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector, Matrix

# Reuse the already-proven composite builder first.
BASE_SCRIPT = Path("tools/sanctum_v2/compose_cathedral_cc0_interior.py")
if not BASE_SCRIPT.is_file():
    raise SystemExit("SANCTUM_DRESS_FAIL: missing base composite script")

exec(compile(BASE_SCRIPT.read_text(encoding="utf-8"), str(BASE_SCRIPT), "exec"), globals(), globals())

DRESS_OUT = Path(os.environ.get("SANCTUM_DRESS_OUT", "sanctum-dressed-probe"))
RUINS_BLEND = Path(os.environ["SANCTUM_RUINS_BLEND"])
DRESS_OUT.mkdir(parents=True, exist_ok=True)

ASSET_NAMES = {
    "arch": "Object.002",
    "pillar_a": "PillarSegmentOne200",
    "pillar_b": "Object.003",
    "roman_column": "RomanTypeColOne200",
    "wall_trim": "Object.004",
}

def dress_fail(msg):
    raise SystemExit(f"SANCTUM_DRESS_FAIL: {msg}")

def bake_normalized_asset(source_obj, asset_name):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = source_obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(
        ev,
        preserve_all_data_layers=True,
        depsgraph=deps,
    )
    if not mesh.vertices:
        dress_fail(f"asset {asset_name} has no vertices")

    # Bake the authored object transform into the mesh, then normalize to
    # XY center + ground at Z=0. This preserves the upstream authored shape.
    mesh.transform(ev.matrix_world)
    pts = [v.co.copy() for v in mesh.vertices]
    mn = Vector((
        min(p.x for p in pts),
        min(p.y for p in pts),
        min(p.z for p in pts),
    ))
    mx = Vector((
        max(p.x for p in pts),
        max(p.y for p in pts),
        max(p.z for p in pts),
    ))
    center = (mn + mx) * 0.5
    offset = Vector((-center.x, -center.y, -mn.z))
    mesh.transform(Matrix.Translation(offset))

    obj = bpy.data.objects.new(f"SANCTUM_ASSET_{asset_name}", mesh)
    scene.collection.objects.link(obj)
    obj.hide_render = True
    obj.hide_viewport = True
    return obj, {
        "source_object": source_obj.name,
        "size": list(mx - mn),
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
    }

def load_ruins_assets():
    with bpy.data.libraries.load(str(RUINS_BLEND), link=False) as (src, dst):
        wanted = set(ASSET_NAMES.values())
        dst.objects = [name for name in src.objects if name in wanted]
        dst.materials = [name for name in src.materials if name == "BrickFloor1"]

    loaded = {obj.name: obj for obj in dst.objects if obj is not None}
    for obj in loaded.values():
        if obj.name not in scene.collection.objects:
            scene.collection.objects.link(obj)
    bpy.context.view_layer.update()

    missing = sorted(set(ASSET_NAMES.values()) - set(loaded))
    if missing:
        dress_fail(f"missing ruins assets: {missing}")

    canonical = {}
    metadata = {}
    for role, source_name in ASSET_NAMES.items():
        obj, info = bake_normalized_asset(loaded[source_name], role)
        canonical[role] = obj
        metadata[role] = info
        loaded[source_name].hide_render = True
        loaded[source_name].hide_viewport = True
    return canonical, metadata

def place_instance(template, name, location, rotation_z=0.0, scale=(1.0, 1.0, 1.0)):
    obj = template.copy()
    obj.data = template.data
    obj.name = name
    obj.hide_render = False
    obj.hide_viewport = False
    obj.location = Vector(location)
    obj.rotation_euler = (0.0, 0.0, rotation_z)
    obj.scale = Vector(scale)
    scene.collection.objects.link(obj)
    obj["xziel_role"] = "interior_dressing"
    obj["source_asset"] = template.name
    return obj

def point_camera_local(cam, target):
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()

def render_dress_view(scene, cam, name, pos, look):
    cam.location = Vector(pos)
    point_camera_local(cam, look)
    scene.render.filepath = str(DRESS_OUT / name)
    bpy.ops.render.render(write_still=True)
    p = DRESS_OUT / name
    if not p.is_file() or p.stat().st_size < 3000:
        dress_fail(f"render failed: {name}")
    return {"name": name, "bytes": p.stat().st_size}

def walkability_with_dressing(scene, inner_stats):
    mn = Vector(inner_stats["min"])
    mx = Vector(inner_stats["max"])
    floor_z = mn.z + 0.12
    xs = [mn.x + (mx.x - mn.x) * (0.18 + 0.64 * i / 10.0) for i in range(11)]
    ys = [mn.y + (mx.y - mn.y) * (0.12 + 0.76 * j / 16.0) for j in range(17)]
    deps = bpy.context.evaluated_depsgraph_get()

    # Gameplay-oriented clearance test:
    # 1) confirm a floor close below ankle/waist height so overhead arches,
    #    beams, and ceilings cannot be mistaken for the floor;
    # 2) probe a player-radius disc horizontally at chest height so walls,
    #    pillars, props, etc. still count as blockers.
    floor_probe_height = 0.75
    player_probe_height = 1.0
    player_radius = 0.34
    radial_dirs = [
        Vector((math.cos(a), math.sin(a), 0.0))
        for a in [i * (math.tau / 8.0) for i in range(8)]
    ]

    walkable = 0
    hits = 0
    blocked = []

    for x in xs:
        for y in ys:
            floor_origin = Vector((x, y, floor_z + floor_probe_height))
            hit, loc, normal, face_index, obj, matrix = scene.ray_cast(
                deps, floor_origin, Vector((0,0,-1)), distance=1.5
            )

            if not hit:
                blocked.append({
                    "x":x,"y":y,"z":None,
                    "normal_z":None,
                    "object":"",
                    "reason":"no_floor",
                })
                continue

            hits += 1
            is_floor = normal.z > 0.70 and abs(loc.z - floor_z) < 0.40
            if not is_floor:
                blocked.append({
                    "x":x,"y":y,"z":loc.z,
                    "normal_z":normal.z,
                    "object":obj.name if obj else "",
                    "reason":"floor_probe_blocked",
                })
                continue

            chest = Vector((x, y, loc.z + player_probe_height))
            blocker = None
            for direction in radial_dirs:
                h2, l2, n2, f2, o2, m2 = scene.ray_cast(
                    deps, chest, direction, distance=player_radius
                )
                if h2:
                    blocker = {
                        "x":x,"y":y,"z":l2.z,
                        "normal_z":n2.z,
                        "object":o2.name if o2 else "",
                        "reason":"player_radius_blocked",
                    }
                    break

            if blocker is None:
                walkable += 1
            else:
                blocked.append(blocker)

    total = len(xs) * len(ys)
    return {
        "samples": total,
        "hits": hits,
        "walkable": walkable,
        "walkable_ratio": walkable / total,
        "player_radius": player_radius,
        "player_probe_height": player_probe_height,
        "floor_probe_height": floor_probe_height,
        "blocked_samples": blocked,
    }

def ensure_material_preview_lights(scene, center, size):
    lights = []
    configs = [
        ("FRONT", Vector((0.0, -0.26, 0.32)), 1700.0, 7.0),
        ("MID", Vector((-0.18, 0.02, 0.38)), 1300.0, 6.0),
        ("ALTAR", Vector((0.16, 0.30, 0.36)), 1500.0, 6.0),
    ]
    for name, frac, energy, area in configs:
        ld = bpy.data.lights.new(f"SANCTUM_MAT_{name}_DATA", "AREA")
        ld.energy = energy
        ld.shape = "DISK"
        ld.size = area
        lo = bpy.data.objects.new(f"SANCTUM_MAT_{name}", ld)
        scene.collection.objects.link(lo)
        lo.location = Vector((
            center.x + size.x * frac.x,
            center.y + size.y * frac.y,
            floor_z + size.z * frac.z,
        ))
        target = Vector((center.x, center.y, floor_z + 2.2))
        lo.rotation_euler = (target - lo.location).to_track_quat("-Z", "Y").to_euler()
        lights.append(lo)
    return lights

def render_material_previews(scene, cam):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 800
    scene.render.resolution_y = 500
    scene.render.resolution_percentage = 100
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"

    if scene.world is None:
        scene.world = bpy.data.worlds.new("SANCTUM_MAT_WORLD")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.012, 0.015, 0.022, 1.0)
        bg.inputs["Strength"].default_value = 0.30

    lights = ensure_material_preview_lights(scene, ic, isz)
    for light in lights:
        light.hide_render = False

    previews = []
    preview_views = [
        ("07-material-nave.png",
         Vector((ic.x, ic.y-half_l*0.68, eye)),
         Vector((ic.x, ic.y+half_l*0.42, eye+0.8))),
        ("08-material-altar.png",
         Vector((ic.x, ic.y+half_l*0.14, eye)),
         Vector((ic.x, ic.y+half_l*0.58, eye+1.1))),
    ]
    for name, pos, look in preview_views:
        previews.append(render_dress_view(scene, cam, name, pos, look))
    return previews

def export_dressed(objects):
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    path = DRESS_OUT / "sanctum-dressed-cathedral-interior.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    if not path.is_file() or path.stat().st_size < 1000000:
        dress_fail("dressed GLB export failed")
    return path

assets, asset_metadata = load_ruins_assets()

# Reuse an authored CC0 floor material from the same Gothic pack.
floor_material = bpy.data.materials.get("BrickFloor1")
if floor_material is not None:
    gameplay_floor.data.materials.clear()
    gameplay_floor.data.materials.append(floor_material)
    gameplay_floor["material_source"] = "3TD Fantasy Ruins Pack / BrickFloor1"

ic = Vector(inner_after["center"])
imn = Vector(inner_after["min"])
isz = Vector(inner_after["size"])
floor_z = imn.z + 0.12
half_w = isz.x * 0.5
half_l = isz.y * 0.5

instances = []

# Four paired bays of existing authored pillar meshes.
bay_offsets = (-0.32, -0.11, 0.10, 0.31)
for idx, frac in enumerate(bay_offsets, 1):
    y = ic.y + isz.y * frac
    role = "pillar_a" if idx % 2 else "pillar_b"
    for side, sign in (("L", -1.0), ("R", 1.0)):
        x = ic.x + sign * half_w * 0.66
        instances.append(place_instance(
            assets[role],
            f"SANCTUM_{role.upper()}_{idx}_{side}",
            (x, y, floor_z),
        ))

# Two taller columns frame the altar end while preserving the central lane.
altar_y = ic.y + half_l * 0.70
for side, sign in (("L", -1.0), ("R", 1.0)):
    instances.append(place_instance(
        assets["roman_column"],
        f"SANCTUM_ROMAN_ALTAR_{side}",
        (ic.x + sign * half_w * 0.55, altar_y, floor_z),
    ))

# Existing authored arch centered near the altar end. Keep its original
# geometry; only orient/position it inside the nave.
instances.append(place_instance(
    assets["arch"],
    "SANCTUM_ALTAR_ARCH",
    (ic.x, ic.y + half_l * 0.64, floor_z),
))

# Existing long wall/trim pieces run along the two side walls.
for side, sign in (("L", -1.0), ("R", 1.0)):
    instances.append(place_instance(
        assets["wall_trim"],
        f"SANCTUM_WALL_TRIM_{side}",
        (ic.x + sign * half_w * 0.78, ic.y, floor_z),
        rotation_z=math.radians(90.0),
        scale=(min(1.0, isz.y / 30.0), 1.0, 1.0),
    ))

# Reveal only the actual composite plus placed dressing.
for obj in scene.objects:
    if hasattr(obj, "hide_render"):
        obj.hide_render = True
for obj in [outer_baked, *inner_objects, *instances]:
    obj.hide_render = False
    obj.hide_viewport = False

scene.render.engine = "BLENDER_WORKBENCH"
scene.render.image_settings.media_type = "IMAGE"
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_x = 800
scene.render.resolution_y = 500
scene.render.resolution_percentage = 100

cam = ensure_camera(scene)
cam.hide_render = False

eye = floor_z + 1.72
views = [
    ("01-dressed-exterior-front.png",
     Vector(outer_stats["center"]) + Vector((max(outer_stats["size"])*0.9, -max(outer_stats["size"])*0.9, max(outer_stats["size"])*0.55)),
     Vector(outer_stats["center"])),
    ("02-dressed-nave-forward.png",
     Vector((ic.x, ic.y-half_l*0.72, eye)),
     Vector((ic.x, ic.y+half_l*0.58, eye+0.8))),
    ("03-dressed-nave-reverse.png",
     Vector((ic.x, ic.y+half_l*0.66, eye)),
     Vector((ic.x, ic.y-half_l*0.62, eye+0.5))),
    ("04-dressed-left-aisle.png",
     Vector((ic.x-half_w*0.42, ic.y-half_l*0.46, eye)),
     Vector((ic.x-half_w*0.42, ic.y+half_l*0.48, eye+0.5))),
    ("05-dressed-right-aisle.png",
     Vector((ic.x+half_w*0.42, ic.y-half_l*0.46, eye)),
     Vector((ic.x+half_w*0.42, ic.y+half_l*0.48, eye+0.5))),
    ("06-dressed-altar.png",
     Vector((ic.x, ic.y+half_l*0.35, eye)),
     Vector((ic.x, ic.y+half_l*0.82, eye+1.5))),
]
renders = [render_dress_view(scene, cam, *v) for v in views]
material_previews = render_material_previews(scene, cam)

walk = walkability_with_dressing(scene, inner_after)

# Always persist pre-gate diagnostics so a failed run tells us exactly which
# authored piece blocked each walkability sample instead of forcing guesswork.
from collections import Counter
blockers = Counter(item.get("object", "") for item in walk["blocked_samples"])
(DRESS_OUT/"walkability-diagnostics.json").write_text(
    json.dumps({
        "walkability": walk,
        "blockers": dict(blockers),
    }, indent=2),
    encoding="utf-8",
)
print("SANCTUM_WALKABILITY_BLOCKERS", json.dumps(dict(blockers), sort_keys=True))

if walk["walkable_ratio"] < 0.88:
    dress_fail(
        f"dressing blocks too much nave: {walk['walkable']} / {walk['samples']} "
        f"({walk['walkable_ratio']:.3f})"
    )

export_objects = [outer_baked, *inner_objects, *instances]
glb = export_dressed(export_objects)
dressed_stats = mesh_stats(export_objects)

report = {
    "status": "PASS",
    "outer_license": "MIT",
    "interior_license": "CC0",
    "dressing_license": "CC0",
    "dressing_source": "3TD Fantasy Ruins Pack for Blender",
    "dressing_source_sha256": os.environ.get("SANCTUM_RUINS_SHA256", ""),
    "floor_material": floor_material.name if floor_material is not None else None,
    "asset_metadata": asset_metadata,
    "instances": [
        {
            "name": obj.name,
            "source_asset": obj.get("source_asset"),
            "location": list(obj.location),
            "rotation_z": obj.rotation_euler.z,
            "scale": list(obj.scale),
        }
        for obj in instances
    ],
    "walkability": walk,
    "stats": dressed_stats,
    "renders": renders,
    "material_previews": material_previews,
    "glb": glb.name,
    "glb_bytes": glb.stat().st_size,
}
(DRESS_OUT/"dressed-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("SANCTUM_DRESSED_INTERIOR_PASS")
print(json.dumps({
    "instances": len(instances),
    "walkable_ratio": walk["walkable_ratio"],
    "vertices": dressed_stats["vertices"],
    "polygons": dressed_stats["polygons"],
    "glb_bytes": glb.stat().st_size,
}, indent=2))
