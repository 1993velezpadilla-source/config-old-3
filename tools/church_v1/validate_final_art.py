import bpy
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(os.environ.get("CHURCH_V1_SPEC", ROOT / "church_v1/spec/church_v1.json"))
SOURCE = Path(os.environ.get("CHURCH_FINAL_SOURCE", ROOT / "church_v1/source/church_final.glb"))
OUT = Path(os.environ.get("CHURCH_V1_OUT", ROOT / "church_v1/out"))
OUT.mkdir(parents=True, exist_ok=True)

spec = json.loads(SPEC.read_text(encoding="utf-8"))
targets = spec["finalArtTargets"]

if not SOURCE.exists():
    raise SystemExit(f"FINAL_ART_SOURCE_MISSING: {SOURCE}")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
materials = {m for o in meshes for m in o.data.materials if m}
images = {img for img in bpy.data.images if img and img.source != "GENERATED"}

triangles = 0
blockout_objects = []
for obj in meshes:
    obj.data.calc_loop_triangles()
    triangles += len(obj.data.loop_triangles)
    if obj.get("xziel_stage") == "blockout" or obj.name.startswith("BLOCKOUT_"):
        blockout_objects.append(obj.name)

image_backed_materials = 0
for mat in materials:
    if not mat.use_nodes or not mat.node_tree:
        continue
    has_image = any(
        n.type == "TEX_IMAGE" and getattr(n, "image", None)
        for n in mat.node_tree.nodes
    )
    if has_image:
        image_backed_materials += 1

errors = []
warnings = []

if blockout_objects:
    errors.append(f"blockout primitives present in final source: {blockout_objects[:12]}")
if triangles < targets["trianglesMin"]:
    errors.append(f"triangle count {triangles} below final-art minimum {targets['trianglesMin']}")
if triangles > targets["trianglesMax"]:
    warnings.append(f"triangle count {triangles} exceeds mobile review ceiling {targets['trianglesMax']}")
if len(meshes) < targets["meshObjectsMin"]:
    errors.append(f"mesh object count {len(meshes)} below {targets['meshObjectsMin']}")
if len(materials) < targets["materialsMin"]:
    errors.append(f"material count {len(materials)} below {targets['materialsMin']}")
if image_backed_materials < targets["imageBackedMaterialsMin"]:
    errors.append(
        f"image-backed material count {image_backed_materials} below {targets['imageBackedMaterialsMin']}"
    )
if len(images) < targets["uniqueImagesMin"]:
    errors.append(f"unique image count {len(images)} below {targets['uniqueImagesMin']}")

report = {
    "ok": not errors,
    "source": str(SOURCE),
    "triangles": triangles,
    "meshObjects": len(meshes),
    "materials": len(materials),
    "imageBackedMaterials": image_backed_materials,
    "uniqueImages": len(images),
    "blockoutObjectsFound": blockout_objects,
    "errors": errors,
    "warnings": warnings,
    "policy": {
        "primitiveOnlyFinalArtRejected": True,
        "pbrImageBackedMaterialsRequired": True
    }
}
(OUT / "final_art_validation.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8"
)

if errors:
    raise SystemExit("CHURCH_V1_FINAL_ART_REJECTED: " + "; ".join(errors))

print("CHURCH_V1_FINAL_ART_OK", json.dumps(report))
