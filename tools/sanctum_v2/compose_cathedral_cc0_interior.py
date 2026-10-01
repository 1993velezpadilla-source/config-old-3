import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

OUT = Path(os.environ.get("SANCTUM_COMPOSITE_OUT", "sanctum-composite-probe"))
CC0_BLEND = Path(os.environ["SANCTUM_CC0_BLEND"])
PLAN_PATH = Path(os.environ.get("XZIEL_MAP_AGENT_PLAN", "tools/sanctum_v2/map_builder_plan.json"))
OUT.mkdir(parents=True, exist_ok=True)

OUTER_OBJECT = "Catehdral"
OUTER_NODE_GROUP = "Generate Cathedral Combined"
CC0_KEEP = {
    "StoneBrickWalls",
    "WindowBars",
    "FrontDoorFrame",
    "FrontDoorRight",
    "FrontDoorLeft",
    "SideDoor",
    "SideStairs",
    "StairsRailing",
    "SunSymbol",
}

def fail(msg):
    raise SystemExit(f"SANCTUM_COMPOSITE_FAIL: {msg}")

def mesh_stats(objects):
    deps = bpy.context.evaluated_depsgraph_get()
    pts = []
    vertices = 0
    polygons = 0
    for obj in objects:
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        try:
            vertices += len(mesh.vertices)
            polygons += len(mesh.polygons)
            pts.extend(ev.matrix_world @ v.co for v in mesh.vertices)
        finally:
            ev.to_mesh_clear()
    if not pts:
        fail("no geometry for bounds")
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return {
        "vertices": vertices,
        "polygons": polygons,
        "min": list(mn),
        "max": list(mx),
        "center": list((mn + mx) * 0.5),
        "size": list(mx - mn),
    }

def find_modifier(obj):
    for mod in obj.modifiers:
        if mod.type == "NODES" and mod.node_group and mod.node_group.name == OUTER_NODE_GROUP:
            return mod
    fail(f"missing {OUTER_NODE_GROUP!r} modifier")

def interface_by_name(mod):
    out = {}
    for item in mod.node_group.interface.items_tree:
        if getattr(item, "item_type", None) == "SOCKET" and getattr(item, "in_out", None) == "INPUT":
            out[item.name] = item
    return out

def set_runtime_inputs(obj, mod, requested):
    if not requested:
        return []
    interfaces = interface_by_name(mod)
    inputs = mod.properties.inputs
    applied = []
    for name, value in requested.items():
        item = interfaces.get(name)
        if item is None:
            fail(f"outer input not found: {name}")
        ident = item.identifier
        runtime = getattr(inputs, ident)
        if not hasattr(runtime, "value"):
            fail(f"outer input has no value: {name}")
        old = runtime.value
        if isinstance(old, bool):
            new_value = bool(value)
        elif isinstance(old, int) and not isinstance(old, bool):
            new_value = int(value)
        elif isinstance(old, float):
            new_value = float(value)
        else:
            new_value = value
        runtime.value = new_value
        applied.append({"name": name, "identifier": ident, "before": old, "after": runtime.value})

    try:
        mod.node_group.update_tag(refresh={"DATA"})
    except Exception:
        mod.node_group.update_tag()
    try:
        obj.data.update_tag()
    except Exception:
        pass
    obj.update_tag(refresh={"OBJECT", "DATA"})
    enabled = mod.show_viewport
    mod.show_viewport = False
    bpy.context.view_layer.update()
    mod.show_viewport = enabled
    obj.update_tag(refresh={"OBJECT", "DATA"})
    bpy.context.view_layer.update()
    return applied

def bake_outer(scene, obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=deps)
    if not mesh.vertices:
        fail("outer bake has no vertices")
    baked = bpy.data.objects.new("SANCTUM_OUTER_BAKED", mesh)
    scene.collection.objects.link(baked)
    baked.matrix_world = ev.matrix_world.copy()
    obj.hide_render = True
    obj.hide_viewport = True
    return baked

def append_cc0_objects(scene):
    with bpy.data.libraries.load(str(CC0_BLEND), link=False) as (src, dst):
        dst.objects = [name for name in src.objects if name in CC0_KEEP]
    out = []
    for obj in dst.objects:
        if obj is None:
            continue
        if obj.name not in scene.collection.objects:
            scene.collection.objects.link(obj)
        obj.name = "CC0_" + obj.name
        out.append(obj)
    missing = sorted(CC0_KEEP - {o.name.replace("CC0_", "", 1) for o in out})
    if "StoneBrickWalls" in missing:
        fail("CC0 StoneBrickWalls missing")
    return out, missing

