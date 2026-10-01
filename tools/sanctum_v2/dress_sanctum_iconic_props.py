import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector, Matrix

BASE_SCRIPT = Path("tools/sanctum_v2/dress_sanctum_with_cc0_gothic.py")
if not BASE_SCRIPT.is_file():
    raise SystemExit("SANCTUM_ICONIC_FAIL: missing dressed base script")

ICONIC_BASE_OUT = Path(os.environ.get("SANCTUM_ICONIC_BASE_OUT", "sanctum-iconic-base"))
ICONIC_OUT = Path(os.environ.get("SANCTUM_ICONIC_OUT", "sanctum-iconic-probe"))
BENCH_BLEND = Path(os.environ["SANCTUM_BENCH_BLEND"])
CANDLE_BLEND = Path(os.environ["SANCTUM_CANDLE_BLEND"])
WINDOW_BLEND = Path(os.environ["SANCTUM_WINDOW_BLEND"])
ICONIC_BASE_OUT.mkdir(parents=True, exist_ok=True)
ICONIC_OUT.mkdir(parents=True, exist_ok=True)

# Build the already-proven cathedral + CC0 interior + Gothic dressing first.
# Keeping this as an explicit upstream stage means the iconic prop pass can fail
# without destabilizing the last known-good playable map.
os.environ["SANCTUM_DRESS_OUT"] = str(ICONIC_BASE_OUT)
exec(compile(BASE_SCRIPT.read_text(encoding="utf-8"), str(BASE_SCRIPT), "exec"), globals(), globals())


def iconic_fail(msg):
    raise SystemExit(f"SANCTUM_ICONIC_FAIL: {msg}")


def append_named_objects(blend_path, names):
    names = list(names)
    with bpy.data.libraries.load(str(blend_path), link=False) as (src, dst):
        available = set(src.objects)
        missing = [n for n in names if n not in available]
        if missing:
            iconic_fail(f"{blend_path.name} missing objects: {missing}")
        dst.objects = [n for n in names]
    result = {}
    for obj in dst.objects:
        if obj is None:
            continue
        if obj.name not in scene.collection.objects:
            scene.collection.objects.link(obj)
        result[obj.name] = obj
    bpy.context.view_layer.update()
    return result


def normalized_template(source_obj, label):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = source_obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(
        ev,
        preserve_all_data_layers=True,
        depsgraph=deps,
    )
    if not mesh.vertices:
        iconic_fail(f"empty prop mesh: {source_obj.name}")

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
    mesh.transform(Matrix.Translation((-center.x, -center.y, -mn.z)))

    obj = bpy.data.objects.new(f"SANCTUM_TEMPLATE_{label}", mesh)
    scene.collection.objects.link(obj)
    obj.hide_render = True
    obj.hide_viewport = True
    source_obj.hide_render = True
    source_obj.hide_viewport = True
    return obj, {
        "source_object": source_obj.name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "size": list(mx - mn),
    }


def normalized_group(source_objects, label):
    deps = bpy.context.evaluated_depsgraph_get()
    meshes = []
    all_pts = []

    for src in source_objects:
        ev = src.evaluated_get(deps)
        mesh = bpy.data.meshes.new_from_object(
            ev,
            preserve_all_data_layers=True,
            depsgraph=deps,
        )
        if not mesh.vertices:
            iconic_fail(f"empty group prop mesh: {src.name}")
        mesh.transform(ev.matrix_world)
        meshes.append((src, mesh))
        all_pts.extend(v.co.copy() for v in mesh.vertices)

    mn = Vector((
        min(p.x for p in all_pts),
        min(p.y for p in all_pts),
        min(p.z for p in all_pts),
    ))
    mx = Vector((
        max(p.x for p in all_pts),
        max(p.y for p in all_pts),
        max(p.z for p in all_pts),
    ))
    center = (mn + mx) * 0.5
    offset = Matrix.Translation((-center.x, -center.y, -mn.z))

    templates = []
    for idx, (src, mesh) in enumerate(meshes):
        mesh.transform(offset)
        obj = bpy.data.objects.new(f"SANCTUM_TEMPLATE_{label}_{idx:02d}", mesh)
        scene.collection.objects.link(obj)
        obj.hide_render = True
        obj.hide_viewport = True
        src.hide_render = True
        src.hide_viewport = True
        templates.append(obj)

    return templates, {
        "source_objects": [o.name for o in source_objects],
        "vertices": sum(len(o.data.vertices) for o in templates),
        "polygons": sum(len(o.data.polygons) for o in templates),
        "size": list(mx - mn),
    }


