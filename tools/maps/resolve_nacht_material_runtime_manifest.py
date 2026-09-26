#!/usr/bin/env python3
"""Resolve Nacht submesh material bindings to a compact runtime texture manifest.

This stage consumes:
- the GLB/XZMS material binding manifest (mesh + materialIndex + materialName),
- a build-time exported material catalog (material identity + semantic textures),
- a texture catalog containing VFS-safe runtime texture paths.

It emits the generic xziel_material_runtime_manifest_v1 consumed by XZMT.
No Unreal/CUE4Parse JSON is parsed on Android.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

NO_TEXTURE = 0xFFFFFFFF
EXPECTED_MESHES = 492
EXPECTED_SUBMESHES = 1063

DIFFUSE_KEYS = (
    "PM_Diffuse",
    "BaseColor",
    "Base Color",
    "Diffuse",
    "Albedo",
)


def norm(value: str) -> str:
    return value.strip().lower()


def pick_diffuse(material: dict) -> str | None:
    textures = material.get("textures", {})
    if isinstance(textures, dict):
        for key in DIFFUSE_KEYS:
            value = textures.get(key)
            if isinstance(value, str) and value:
                return value
        # Deterministic fallback for exporter-specific parameter names.
        for key in sorted(textures):
            low = key.lower()
            if any(token in low for token in ("diffuse", "albedo", "basecolor", "base_color")):
                value = textures[key]
                if isinstance(value, str) and value:
                    return value
    return None


def resolve(bindings_doc: dict, material_doc: dict, texture_doc: dict) -> dict:
    if bindings_doc.get("format") != "xziel_nacht_material_bindings_v1":
        raise ValueError("invalid Nacht material binding manifest")
    if material_doc.get("format") != "xziel_material_export_catalog_v1":
        raise ValueError("invalid material export catalog")
    if texture_doc.get("format") != "xziel_texture_runtime_catalog_v1":
        raise ValueError("invalid texture runtime catalog")

    materials = material_doc.get("materials", [])
    textures = texture_doc.get("textures", [])
    meshes = bindings_doc.get("meshes", [])

    by_material: dict[str, dict] = {}
    for row in materials:
        if not isinstance(row, dict):
            continue
        names = [
            row.get("name"),
            row.get("slotName"),
            row.get("objectName"),
            row.get("pathName"),
        ]
        for value in names:
            if isinstance(value, str) and value:
                by_material.setdefault(norm(value.rsplit("/", 1)[-1].split(".", 1)[0]), row)

    texture_index_by_name: dict[str, int] = {}
    runtime_textures: list[dict] = []
    for row in textures:
        if not isinstance(row, dict):
            continue
        idx = len(runtime_textures)
        runtime_path = row.get("runtimePath")
        names = [
            row.get("name"),
            row.get("objectName"),
            row.get("pathName"),
            row.get("sourcePath"),
        ]
        if not isinstance(runtime_path, str) or not runtime_path:
            continue
        runtime_textures.append({
            "index": idx,
            "runtimePath": runtime_path,
        })
        for value in names:
            if isinstance(value, str) and value:
                key = norm(value.rsplit("/", 1)[-1].split(".", 1)[0])
                texture_index_by_name.setdefault(key, idx)

    runtime_bindings: list[dict] = []
    unresolved_materials: list[dict] = []
    unresolved_diffuse: list[dict] = []
    covered_diffuse = 0
    submesh_count = 0

    for mesh in meshes:
        mesh_index = int(mesh["meshIndex"])
        for submesh in mesh.get("submeshes", []):
            submesh_count += 1
            material_index = int(submesh["materialIndex"])
            material_name = submesh.get("materialName")
            texture_index = NO_TEXTURE

            material = None
            if isinstance(material_name, str) and material_name:
                material = by_material.get(norm(material_name))

            if material is None:
                unresolved_materials.append({
                    "meshIndex": mesh_index,
                    "submeshIndex": submesh.get("submeshIndex"),
                    "materialIndex": material_index,
                    "materialName": material_name,
                })
            else:
                diffuse = pick_diffuse(material)
                if diffuse:
                    key = norm(diffuse.rsplit("/", 1)[-1].split(".", 1)[0])
                    found = texture_index_by_name.get(key)
                    if found is not None:
                        texture_index = found
                        covered_diffuse += 1
                    else:
                        unresolved_diffuse.append({
                            "meshIndex": mesh_index,
                            "submeshIndex": submesh.get("submeshIndex"),
                            "materialName": material_name,
                            "diffuse": diffuse,
                            "reason": "texture-not-in-runtime-catalog",
                        })
                else:
                    unresolved_diffuse.append({
                        "meshIndex": mesh_index,
                        "submeshIndex": submesh.get("submeshIndex"),
                        "materialName": material_name,
                        "reason": "material-has-no-diffuse-semantic",
                    })

            runtime_bindings.append({
                "meshIndex": mesh_index,
                "materialIndex": material_index,
                "diffuseTextureIndex": texture_index,
                "flags": 0,
            })

    if len(meshes) != EXPECTED_MESHES:
        raise ValueError(f"mesh coverage drift: {len(meshes)} != {EXPECTED_MESHES}")
    if submesh_count != EXPECTED_SUBMESHES:
        raise ValueError(
            f"submesh coverage drift: {submesh_count} != {EXPECTED_SUBMESHES}"
        )

    summary = {
        "meshCount": len(meshes),
        "submeshCount": submesh_count,
        "resolvedMaterialSubmeshes": submesh_count - len(unresolved_materials),
        "unresolvedMaterialSubmeshes": len(unresolved_materials),
        "diffuseCoveredSubmeshes": covered_diffuse,
        "diffuseMissingSubmeshes": submesh_count - covered_diffuse,
        "textureCount": len(runtime_textures),
        "zeroOmissionBindingCoverage": len(runtime_bindings) == EXPECTED_SUBMESHES,
    }

    return {
        "format": "xziel_material_runtime_manifest_v1",
        "meshCount": EXPECTED_MESHES,
        "textures": runtime_textures,
        "bindings": runtime_bindings,
        "summary": summary,
        "unresolvedMaterials": unresolved_materials,
        "unresolvedDiffuse": unresolved_diffuse,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bindings", type=Path, required=True)
    ap.add_argument("--materials", type=Path, required=True)
    ap.add_argument("--textures", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    out = resolve(
        json.loads(args.bindings.read_text(encoding="utf-8")),
        json.loads(args.materials.read_text(encoding="utf-8")),
        json.loads(args.textures.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("XZIEL_NACHT_MATERIAL_RUNTIME_MANIFEST", json.dumps(out["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
