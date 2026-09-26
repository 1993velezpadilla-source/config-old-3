#!/usr/bin/env python3
"""Compile the persisted 492-mesh / 10,791-instance Nacht reference directly to XZSC."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "assets/nacht_reference/pavlov_scene_reference"
VISUAL_COMPILER = ROOT / "tools/maps/compile_nacht_visual_scene.py"
STATIC_COMPILER = ROOT / "tools/maps/compile_xziel_static_scene.py"
EXPECTED_MESHES = 492
EXPECTED_INSTANCES = 10791


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--runtime-map-id",
        default="xziel_nacht_bo3",
    )
    args = parser.parse_args()

    visual = load_module(
        "xziel_nacht_visual_compiler",
        VISUAL_COMPILER,
    )
    static = load_module(
        "xziel_static_scene_compiler",
        STATIC_COMPILER,
    )

    assets = json.loads(
        (REFERENCE / "assets.json").read_text(
            encoding="utf-8"
        )
    )
    scene = json.loads(
        (REFERENCE / "scene_instances.json").read_text(
            encoding="utf-8"
        )
    )

    mesh_rows = assets.get("meshes", [])
    instances = scene.get("instances", [])

    if (
        assets.get("uniqueMeshCount") != EXPECTED_MESHES
        or len(mesh_rows) != EXPECTED_MESHES
    ):
        raise SystemExit(
            f"expected {EXPECTED_MESHES} Nacht meshes"
        )

    if len(instances) != EXPECTED_INSTANCES:
        raise SystemExit(
            f"expected {EXPECTED_INSTANCES} Nacht instances, "
            f"got {len(instances)}"
        )

    mesh_index: dict[str, int] = {}
    compiled_meshes: list[dict] = []
    for index, row in enumerate(mesh_rows):
        source = row.get("sourcePath")
        if not isinstance(source, str) or not source:
            raise SystemExit(
                f"invalid mesh sourcePath at {index}"
            )
        if source in mesh_index:
            raise SystemExit(
                f"duplicate mesh sourcePath: {source}"
            )

        basename = source.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        mesh_index[source] = index
        compiled_meshes.append({
            "index": index,
            "sourceBasename": basename,
            "runtimeFile": f"m{index:04d}.xzm",
        })

    default_counts = {
        "position": 0,
        "rotation": 0,
        "scale": 0,
    }
    referenced: set[int] = set()
    compiled_instances: list[dict] = []

    for index, row in enumerate(instances):
        source = row.get("mesh")
        if source not in mesh_index:
            raise SystemExit(
                f"instance {index} references unknown mesh: {source!r}"
            )

        matrix, defaults = visual.transform_matrix(
            row.get("transform")
        )
        for key, used in defaults.items():
            if used:
                default_counts[key] += 1

        idx = mesh_index[source]
        referenced.add(idx)
        compiled_instances.append({
            "meshIndex": idx,
            "matrixRowMajor": [
                round(float(value), 9)
                for value in matrix
            ],
        })

    if len(referenced) != EXPECTED_MESHES:
        raise SystemExit(
            f"only {len(referenced)}/{EXPECTED_MESHES} "
            "Nacht meshes are referenced"
        )

    visual_scene = {
        "format": "xziel_visual_scene_v1",
        "meshes": compiled_meshes,
        "instances": compiled_instances,
    }

    payload = static.compile_scene(
        visual_scene,
        args.runtime_map_id,
        39.3700787402,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)

    longest_path = max(
        len(
            (
                f"xziel/maps/{args.runtime_map_id}/meshes/"
                f"m{index:04d}.xzm"
            ).encode("ascii")
        )
        for index in range(EXPECTED_MESHES)
    )

    report = {
        "schemaVersion": 1,
        "format": "xziel_nacht_xzscene_build_v1",
        "runtimeMapId": args.runtime_map_id,
        "meshCount": EXPECTED_MESHES,
        "instanceCount": EXPECTED_INSTANCES,
        "sceneBytes": len(payload),
        "gameplayUnitsPerMeter": 39.3700787402,
        "defaultTransformFields": default_counts,
        "allMeshesReferenced": True,
        "runtimeNaming": {
            "scheme": "compact_ordinal_v1",
            "first": "m0000.xzm",
            "last": "m0491.xzm",
            "longestPathBytes": longest_path,
            "maxQpathBytes": 63,
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
        "XZIEL_NACHT_XZSC_OK",
        json.dumps(report, sort_keys=True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
