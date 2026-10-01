import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

OUT = Path(os.environ.get("XZIEL_MAP_AGENT_OUT", "xziel-map-agent-out"))
PLAN_PATH = Path(os.environ.get("XZIEL_MAP_AGENT_PLAN", "tools/sanctum_v2/map_builder_plan.json"))
OUT.mkdir(parents=True, exist_ok=True)

ALLOWED_POLICY = "existing-assets-only"

def fail(msg):
    raise SystemExit(f"XZIEL_MAP_AGENT_FAIL: {msg}")

def load_plan():
    if not PLAN_PATH.is_file():
        fail(f"missing plan: {PLAN_PATH}")
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if plan.get("geometry_policy") != ALLOWED_POLICY:
        fail(f"geometry_policy must be {ALLOWED_POLICY!r}")
    if plan.get("allow_new_architecture", False):
        fail("allow_new_architecture must remain false")
    return plan

def get_target(plan):
    name = plan.get("source_object", "")
    obj = bpy.data.objects.get(name)
    if obj is None:
        fail(f"source object not found: {name!r}")
    return obj

def find_geometry_nodes_modifier(obj, expected_group=None):
    mods = [m for m in obj.modifiers if m.type == "NODES" and m.node_group]
    if expected_group:
        mods = [m for m in mods if m.node_group.name == expected_group]
    if not mods:
        fail(f"required Geometry Nodes modifier not found on {obj.name!r}")
    return mods[0]

def serialize_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return list(value)
    except Exception:
        return str(value)

def list_modifier_inputs(mod):
    group = mod.node_group
    items = []
    try:
        tree = list(group.interface.items_tree)
    except Exception:
        tree = []
    for item in tree:
        if getattr(item, "item_type", None) != "SOCKET":
            continue
        if getattr(item, "in_out", None) != "INPUT":
            continue
        ident = getattr(item, "identifier", "")
        if not ident:
            continue
        has_override = ident in mod.keys()
        try:
            value = mod[ident] if has_override else getattr(item, "default_value", None)
        except Exception:
            value = getattr(item, "default_value", None)
        items.append({
            "name": item.name,
            "identifier": ident,
            "socket_type": getattr(item, "socket_type", getattr(item, "bl_socket_idname", "")),
            "hide_in_modifier": bool(getattr(item, "hide_in_modifier", False)),
            "has_modifier_override": bool(has_override),
            "value": serialize_value(value),
            "interface_default": serialize_value(getattr(item, "default_value", None)),
            "min_value": serialize_value(getattr(item, "min_value", None)),
            "max_value": serialize_value(getattr(item, "max_value", None)),
        })
    return items

def coerce_value(old, new):
    if isinstance(old, bool):
        return bool(new)
    if isinstance(old, int) and not isinstance(old, bool):
        return int(new)
    if isinstance(old, float):
        return float(new)
    try:
        if hasattr(old, "__len__") and not isinstance(old, str):
            vals = list(new)
            return vals
    except Exception:
        pass
    return new

def apply_gn_inputs(mod, requested):
    if not requested:
        return []
    sockets = {x["name"]: x for x in list_modifier_inputs(mod)}
    sockets_by_id = {x["identifier"]: x for x in sockets.values()}
    applied = []
    for key, new_value in requested.items():
        socket = sockets.get(key) or sockets_by_id.get(key)
        if socket is None:
            fail(f"Geometry Nodes input {key!r} is not exposed by {mod.node_group.name!r}")
        ident = socket["identifier"]
        if ident in mod.keys():
            try:
                old = mod[ident]
            except Exception:
                old = socket.get("interface_default")
        else:
            old = socket.get("interface_default")
        try:
            mod[ident] = coerce_value(old, new_value)
        except Exception as exc:
            fail(f"could not set {key!r}: {exc}")
        applied.append({
            "name": socket["name"],
            "identifier": ident,
            "before": serialize_value(old),
            "after": serialize_value(mod[ident]),
        })
    return applied

def apply_transform(obj, transform):
    if not transform:
        return
    if "location" in transform:
        obj.location = Vector(transform["location"])
    if "rotation_deg" in transform:
        obj.rotation_euler = tuple(math.radians(float(v)) for v in transform["rotation_deg"])
    if "scale" in transform:
        obj.scale = Vector(transform["scale"])

