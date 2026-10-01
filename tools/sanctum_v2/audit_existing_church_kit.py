import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

OUT = Path(os.environ.get("SANCTUM_V2_AUDIT_OUT", "sanctum-v2-audit"))
OUT.mkdir(parents=True, exist_ok=True)

TOKENS = ("church", "cathedral", "gothic", "chapel")


def has_token(text):
    s = (text or "").lower()
    return any(t in s for t in TOKENS)


def geometry_node_names(obj):
    names = []
    for mod in getattr(obj, "modifiers", []):
        if mod.type == "NODES" and getattr(mod, "node_group", None):
            names.append(mod.node_group.name)
    return names


def evaluated_stats(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = None
    try:
        mesh = ev.to_mesh()
        if mesh is None:
            return None
        verts = len(mesh.vertices)
        polys = len(mesh.polygons)
        if verts:
            pts = [ev.matrix_world @ v.co for v in mesh.vertices]
            mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
            mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
            center = (mn + mx) * 0.5
            size = mx - mn
        else:
            center = ev.matrix_world.translation.copy()
            size = Vector((1.0, 1.0, 1.0))
        return {
            "vertices": verts,
            "polygons": polys,
            "center": [center.x, center.y, center.z],
            "size": [size.x, size.y, size.z],
        }
    except Exception as exc:
        return {"error": repr(exc)}
    finally:
        try:
            ev.to_mesh_clear()
        except Exception:
            pass


def ensure_review_rig(scene):
    cam_data = bpy.data.cameras.get("SANCTUM_V2_AUDIT_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_V2_AUDIT_CAMERA_DATA")
    cam = bpy.data.objects.get("SANCTUM_V2_AUDIT_CAMERA") or bpy.data.objects.new("SANCTUM_V2_AUDIT_CAMERA", cam_data)
    if cam.name not in scene.collection.objects:
        try:
            scene.collection.objects.link(cam)
        except RuntimeError:
            pass
    scene.camera = cam

    key_data = bpy.data.lights.get("SANCTUM_V2_AUDIT_KEY_DATA") or bpy.data.lights.new("SANCTUM_V2_AUDIT_KEY_DATA", "AREA")
    key = bpy.data.objects.get("SANCTUM_V2_AUDIT_KEY") or bpy.data.objects.new("SANCTUM_V2_AUDIT_KEY", key_data)
    if key.name not in scene.collection.objects:
        try:
            scene.collection.objects.link(key)
        except RuntimeError:
            pass

    fill_data = bpy.data.lights.get("SANCTUM_V2_AUDIT_FILL_DATA") or bpy.data.lights.new("SANCTUM_V2_AUDIT_FILL_DATA", "AREA")
    fill = bpy.data.objects.get("SANCTUM_V2_AUDIT_FILL") or bpy.data.objects.new("SANCTUM_V2_AUDIT_FILL", fill_data)
    if fill.name not in scene.collection.objects:
        try:
            scene.collection.objects.link(fill)
        except RuntimeError:
            pass

    return cam, key, fill


def point_camera(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def render_candidate(obj, index):
    scene = bpy.context.scene
    stats = evaluated_stats(obj) or {}
    if "center" not in stats or "size" not in stats:
        return {"object": obj.name, "rendered": False, "stats": stats}

    center = Vector(stats["center"])
    size = Vector(stats["size"])
    extent = max(size.x, size.y, size.z, 1.0)

    previous = {}
    for other in scene.objects:
        if hasattr(other, "hide_render"):
            previous[other.name] = other.hide_render
            if other.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
                other.hide_render = True

    obj.hide_render = False
    cam, key, fill = ensure_review_rig(scene)
    cam.hide_render = False
    key.hide_render = False
    fill.hide_render = False

    cam.location = center + Vector((extent * 1.35, -extent * 1.35, extent * 0.82))
    cam.data.lens = 50
    cam.data.sensor_width = 36
    point_camera(cam, center)

    key.location = center + Vector((extent * 0.55, -extent * 0.35, extent * 1.25))
    key.data.energy = 1600
    key.data.shape = "DISK"
    key.data.size = max(extent * 0.45, 2.0)
    point_camera(key, center)

    fill.location = center + Vector((-extent * 0.65, extent * 0.25, extent * 0.65))
    fill.data.energy = 900
    fill.data.shape = "DISK"
    fill.data.size = max(extent * 0.6, 2.0)
    point_camera(fill, center)

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("SANCTUM_V2_AUDIT_WORLD")
        scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.028, 0.028, 0.035, 1.0)
        bg.inputs["Strength"].default_value = 0.3

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in obj.name)
    out = OUT / f"{index:02d}-{safe}.png"
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)

    for name, state in previous.items():
        o = bpy.data.objects.get(name)
        if o is not None:
            o.hide_render = state

    return {
        "object": obj.name,
        "rendered": True,
        "image": out.name,
        "stats": stats,
        "geometry_nodes": geometry_node_names(obj),
    }


node_groups = sorted(
    [ng.name for ng in bpy.data.node_groups if has_token(ng.name)]
)

candidate_objects = []
for obj in bpy.data.objects:
    node_names = geometry_node_names(obj)
    if has_token(obj.name) or any(has_token(n) for n in node_names):
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            candidate_objects.append(obj)

candidate_objects = sorted(candidate_objects, key=lambda o: o.name.lower())

collections = sorted([c.name for c in bpy.data.collections if has_token(c.name)])

report = {
    "source_blend": bpy.data.filepath,
    "blender_version": bpy.app.version_string,
    "matching_node_groups": node_groups,
    "matching_collections": collections,
    "candidate_objects": [
        {
            "name": o.name,
            "type": o.type,
            "geometry_nodes": geometry_node_names(o),
        }
        for o in candidate_objects
    ],
    "renders": [],
}

# Render only existing upstream-authored candidates. This script does not build church geometry.
for i, obj in enumerate(candidate_objects[:12], 1):
    try:
        report["renders"].append(render_candidate(obj, i))
    except Exception as exc:
        report["renders"].append({
            "object": obj.name,
            "rendered": False,
            "error": repr(exc),
            "geometry_nodes": geometry_node_names(obj),
        })

(OUT / "existing-church-kit-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

with (OUT / "existing-church-kit-audit.txt").open("w", encoding="utf-8") as f:
    f.write(f"BLENDER={bpy.app.version_string}\n")
    f.write(f"NODE_GROUPS={len(node_groups)}\n")
    for name in node_groups:
        f.write(f"NODE_GROUP {name}\n")
    f.write(f"CANDIDATE_OBJECTS={len(candidate_objects)}\n")
    for obj in candidate_objects:
        f.write(f"OBJECT {obj.name} | GN={geometry_node_names(obj)}\n")
    rendered = [r for r in report["renders"] if r.get("rendered")]
    f.write(f"RENDERED={len(rendered)}\n")
    for item in rendered:
        f.write(f"RENDER {item['object']} -> {item['image']} | {item.get('stats')}\n")

print("SANCTUM_V2_EXISTING_ASSET_AUDIT_DONE")
print(json.dumps({
    "matchingNodeGroups": len(node_groups),
    "candidateObjects": len(candidate_objects),
    "rendered": len([r for r in report["renders"] if r.get("rendered")]),
}, indent=2))