def fit_inner(inner_objects, outer_stats):
    inner_before = mesh_stats(inner_objects)
    outer_size = Vector(outer_stats["size"])
    inner_size = Vector(inner_before["size"])

    sx = outer_size.x * 0.82 / max(inner_size.x, 1e-6)
    sy = outer_size.y * 0.88 / max(inner_size.y, 1e-6)
    sz = outer_size.z * 0.80 / max(inner_size.z, 1e-6)
    scale = min(sx, sy, sz)

    root = bpy.data.objects.new("SANCTUM_CC0_INTERIOR_ROOT", None)
    bpy.context.scene.collection.objects.link(root)
    for obj in inner_objects:
        obj.parent = root

    root.scale = (scale, scale, scale)
    bpy.context.view_layer.update()

    scaled = mesh_stats(inner_objects)
    outer_center = Vector(outer_stats["center"])
    scaled_center = Vector(scaled["center"])
    outer_min = Vector(outer_stats["min"])
    scaled_min = Vector(scaled["min"])

    delta = Vector((
        outer_center.x - scaled_center.x,
        outer_center.y - scaled_center.y,
        (outer_min.z + 0.10) - scaled_min.z,
    ))
    root.location += delta
    bpy.context.view_layer.update()

    return root, scale, inner_before, mesh_stats(inner_objects)

def create_gameplay_floor(scene, inner_stats):
    center = Vector(inner_stats["center"])
    mn = Vector(inner_stats["min"])
    size = Vector(inner_stats["size"])

    hx = size.x * 0.34
    hy = size.y * 0.39
    z = mn.z + 0.12

    verts = [
        (center.x - hx, center.y - hy, z),
        (center.x + hx, center.y - hy, z),
        (center.x + hx, center.y + hy, z),
        (center.x - hx, center.y + hy, z),
    ]
    mesh = bpy.data.meshes.new("SANCTUM_GAMEPLAY_FLOOR_MESH")
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()

    floor = bpy.data.objects.new("SANCTUM_GAMEPLAY_FLOOR", mesh)
    scene.collection.objects.link(floor)

    stone = bpy.data.materials.get("Stone")
    if stone is not None:
        floor.data.materials.append(stone)

    floor["xziel_role"] = "walkable_floor"
    floor["source"] = "derived_from_cc0_interior_footprint"
    return floor

def sample_walkability(scene, outer, inner_objects, inner_stats):
    # Probe the CC0 shell by itself so the outer facade cannot fake floor hits.
    outer.hide_viewport = True
    for obj in scene.objects:
        if obj.type == "MESH":
            obj.hide_viewport = obj not in inner_objects
    bpy.context.view_layer.update()

    mn = Vector(inner_stats["min"])
    mx = Vector(inner_stats["max"])
    floor_guess = mn.z
    start_z = floor_guess + min(6.0, max(3.0, (mx.z - mn.z) * 0.12))
    xs = [mn.x + (mx.x - mn.x) * (0.18 + 0.64 * i / 10.0) for i in range(11)]
    ys = [mn.y + (mx.y - mn.y) * (0.12 + 0.76 * j / 16.0) for j in range(17)]
    deps = bpy.context.evaluated_depsgraph_get()

    hits = 0
    walkable = 0
    samples = []
    for x in xs:
        for y in ys:
            origin = Vector((x, y, start_z))
            hit, loc, normal, face_index, obj, matrix = scene.ray_cast(
                deps, origin, Vector((0, 0, -1)), distance=20.0
            )
            rec = {"x": x, "y": y, "hit": bool(hit)}
            if hit:
                hits += 1
                rec.update({"z": loc.z, "normal_z": normal.z, "object": obj.name if obj else ""})
                if normal.z > 0.70 and abs(loc.z - floor_guess) < 2.5:
                    walkable += 1
                    rec["walkable"] = True
                else:
                    rec["walkable"] = False
            samples.append(rec)

    for obj in scene.objects:
        if obj.type == "MESH":
            obj.hide_viewport = False
    outer.hide_viewport = False
    bpy.context.view_layer.update()

    total = len(samples)
    return {
        "samples": total,
        "hits": hits,
        "walkable": walkable,
        "hit_ratio": hits / total if total else 0.0,
        "walkable_ratio": walkable / total if total else 0.0,
        "details": samples,
    }

def ensure_camera(scene):
    data = bpy.data.cameras.get("SANCTUM_COMPOSITE_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_COMPOSITE_CAMERA_DATA")
    cam = bpy.data.objects.get("SANCTUM_COMPOSITE_CAMERA") or bpy.data.objects.new("SANCTUM_COMPOSITE_CAMERA", data)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 34
    cam.data.clip_start = 0.05
    cam.data.clip_end = 5000
    return cam

def point(cam, target):
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()