def evaluated_mesh_stats(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    try:
        if not mesh.vertices:
            fail("evaluated architecture has no vertices")
        verts = [ev.matrix_world @ v.co for v in mesh.vertices]
        mn = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
        mx = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
        return {
            "vertices": len(mesh.vertices),
            "polygons": len(mesh.polygons),
            "center": list((mn + mx) * 0.5),
            "min": list(mn),
            "max": list(mx),
            "size": list(mx - mn),
        }
    finally:
        ev.to_mesh_clear()

def bake_evaluated_object(scene, source):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = source.evaluated_get(deps)
    try:
        mesh = bpy.data.meshes.new_from_object(
            ev,
            preserve_all_data_layers=True,
            depsgraph=deps,
        )
    except TypeError:
        mesh = bpy.data.meshes.new_from_object(ev, depsgraph=deps)
    if mesh is None or not mesh.vertices:
        fail("could not bake evaluated architecture")
    baked = bpy.data.objects.new("XZIEL_MAP_AGENT_BAKED", mesh)
    scene.collection.objects.link(baked)
    baked.matrix_world = ev.matrix_world.copy()
    return baked

def ensure_camera(scene, lens):
    data = bpy.data.cameras.get("XZIEL_MAP_AGENT_CAMERA_DATA") or bpy.data.cameras.new("XZIEL_MAP_AGENT_CAMERA_DATA")
    cam = bpy.data.objects.get("XZIEL_MAP_AGENT_CAMERA") or bpy.data.objects.new("XZIEL_MAP_AGENT_CAMERA", data)
    if cam.name not in scene.collection.objects:
        try:
            scene.collection.objects.link(cam)
        except RuntimeError:
            pass
    scene.camera = cam
    cam.data.lens = lens
    return cam

def point_camera(cam, target):
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()

def ensure_world(scene, cfg):
    if scene.world is None:
        scene.world = bpy.data.worlds.new("XZIEL_MAP_AGENT_WORLD")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = tuple(cfg.get("world_color", [0.025, 0.03, 0.04, 1.0]))
        bg.inputs["Strength"].default_value = float(cfg.get("world_strength", 0.45))

def ensure_lights(scene, center, size):
    ext = max(size.x, size.y, size.z)
    configs = [
        ("KEY", Vector((0.7, -0.8, 1.1)), 2400.0, ext * 0.55),
        ("FILL", Vector((-0.8, 0.2, 0.65)), 1400.0, ext * 0.70),
        ("RIM", Vector((0.1, 0.8, 1.3)), 1800.0, ext * 0.45),
    ]
    out = []
    for name, offset, energy, area in configs:
        ld = bpy.data.lights.get(f"XZIEL_MAP_AGENT_{name}_DATA") or bpy.data.lights.new(f"XZIEL_MAP_AGENT_{name}_DATA", "AREA")
        lo = bpy.data.objects.get(f"XZIEL_MAP_AGENT_{name}") or bpy.data.objects.new(f"XZIEL_MAP_AGENT_{name}", ld)
        if lo.name not in scene.collection.objects:
            try:
                scene.collection.objects.link(lo)
            except RuntimeError:
                pass
        lo.location = center + offset * ext
        ld.energy = energy
        ld.shape = "DISK"
        ld.size = max(area, 2.0)
        lo.rotation_euler = (center - lo.location).to_track_quat("-Z", "Y").to_euler()
        out.append(lo)
    return out

def isolate(scene, target, keep):
    allowed = {target.name, *(o.name for o in keep)}
    for obj in scene.objects:
        if hasattr(obj, "hide_render"):
            obj.hide_render = obj.name not in allowed
    target.hide_render = False

def auto_cameras(stats):
    center = Vector(stats["center"])
    mn = Vector(stats["min"])
    size = Vector(stats["size"])
    ext = max(size.x, size.y, size.z)
    eye_z = mn.z + max(1.65, min(2.0, size.z * 0.08))
    return [
        {
            "name": "01-exterior-front-3q.png",
            "position": list(center + Vector((ext * 0.9, -ext * 0.9, ext * 0.55))),
            "look_at": list(center + Vector((0, 0, size.z * 0.05))),
        },
        {
            "name": "02-exterior-rear-3q.png",
            "position": list(center + Vector((-ext * 0.9, ext * 0.9, ext * 0.5))),
            "look_at": list(center),
        },
        {
            "name": "03-exterior-side.png",
            "position": list(center + Vector((ext * 1.15, 0, ext * 0.3))),
            "look_at": list(center),
        },
        {
            "name": "04-interior-center.png",
            "position": [center.x, center.y, eye_z],
            "look_at": [center.x, center.y + min(size.y * 0.30, 8.0), eye_z + 1.0],
        },
        {
            "name": "05-interior-nave-a.png",
            "position": [center.x, center.y - size.y * 0.18, eye_z],
            "look_at": [center.x, center.y + size.y * 0.25, eye_z + 1.0],
        },
        {
            "name": "06-interior-nave-b.png",
            "position": [center.x, center.y + size.y * 0.18, eye_z],
            "look_at": [center.x, center.y - size.y * 0.25, eye_z + 1.0],
        },
    ]

def render_views(scene, cam, views):
    rendered = []
    for view in views:
        name = view["name"]
        cam.location = Vector(view["position"])
        point_camera(cam, view["look_at"])
        scene.render.filepath = str(OUT / name)
        bpy.ops.render.render(write_still=True)
        p = OUT / name
        rendered.append({
            "name": name,
            "bytes": p.stat().st_size if p.is_file() else 0,
            "position": view["position"],
            "look_at": view["look_at"],
        })
    return rendered

def export_glb(target, filename):
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    path = OUT / filename
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    if not path.is_file():
        fail("GLB export missing")
    return path

plan = load_plan()
scene = bpy.context.scene
target = get_target(plan)
expected_group = plan.get("geometry_node_group")
modifier = find_geometry_nodes_modifier(target, expected_group)

before_inputs = list_modifier_inputs(modifier)
apply_transform(target, plan.get("object_transform", {}))
applied_inputs = apply_gn_inputs(modifier, plan.get("geometry_nodes_inputs", {}))

baked_target = bake_evaluated_object(scene, target)
stats = evaluated_mesh_stats(baked_target)
quality = plan.get("quality_gate", {})
if stats["vertices"] < int(quality.get("min_vertices", 1)):
    fail(f"vertex gate failed: {stats['vertices']}")
if stats["polygons"] < int(quality.get("min_polygons", 1)):
    fail(f"polygon gate failed: {stats['polygons']}")

render_cfg = plan.get("render", {})
scene.render.engine = render_cfg.get("engine", "BLENDER_EEVEE")
scene.render.image_settings.media_type = "IMAGE"
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_x = int(render_cfg.get("width", 1280))
scene.render.resolution_y = int(render_cfg.get("height", 800))
scene.render.resolution_percentage = 100

ensure_world(scene, render_cfg)
center = Vector(stats["center"])
size = Vector(stats["size"])
cam = ensure_camera(scene, float(render_cfg.get("lens_mm", 38.0)))
lights = ensure_lights(scene, center, size)
isolate(scene, baked_target, [cam, *lights])

views = plan.get("camera_views") or auto_cameras(stats)
renders = render_views(scene, cam, views)

glb_name = plan.get("export_glb", "xziel-map-agent.glb")
glb = export_glb(baked_target, glb_name)
min_glb = int(quality.get("min_glb_bytes", 1))
if glb.stat().st_size < min_glb:
    fail(f"GLB size gate failed: {glb.stat().st_size} < {min_glb}")

report = {
    "status": "PASS",
    "geometry_policy": plan["geometry_policy"],
    "allow_new_architecture": False,
    "source_object": target.name,
    "baked_object": baked_target.name,
    "geometry_node_group": modifier.node_group.name,
    "source_revision": os.environ.get("XZIEL_SOURCE_REV", ""),
    "blender_version": bpy.app.version_string,
    "stats": stats,
    "modifier_property_keys": list(modifier.keys()),
    "modifier_inputs_before": before_inputs,
    "modifier_inputs_after": list_modifier_inputs(modifier),
    "applied_inputs": applied_inputs,
    "renders": renders,
    "glb": glb.name,
    "glb_bytes": glb.stat().st_size,
    "plan": str(PLAN_PATH),
}
(OUT / "agent-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
(OUT / "agent-report.txt").write_text(
    "\n".join([
        "XZIEL MAP BUILDER AGENT",
        "STATUS=PASS",
        f"POLICY={plan['geometry_policy']}",
        f"SOURCE_OBJECT={target.name}",
        f"NODE_GROUP={modifier.node_group.name}",
        f"VERTICES={stats['vertices']}",
        f"POLYGONS={stats['polygons']}",
        f"GLB_BYTES={glb.stat().st_size}",
        f"RENDERS={len(renders)}",
    ]) + "\n",
    encoding="utf-8",
)
print("XZIEL_MAP_BUILDER_AGENT_PASS")
print(json.dumps(report, indent=2))
