import bpy
import json
import os
from pathlib import Path
from mathutils import Vector

OUT = Path(os.environ.get("SANCTUM_CC0_INTERIOR_OUT", "sanctum-cc0-interior-probe"))
OUT.mkdir(parents=True, exist_ok=True)

def fail(msg):
    raise SystemExit(f"SANCTUM_CC0_INTERIOR_FAIL: {msg}")

def mesh_objects(scene):
    return [o for o in scene.objects if o.type == "MESH"]

def evaluated_scene_stats(objects):
    deps = bpy.context.evaluated_depsgraph_get()
    total_vertices = 0
    total_polygons = 0
    material_names = set()
    all_points = []
    per_object = []
    for obj in objects:
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        try:
            total_vertices += len(mesh.vertices)
            total_polygons += len(mesh.polygons)
            pts = [ev.matrix_world @ v.co for v in mesh.vertices]
            all_points.extend(pts)
            for slot in obj.material_slots:
                if slot.material:
                    material_names.add(slot.material.name)
            if pts:
                mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
                mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
                per_object.append({
                    "name": obj.name,
                    "vertices": len(mesh.vertices),
                    "polygons": len(mesh.polygons),
                    "min": list(mn),
                    "max": list(mx),
                    "size": list(mx - mn),
                })
        finally:
            ev.to_mesh_clear()

    if not all_points:
        fail("no mesh vertices found")

    mn = Vector((min(p.x for p in all_points), min(p.y for p in all_points), min(p.z for p in all_points)))
    mx = Vector((max(p.x for p in all_points), max(p.y for p in all_points), max(p.z for p in all_points)))
    return {
        "mesh_objects": len(objects),
        "vertices": total_vertices,
        "polygons": total_polygons,
        "materials": sorted(material_names),
        "material_count": len(material_names),
        "min": list(mn),
        "max": list(mx),
        "center": list((mn + mx) * 0.5),
        "size": list(mx - mn),
        "objects": sorted(per_object, key=lambda x: x["polygons"], reverse=True),
    }

def ensure_camera(scene):
    data = bpy.data.cameras.get("SANCTUM_CC0_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_CC0_CAMERA_DATA")
    cam = bpy.data.objects.get("SANCTUM_CC0_CAMERA") or bpy.data.objects.new("SANCTUM_CC0_CAMERA", data)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 34
    cam.data.clip_start = 0.05
    cam.data.clip_end = 5000
    return cam

def point_camera(cam, target):
    direction = Vector(target) - cam.location
    if direction.length < 1e-6:
        direction = Vector((0, 1, 0))
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def render(scene, cam, name, position, target):
    cam.location = Vector(position)
    point_camera(cam, target)
    scene.render.filepath = str(OUT / name)
    bpy.ops.render.render(write_still=True)
    p = OUT / name
    if not p.is_file() or p.stat().st_size < 3000:
        fail(f"render failed: {name}")
    return {"name": name, "bytes": p.stat().st_size, "position": list(position), "look_at": list(target)}

def review_views(stats):
    center = Vector(stats["center"])
    mn = Vector(stats["min"])
    size = Vector(stats["size"])
    horizontal = max(size.x, size.y)
    ext = max(size.x, size.y, size.z)
    eye = mn.z + min(max(1.7, size.z * 0.08), max(1.7, size.z * 0.25))
    views = [
        ("01-exterior-front-3q.png", center + Vector((ext * 0.8, -ext * 0.8, ext * 0.45)), center),
        ("02-exterior-rear-3q.png", center + Vector((-ext * 0.8, ext * 0.8, ext * 0.4)), center),
        ("03-exterior-side.png", center + Vector((ext * 1.1, 0, ext * 0.25)), center),
    ]

    if size.y >= size.x:
        axis = Vector((0, 1, 0))
        lateral = Vector((1, 0, 0))
    else:
        axis = Vector((1, 0, 0))
        lateral = Vector((0, 1, 0))

    c_eye = Vector((center.x, center.y, eye))
    views.extend([
        ("04-interior-center.png", c_eye - axis * horizontal * 0.18, c_eye + axis * horizontal * 0.28),
        ("05-interior-reverse.png", c_eye + axis * horizontal * 0.18, c_eye - axis * horizontal * 0.28),
        ("06-interior-across.png", c_eye - lateral * min(size.x, size.y) * 0.16, c_eye + lateral * min(size.x, size.y) * 0.20),
    ])
    return views

def export_glb(objects):
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.hide_render = False
        obj.select_set(True)
    if not objects:
        fail("no mesh objects to export")
    bpy.context.view_layer.objects.active = objects[0]
    path = OUT / "cc0-medieval-church-interior.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
    )
    if not path.is_file() or path.stat().st_size < 100000:
        fail("GLB export missing or too small")
    return path

scene = bpy.context.scene
objects = mesh_objects(scene)
if not objects:
    fail("source .blend contains no mesh objects")

stats = evaluated_scene_stats(objects)

scene.render.engine = "BLENDER_WORKBENCH"
scene.render.image_settings.media_type = "IMAGE"
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_x = 640
scene.render.resolution_y = 400
scene.render.resolution_percentage = 100

for obj in scene.objects:
    if hasattr(obj, "hide_render"):
        obj.hide_render = obj.type != "MESH"

cam = ensure_camera(scene)
cam.hide_render = False

renders = []
for name, pos, look in review_views(stats):
    renders.append(render(scene, cam, name, pos, look))

glb = export_glb(objects)
report = {
    "status": "PASS",
    "source": "OpenGameArt Medieval Church Interior by AnyRPG",
    "license": "CC0",
    "source_url": "https://opengameart.org/content/medieval-church-interior",
    "source_file_url": "https://opengameart.org/sites/default/files/church.blend",
    "source_sha256": os.environ.get("SANCTUM_CC0_SOURCE_SHA256", ""),
    "blender_version": bpy.app.version_string,
    "stats": stats,
    "renders": renders,
    "glb": glb.name,
    "glb_bytes": glb.stat().st_size,
}
(OUT / "probe-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
(OUT / "probe-report.txt").write_text(
    "\n".join([
        "SANCTUM CC0 CHURCH INTERIOR PROBE",
        "STATUS=PASS",
        "LICENSE=CC0",
        f"MESH_OBJECTS={stats['mesh_objects']}",
        f"VERTICES={stats['vertices']}",
        f"POLYGONS={stats['polygons']}",
        f"MATERIALS={stats['material_count']}",
        f"GLB_BYTES={glb.stat().st_size}",
        f"RENDERS={len(renders)}",
    ]) + "\n",
    encoding="utf-8",
)
print("SANCTUM_CC0_INTERIOR_PROBE_PASS")
print(json.dumps(report, indent=2))
