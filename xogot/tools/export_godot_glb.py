import bpy
import json
import os
from pathlib import Path

out = Path(os.environ.get("XOGOT_GLB_OUT", "xogot/assets/church/sanctum_current.glb"))
report_path = Path(os.environ.get("XOGOT_GLB_REPORT", "xogot/assets/church/sanctum_current.report.json"))
out.parent.mkdir(parents=True, exist_ok=True)

for obj in bpy.context.scene.objects:
    obj.select_set(False)

# The Hero bake marks the actual church meshes with the xziel_snapshot_export
# custom property. Do not look for a collection with that name: the packed
# .blend does not guarantee such a collection exists.
authority = [
    o for o in bpy.context.scene.objects
    if o.type == "MESH"
    and not o.hide_render
    and bool(o.get("xziel_snapshot_export", False))
]

polish_names = {
    "SANCTUM_EXTERIOR_FLOOR_VISUAL",
    "SANCTUM_UPPER_FLOOR_VISUAL",
    "SANCTUM_SPAWNER_WINDOWS_GLASS",
    "SANCTUM_SPAWNER_WINDOWS_BOARDS",
}
polish = [
    o for o in bpy.context.scene.objects
    if o.type == "MESH" and not o.hide_render and o.name in polish_names
]

targets = list(authority)
for obj in polish:
    if obj not in targets:
        targets.append(obj)

# Safety fallback for older Hero packs that predate the custom property.
if not authority:
    targets = [
        o for o in bpy.context.scene.objects
        if o.type == "MESH" and not o.hide_render
    ]

if not targets:
    raise SystemExit("XOGOT_GLTF_FAIL: no visible mesh objects")

triangles = 0
for obj in targets:
    obj.select_set(True)
    obj.data.calc_loop_triangles()
    triangles += len(obj.data.loop_triangles)

# Never allow a polish-only GLB to pass again. The failed v1 artifact had only
# 4 objects / 74 triangles. A real church authority is orders of magnitude
# larger, so this is intentionally conservative.
if triangles < 1000:
    raise SystemExit(
        f"XOGOT_GLTF_FAIL: detailed church missing; only {len(targets)} objects / {triangles} triangles"
    )

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
    "authority_objects": len(authority),
    "polish_objects": len(polish),
    "objects": len(targets),
    "triangles": triangles,
    "bytes": out.stat().st_size,
    "names": [o.name for o in targets],
}
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(
    "XOGOT_GLTF_EXPORT_GREEN",
    json.dumps({k: report[k] for k in ("authority_objects", "polish_objects", "objects", "triangles", "bytes")}),
)
