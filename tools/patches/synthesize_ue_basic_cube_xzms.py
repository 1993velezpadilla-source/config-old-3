#!/usr/bin/env python3
"""Add Unreal Engine's canonical /Engine/BasicShapes/Cube.Cube to an XZMS runtime report.

The workshop PAK intentionally does not contain Engine Content. Nacht references
UE's built-in 100 cm cube from /Engine/BasicShapes/Cube.Cube, so source-package
authority remains 568 StaticMesh assets while runtime scene authority needs one
additional engine-provided primitive.

The generated XZMS is a 1 m cube centered at the origin (UE default Cube is
100x100x100 cm), with per-face normals, tangents and UV0. No workshop asset is
invented or counted as source content.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path

MAGIC = b"XZMS"
VERSION = 4
FLAGS = (1 << 0) | (1 << 1)  # XZIEL basis + uint32 indices
VERTEX_STRIDE = 104
SUBMESH_STRIDE = 16
ATTRS = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 6)
OBJECT_PATH = "/Engine/BasicShapes/Cube.Cube"
RUNTIME_FILE = "ue_engine_basic_cube.xzm"


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def face_vertices(normal, tangent):
    bitangent = cross(normal, tangent)
    center = mul(normal, 0.5)
    corners = [
        add(add(center, mul(tangent, -0.5)), mul(bitangent, -0.5)),
        add(add(center, mul(tangent,  0.5)), mul(bitangent, -0.5)),
        add(add(center, mul(tangent,  0.5)), mul(bitangent,  0.5)),
        add(add(center, mul(tangent, -0.5)), mul(bitangent,  0.5)),
    ]
    uvs = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
    rows = []
    for pos, uv in zip(corners, uvs):
        rows.append((pos, normal, (*tangent, 1.0), uv))
    return rows


def write_cube(path: Path) -> dict:
    faces = [
        (( 1.0,  0.0,  0.0), ( 0.0,  1.0,  0.0)),
        ((-1.0,  0.0,  0.0), ( 0.0, -1.0,  0.0)),
        (( 0.0,  1.0,  0.0), (-1.0,  0.0,  0.0)),
        (( 0.0, -1.0,  0.0), ( 1.0,  0.0,  0.0)),
        (( 0.0,  0.0,  1.0), ( 1.0,  0.0,  0.0)),
        (( 0.0,  0.0, -1.0), (-1.0,  0.0,  0.0)),
    ]

    vertices = []
    indices = []
    for normal, tangent in faces:
        base = len(vertices)
        vertices.extend(face_vertices(normal, tangent))
        # face_vertices is CCW when viewed from outside.
        indices.extend([base + 0, base + 1, base + 2, base + 0, base + 2, base + 3])

    if len(vertices) != 24 or len(indices) != 36:
        raise AssertionError((len(vertices), len(indices)))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(MAGIC)
        f.write(struct.pack(
            "<7I",
            VERSION,
            len(vertices),
            len(indices),
            1,
            FLAGS,
            VERTEX_STRIDE,
            SUBMESH_STRIDE,
        ))
        f.write(struct.pack("<6f", -0.5, -0.5, -0.5, 0.5, 0.5, 0.5))

        for pos, normal, tangent, uv in vertices:
            values = [
                *pos,
                *normal,
                *tangent,
                *uv,
                *([0.0, 0.0] * 7),
            ]
            if len(values) != 26 or not all(math.isfinite(v) for v in values):
                raise AssertionError(values)
            f.write(struct.pack("<26f", *values))

        f.write(struct.pack("<" + "I" * len(indices), *indices))
        f.write(struct.pack("<4I", 0, len(indices), 0, ATTRS))

    expected = 56 + 24 * VERTEX_STRIDE + 36 * 4 + SUBMESH_STRIDE
    actual = path.stat().st_size
    if actual != expected:
        raise AssertionError((actual, expected))

    return {
        "vertexCount": 24,
        "indexCount": 36,
        "triangleCount": 12,
        "submeshCount": 1,
        "bytes": actual,
        "boundsMin": [-0.5, -0.5, -0.5],
        "boundsMax": [0.5, 0.5, 0.5],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-report", type=Path, required=True)
    ap.add_argument("--mesh-dir", type=Path, required=True)
    ap.add_argument("--output-report", type=Path, required=True)
    args = ap.parse_args()

    source = json.loads(args.source_report.read_text(encoding="utf-8"))
    rows = list(source.get("meshes", []))
    if len(rows) != 568:
        raise ValueError(f"expected 568 source StaticMesh rows, got {len(rows)}")
    if any(str(row.get("objectPath", "")).lower() == OBJECT_PATH.lower() for row in rows):
        raise ValueError("engine basic cube unexpectedly exists in workshop XZMS source report")

    runtime_file = args.mesh_dir / RUNTIME_FILE
    result = write_cube(runtime_file)
    source_index = max(int(row["index"]) for row in rows) + 1

    synthetic = {
        "index": source_index,
        "file": RUNTIME_FILE,
        "packagePath": "/Engine/BasicShapes/Cube.uasset",
        "resolvedPackagePath": None,
        "objectPath": OBJECT_PATH,
        "sourceLodIndex": 0,
        "sourceMaterialCount": 1,
        "sourceSectionCount": 1,
        "sourceUvChannelCount": 1,
        "sourceMaterials": [{
            "index": 0,
            "slotName": "DefaultMaterial",
            "objectPath": None,
            "referenceName": None,
        }],
        "sourceSectionMaterialIndices": [0],
        **result,
        "authorityKind": "ue_engine_builtin",
        "engineCanonicalSizeCentimeters": [100.0, 100.0, 100.0],
    }
    rows.append(synthetic)

    runtime = dict(source)
    runtime["meshes"] = rows
    runtime["runtimeMeshCount"] = len(rows)
    runtime["sourcePackageMeshCount"] = 568
    runtime["engineBuiltinMeshCount"] = 1
    runtime["engineBuiltins"] = [{
        "objectPath": OBJECT_PATH,
        "runtimeFile": RUNTIME_FILE,
        "geometry": "canonical UE BasicShapes Cube, 100 cm edge",
    }]

    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        json.dumps(runtime, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "XZOGOT_UE_ENGINE_BASIC_CUBE_GREEN",
        f"source_meshes=568 runtime_meshes={len(rows)}",
        f"bytes={result['bytes']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
