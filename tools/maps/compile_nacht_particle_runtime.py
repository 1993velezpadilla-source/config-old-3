#!/usr/bin/env python3
"""Compile exact Nacht Cascade placement + graph authority into a Godot runtime manifest.

This compiler does not approximate unsupported Cascade modules. It preserves
all source nodes/properties and marks each placed system runtimeReady only when
all non-structural node types are explicitly supported by the runtime bridge.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

STRUCTURAL_TYPES = {
    "ParticleSystem",
    "ParticleSpriteEmitter",
    "ParticleLODLevel",
}

VALUE_NODE_PREFIXES = (
    "DistributionFloat",
    "DistributionVector",
)

# These Cascade module families appear to have direct Godot mapping candidates.
# This is NOT a runtime-support declaration. Visual runtime remains RED until
# the renderer implements and probes every placed source graph.
DIRECT_MAPPING_CANDIDATE_TYPES = {
    "ParticleModuleRequired",
    "ParticleModuleSpawn",
    "ParticleModuleLifetime",
    "ParticleModuleSize",
    "ParticleModuleColorOverLife",
    "ParticleModuleSizeMultiplyLife",
    "ParticleModuleVelocity",
    "ParticleModuleRotation",
    "ParticleModuleLocation",
    "ParticleModuleSubUV",
    "ParticleModuleColor",
    "ParticleModuleLocationPrimitiveCylinder",
    "ParticleModuleOrientationAxisLock",
}


def canonical(raw: str) -> str:
    value = (raw or "").strip().replace("\\", "/")
    if "'" in value and value.endswith("'"):
        value = value.split("'", 1)[1][:-1]
    if value.startswith("Content/"):
        value = "/Game/" + value[len("Content/"):]
    elif value.startswith("Game/"):
        value = "/" + value
    return value.lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--placements", type=Path, required=True)
    ap.add_argument("--graphs", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    placements = json.loads(args.placements.read_text())
    graphs = json.loads(args.graphs.read_text())

    assert placements.get("ready") is True, placements
    assert graphs.get("ready") is True, graphs
    assert placements.get("particleComponentCount") == 29, placements
    assert placements.get("referencedTemplateCount") == 29, placements
    assert placements.get("nullTemplateCount") == 0, placements
    assert graphs.get("particleSystemCount") == 39, graphs

    graph_by_path = {
        canonical(row.get("objectPath", "")): row
        for row in graphs.get("systems", [])
        if row.get("objectPath")
    }

    compiled = []
    missing_graphs = []
    unsupported_types = set()
    runtime_ready_count = 0

    for row in placements.get("particleComponents", []):
        template = row.get("template", {})
        template_path = str(template.get("objectPath") or "")
        key = canonical(template_path)
        graph = graph_by_path.get(key)
        if graph is None:
            missing_graphs.append(
                {
                    "actorName": row.get("actorName"),
                    "componentName": row.get("componentName"),
                    "templatePath": template_path,
                }
            )
            continue

        system_unsupported = sorted(
            {
                str(node.get("exportType", ""))
                for node in graph.get("nodes", [])
                if str(node.get("exportType", ""))
                and str(node.get("exportType", "")) not in STRUCTURAL_TYPES
                and str(node.get("exportType", "")) not in DIRECT_MAPPING_CANDIDATE_TYPES
            }
        )
        unsupported_types.update(system_unsupported)

        # Authority and module classification are complete, but no placed
        # Cascade renderer has passed a Godot visual/runtime probe yet.
        runtime_ready = False

        compiled.append(
            {
                "id": row.get("id"),
                "actorName": row.get("actorName"),
                "componentName": row.get("componentName"),
                "sourcePath": row.get("sourcePath"),
                "ownerExportType": row.get("ownerExportType"),
                "ownerClassPath": row.get("ownerClassPath"),
                "hierarchy": row.get("hierarchy", []),
                "template": template,
                "templatePath": template_path,
                "graphObjectPath": graph.get("objectPath"),
                "graphPackagePath": graph.get("packagePath"),
                "nodeCount": graph.get("nodeCount"),
                "referenceCount": graph.get("referenceCount"),
                "references": graph.get("references", []),
                "nodes": graph.get("nodes", []),
                "unsupportedNodeTypes": system_unsupported,
                "runtimeReady": runtime_ready,
            }
        )

    assert not missing_graphs, missing_graphs
    assert len(compiled) == 29, len(compiled)

    result = {
        "schemaVersion": 1,
        "authority": "exact Nacht UMAP particle placement + Cascade graph authority",
        "placementCount": len(compiled),
        "sourceParticleSystemCount": graphs.get("particleSystemCount"),
        "supportedStructuralTypes": sorted(STRUCTURAL_TYPES),
        "directMappingCandidateTypes": sorted(DIRECT_MAPPING_CANDIDATE_TYPES),
        "unsupportedNodeTypes": sorted(unsupported_types),
        "runtimeReadyPlacementCount": runtime_ready_count,
        "allPlacementsSemanticallySupported": False,
        "visualRuntimeReady": False,
        "placements": compiled,
        "ready": True,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        "XZOGOT_NACHT_PARTICLE_RUNTIME_MANIFEST_GREEN",
        json.dumps(
            {
                "placements": len(compiled),
                "runtimeReady": runtime_ready_count,
                "unsupportedNodeTypes": sorted(unsupported_types),
            },
            separators=(",", ":"),
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
