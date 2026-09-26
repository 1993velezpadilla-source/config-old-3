#!/usr/bin/env python3
"""Compile BO3 Nacht GLB material slots into a stable XZIEL binding manifest.

The XZMS converter preserves glTF primitive.material as each submesh's
materialIndex. This compiler walks the same scene/node/primitive order without
touching vertex payloads and records the corresponding glTF material name for
every runtime mesh/submesh. The result is build-time metadata used to bind
CUE4Parse material JSON/texture exports to the already-proven XZMS geometry.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONVERTER = ROOT / "tools/maps/convert_glb_to_xzmesh.py"
EXPECTED_MESHES = 492
NO_MATERIAL = 0xFFFFFFFF


def load_converter():
    spec = importlib.util.spec_from_file_location(
        "xzmesh_converter", CONVERTER
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load {CONVERTER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


converter = load_converter()


def index_glbs(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in root.rglob("*.glb"):
        key = path.stem.lower()
        if key in result:
            raise SystemExit(
                f"duplicate GLB stem {path.stem!r}: "
                f"{result[key]} vs {path}"
            )
        result[key] = path
    return result


def primitive_material_rows(doc: dict) -> list[dict]:
    nodes = doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    materials = doc.get("materials", [])
    scenes = doc.get("scenes", [])
    scene_index = int(doc.get("scene", 0) or 0)

    if scenes and 0 <= scene_index < len(scenes):
        roots = scenes[scene_index].get("nodes", [])
    elif nodes:
        roots = list(range(len(nodes)))
    else:
        raise ValueError("GLB contains no scene nodes")

    rows: list[dict] = []

    def visit(node_index: int) -> None:
        if (
            not isinstance(node_index, int)
            or not 0 <= node_index < len(nodes)
        ):
            raise ValueError(f"invalid node index {node_index}")

        node = nodes[node_index]
        mesh_index = node.get("mesh")
        if isinstance(mesh_index, int):
            if not 0 <= mesh_index < len(meshes):
                raise ValueError(
                    f"node {node_index} references invalid mesh "
                    f"{mesh_index}"
                )

            primitives = meshes[mesh_index].get("primitives", [])
            for primitive_index, primitive in enumerate(primitives):
                material = primitive.get("material")

                if isinstance(material, int):
                    if not 0 <= material < len(materials):
                        raise ValueError(
                            f"primitive references invalid material "
                            f"{material}"
                        )
                    name = materials[material].get("name")
                    if not isinstance(name, str) or not name.strip():
                        name = f"MaterialSlot_{material}"
                    material_index = material
                else:
                    name = None
                    material_index = NO_MATERIAL

                rows.append({
                    "submeshIndex": len(rows),
                    "sourceNodeIndex": node_index,
                    "sourceMeshIndex": mesh_index,
                    "sourcePrimitiveIndex": primitive_index,
                    "materialIndex": material_index,
                    "materialName": name,
                })

        for child in node.get("children", []):
            visit(child)

    for root in roots:
        visit(root)

    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb-root", type=Path, required=True)
    ap.add_argument("--bundle-manifest", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    bundle = json.loads(
        args.bundle_manifest.read_text(encoding="utf-8")
    )
    meshes = bundle.get("meshes", [])
    if (
        bundle.get("format") != "xziel_xzmesh_bundle_v1"
        or len(meshes) != EXPECTED_MESHES
    ):
        raise SystemExit(
            f"expected {EXPECTED_MESHES}-mesh XZMS bundle manifest"
        )

    glbs = index_glbs(args.glb_root)
    output_meshes: list[dict] = []
    unique_materials: set[str] = set()
    no_material_submeshes = 0
    total_submeshes = 0

    for mesh_row in meshes:
        index = int(mesh_row["index"])
        source_glb = Path(mesh_row["sourceGlb"]).name
        glb = glbs.get(Path(source_glb).stem.lower())
        if glb is None:
            raise SystemExit(
                f"missing GLB for bundle mesh {index}: {source_glb}"
            )

        doc, _ = converter.parse_glb(glb)
        material_rows = primitive_material_rows(doc)

        expected_submeshes = int(
            mesh_row.get("stats", {}).get("submeshCount", -1)
        )
        if len(material_rows) != expected_submeshes:
            raise SystemExit(
                f"mesh {index} material/submesh drift: "
                f"{len(material_rows)} != {expected_submeshes}"
            )

        for row in material_rows:
            name = row["materialName"]
            if name is None:
                no_material_submeshes += 1
            else:
                unique_materials.add(name.lower())

        total_submeshes += len(material_rows)
        output_meshes.append({
            "meshIndex": index,
            "sourcePath": mesh_row["sourcePath"],
            "sourceGlb": source_glb,
            "runtimeFile": mesh_row["runtimeFile"],
            "submeshes": material_rows,
        })

    summary = {
        "meshCount": len(output_meshes),
        "submeshCount": total_submeshes,
        "uniqueMaterialNameCount": len(unique_materials),
        "submeshesWithoutMaterial": no_material_submeshes,
        "allMeshesMapped": len(output_meshes) == EXPECTED_MESHES,
        "materialBindingGeometryReady": True,
        "textureFilesResolved": False,
    }

    payload = {
        "schemaVersion": 1,
        "format": "xziel_nacht_material_bindings_v1",
        "mapId": "xziel_nacht_bo3",
        "policy": {
            "materialIndexSource": "glTF primitive.material",
            "submeshOrderMatches": "convert_glb_to_xzmesh.flatten_scene",
            "zeroOmission": True,
            "textureResolutionPending": True,
        },
        "summary": summary,
        "meshes": output_meshes,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    print(
        "XZIEL_NACHT_MATERIAL_BINDINGS_OK",
        json.dumps(summary, sort_keys=True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
