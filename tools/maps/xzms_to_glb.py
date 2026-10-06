#!/usr/bin/env python3
"""Convert resolved XZIEL XZMS meshes into compact multi-primitive GLB.

The source XZMS vertex buffer is preserved byte-for-byte. Each XZMS submesh
becomes one glTF primitive sharing the same interleaved vertex attributes and
referencing only its authored index range. Coordinates stay in the XZIEL basis;
the Godot benchmark loader applies the single world-basis conversion to the
scene root so geometry and instance transforms remain in the same source space.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

HEADER_BYTES = 56
SUBMESH_BYTES = 16
MAGIC = b"XZMS"
GLB_MAGIC = 0x46546C67
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942

def align4(data: bytes, pad: bytes = b"\0") -> bytes:
    return data + pad * ((-len(data)) & 3)

def parse_xzms(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < HEADER_BYTES or data[:4] != MAGIC:
        raise ValueError(f"{path}: invalid XZMS")
    version, vc, ic, sc, flags, vstride, sstride = struct.unpack_from("<7I", data, 4)
    if version not in (3, 4):
        raise ValueError(f"{path}: unsupported XZMS version {version}")
    expected_stride = 72 if version == 3 else 104
    if vstride != expected_stride or sstride != SUBMESH_BYTES:
        raise ValueError(f"{path}: stride mismatch v={vstride} s={sstride}")
    if not vc or not ic or not sc or ic % 3:
        raise ValueError(f"{path}: invalid counts")
    bmin = struct.unpack_from("<3f", data, 32)
    bmax = struct.unpack_from("<3f", data, 44)
    vo = HEADER_BYTES
    io = vo + vc * vstride
    so = io + ic * 4
    if so + sc * sstride != len(data):
        raise ValueError(f"{path}: size mismatch")
    subs = []
    for i in range(sc):
        first, count, material, attrs = struct.unpack_from("<4I", data, so + i * sstride)
        if count == 0 or count % 3 or first + count > ic:
            raise ValueError(f"{path}: invalid submesh {i}")
        subs.append((first, count, material, attrs))
    return {
        "data": data,
        "version": version,
        "vertex_count": vc,
        "index_count": ic,
        "submeshes": subs,
        "vertex_stride": vstride,
        "vertex_offset": vo,
        "index_offset": io,
        "bounds_min": list(bmin),
        "bounds_max": list(bmax),
    }

def build_glb(src: Path, dst: Path) -> dict:
    x = parse_xzms(src)
    data = x["data"]
    vc = x["vertex_count"]
    vstride = x["vertex_stride"]
    vertex_bytes = data[x["vertex_offset"]:x["index_offset"]]
    index_bytes = data[x["index_offset"]:x["index_offset"] + x["index_count"] * 4]
    binary = align4(vertex_bytes + index_bytes)
    index_base = len(vertex_bytes)

    views = [{
        "buffer": 0,
        "byteOffset": 0,
        "byteLength": len(vertex_bytes),
        "byteStride": vstride,
        "target": 34962,
    }]
    accessors = [
        {
            "bufferView": 0, "byteOffset": 0, "componentType": 5126,
            "count": vc, "type": "VEC3",
            "min": x["bounds_min"], "max": x["bounds_max"],
        },
        {
            "bufferView": 0, "byteOffset": 12, "componentType": 5126,
            "count": vc, "type": "VEC3",
        },
        {
            "bufferView": 0, "byteOffset": 24, "componentType": 5126,
            "count": vc, "type": "VEC4",
        },
        {
            "bufferView": 0, "byteOffset": 40, "componentType": 5126,
            "count": vc, "type": "VEC2",
        },
    ]

    primitives = []
    for first, count, source_material, attrs in x["submeshes"]:
        view_idx = len(views)
        views.append({
            "buffer": 0,
            "byteOffset": index_base + first * 4,
            "byteLength": count * 4,
            "target": 34963,
        })
        accessor_idx = len(accessors)
        accessors.append({
            "bufferView": view_idx,
            "byteOffset": 0,
            "componentType": 5125,
            "count": count,
            "type": "SCALAR",
        })
        attributes = {"POSITION": 0}
        if attrs & (1 << 1):
            attributes["NORMAL"] = 1
        if attrs & (1 << 6):
            attributes["TANGENT"] = 2
        if attrs & (1 << 2):
            attributes["TEXCOORD_0"] = 3
        primitives.append({
            "attributes": attributes,
            "indices": accessor_idx,
            "mode": 4,
            "extras": {
                "xz_source_material_index": source_material,
                "xz_attribute_flags": attrs,
            },
        })

    doc = {
        "asset": {
            "version": "2.0",
            "generator": "XZIEL XZMS -> Godot benchmark GLB source bridge",
        },
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": src.stem, "mesh": 0}],
        "meshes": [{"name": src.stem, "primitives": primitives}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
        "extras": {
            "xziel_basis_preserved": True,
            "source_file": src.name,
            "source_version": x["version"],
            "source_vertex_stride": vstride,
        },
    }
    j = align4(json.dumps(doc, separators=(",", ":")).encode("utf-8"), b" ")
    total = 12 + 8 + len(j) + 8 + len(binary)
    payload = (
        struct.pack("<III", GLB_MAGIC, GLB_VERSION, total)
        + struct.pack("<II", len(j), JSON_CHUNK) + j
        + struct.pack("<II", len(binary), BIN_CHUNK) + binary
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(payload)
    return {
        "source": src.name,
        "output": dst.name,
        "vertices": vc,
        "indices": x["index_count"],
        "submeshes": len(x["submeshes"]),
        "bytes": len(payload),
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    rows = []
    for src in sorted(args.input_dir.glob("*.xzm")):
        rows.append(build_glb(src, args.output_dir / (src.stem + ".glb")))
    if not rows:
        raise SystemExit("no XZMS meshes found")
    report = {
        "schema": 1,
        "mesh_count": len(rows),
        "vertices": sum(x["vertices"] for x in rows),
        "indices": sum(x["indices"] for x in rows),
        "submeshes": sum(x["submeshes"] for x in rows),
        "meshes": rows,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        "XZOGOT_XZMS_GLB_GREEN",
        "meshes=", report["mesh_count"],
        "vertices=", report["vertices"],
        "indices=", report["indices"],
        "submeshes=", report["submeshes"],
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
