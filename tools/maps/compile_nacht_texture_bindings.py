#!/usr/bin/env python3
"""Compile Nacht GLB material slots + CUE4Parse XZTX exports into runtime bindings."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONVERTER = ROOT / "tools/maps/convert_glb_to_xzmesh.py"
EXPECTED_MESHES = 492
EXPECTED_SUBMESHES = 1063
NO_TEXTURE = 0xFFFFFFFF


def _load_converter():
    spec = importlib.util.spec_from_file_location("xzmesh_converter", CONVERTER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load {CONVERTER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


converter = _load_converter()


def _norm(value: str) -> str:
    value = value.strip().replace("\\", "/")
    leaf = value.rsplit("/", 1)[-1]
    return leaf.split(".", 1)[0].lower()


def _glb_index(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in root.rglob("*.glb"):
        key = path.stem.lower()
        if key in out:
            raise ValueError(f"duplicate GLB stem {path.stem!r}")
        out[key] = path
    return out


def primitive_material_rows(doc: dict) -> list[dict]:
    nodes = doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    materials = doc.get("materials", [])
    scenes = doc.get("scenes", [])
    scene_index = int(doc.get("scene", 0) or 0)
    roots = scenes[scene_index].get("nodes", []) if scenes else list(range(len(nodes)))
    rows: list[dict] = []

    def visit(node_index: int) -> None:
        node = nodes[node_index]
        mesh_index = node.get("mesh")
        if isinstance(mesh_index, int):
            for primitive_index, primitive in enumerate(meshes[mesh_index].get("primitives", [])):
                material_index = primitive.get("material")
                material_name = None
                if isinstance(material_index, int):
                    if not 0 <= material_index < len(materials):
                        raise ValueError(f"invalid material index {material_index}")
                    material_name = materials[material_index].get("name")
                    if not isinstance(material_name, str) or not material_name.strip():
                        material_name = f"MaterialSlot_{material_index}"
                else:
                    material_index = NO_TEXTURE

                rows.append({
                    "submeshIndex": len(rows),
                    "materialIndex": material_index,
                    "materialName": material_name,
                    "sourceNodeIndex": node_index,
                    "sourceMeshIndex": mesh_index,
                    "sourcePrimitiveIndex": primitive_index,
                })

        for child in node.get("children", []):
            visit(int(child))

    for root in roots:
        visit(int(root))
    return rows


def semantic_priority(source: str) -> int | None:
    low = source.lower().replace("_", "")
    if "albedo" in low:
        return 0
    if "diffuse" in low:
        return 1
    if "basecolor" in low:
        return 2
    if "color" in low and not any(
        bad in low for bad in (
            "normal", "specular", "rough", "metal", "emiss", "opacity",
            "mask", "ambientocclusion", "ao",
        )
    ):
        return 3
    return None


def build_texture_choices(texture_manifest: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    textures = texture_manifest.get("textures", [])
    bindings = texture_manifest.get("bindings", [])
    by_path: dict[str, dict] = {}
    for row in textures:
        path = row.get("texturePath")
        file_name = row.get("file")
        if isinstance(path, str) and isinstance(file_name, str):
            by_path[path.lower()] = row

    chosen: dict[str, tuple[int, dict]] = {}
    for row in bindings:
        material = row.get("materialName")
        texture_path = row.get("texturePath")
        source = row.get("source", "")
        if not isinstance(material, str) or not isinstance(texture_path, str):
            continue
        priority = semantic_priority(str(source))
        if priority is None:
            continue
        tex = by_path.get(texture_path.lower())
        if tex is None:
            continue
        key = _norm(material)
        previous = chosen.get(key)
        if previous is None or priority < previous[0]:
            chosen[key] = (priority, tex)

    return {key: row for key, (_, row) in chosen.items()}, by_path


def compile_runtime(
    glb_root: Path,
    bundle_manifest: Path,
    texture_manifest_path: Path,
    texture_source_root: Path,
    texture_output_root: Path,
) -> tuple[dict, dict]:
    bundle = json.loads(bundle_manifest.read_text(encoding="utf-8"))
    texture_manifest = json.loads(texture_manifest_path.read_text(encoding="utf-8"))
    meshes = bundle.get("meshes", [])
    if bundle.get("format") != "xziel_xzmesh_bundle_v1" or len(meshes) != EXPECTED_MESHES:
        raise ValueError(f"expected {EXPECTED_MESHES}-mesh XZMS bundle")

    choices, _ = build_texture_choices(texture_manifest)
    glbs = _glb_index(glb_root)
    texture_output_root.mkdir(parents=True, exist_ok=True)

    runtime_textures: list[dict] = []
    texture_runtime_index: dict[str, int] = {}
    runtime_bindings: list[dict] = []
    seen_binding: dict[tuple[int, int], int] = {}
    missing_materials: set[str] = set()
    submesh_count = 0
    textured_submeshes = 0
    no_material_submeshes = 0

    def runtime_texture_index(tex: dict) -> int:
        source_rel = tex["file"]
        source_path = texture_source_root / source_rel
        if not source_path.is_file():
            raise ValueError(f"missing decoded XZTX {source_path}")
        identity = str(tex.get("texturePath", source_rel)).lower()
        existing = texture_runtime_index.get(identity)
        if existing is not None:
            return existing
        index = len(runtime_textures)
        runtime_name = f"t{index:04d}.xzt"
        target = texture_output_root / runtime_name
        shutil.copyfile(source_path, target)
        runtime_textures.append({
            "index": index,
            "runtimePath": f"xziel/maps/xziel_nacht_bo3/textures/{runtime_name}",
            "sourceTexturePath": tex.get("texturePath"),
            "sourceTextureName": tex.get("textureName"),
            "width": int(tex.get("width", 0)),
            "height": int(tex.get("height", 0)),
            "runtimeFormat": tex.get("runtimeFormat", "RGBA8"),
        })
        texture_runtime_index[identity] = index
        return index

    for mesh_row in meshes:
        mesh_index = int(mesh_row["index"])
        glb_name = Path(mesh_row["sourceGlb"]).stem.lower()
        glb = glbs.get(glb_name)
        if glb is None:
            raise ValueError(f"missing GLB for mesh {mesh_index}: {glb_name}")
        doc, _ = converter.parse_glb(glb)
        material_rows = primitive_material_rows(doc)
        expected = int(mesh_row.get("stats", {}).get("submeshCount", -1))
        if len(material_rows) != expected:
            raise ValueError(
                f"mesh {mesh_index} material/submesh drift {len(material_rows)} != {expected}"
            )

        for row in material_rows:
            submesh_count += 1
            material_index = int(row["materialIndex"])
            material_name = row.get("materialName")
            texture_index = NO_TEXTURE

            if material_index == NO_TEXTURE or not isinstance(material_name, str):
                no_material_submeshes += 1
            else:
                tex = choices.get(_norm(material_name))
                if tex is not None:
                    texture_index = runtime_texture_index(tex)
                    textured_submeshes += 1
                else:
                    missing_materials.add(material_name)

            if material_index == NO_TEXTURE:
                continue

            key = (mesh_index, material_index)
            previous = seen_binding.get(key)
            if previous is not None:
                if runtime_bindings[previous]["diffuseTextureIndex"] != texture_index:
                    raise ValueError(
                        f"conflicting texture binding for mesh/material {mesh_index}/{material_index}"
                    )
                continue

            seen_binding[key] = len(runtime_bindings)
            runtime_bindings.append({
                "meshIndex": mesh_index,
                "materialIndex": material_index,
                "diffuseTextureIndex": texture_index,
                "flags": 0,
            })

    if submesh_count != EXPECTED_SUBMESHES:
        raise ValueError(f"submesh coverage drift {submesh_count} != {EXPECTED_SUBMESHES}")

    summary = {
        "meshCount": len(meshes),
        "submeshCount": submesh_count,
        "bindingCount": len(runtime_bindings),
        "runtimeTextureCount": len(runtime_textures),
        "texturedSubmeshes": textured_submeshes,
        "untexturedSubmeshes": submesh_count - textured_submeshes,
        "noMaterialSubmeshes": no_material_submeshes,
        "missingMaterialNameCount": len(missing_materials),
        "zeroOmissionSubmeshScan": submesh_count == EXPECTED_SUBMESHES,
    }

    runtime = {
        "format": "xziel_material_runtime_manifest_v1",
        "meshCount": EXPECTED_MESHES,
        "textures": runtime_textures,
        "bindings": runtime_bindings,
        "summary": summary,
    }
    report = {
        "format": "xziel_nacht_texture_binding_report_v1",
        "summary": summary,
        "missingMaterialNames": sorted(missing_materials),
    }
    return runtime, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb-root", type=Path, required=True)
    ap.add_argument("--bundle-manifest", type=Path, required=True)
    ap.add_argument("--texture-manifest", type=Path, required=True)
    ap.add_argument("--texture-source-root", type=Path, required=True)
    ap.add_argument("--texture-output-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    runtime, report = compile_runtime(
        args.glb_root,
        args.bundle_manifest,
        args.texture_manifest,
        args.texture_source_root,
        args.texture_output_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(runtime, separators=(",", ":")) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("XZIEL_NACHT_TEXTURE_BINDINGS_OK", json.dumps(runtime["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
