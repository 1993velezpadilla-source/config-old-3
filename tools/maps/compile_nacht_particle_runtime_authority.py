#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
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

        binding = {
            "id": row.get("id"),
            "actorName": row.get("actorName"),
            "ownerExportType": row.get("ownerExportType"),
            "ownerClassPath": row.get("ownerClassPath"),
            "componentName": row.get("componentName"),
            "sourcePath": row.get("sourcePath"),
            "hierarchy": row.get("hierarchy", []),
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
