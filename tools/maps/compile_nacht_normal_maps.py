#!/usr/bin/env python3
"""Compile authored tangent-space normal maps for BO3 Nacht.

XZMN v1 is a sidecar to the proven XZMT/XZPB material ABIs. It stores one
normal-texture binding per static-scene submesh and a deduplicated RGBA8 texture
table. Only bindings with explicit normal-map semantics are accepted; ambiguous
or filename-only guesses are left unmapped.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct

from compile_nacht_xzmat_bundle import (
    read_xzt_header,
    read_xzt_rgba,
    resize_nearest_rgba,
    runtime_size,
)

MAGIC = b"XZMN"
VERSION = 1
HEADER = struct.Struct("<4sIIIII")
TEXTURE = struct.Struct("<IIIII")
NO_TEXTURE = 0xFFFFFFFF
EXPECTED_BINDINGS = 1063
FLAG_RGBA8_NORMAL = 2


def canonical(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def normal_score(row: dict) -> int:
    source = str(row.get("source", "")).lower()
    name = str(row.get("textureName", "")).lower()
    score = 0

    if "normaltexture" in source:
        score += 30000
    elif "normal" in source:
        score += 18000

    if "normal" in name:
        score += 9000
    if re.search(r"(?:^|[_\-.])n(?:$|[_\-.])", name):
        score += 6500
    if name.endswith("_n") or name.endswith("_normal"):
        score += 5000

    negative = (
        "albedo", "basecolor", "diffuse", "rough", "metal", "spec",
        "opacity", "emissive", "ambientocclusion", "_ao", "mask",
    )
    if any(token in source for token in ("albedotexture", "basecolor")):
        score -= 30000
    if any(token in name for token in negative):
        score -= 12000

    return score


def select_normal(
    material_path: str,
    bindings_by_material: dict[str, list[dict]],
    textures_by_path: dict[str, dict],
) -> dict | None:
    candidates = []
    seen_paths = set()
    for row in bindings_by_material.get(material_path, []):
        texture_path = str(row.get("texturePath", "")).strip().lower()
        if not texture_path or texture_path not in textures_by_path:
            continue
        score = normal_score(row)
        if score < 18000:
            continue
        if texture_path in seen_paths:
            continue
        seen_paths.add(texture_path)
        candidates.append((score, texture_path, row))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    best_score = candidates[0][0]
    best = [item for item in candidates if item[0] == best_score]
    if len(best) != 1:
        return None
    return best[0][2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--materials-report", type=Path, required=True)
    ap.add_argument("--texture-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--max-dimension", type=int, default=256)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    material_report = json.loads(
        args.materials_report.read_text(encoding="utf-8")
    )

    texture_rows = manifest.get("textures", [])
    binding_rows = manifest.get("bindings", [])
    binding_materials = material_report.get("bindingMaterials", [])

    if len(binding_materials) != EXPECTED_BINDINGS:
        raise SystemExit(
            f"expected {EXPECTED_BINDINGS} binding materials, "
            f"got {len(binding_materials)}"
        )
    if not texture_rows or not binding_rows:
        raise SystemExit("texture manifest missing textures/bindings")

    textures_by_path = {
        str(row.get("texturePath", "")).strip().lower(): row
        for row in texture_rows
        if str(row.get("texturePath", "")).strip()
    }
    bindings_by_material: dict[str, list[dict]] = {}
    for row in binding_rows:
        material_path = str(row.get("materialPath", "")).strip().lower()
        if material_path:
            bindings_by_material.setdefault(material_path, []).append(row)

    selected_paths: list[str | None] = []
    selected_rows: list[dict | None] = []
    alias_resolved = 0
    unresolved_samples = []

    for binding_index, binding in enumerate(binding_materials):
        primary = str(binding.get("materialPath", "")).strip().lower()
        alias = str(binding.get("aliasMaterialPath", "")).strip().lower()

        selected = None
        selected_material = ""
        used_alias = False

        if primary:
            selected = select_normal(
                primary, bindings_by_material, textures_by_path
            )
            selected_material = primary if selected is not None else ""

        if selected is None and alias and alias != primary:
            selected = select_normal(
                alias, bindings_by_material, textures_by_path
            )
            if selected is not None:
                selected_material = alias
                used_alias = True
                alias_resolved += 1

        if selected is None:
            selected_paths.append(None)
            selected_rows.append(None)
            if len(unresolved_samples) < 80:
                unresolved_samples.append({
                    "bindingIndex": binding_index,
                    "materialPath": primary,
                    "aliasMaterialPath": alias,
                })
            continue

        texture_path = str(selected["texturePath"]).strip().lower()
        selected_paths.append(texture_path)
        selected_rows.append({
            "bindingIndex": binding_index,
            "materialPath": primary,
            "aliasMaterialPath": alias,
            "selectedMaterialPath": selected_material,
            "texturePath": texture_path,
            "textureName": str(selected.get("textureName", "")),
            "source": str(selected.get("source", "")),
            "score": normal_score(selected),
            "alias": used_alias,
        })

    if len(selected_paths) != EXPECTED_BINDINGS:
        raise SystemExit("normal binding count mismatch")

    used_paths = sorted({path for path in selected_paths if path is not None})
    texture_index = {path: index for index, path in enumerate(used_paths)}
    bindings = [
        texture_index[path] if path is not None else NO_TEXTURE
        for path in selected_paths
    ]

    runtime_textures = []
    data_offset = (
        HEADER.size
        + len(used_paths) * TEXTURE.size
        + len(bindings) * 4
    )

    for path in used_paths:
        row = textures_by_path[path]
        source = args.texture_root / str(row["file"])
        width, height, _fmt, _bytes = read_xzt_header(source)
        runtime_width, runtime_height = runtime_size(
            width, height, args.max_dimension
        )
        runtime_bytes = runtime_width * runtime_height * 4
        runtime_textures.append({
            "texturePath": path,
            "textureName": str(row.get("textureName", "")),
            "source": source,
            "sourceWidth": width,
            "sourceHeight": height,
            "width": runtime_width,
            "height": runtime_height,
            "offset": data_offset,
            "bytes": runtime_bytes,
        })
        data_offset += runtime_bytes

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as out:
        out.write(HEADER.pack(
            MAGIC,
            VERSION,
            len(runtime_textures),
            len(bindings),
            TEXTURE.size,
            FLAG_RGBA8_NORMAL,
        ))
        for texture in runtime_textures:
            out.write(TEXTURE.pack(
                texture["width"],
                texture["height"],
                texture["offset"],
                texture["bytes"],
                FLAG_RGBA8_NORMAL,
            ))
        for binding in bindings:
            out.write(struct.pack("<I", binding))

        for texture in runtime_textures:
            width, height, rgba = read_xzt_rgba(texture["source"])
            runtime_rgba = resize_nearest_rgba(
                rgba,
                width,
                height,
                texture["width"],
                texture["height"],
            )
            if len(runtime_rgba) != texture["bytes"]:
                raise SystemExit("normal texture resize byte mismatch")
            out.write(runtime_rgba)

    mapped = sum(binding != NO_TEXTURE for binding in bindings)
    report = {
        "schemaVersion": 1,
        "format": "XZMN",
        "version": VERSION,
        "mapId": "bo3_nacht_reference",
        "bindingCount": len(bindings),
        "mappedBindings": mapped,
        "unmappedBindings": len(bindings) - mapped,
        "textureCount": len(runtime_textures),
        "runtimeMaxDimension": args.max_dimension,
        "runtimeBytes": args.output.stat().st_size,
        "aliasResolvedBindings": alias_resolved,
        "unresolvedSamples": unresolved_samples,
        "mappedBindingsDetail": [
            row for row in selected_rows if row is not None
        ],
        "textures": [
            {
                key: value
                for key, value in texture.items()
                if key != "source"
            }
            for texture in runtime_textures
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if mapped == 0 or not runtime_textures:
        raise SystemExit("no authored normal-map bindings resolved")

    print(
        "XZIEL_NACHT_XZMN_OK",
        f"textures={len(runtime_textures)}",
        f"bindings={len(bindings)}",
        f"mapped={mapped}",
        f"unmapped={len(bindings)-mapped}",
        f"alias={alias_resolved}",
        f"maxDim={args.max_dimension}",
        f"bytes={args.output.stat().st_size}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