def place_template(template, name, location, rotation_z=0.0, scale=(1.0, 1.0, 1.0), cosmetic=False):
    obj = template.copy()
    obj.data = template.data
    obj.name = name
    obj.hide_render = False
    obj.hide_viewport = False
    obj.location = Vector(location)
    obj.rotation_euler = (0.0, 0.0, rotation_z)
    obj.scale = Vector(scale)
    scene.collection.objects.link(obj)
    obj["xziel_role"] = "cosmetic_prop" if cosmetic else "gameplay_prop"
    obj["xziel_collision"] = not cosmetic
    obj["source_asset"] = template.name
    return obj


def place_group(templates, prefix, location, rotation_z=0.0, scale=(1.0, 1.0, 1.0), cosmetic=True):
    placed = []
    for idx, template in enumerate(templates):
        placed.append(place_template(
            template,
            f"{prefix}_{idx:02d}",
            location,
            rotation_z=rotation_z,
            scale=scale,
            cosmetic=cosmetic,
        ))
    return placed


def tune_glass(objects):
    material_map = {}
    for obj in objects:
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None:
                continue
            low = mat.name.lower()
            if "windowblue" not in low and "windowyellow" not in low:
                continue
            if mat.name not in material_map:
                clone = mat.copy()
                clone.name = f"SANCTUM_GLASS_{mat.name}"
                clone.use_nodes = True
                bsdf = clone.node_tree.nodes.get("Principled BSDF") if clone.node_tree else None
                if bsdf:
                    if "Roughness" in bsdf.inputs:
                        bsdf.inputs["Roughness"].default_value = 0.12
                    if "Metallic" in bsdf.inputs:
                        bsdf.inputs["Metallic"].default_value = 0.0
                    if "Transmission Weight" in bsdf.inputs:
                        bsdf.inputs["Transmission Weight"].default_value = 0.55
                    elif "Transmission" in bsdf.inputs:
                        bsdf.inputs["Transmission"].default_value = 0.55
                    if "IOR" in bsdf.inputs:
                        bsdf.inputs["IOR"].default_value = 1.45
                material_map[mat.name] = clone
            slot.material = material_map[mat.name]
    return sorted(m.name for m in material_map.values())


def clearance_point_set(result):
    return {
        (round(float(p[0]), 5), round(float(p[1]), 5))
        for p in result.get("walkable_points", [])
    }


def render_iconic(scene, cam, name, pos, look):
    cam.location = Vector(pos)
    point_camera_local(cam, look)
    scene.render.filepath = str(ICONIC_OUT / name)
    bpy.ops.render.render(write_still=True)
    p = ICONIC_OUT / name
    if not p.is_file() or p.stat().st_size < 4000:
        iconic_fail(f"render failed: {name}")
    return {"name": name, "bytes": p.stat().st_size}


def export_iconic(objects):
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    p = ICONIC_OUT / "sanctum-iconic-church.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(p),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    if not p.is_file() or p.stat().st_size < 1000000:
        iconic_fail("iconic GLB export failed")
    return p


# Import only verified CC0 source objects.
bench_src = append_named_objects(BENCH_BLEND, ["BenchWoodOld"])
candle_src = append_named_objects(CANDLE_BLEND, ["CandleStand.001", "Candle"])
window_src = append_named_objects(
    WINDOW_BLEND,
    [
        "WindowRectBlueWeathered",
        "WindowOut4YellowFrame",
        "WindowOut4Yellow",
    ],
)

bench_template, bench_meta = normalized_template(bench_src["BenchWoodOld"], "PEW")
stand_template, stand_meta = normalized_template(candle_src["CandleStand.001"], "CANDLE_STAND")
candle_template, candle_meta = normalized_template(candle_src["Candle"], "CANDLE")
blue_template, blue_meta = normalized_template(window_src["WindowRectBlueWeathered"], "BLUE_WINDOW")
yellow_templates, yellow_meta = normalized_group(
    [window_src["WindowOut4YellowFrame"], window_src["WindowOut4Yellow"]],
    "YELLOW_WINDOW",
)

glass_materials = tune_glass([blue_template, *yellow_templates])

