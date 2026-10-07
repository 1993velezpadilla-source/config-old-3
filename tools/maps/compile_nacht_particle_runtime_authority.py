#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from math import cos, isfinite, radians, sin
from collections import Counter
from pathlib import Path
from typing import Any


def strip_ref(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    match = re.match(r"^[A-Za-z0-9_]+['\"](.*)['\"]$", text)
    if match:
        text = match.group(1)
    return text.replace("\\", "/")


def canonical(value: Any) -> str:
    text = strip_ref(value)
    if text.startswith("Content/"):
        text = "/Game/" + text[len("Content/"):]
    elif text.startswith("Game/"):
        text = "/" + text
    return text


def prop_map(node: dict[str, Any]) -> dict[str, Any]:
    return {
        str(row.get("name", "")): row.get("value")
        for row in node.get("properties", [])
        if isinstance(row, dict) and row.get("name")
    }


def _mat4_mul(a: list[float], b: list[float]) -> list[float]:
    return [
        sum(a[row * 4 + k] * b[k * 4 + col] for k in range(4))
        for row in range(4)
        for col in range(4)
    ]


def _local_column_matrix(row: dict[str, Any]) -> list[float]:
    location = row.get("locationUEcm") or {}
    rotation = row.get("rotationUE") or {}
    scale = row.get("scale") or {}

    pitch = radians(float(rotation.get("Pitch", 0.0)))
    yaw = radians(float(rotation.get("Yaw", 0.0)))
    roll = radians(float(rotation.get("Roll", 0.0)))
    sp, cp = sin(pitch), cos(pitch)
    sy, cy = sin(yaw), cos(yaw)
    sr, cr = sin(roll), cos(roll)

    # Unreal FRotationMatrix row-vector basis. FTransform::ToMatrixWithScale
    # scales those three basis rows, then stores translation in row 3.
    ue_row = [
        cp * cy, cp * sy, sp,
        sr * sp * cy - cr * sy,
        sr * sp * sy + cr * cy,
        -sr * cp,
        -(cr * sp * cy + sr * sy),
        cy * sr - cr * sp * sy,
        cr * cp,
    ]
    sx = float(scale.get("X", 1.0))
    sy_scale = float(scale.get("Y", 1.0))
    sz = float(scale.get("Z", 1.0))
    tx = float(location.get("X", 0.0))
    ty = float(location.get("Y", 0.0))
    tz = float(location.get("Z", 0.0))
    row_major_ue = [
        ue_row[0] * sx, ue_row[1] * sx, ue_row[2] * sx, 0.0,
        ue_row[3] * sy_scale, ue_row[4] * sy_scale, ue_row[5] * sy_scale, 0.0,
        ue_row[6] * sz, ue_row[7] * sz, ue_row[8] * sz, 0.0,
        tx, ty, tz, 1.0,
    ]

    # CUE4Parse/Unreal matrices are row-vector matrices. Runtime matrices use
    # column vectors, so transpose here exactly like UEStaticSceneExtract.
    return [
        row_major_ue[0], row_major_ue[4], row_major_ue[8], row_major_ue[12],
        row_major_ue[1], row_major_ue[5], row_major_ue[9], row_major_ue[13],
        row_major_ue[2], row_major_ue[6], row_major_ue[10], row_major_ue[14],
        row_major_ue[3], row_major_ue[7], row_major_ue[11], row_major_ue[15],
    ]


def hierarchy_world_matrix(hierarchy: Any) -> list[float]:
    if not isinstance(hierarchy, list) or not hierarchy:
        raise ValueError("particle hierarchy is empty")

    identity = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]

    # Extractor authority is child-to-parent. For column-vector math:
    # world = root * ... * parent * child.
    world = identity
    for row in reversed(hierarchy):
        if not isinstance(row, dict):
            raise ValueError("particle hierarchy row is not an object")
        world = _mat4_mul(world, _local_column_matrix(row))

    # Match UEStaticSceneExtract::ToXzielMatrix exactly: B*M*B where
    # B=diag(1,-1,1,1), then convert translation cm -> meters.
    result = list(world)
    for row in range(4):
        for col in range(4):
            value = result[row * 4 + col]
            if row == 1:
                value = -value
            if col == 1:
                value = -value
            if col == 3 and row < 3:
                value *= 0.01
            if not isfinite(value):
                raise ValueError("non-finite particle transform")
            result[row * 4 + col] = value

    if any(abs(result[i]) > 1.0e-5 for i in (12, 13, 14)) or abs(result[15] - 1.0) > 1.0e-5:
        raise ValueError("particle transform is not affine")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, type=Path)
    ap.add_argument("--graphs", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    scene = json.loads(args.scene.read_text())
    graphs = json.loads(args.graphs.read_text())

    if scene.get("ready") is not True:
        raise SystemExit("particle placement scene is not ready")
    if graphs.get("ready") is not True:
        raise SystemExit("particle graph authority is not ready")

    graph_by_path = {
        canonical(row.get("objectPath")): row
        for row in graphs.get("systems", [])
        if canonical(row.get("objectPath"))
    }

    placements: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    node_types: Counter[str] = Counter()
    placed_systems: dict[str, dict[str, Any]] = {}

    for row in scene.get("particleComponents", []):
        template = row.get("template") or {}
        system_path = canonical(template.get("objectPath"))
        graph = graph_by_path.get(system_path)

        hierarchy = row.get("hierarchy", [])
        matrix_row_major = hierarchy_world_matrix(hierarchy)

        binding = {
            "id": row.get("id"),
            "actorName": row.get("actorName"),
            "ownerExportType": row.get("ownerExportType"),
            "ownerClassPath": row.get("ownerClassPath"),
            "componentName": row.get("componentName"),
            "sourcePath": row.get("sourcePath"),
            "hierarchy": hierarchy,
            "matrixRowMajor": matrix_row_major,
            "templateObjectPath": system_path,
            "templateProvenance": template.get("provenance"),
            "properties": row.get("properties", {}),
            "graphFound": graph is not None,
        }

        if graph is None:
            unresolved.append(binding)
            placements.append(binding)
            continue

        nodes = []
        for node in graph.get("nodes", []):
            node_type = str(node.get("exportType", ""))
            if node_type:
                node_types[node_type] += 1
            nodes.append({
                "objectPath": canonical(node.get("objectPath")),
                "exportType": node_type,
                "references": [canonical(x) for x in node.get("references", [])],
                "properties": prop_map(node),
            })

        system = {
            "objectPath": system_path,
            "packagePath": graph.get("packagePath"),
            "nodeCount": graph.get("nodeCount"),
            "referenceCount": graph.get("referenceCount"),
            "references": [canonical(x) for x in graph.get("references", [])],
            "nodes": nodes,
        }
        placed_systems.setdefault(system_path, system)
        binding["graphNodeCount"] = graph.get("nodeCount")
        binding["graphReferenceCount"] = graph.get("referenceCount")
        placements.append(binding)

    placement_count = len(placements)
    resolved_count = placement_count - len(unresolved)
    expected_placements = int(scene.get("particleComponentCount", -1))

    ready = (
        expected_placements == 29
        and placement_count == 29
        and resolved_count == 29
        and not unresolved
    )

    output = {
        "schemaVersion": 1,
        "format": "xogot_nacht_placed_particle_runtime_authority_v1",
        "sourceGame": scene.get("sourceGame"),
        "coordinateSystem": {
            "source": "Unreal X,Y,Z centimeters",
            "runtime": "XZIEL X,-Y,Z meters",
            "matrixConvention": "row_major_column_vector_T_R_S",
            "hierarchyConvention": "component local transforms child-to-parent",
            "centimetersToMeters": 0.01,
        },
        "placementCount": placement_count,
        "resolvedPlacementCount": resolved_count,
        "uniquePlacedSystemCount": len(placed_systems),
        "placedNodeTypeCounts": dict(sorted(node_types.items())),
        "placements": placements,
        "placedSystems": list(placed_systems.values()),
        "unresolvedPlacements": unresolved,
        # Explicitly false until a Godot renderer implements every placed graph
        # module and passes a visual/runtime probe. Authority != reproduction.
        "visualRuntimeReady": False,
        "ready": ready,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")

    print(
        "XZOGOT_NACHT_PARTICLE_RUNTIME_AUTHORITY",
        json.dumps(
            {
                "placements": placement_count,
                "resolved": resolved_count,
                "uniqueSystems": len(placed_systems),
                "nodeTypes": output["placedNodeTypeCounts"],
                "unresolved": len(unresolved),
                "visualRuntimeReady": False,
                "ready": ready,
            },
            separators=(",", ":"),
        ),
    )

    if not ready:
        print("XZOGOT_NACHT_PARTICLE_RUNTIME_AUTHORITY_FAILURE")
        return 5

    print("XZOGOT_NACHT_PARTICLE_RUNTIME_AUTHORITY_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