def render(scene, cam, name, pos, look):
    cam.location = Vector(pos)
    point(cam, look)
    scene.render.filepath = str(OUT / name)
    bpy.ops.render.render(write_still=True)
    p = OUT / name
    if not p.is_file() or p.stat().st_size < 3000:
        fail(f"render failed: {name}")
    return {"name": name, "bytes": p.stat().st_size, "position": list(pos), "look_at": list(look)}

def build_views(outer_stats, inner_stats):
    oc = Vector(outer_stats["center"])
    osz = Vector(outer_stats["size"])
    ext = max(osz)
    ic = Vector(inner_stats["center"])
    imn = Vector(inner_stats["min"])
    isz = Vector(inner_stats["size"])
    eye = imn.z + 1.75
    return [
        ("01-composite-exterior-front.png", oc + Vector((ext*0.9, -ext*0.9, ext*0.55)), oc),
        ("02-composite-exterior-side.png", oc + Vector((ext*1.15, 0, ext*0.3)), oc),
        ("03-composite-exterior-rear.png", oc + Vector((-ext*0.9, ext*0.9, ext*0.5)), oc),
        ("04-composite-interior-forward.png", Vector((ic.x, ic.y-isz.y*0.24, eye)), Vector((ic.x, ic.y+isz.y*0.28, eye+0.6))),
        ("05-composite-interior-reverse.png", Vector((ic.x, ic.y+isz.y*0.24, eye)), Vector((ic.x, ic.y-isz.y*0.28, eye+0.6))),
        ("06-composite-interior-across.png", Vector((ic.x-isz.x*0.20, ic.y, eye)), Vector((ic.x+isz.x*0.22, ic.y, eye+0.3))),
    ]

def export_glb(objects):
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    path = OUT / "sanctum-composite-cathedral-interior.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    if not path.is_file() or path.stat().st_size < 1000000:
        fail("composite GLB export failed")
    return path

scene = bpy.context.scene
outer = bpy.data.objects.get(OUTER_OBJECT)
if outer is None:
    fail(f"missing outer object {OUTER_OBJECT}")

modifier = find_modifier(outer)
plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
applied = set_runtime_inputs(outer, modifier, plan.get("geometry_nodes_inputs", {}))
outer_baked = bake_outer(scene, outer)
outer_stats = mesh_stats([outer_baked])

inner_objects, missing = append_cc0_objects(scene)
root, scale, inner_before, inner_after = fit_inner(inner_objects, outer_stats)

gameplay_floor = create_gameplay_floor(scene, inner_after)
inner_objects.append(gameplay_floor)

walk = sample_walkability(scene, outer_baked, inner_objects, inner_after)
if walk["walkable_ratio"] < 0.40:
    fail(
        f"walkability ratio too weak: {walk['walkable']} / {walk['samples']} "
        f"({walk['walkable_ratio']:.3f})"
    )

scene.render.engine = "BLENDER_WORKBENCH"
scene.render.image_settings.media_type = "IMAGE"
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_x = 640
scene.render.resolution_y = 400
scene.render.resolution_percentage = 100

for obj in scene.objects:
    if hasattr(obj, "hide_render"):
        obj.hide_render = obj not in [outer_baked, *inner_objects]

cam = ensure_camera(scene)
cam.hide_render = False

renders = [render(scene, cam, *view) for view in build_views(outer_stats, inner_after)]
glb = export_glb([outer_baked, *inner_objects])
combined_stats = mesh_stats([outer_baked, *inner_objects])

report = {
    "status": "PASS",
    "outer_source": "IRCSS Blender-Geometry-Node-French-Houses",
    "outer_license": "MIT",
    "inner_source": "OpenGameArt Medieval Church Interior by AnyRPG",
    "inner_license": "CC0",
    "blender_version": bpy.app.version_string,
    "applied_outer_inputs": applied,
    "outer_stats": outer_stats,
    "inner_stats_before_fit": inner_before,
    "inner_stats_after_fit": inner_after,
    "inner_uniform_scale": scale,
    "inner_objects": [o.name for o in inner_objects],
    "gameplay_floor": gameplay_floor.name,
    "gameplay_floor_role": gameplay_floor.get("xziel_role"),
    "missing_optional_inner_objects": missing,
    "walkability": walk,
    "combined_stats": combined_stats,
    "renders": renders,
    "glb": glb.name,
    "glb_bytes": glb.stat().st_size,
}
(OUT / "composite-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("SANCTUM_COMPOSITE_PROBE_PASS")
print(json.dumps({
    "outer": outer_stats,
    "inner_after": inner_after,
    "scale": scale,
    "walkable_ratio": walk["walkable_ratio"],
    "combined": combined_stats,
    "glb_bytes": glb.stat().st_size,
}, indent=2))