# Baseline here is the already-proven Dressed Gothic map. This pass may add
# visual density but is not allowed to destroy the known-good combat lanes.
prop_baseline = walkability_with_dressing(scene, inner_after)
prop_instances = []

# Six pews: three paired rows. This gives church identity while deliberately
# leaving the central aisle wide enough for touch-first zombie kiting.
for row, yoff in enumerate((-5.0, -1.5, 2.0), 1):
    for side, sign in (("L", -1.0), ("R", 1.0)):
        prop_instances.append(place_template(
            bench_template,
            f"SANCTUM_PEW_{row}_{side}",
            (ic.x + sign * 2.45, ic.y + yoff, floor_z),
            scale=(1.12, 1.0, 1.0),
            cosmetic=False,
        ))

# Side windows are visual-only. Alternate blue and warm yellow panes to make
# individual bays readable under dark/night lighting.
window_y = (-6.0, 0.0, 6.0)
for idx, yoff in enumerate(window_y, 1):
    for side, sign in (("L", -1.0), ("R", 1.0)):
        loc = (ic.x + sign * half_w * 0.94, ic.y + yoff, floor_z + 2.1)
        rot = math.radians(90.0)
        if idx % 2:
            prop_instances.append(place_template(
                blue_template,
                f"SANCTUM_COSMETIC_BLUE_WINDOW_{idx}_{side}",
                loc,
                rotation_z=rot,
                scale=(1.30, 1.0, 1.30),
                cosmetic=True,
            ))
        else:
            prop_instances.extend(place_group(
                yellow_templates,
                f"SANCTUM_COSMETIC_YELLOW_WINDOW_{idx}_{side}",
                loc,
                rotation_z=rot,
                scale=(1.15, 1.0, 1.15),
                cosmetic=True,
            ))

# Four floor-standing candle clusters near the altar. They are intentionally
# cosmetic and excluded from runtime collision/navmesh sidecars.
candle_locs = [
    (ic.x - 1.20, ic.y + half_l * 0.56),
    (ic.x + 1.20, ic.y + half_l * 0.56),
    (ic.x - 0.72, ic.y + half_l * 0.69),
    (ic.x + 0.72, ic.y + half_l * 0.69),
]
candle_lights = []
for idx, (x, y) in enumerate(candle_locs, 1):
    prop_instances.append(place_template(
        stand_template,
        f"SANCTUM_COSMETIC_CANDLE_STAND_{idx}",
        (x, y, floor_z),
        scale=(1.35, 1.35, 1.35),
        cosmetic=True,
    ))
    prop_instances.append(place_template(
        candle_template,
        f"SANCTUM_COSMETIC_CANDLE_{idx}",
        (x, y, floor_z + 0.58),
        scale=(1.05, 1.05, 1.05),
        cosmetic=True,
    ))

    ld = bpy.data.lights.new(f"SANCTUM_CANDLE_LIGHT_{idx}_DATA", "POINT")
    ld.energy = 85.0
    ld.color = (1.0, 0.38, 0.10)
    ld.shadow_soft_size = 0.55
    lo = bpy.data.objects.new(f"SANCTUM_CANDLE_LIGHT_{idx}", ld)
    scene.collection.objects.link(lo)
    lo.location = Vector((x, y, floor_z + 0.92))
    candle_lights.append(lo)

bpy.context.view_layer.update()

prop_walk = walkability_with_dressing(scene, inner_after)
base_points = clearance_point_set(prop_baseline)
final_points = clearance_point_set(prop_walk)
retained = base_points & final_points
prop_retention = len(retained) / len(base_points) if base_points else 0.0

if prop_retention < 0.94:
    iconic_fail(
        "props reduce Dressed clearance too much: "
        f"{len(retained)} / {len(base_points)} ({prop_retention:.3f})"
    )

# Final material/night preview.
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 900
scene.render.resolution_y = 560
scene.render.resolution_percentage = 100
scene.render.image_settings.media_type = "IMAGE"
scene.render.image_settings.file_format = "PNG"

if scene.world is None:
    scene.world = bpy.data.worlds.new("SANCTUM_ICONIC_WORLD")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.006, 0.009, 0.018, 1.0)
    bg.inputs["Strength"].default_value = 0.18

