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

    loaded = {obj.name: obj for obj in dst.objects if obj is not None}
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
    start_z = floor_z + 4.0
    xs = [mn.x + (mx.x - mn.x) * (0.18 + 0.64 * i / 10.0) for i in range(11)]
    ys = [mn.y + (mx.y - mn.y) * (0.12 + 0.76 * j / 16.0) for j in range(17)]
    deps = bpy.context.evaluated_depsgraph_get()
    walkable = 0
    hits = 0
    blocked = []
    for x in xs:
        for y in ys:
            origin = Vector((x, y, start_z))
            hit, loc, normal, face_index, obj, matrix = scene.ray_cast(
                deps, origin, Vector((0,0,-1)), distance=20.0
            )
            if hit:
                hits += 1
                is_floor = normal.z > 0.70 and abs(loc.z - floor_z) < 0.40
                if is_floor:
                    walkable += 1
                else:
                    blocked.append({
                        "x":x,"y":y,"z":loc.z,
                        "normal_z":normal.z,
                        "object":obj.name if obj else "",
                    })
    total = len(xs) * len(ys)
    return {
        "samples": total,
        "hits": hits,
        "walkable": walkable,
        "walkable_ratio": walkable / total,
        "blocked_samples": blocked,
    }

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

ic = Vector(inner_after["center"])
imn = Vector(inner_after["min"])
isz = Vector(inner_after["size"])
floor_z = imn.z + 0.12
half_w = isz.x * 0.5
half_l = isz.y * 0.5

instances = []

# Four paired bays of existing authored pillar meshes.
bay_offsets = (-0.30, -0.10, 0.10, 0.30)
for idx, frac in enumerate(bay_offsets, 1):
    y = ic.y + isz.y * frac
    role = "pillar_a" if idx % 2 else "pillar_b"
    for side, sign in (("L", -1.0), ("R", 1.0)):
        x = ic.x + sign * half_w * 0.78
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
        (ic.x + sign * half_w * 0.56, altar_y, floor_z),
    ))

# Existing authored arch centered near the altar end. Keep its original
# geometry; only orient/position it inside the nave.
instances.append(place_instance(
    assets["arch"],
    "SANCTUM_ALTAR_ARCH",
    (ic.x, ic.y + half_l * 0.80, floor_z),
))

# Existing long wall/trim pieces run along the two side walls.
for side, sign in (("L", -1.0), ("R", 1.0)):
    instances.append(place_instance(
        assets["wall_trim"],
        f"SANCTUM_WALL_TRIM_{side}",
        (ic.x + sign * half_w * 0.92, ic.y, floor_z),
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

walk = walkability_with_dressing(scene, inner_after)
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
