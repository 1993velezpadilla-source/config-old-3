import bpy
import json
import os
from collections import defaultdict
from pathlib import Path

OUT = Path(os.environ.get("SANCTUM_V2_MATERIAL_INVENTORY_OUT", "sanctum-v2-material-inventory"))
OUT.mkdir(parents=True, exist_ok=True)
TARGET_NAME = "Catehdral"

obj = bpy.data.objects.get(TARGET_NAME)
if obj is None:
    raise SystemExit(f"Missing upstream cathedral object {TARGET_NAME!r}")

deps = bpy.context.evaluated_depsgraph_get()
ev = obj.evaluated_get(deps)
mesh = ev.to_mesh()

try:
    mats = list(mesh.materials)
    rows = []
    counts = defaultdict(int)
    area = defaultdict(float)

    for poly in mesh.polygons:
        idx = int(poly.material_index)
        counts[idx] += 1
        area[idx] += float(poly.area)

    total_polys = len(mesh.polygons)
    total_area = sum(area.values()) or 1.0

    for idx, mat in enumerate(mats):
        name = mat.name if mat else "<None>"
        poly_count = counts.get(idx, 0)
        surface_area = area.get(idx, 0.0)
        rows.append({
            "material_index": idx,
            "material_name": name,
            "polygon_count": poly_count,
            "polygon_share": poly_count / total_polys if total_polys else 0.0,
            "surface_area_local": surface_area,
            "surface_area_share": surface_area / total_area,
            "uses_nodes": bool(mat and mat.use_nodes),
            "node_types": sorted({n.bl_idname for n in mat.node_tree.nodes}) if mat and mat.use_nodes and mat.node_tree else [],
            "image_names": sorted({n.image.name for n in mat.node_tree.nodes if hasattr(n, "image") and n.image}) if mat and mat.use_nodes and mat.node_tree else [],
        })

    rows.sort(key=lambda r: (r["surface_area_local"], r["polygon_count"]), reverse=True)

    report = {
        "source_object": obj.name,
        "geometry_nodes": [m.node_group.name for m in obj.modifiers if m.type == "NODES" and m.node_group],
        "evaluated_vertices": len(mesh.vertices),
        "evaluated_polygons": total_polys,
        "material_slot_count": len(mats),
        "materials_by_surface_area": rows,
    }

    (OUT / "cathedral-material-inventory.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        f"source_object={obj.name}",
        f"geometry_nodes={report['geometry_nodes']}",
        f"evaluated_vertices={len(mesh.vertices)}",
        f"evaluated_polygons={total_polys}",
        f"material_slot_count={len(mats)}",
        "",
        "rank | idx | area_share | poly_share | polygons | material | images",
    ]
    for rank, r in enumerate(rows, 1):
        imgs = ",".join(r["image_names"]) if r["image_names"] else "-"
        lines.append(
            f"{rank:02d} | {r['material_index']:02d} | {r['surface_area_share']:.4f} | "
            f"{r['polygon_share']:.4f} | {r['polygon_count']:6d} | {r['material_name']} | {imgs}"
        )
    (OUT / "cathedral-material-inventory.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("SANCTUM_V2_MATERIAL_INVENTORY_OK")
    print("\n".join(lines[:80]))
finally:
    ev.to_mesh_clear()
