#!/usr/bin/env python3
"""Compile resolved XZIEL static-material bindings into XZMT v1.

Input is deliberately exporter-agnostic. CUE4Parse/Pavlov-specific tooling
resolves materials and textures at build time; this compiler only packs the
runtime result into a small binary that Android can validate without JSON.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

MAGIC = b"XZMT"
VERSION = 1
MAX_QPATH_BYTES = 63
HEADER = struct.Struct("<4s6I")
TEXTURE = struct.Struct("<II")
BINDING = struct.Struct("<4I")
NO_TEXTURE = 0xFFFFFFFF


def safe_path(value: str) -> bool:
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return False
    if (
        not value
        or len(encoded) > MAX_QPATH_BYTES
        or value.startswith("/")
        or "\\" in value
        or ":" in value
    ):
        return False
    parts = value.split("/")
    return all(
        part not in {"", ".", ".."}
        and all(ch.isalnum() or ch in "_.-" for ch in part)
        for part in parts
    )


def compile_table(doc: dict) -> bytes:
    if doc.get("format") != "xziel_material_runtime_manifest_v1":
        raise ValueError("invalid material runtime manifest")

    mesh_count = int(doc.get("meshCount", 0))
    textures = doc.get("textures")
    bindings = doc.get("bindings")

    if mesh_count <= 0:
        raise ValueError("meshCount must be positive")
    if not isinstance(textures, list):
        raise ValueError("textures must be a list")
    if not isinstance(bindings, list) or not bindings:
        raise ValueError("bindings must be a non-empty list")

    strings = bytearray()
    texture_records = bytearray()
    seen_paths: set[str] = set()

    for index, row in enumerate(textures):
        if not isinstance(row, dict) or row.get("index") != index:
            raise ValueError(f"texture index drift at {index}")
        path = row.get("runtimePath")
        if not isinstance(path, str) or not safe_path(path):
            raise ValueError(f"unsafe texture runtimePath at {index}")
        key = path.lower()
        if key in seen_paths:
            raise ValueError(f"duplicate texture path {path!r}")
        seen_paths.add(key)
        encoded = path.encode("ascii")
        offset = len(strings)
        strings.extend(encoded)
        texture_records.extend(TEXTURE.pack(offset, len(encoded)))

    binding_records = bytearray()
    seen_bindings: set[tuple[int, int]] = set()

    for row in bindings:
        if not isinstance(row, dict):
            raise ValueError("binding is not an object")
        mesh_index = int(row.get("meshIndex", -1))
        material_index = int(row.get("materialIndex", -1))
        texture_index = int(row.get("diffuseTextureIndex", NO_TEXTURE))
        flags = int(row.get("flags", 0))

        if not 0 <= mesh_index < mesh_count:
            raise ValueError(f"invalid meshIndex {mesh_index}")
        if material_index < 0 or material_index > 0xFFFFFFFF:
            raise ValueError(f"invalid materialIndex {material_index}")
        if texture_index != NO_TEXTURE and not 0 <= texture_index < len(textures):
            raise ValueError(f"invalid texture index {texture_index}")

        key = (mesh_index, material_index)
        if key in seen_bindings:
            raise ValueError(
                f"duplicate mesh/material binding {mesh_index}/{material_index}"
            )
        seen_bindings.add(key)

        binding_records.extend(
            BINDING.pack(
                mesh_index,
                material_index,
                texture_index,
                flags,
            )
        )

    header = HEADER.pack(
        MAGIC,
        VERSION,
        mesh_count,
        len(textures),
        len(bindings),
        len(strings),
        0,
    )
    return bytes(header + texture_records + binding_records + strings)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    doc = json.loads(args.manifest.read_text(encoding="utf-8"))
    payload = compile_table(doc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)

    print(
        "XZIEL_XZMT_COMPILE_OK",
        f"bytes={len(payload)}",
        f"textures={len(doc['textures'])}",
        f"bindings={len(doc['bindings'])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
