import bpy
import json
import os
from pathlib import Path

out = Path(os.environ.get("XOGOT_GLB_OUT", "xogot/assets/church/sanctum_current.glb"))
report_path = Path(os.environ.get("XOGOT_GLB_REPORT", "xogot/assets/church/sanctum_current.report.json"))
out.parent.mkdir(parents=True, exist_ok=True)

for obj in bpy.context.scene.objects:
    obj.select_set(False)

targets = []
primary = bpy.data.collections.get("xziel_snapshot_export")
if primary:
    targets.extend([o for o in primary.all_objects if o.type == "MESH" and not o.hide_render])

polish_names = {
    "SANCTUM_EXTERIOR_FLOOR_VISUAL",
    "SANCTUM_UPPER_FLOOR_VISUAL",
    "SANCTUM_SPAWNER_WINDOWS_GLASS",
    "SANCTUM_SPAWNER_WINDOWS_BOARDS",
}
for obj in bpy.context.scene.objects:
    if obj.type == "MESH" and not obj.hide_render and obj.name in polish_names and obj not in targets:
        targets.append(obj)

if not targets:
    targets = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]

if not targets:
    raise SystemExit("XOGOT_GLTF_FAIL: no visible mesh objects")

triangles = 0
for obj in targets:
    obj.select_set(True)
    obj.data.calc_loop_triangles()
    triangles += len(obj.data.loop_triangles)

bpy.context.view_layer.objects.active = targets[0]

bpy.ops.export_scene.gltf(
    filepath=str(out),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_materials="EXPORT",
    export_cameras=False,
    export_lights=False,
)

if not out.is_file() or out.stat().st_size < 1_000_000:
    raise SystemExit("XOGOT_GLTF_FAIL: output missing or unexpectedly small")

report = {
    "format": "glTF 2.0 GLB",
    "target": "Godot 4.6 / Xogot",
    "objects": len(targets),
    "triangles": triangles,
    "bytes": out.stat().st_size,
    "names": [o.name for o in targets],
}
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("XOGOT_GLTF_EXPORT_GREEN", json.dumps({k: report[k] for k in ("objects", "triangles", "bytes")}))
