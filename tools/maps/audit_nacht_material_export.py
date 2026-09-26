#!/usr/bin/env python3
"""Audit CUE4Parse material/texture output for the 492-mesh Nacht scene.

This intentionally does not assume a CUE4Parse sidecar naming convention.
It inspects every exported GLB JSON chunk plus all sibling files, then emits a
stable JSON report that can drive the XZIEL material compiler/runtime work.
"""

from __future__ import annotations

import argparse
import collections
import json
import struct
from pathlib import Path

EXPECTED_GLBS = 492
JSON_CHUNK = 0x4E4F534A


def parse_glb_json(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError(f"GLB too small: {path}")

    magic, version, declared = struct.unpack_from("<III", raw, 0)
    if magic != 0x46546C67 or version != 2 or declared != len(raw):
        raise ValueError(f"invalid GLB header: {path}")

    offset = 12
    while offset + 8 <= len(raw):
        length, kind = struct.unpack_from("<II", raw, offset)
        offset += 8
        end = offset + length
        if end > len(raw):
            raise ValueError(f"GLB chunk overflow: {path}")
        chunk = raw[offset:end]
        offset = end

        if kind == JSON_CHUNK:
            return json.loads(
                chunk.rstrip(b" \t\r\n\x00").decode("utf-8")
            )

    raise ValueError(f"GLB JSON chunk missing: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("export_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    root = args.export_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"material export root missing: {root}")

    files = sorted(
        path for path in root.rglob("*")
        if path.is_file()
    )
    glbs = [path for path in files if path.suffix.lower() == ".glb"]

    if len(glbs) != EXPECTED_GLBS:
        raise SystemExit(
            f"expected {EXPECTED_GLBS} GLBs, found {len(glbs)}"
        )

    extension_counts: collections.Counter[str] = collections.Counter()
    total_bytes = 0
    external_files = []

    for path in files:
        suffix = path.suffix.lower() or "<none>"
        extension_counts[suffix] += 1
        total_bytes += path.stat().st_size
        if suffix != ".glb":
            external_files.append(path)

    glbs_with_materials = 0
    glbs_with_textures = 0
    glbs_with_images = 0
    material_count = 0
    texture_count = 0
    image_count = 0
    embedded_image_count = 0
    external_image_uris: set[str] = set()
    material_names: set[str] = set()

    for path in glbs:
        doc = parse_glb_json(path)

        materials = doc.get("materials", [])
        textures = doc.get("textures", [])
        images = doc.get("images", [])

        if materials:
            glbs_with_materials += 1
        if textures:
            glbs_with_textures += 1
        if images:
            glbs_with_images += 1

        material_count += len(materials)
        texture_count += len(textures)
        image_count += len(images)

        for row in materials:
            if isinstance(row, dict):
                name = row.get("name")
                if isinstance(name, str) and name:
                    material_names.add(name)

        for row in images:
            if not isinstance(row, dict):
                continue
            uri = row.get("uri")
            if isinstance(uri, str) and uri:
                external_image_uris.add(uri)
            elif isinstance(row.get("bufferView"), int):
                embedded_image_count += 1

    external_suffixes = collections.Counter(
        path.suffix.lower() or "<none>"
        for path in external_files
    )

    report = {
        "format": "xziel_nacht_material_export_audit_v1",
        "expectedGlbs": EXPECTED_GLBS,
        "glbs": len(glbs),
        "files": len(files),
        "bytes": total_bytes,
        "extensionCounts": dict(sorted(extension_counts.items())),
        "glbsWithMaterials": glbs_with_materials,
        "glbsWithTextures": glbs_with_textures,
        "glbsWithImages": glbs_with_images,
        "materialRecords": material_count,
        "textureRecords": texture_count,
        "imageRecords": image_count,
        "embeddedImageRecords": embedded_image_count,
        "externalImageUris": len(external_image_uris),
        "uniqueMaterialNames": len(material_names),
        "externalFiles": len(external_files),
        "externalExtensionCounts": dict(sorted(external_suffixes.items())),
        "sampleMaterialNames": sorted(material_names)[:100],
        "sampleExternalImageUris": sorted(external_image_uris)[:100],
        "sampleExternalFiles": [
            path.relative_to(root).as_posix()
            for path in external_files[:150]
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "XZIEL_NACHT_MATERIAL_EXPORT_AUDIT "
        f"glbs={len(glbs)} "
        f"glbsWithMaterials={glbs_with_materials} "
        f"materials={material_count} "
        f"textures={texture_count} "
        f"images={image_count} "
        f"externalFiles={len(external_files)}"
    )

    if (
        glbs_with_materials == 0
        and material_count == 0
        and len(external_files) == 0
    ):
        raise SystemExit(
            "CUE4Parse material export produced no material evidence"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
