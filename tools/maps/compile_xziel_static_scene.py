#!/usr/bin/env python3
"""Compile XZIEL visual-scene metadata into the compact XZSC v1 static-scene format.

XZSC does not contain third-party mesh bytes. It binds a map's instance matrices
to safe VFS-relative XZMS mesh paths so the native runtime can validate and later
stream the scene without parsing JSON or glTF on Android.

XZIEL keeps runtime-relative paths bounded to 63 bytes plus the terminating NUL. Long source asset names therefore
stay in metadata; runtime mesh files use compact stable ordinals.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
from pathlib import Path

MAGIC = b"XZSC"
VERSION = 1
MAX_RUNTIME_PATH_BYTES = 63

FLAG_XZIEL_Z_UP = 1 << 0
FLAG_METERS = 1 << 1
FLAG_ROW_MAJOR_COLUMN_VECTOR = 1 << 2
FLAG_XZMS_MESHES = 1 << 3
FLAGS = (
    FLAG_XZIEL_Z_UP
    | FLAG_METERS
    | FLAG_ROW_MAJOR_COLUMN_VECTOR
    | FLAG_XZMS_MESHES
)

HEADER = struct.Struct("<4s7IfI")
MESH_RECORD = struct.Struct("<II")
INSTANCE_RECORD = struct.Struct("<I16f")
RUNTIME_MAP_ID = re.compile(r"^[A-Za-z0-9_-]+$")
RUNTIME_MESH_FILE = re.compile(r"^[A-Za-z0-9_.-]+\.xzm$", re.IGNORECASE)


def safe_relative_path(value: str) -> bool:
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return False

    if (
        not value
        or len(encoded) > MAX_RUNTIME_PATH_BYTES
        or value.startswith("/")
        or "\\" in value
        or ":" in value
    ):
        return False

    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False

    return all(
        all(ch.isalnum() or ch in "_.-" for ch in part)
        for part in parts
    )


def default_runtime_file(index: int) -> str:
    if not 0 <= index < 10000:
        raise ValueError(f"runtime mesh ordinal out of range: {index}")
    return f"m{index:04d}.xzm"


def compile_scene(
    visual_scene: dict,
    runtime_map_id: str,
    gameplay_units_per_meter: float,
) -> bytes:
    if visual_scene.get("format") != "xziel_visual_scene_v1":
        raise ValueError("input must be xziel_visual_scene_v1")

    if not RUNTIME_MAP_ID.fullmatch(runtime_map_id):
        raise ValueError(f"unsafe runtime map id: {runtime_map_id!r}")

    if (
        not math.isfinite(gameplay_units_per_meter)
        or gameplay_units_per_meter <= 0.0
    ):
        raise ValueError("invalid gameplay-units-per-meter")

    meshes = visual_scene.get("meshes")
    instances = visual_scene.get("instances")

    if not isinstance(meshes, list) or not meshes:
        raise ValueError("visual scene has no meshes")
    if not isinstance(instances, list) or not instances:
        raise ValueError("visual scene has no instances")

    paths: list[str] = []
    for index, row in enumerate(meshes):
        if not isinstance(row, dict) or row.get("index") != index:
            raise ValueError(f"mesh index drift at {index}")

        runtime_file = row.get("runtimeFile", default_runtime_file(index))
        if (
            not isinstance(runtime_file, str)
            or not RUNTIME_MESH_FILE.fullmatch(runtime_file)
            or "/" in runtime_file
        ):
            raise ValueError(
                f"invalid compact runtime mesh filename at {index}: "
                f"{runtime_file!r}"
            )

        runtime_path = (
            f"xziel/maps/{runtime_map_id}/meshes/{runtime_file}"
        )
        if not safe_relative_path(runtime_path):
            raise ValueError(
                "runtime mesh path exceeds XZIEL runtime path limit "
                f"({MAX_RUNTIME_PATH_BYTES} bytes): {runtime_path!r}"
            )
        paths.append(runtime_path)

    if len({value.lower() for value in paths}) != len(paths):
        raise ValueError("duplicate runtime mesh paths")

    strings = bytearray()
    mesh_records = bytearray()
    for runtime_path in paths:
        encoded = runtime_path.encode("ascii")
        offset = len(strings)
        strings.extend(encoded)
        mesh_records.extend(
            MESH_RECORD.pack(offset, len(encoded))
        )

    instance_records = bytearray()
    referenced: set[int] = set()

    for index, row in enumerate(instances):
        if not isinstance(row, dict):
            raise ValueError(f"instance {index} is not an object")

        mesh_index = row.get("meshIndex")
        matrix = row.get("matrixRowMajor")

        if (
            not isinstance(mesh_index, int)
            or not 0 <= mesh_index < len(meshes)
        ):
            raise ValueError(
                f"instance {index} has invalid meshIndex"
            )

        if not isinstance(matrix, list) or len(matrix) != 16:
            raise ValueError(
                f"instance {index} has invalid matrix"
            )

        values = [float(value) for value in matrix]
        if not all(math.isfinite(value) for value in values):
            raise ValueError(
                f"instance {index} has non-finite matrix"
            )

        for matrix_index, expected in (
            (12, 0.0),
            (13, 0.0),
            (14, 0.0),
            (15, 1.0),
        ):
            if abs(values[matrix_index] - expected) > 1.0e-5:
                raise ValueError(
                    f"instance {index} is not affine"
                )

        referenced.add(mesh_index)
        instance_records.extend(
            INSTANCE_RECORD.pack(mesh_index, *values)
        )

    if len(referenced) != len(meshes):
        raise ValueError(
            f"only {len(referenced)}/{len(meshes)} meshes are referenced"
        )

    header = HEADER.pack(
        MAGIC,
        VERSION,
        FLAGS,
        len(meshes),
        len(instances),
        MESH_RECORD.size,
        INSTANCE_RECORD.size,
        len(strings),
        gameplay_units_per_meter,
        0,
    )

    return bytes(
        header + mesh_records + instance_records + strings
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("visual_scene", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--runtime-map-id",
        default="xziel_nacht_bo3",
    )
    parser.add_argument(
        "--gameplay-units-per-meter",
        type=float,
        default=39.3700787402,
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    visual_scene = json.loads(
        args.visual_scene.read_text(encoding="utf-8")
    )

    payload = compile_scene(
        visual_scene,
        args.runtime_map_id,
        args.gameplay_units_per_meter,
    )

    paths = [
        (
            f"xziel/maps/{args.runtime_map_id}/meshes/"
            f"{row.get('runtimeFile', default_runtime_file(index))}"
        )
        for index, row in enumerate(visual_scene["meshes"])
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)

    report = {
        "format": "XZSC",
        "version": VERSION,
        "runtimeMapId": args.runtime_map_id,
        "meshCount": len(visual_scene["meshes"]),
        "instanceCount": len(visual_scene["instances"]),
        "bytes": len(payload),
        "gameplayUnitsPerMeter": (
            args.gameplay_units_per_meter
        ),
        "runtimeNaming": {
            "scheme": "compact_ordinal_v1",
            "maxQpathBytes": MAX_RUNTIME_PATH_BYTES,
            "longestPathBytes": max(
                len(path.encode("ascii"))
                for path in paths
            ),
        },
    }

    if args.report:
        args.report.parent.mkdir(
            parents=True, exist_ok=True
        )
        args.report.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        "XZIEL_STATIC_SCENE_OK",
        json.dumps(report, sort_keys=True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
