import bpy
import bmesh
import json
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "zombies" / "monja_basica.glb"
OUT_DIR = ROOT / "build" / "monja-dismember"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_GLB = OUT_DIR / "monja_basica_dismember.glb"
REPORT = OUT_DIR / "monja_dismember_report.json"

PART_NAMES = {
    "torso": "Dismember_Torso",
    "head": "Dismember_Head",
    "left_arm": "Dismember_LeftArm",
    "right_arm": "Dismember_RightArm",
    "left_leg": "Dismember_LeftLeg",
    "right_leg": "Dismember_RightLeg",
}

def fail(message):
    print("XZOGOT_MONJA_DISMEMBER_AUTHOR_FAIL", message)
    raise SystemExit(2)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def apply_and_join_meshes():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        fail("no mesh objects in source")
    for obj in meshes:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        try:
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        except Exception:
            pass
        obj.select_set(False)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    base = bpy.context.view_layer.objects.active
    base.name = "Monja_SourceJoined"
    return base

def bounds(obj):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if not coords:
        fail("source mesh has zero vertices")
    mn = Vector(coords[0]); mx = Vector(coords[0])
    for p in coords[1:]:
        mn.x = min(mn.x, p.x); mn.y = min(mn.y, p.y); mn.z = min(mn.z, p.z)
        mx.x = max(mx.x, p.x); mx.y = max(mx.y, p.y); mx.z = max(mx.z, p.z)
    return mn, mx

def classify(center, mn, mx):
    size = mx - mn
    if size.z <= 1e-8 or size.x <= 1e-8:
        fail("invalid humanoid bounds")
    nz = (center.z - mn.z) / size.z
    cx = (mn.x + mx.x) * 0.5
    half_x = max(size.x * 0.5, 1e-8)
    nx = (center.x - cx) / half_x

    # Conservative anatomical segmentation. Every source polygon belongs to
    # exactly one output piece, so assembled pieces reproduce the source surface
    # without decimation or UV/material rebakes.
    if nz >= 0.825:
        return "head"

    if 0.405 <= nz < 0.825 and abs(nx) >= 0.48:
        return "left_arm" if nx < 0.0 else "right_arm"

    if nz < 0.405:
        # Nun robes hide much of the legs, so the lower garment is split at the
        # body centerline. The two halves meet exactly until one side is severed.
        return "left_leg" if nx < 0.0 else "right_leg"

    return "torso"

def face_center_world(obj, face):
    c = sum((obj.data.vertices[i].co for i in face.vertices), Vector()) / max(len(face.vertices), 1)
    return obj.matrix_world @ c

def build_piece(base, key, mn, mx, collection):
    dup = base.copy()
    dup.data = base.data.copy()
    dup.name = PART_NAMES[key]
    dup.data.name = PART_NAMES[key] + "_Mesh"
    collection.objects.link(dup)

    bm = bmesh.new()
    bm.from_mesh(dup.data)
    bm.faces.ensure_lookup_table()

    # bmesh polygon indices still correspond to the copied mesh face order.
    remove = []
    for f in bm.faces:
        center = dup.matrix_world @ f.calc_center_median()
        if classify(center, mn, mx) != key:
            remove.append(f)
    if remove:
        bmesh.ops.delete(bm, geom=remove, context="FACES")

    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")

    bm.to_mesh(dup.data)
    bm.free()
    dup.data.update()

    if len(dup.data.polygons) == 0:
        fail(f"{key} produced zero polygons")

    # Semantic metadata survives glTF as extras and gives Godot/tooling another
    # deterministic way to identify pieces.
    dup["xogot_dismember_part"] = key
    dup["xogot_source"] = "monja_basica.glb"
    return dup

def write_report(source_poly_count, source_vert_count, mn, mx, pieces):
    data = {
        "source": str(SOURCE.relative_to(ROOT)),
        "output": str(OUT_GLB.relative_to(ROOT)),
        "policy": {
            "decimation": False,
            "texture_rebake": False,
            "uv_regeneration": False,
            "material_preservation": True,
            "face_partition": "exclusive",
        },
        "source_vertices": source_vert_count,
        "source_polygons": source_poly_count,
        "bounds": {
            "min": [round(v, 7) for v in mn],
            "max": [round(v, 7) for v in mx],
            "size": [round(v, 7) for v in (mx - mn)],
        },
        "parts": {},
    }
    total = 0
    for key, obj in pieces.items():
        entry = {
            "object": obj.name,
            "vertices": len(obj.data.vertices),
            "polygons": len(obj.data.polygons),
            "materials": [m.name if m else None for m in obj.data.materials],
        }
        total += entry["polygons"]
        data["parts"][key] = entry
    data["partition_polygon_total"] = total
    data["polygon_conservation_ok"] = total == source_poly_count
    REPORT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if total != source_poly_count:
        fail(f"polygon conservation failed source={source_poly_count} pieces={total}")
    return data

def main():
    if not SOURCE.exists():
        fail(f"missing {SOURCE}")

    reset()
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    base = apply_and_join_meshes()
    source_poly_count = len(base.data.polygons)
    source_vert_count = len(base.data.vertices)
    mn, mx = bounds(base)

    # Delete non-mesh helpers from the unrigged source; this pass authors the
    # geometry partition only. Rig/animation retarget remains a separate gate.
    for obj in list(bpy.context.scene.objects):
        if obj != base and obj.type != "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)

    collection = bpy.context.scene.collection
    pieces = {}
    for key in PART_NAMES:
        pieces[key] = build_piece(base, key, mn, mx, collection)

    bpy.data.objects.remove(base, do_unlink=True)

    report = write_report(source_poly_count, source_vert_count, mn, mx, pieces)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in pieces.values():
        obj.select_set(True)
    bpy.context.view_layer.objects.active = pieces["torso"]

    bpy.ops.export_scene.gltf(
        filepath=str(OUT_GLB),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_extras=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=True,
        export_materials="EXPORT",
    )

    if not OUT_GLB.exists() or OUT_GLB.stat().st_size < 1024:
        fail("GLB export missing or empty")

    # Re-import the generated GLB and hard-gate object names.
    reset()
    bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
    names = {o.name for o in bpy.context.scene.objects if o.type == "MESH"}
    missing = [name for name in PART_NAMES.values() if name not in names]
    if missing:
        fail("re-import missing pieces: " + ",".join(missing))

    print("XZOGOT_MONJA_DISMEMBER_PIECES_GREEN", len(PART_NAMES))
    print("XZOGOT_MONJA_DISMEMBER_POLYGONS_GREEN", source_poly_count)
    print("XZOGOT_MONJA_DISMEMBER_GLB_GREEN", OUT_GLB.stat().st_size)
    print(json.dumps(report["parts"], sort_keys=True))

if __name__ == "__main__":
    main()
