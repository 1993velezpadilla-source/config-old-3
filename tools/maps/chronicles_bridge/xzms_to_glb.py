#!/usr/bin/env python3
"""Convert resolved XZIEL XZMS meshes into Godot-safe multi-primitive GLB.

The source XZMS vertex/index payload and submesh order are preserved. Godot has
an engine limit on the number of surfaces in one ArrayMesh, so a source mesh
with many sections is represented by multiple identity-transform glTF mesh
nodes. No geometry, material section, index range, or authored transform is
dropped or merged.
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

# Godot's RenderingServer caps surfaces per mesh. Stay below the hard limit so
# import/runtime behavior is stable across renderer backends and mobile builds.
GODOT_SAFE_SURFACES_PER_MESH = 240


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

    primitive_chunks = [
        primitives[i:i + GODOT_SAFE_SURFACES_PER_MESH]
        for i in range(0, len(primitives), GODOT_SAFE_SURFACES_PER_MESH)
    ]
    meshes = []
    nodes = []
    scene_nodes = []
    surface_start = 0
    for chunk_index, chunk in enumerate(primitive_chunks):
        mesh_index = len(meshes)
        chunk_name = f"{src.stem}_chunk_{chunk_index:03d}"
        meshes.append({"name": chunk_name, "primitives": chunk})
        nodes.append({
            "name": chunk_name,
            "mesh": mesh_index,
            "extras": {
                "xz_source_surface_start": surface_start,
                "xz_source_surface_count": len(chunk),
            },
        })
        scene_nodes.append(len(nodes) - 1)
        surface_start += len(chunk)

    if surface_start != len(primitives):
        raise AssertionError(f"{src}: primitive chunking lost surfaces")

    doc = {
        "asset": {
            "version": "2.0",
            "generator": "XZIEL XZMS -> Godot-safe GLB source bridge",
        },
        "scene": 0,
        "scenes": [{"nodes": scene_nodes}],
        "nodes": nodes,
        "meshes": meshes,
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
        "extras": {
            "xziel_basis_preserved": True,
            "source_file": src.name,
            "source_version": x["version"],
            "source_vertex_stride": vstride,
            "source_submesh_count": len(primitives),
            "godot_surface_chunk_limit": GODOT_SAFE_SURFACES_PER_MESH,
            "mesh_chunk_count": len(primitive_chunks),
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
        "mesh_chunks": len(primitive_chunks),
        "max_chunk_surfaces": max(len(chunk) for chunk in primitive_chunks),
        "chunk_surface_counts": [len(chunk) for chunk in primitive_chunks],
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
        "schema": 2,
        "mesh_count": len(rows),
        "mesh_chunks": sum(x["mesh_chunks"] for x in rows),
        "max_chunk_surfaces": max(x["max_chunk_surfaces"] for x in rows),
        "surface_chunk_limit": GODOT_SAFE_SURFACES_PER_MESH,
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
        "chunks=", report["mesh_chunks"],
        "max_surfaces=", report["max_chunk_surfaces"],
        "vertices=", report["vertices"],
        "indices=", report["indices"],
        "submeshes=", report["submeshes"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