# Keep only actual map objects/lights visible for the final views.
for obj in scene.objects:
    if hasattr(obj, "hide_render") and obj.name.startswith("SANCTUM_TEMPLATE_"):
        obj.hide_render = True
for obj in [outer_baked, *inner_objects, *instances, *prop_instances, *candle_lights]:
    obj.hide_render = False
    obj.hide_viewport = False

cam = ensure_camera(scene)
cam.hide_render = False
eye = floor_z + 1.72

views = [
    ("01-iconic-exterior.png",
     Vector(outer_stats["center"]) + Vector((max(outer_stats["size"])*0.90, -max(outer_stats["size"])*0.90, max(outer_stats["size"])*0.55)),
     Vector(outer_stats["center"])),
    ("02-iconic-nave-forward.png",
     Vector((ic.x, ic.y-half_l*0.72, eye)),
     Vector((ic.x, ic.y+half_l*0.58, eye+0.8))),
    ("03-iconic-nave-reverse.png",
     Vector((ic.x, ic.y+half_l*0.64, eye)),
     Vector((ic.x, ic.y-half_l*0.58, eye+0.4))),
    ("04-iconic-pews.png",
     Vector((ic.x, ic.y-7.4, eye)),
     Vector((ic.x, ic.y+2.3, eye+0.35))),
    ("05-iconic-left-windows.png",
     Vector((ic.x+1.2, ic.y-3.5, eye)),
     Vector((ic.x-half_w*0.93, ic.y+0.5, floor_z+3.3))),
    ("06-iconic-right-windows.png",
     Vector((ic.x-1.2, ic.y+3.0, eye)),
     Vector((ic.x+half_w*0.93, ic.y+0.5, floor_z+3.3))),
    ("07-iconic-altar-candles.png",
     Vector((ic.x, ic.y+half_l*0.28, eye)),
     Vector((ic.x, ic.y+half_l*0.68, floor_z+1.2))),
    ("08-iconic-altar-wide.png",
     Vector((ic.x-2.2, ic.y+half_l*0.10, eye+0.2)),
     Vector((ic.x, ic.y+half_l*0.62, floor_z+1.8))),
]
renders = [render_iconic(scene, cam, *v) for v in views]

export_objects = [outer_baked, *inner_objects, *instances, *prop_instances]
glb = export_iconic(export_objects)
stats = mesh_stats(export_objects)

report = {
    "status": "PASS",
    "stage": "iconic-props-v1",
    "base_stage": "Sanctum Dressed Gothic Interior",
    "licenses": {
        "outer": "MIT",
        "interior": "CC0",
        "gothic_dressing": "CC0",
        "benches": "CC0",
        "candles": "CC0",
        "windows": "CC0",
    },
    "source_sha256": {
        "benches": os.environ.get("SANCTUM_BENCH_SHA256", ""),
        "candles": os.environ.get("SANCTUM_CANDLE_SHA256", ""),
        "windows": os.environ.get("SANCTUM_WINDOW_SHA256", ""),
    },
    "templates": {
        "bench": bench_meta,
        "candle_stand": stand_meta,
        "candle": candle_meta,
        "blue_window": blue_meta,
        "yellow_window": yellow_meta,
    },
    "glass_materials": glass_materials,
    "prop_instances": [
        {
            "name": o.name,
            "source_asset": o.get("source_asset"),
            "role": o.get("xziel_role"),
            "collision": bool(o.get("xziel_collision")),
            "location": list(o.location),
            "rotation_z": float(o.rotation_euler.z),
            "scale": list(o.scale),
        }
        for o in prop_instances
    ],
    "prop_clearance_baseline": prop_baseline,
    "prop_clearance_final": prop_walk,
    "prop_clearance_retention_ratio": prop_retention,
    "stats": stats,
    "renders": renders,
    "glb": glb.name,
    "glb_bytes": glb.stat().st_size,
}
for name, value in report["source_sha256"].items():
    if len(value) != 64:
        iconic_fail(f"missing verified SHA256 for {name}")

(ICONIC_OUT/"iconic-report.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8",
)

print("SANCTUM_ICONIC_PROPS_PASS")
print(json.dumps({
    "prop_instances": len(prop_instances),
    "prop_clearance_retention_ratio": prop_retention,
    "vertices": stats["vertices"],
    "polygons": stats["polygons"],
    "glb_bytes": glb.stat().st_size,
    "glass_materials": glass_materials,
}, indent=2))
