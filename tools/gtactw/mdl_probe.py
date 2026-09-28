#!/usr/bin/env python3
"""Inspect GTA Chinatown Wars Leeds Engine .mdl resources.

Layout is based on DK22Pac/CTW-Mobile-Explorer's public CTWModel parser.
No game assets are bundled or downloaded.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

HEADER = struct.Struct("<2sHBBHII8I")
VERTEX = struct.Struct("<8h")
MATRIX = struct.Struct("<9hbb2x3i")
MATERIAL = struct.Struct("<hHBB2xI")

assert HEADER.size == 48
assert VERTEX.size == 16
assert MATRIX.size == 32
assert MATERIAL.size == 12


def parse_mdl_bytes(blob: bytes) -> dict:
    if len(blob) < HEADER.size:
        raise ValueError("model is smaller than the 48-byte CTW header")

    unpacked = HEADER.unpack_from(blob, 0)
    signature = unpacked[0]
    if signature != b"MG":
        raise ValueError(f"invalid CTW model signature {signature!r}")

    num_variances = unpacked[1]
    num_matrices = unpacked[2]
    num_materials = unpacked[3]
    num_vertices = unpacked[4]
    unknown1 = unpacked[5]
    unknown2 = unpacked[6]
    unknown3 = list(unpacked[7:15])

    vertex_off = HEADER.size
    matrix_count = max(0, num_matrices - 1)
    matrix_off = vertex_off + num_vertices * VERTEX.size
    material_off = matrix_off + matrix_count * MATRIX.size
    expected_end = material_off + num_materials * MATERIAL.size

    if expected_end > len(blob):
        raise ValueError(
            "truncated CTW model: "
            f"needs {expected_end} bytes, has {len(blob)}"
        )

    vertices = []
    for i in range(num_vertices):
        raw = VERTEX.unpack_from(blob, vertex_off + i * VERTEX.size)
        x, y, z, nx, ny, nz, u, v = raw
        vertices.append({
            "index": i,
            "position": [x / 64.0, y / 64.0, z / 64.0],
            "normal": [nx / 32767.0, ny / 32767.0, nz / 32767.0],
            "uv": [u / 2048.0, v / 2048.0],
        })

    matrices = [{
        "node": 0,
        "parent": -1,
        "right": [1.0, 0.0, 0.0],
        "top": [0.0, 1.0, 0.0],
        "at": [0.0, 0.0, 1.0],
        "position": [0.0, 0.0, 0.0],
        "implicit_root": True,
    }]
    for i in range(matrix_count):
        raw = MATRIX.unpack_from(blob, matrix_off + i * MATRIX.size)
        matrices.append({
            "node": i + 1,
            "parent": raw[9] - 1,
            "parent_raw": raw[9],
            "unknown1": raw[10],
            "right": [raw[0] / 4096.0, raw[1] / 4096.0, raw[2] / 4096.0],
            "top": [raw[3] / 4096.0, raw[4] / 4096.0, raw[5] / 4096.0],
            "at": [raw[6] / 4096.0, raw[7] / 4096.0, raw[8] / 4096.0],
            "position": [raw[11] / 4096.0, raw[12] / 4096.0, raw[13] / 4096.0],
            "implicit_root": False,
        })

    materials = []
    cursor = 0
    node_stats = {
        i: {
            "node": i,
            "material_count": 0,
            "vertex_count": 0,
            "textures": [],
            "rendering_flags": [],
            "variance_flags": [],
            "bounds": None,
        }
        for i in range(num_matrices)
    }

    for i in range(num_materials):
        texture, vertex_count, rendering_flags, node, variance_flags = MATERIAL.unpack_from(
            blob, material_off + i * MATERIAL.size
        )
        if node >= num_matrices:
            raise ValueError(
                f"material {i} references node {node}, "
                f"but model has {num_matrices} nodes"
            )
        if cursor + vertex_count > num_vertices:
            raise ValueError(
                f"material {i} vertex range overruns vertex array: "
                f"{cursor}+{vertex_count}>{num_vertices}"
            )

        start = cursor
        end = cursor + vertex_count
        cursor = end

        materials.append({
            "index": i,
            "texture": texture,
            "vertex_count": vertex_count,
            "rendering_flags": rendering_flags,
            "node": node,
            "variance_flags": variance_flags,
            "vertex_range": [start, end],
        })

        stats = node_stats[node]
        stats["material_count"] += 1
        stats["vertex_count"] += vertex_count
        if texture not in stats["textures"]:
            stats["textures"].append(texture)
        if rendering_flags not in stats["rendering_flags"]:
            stats["rendering_flags"].append(rendering_flags)
        if variance_flags not in stats["variance_flags"]:
            stats["variance_flags"].append(variance_flags)

        if vertex_count:
            pts = [vertices[j]["position"] for j in range(start, end)]
            mins = [min(p[axis] for p in pts) for axis in range(3)]
            maxs = [max(p[axis] for p in pts) for axis in range(3)]
            if stats["bounds"] is None:
                stats["bounds"] = {"min": mins, "max": maxs}
            else:
                old = stats["bounds"]
                old["min"] = [min(old["min"][a], mins[a]) for a in range(3)]
                old["max"] = [max(old["max"][a], maxs[a]) for a in range(3)]

    unassigned_vertices = num_vertices - cursor

    if vertices:
        model_min = [
            min(v["position"][axis] for v in vertices)
            for axis in range(3)
        ]
        model_max = [
            max(v["position"][axis] for v in vertices)
            for axis in range(3)
        ]
        bounds = {"min": model_min, "max": model_max}
    else:
        bounds = None

    empty_nodes = [
        node for node, stats in node_stats.items()
        if stats["vertex_count"] == 0
    ]

    return {
        "signature": "MG",
        "file_size": len(blob),
        "expected_payload_size": expected_end,
        "trailing_bytes": len(blob) - expected_end,
        "num_variances": num_variances,
        "num_matrices": num_matrices,
        "num_materials": num_materials,
        "num_vertices": num_vertices,
        "unknown1": unknown1,
        "unknown2": unknown2,
        "unknown3": unknown3,
        "bounds": bounds,
        "unassigned_vertices": unassigned_vertices,
        "empty_nodes": empty_nodes,
        "matrices": matrices,
        "materials": materials,
        "nodes": list(node_stats.values()),
    }


def parse_mdl(path: Path) -> dict:
    report = parse_mdl_bytes(path.read_bytes())
    report["path"] = str(path)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mdl", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--include-vertices",
        action="store_true",
        help="Reserved for a future detailed vertex dump; summary stays compact.",
    )
    args = ap.parse_args()

    try:
        report = parse_mdl(args.mdl)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    report["ok"] = True
    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
