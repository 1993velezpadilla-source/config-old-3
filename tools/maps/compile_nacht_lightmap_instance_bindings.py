#!/usr/bin/env python3
"""Join Nacht scene instances to exact UE4 baked-lighting records."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

EXPECTED_INSTANCES = 10791


def normalize_asset_path(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.replace("\\", "/").strip()
    lower = text.lower()

    marker = "/content/"
    at = lower.find(marker)
    if at >= 0:
        text = "/Game/" + text[at + len(marker):]
    elif lower.startswith("content/"):
        text = "/Game/" + text[len("content/"):]

    text = text.rstrip("/")
    if text.lower().endswith(".uasset"):
        text = text[:-7]

    if "/" in text:
        head, tail = text.rsplit("/", 1)
    else:
        head, tail = "", text

    if "." in tail:
        package, obj = tail.split(".", 1)
        if package.lower() == obj.lower():
            tail = package

    text = f"{head}/{tail}" if head else tail
    return text.lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=Path, required=True)
    ap.add_argument("--census", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    scene = json.loads(args.scene.read_text(encoding="utf-8"))
    census = json.loads(args.census.read_text(encoding="utf-8"))

    instances = scene.get("instances", [])
    if len(instances) != EXPECTED_INSTANCES:
        raise SystemExit(
            f"expected {EXPECTED_INSTANCES} scene instances, got {len(instances)}"
        )

    static_component_metadata = {
        row["componentExportIndex"]: row
        for row in census.get("staticMeshComponents", [])
        if isinstance(row, dict)
        and isinstance(row.get("componentExportIndex"), int)
    }

    by_component: dict[int, list[dict]] = defaultdict(list)
    for mesh_build in census.get("meshBuildData", []):
        if not isinstance(mesh_build, dict):
            continue
        for link in mesh_build.get("linkedComponents", []):
            if not isinstance(link, dict):
                continue
            if link.get("bindingKind") != "staticMeshLOD":
                continue
            component_index = link.get("componentExportIndex")
            if not isinstance(component_index, int):
                continue
            row = {
                "mapBuildDataId": mesh_build.get("mapBuildDataId"),
                "lightMapType": mesh_build.get("lightMapType"),
                "shadowMapType": mesh_build.get("shadowMapType"),
                "lightTextures": mesh_build.get("lightTextures", []),
                "shadowTexture": mesh_build.get("shadowTexture"),
                "skyOcclusionTexture": mesh_build.get("skyOcclusionTexture"),
                "aoMaskTexture": mesh_build.get("aoMaskTexture"),
                "bindingIndex": link.get("bindingIndex"),
                "assetPath": link.get("assetPath"),
                "lightMapCoordinateIndex": link.get("lightMapCoordinateIndex", -1),
                "numTexCoords": link.get("numTexCoords", -1),
            }
            by_component[component_index].append(row)

    mapped = 0
    missing = 0
    ambiguous = 0
    asset_mismatch = 0
    unresolved_uv = 0
    non_lightmap2d = 0
    records: list[dict] = []
    seen_scene_components: set[int] = set()
    duplicate_scene_components = 0

    for instance_index, instance in enumerate(instances):
        component_index = instance.get("componentExportIndex")
        if not isinstance(component_index, int):
            raise SystemExit(
                f"instance {instance_index} has no integer componentExportIndex"
            )

        if component_index in seen_scene_components:
            duplicate_scene_components += 1
        seen_scene_components.add(component_index)

        candidates = [
            row
            for row in by_component.get(component_index, [])
            if row.get("bindingIndex") == 0
        ]

        status = "mapped"
        chosen = None
        if not candidates:
            status = "missing"
            missing += 1
        elif len(candidates) != 1:
            status = "ambiguous"
            ambiguous += 1
        else:
            chosen = candidates[0]
            mapped += 1

        scene_mesh = instance.get("mesh")
        scene_mesh_norm = normalize_asset_path(scene_mesh)
        asset_matches = None
        if chosen is not None:
            bound_mesh_norm = normalize_asset_path(chosen.get("assetPath"))
            asset_matches = (
                bool(scene_mesh_norm)
                and bool(bound_mesh_norm)
                and scene_mesh_norm == bound_mesh_norm
            )
            if asset_matches is False:
                asset_mismatch += 1
            if chosen.get("lightMapCoordinateIndex", -1) < 0:
                unresolved_uv += 1
            if chosen.get("lightMapType") != "2d":
                non_lightmap2d += 1

        records.append(
            {
                "instanceIndex": instance_index,
                "instanceId": instance.get("instanceId"),
                "componentExportIndex": component_index,
                "actorExportIndex": instance.get("actorExportIndex"),
                "actorName": instance.get("actorName"),
                "componentName": instance.get("componentName"),
                "sceneMesh": scene_mesh,
                "status": status,
                "assetMatchesSceneMesh": asset_matches,
                "componentMetadata":
                    static_component_metadata.get(component_index),
                "binding": chosen,
            }
        )

    known_indices_by_mesh: dict[str, set[int]] = defaultdict(set)
    for record in records:
        binding = record.get("binding")
        if record["status"] != "mapped" or not isinstance(binding, dict):
            continue
        index = binding.get("lightMapCoordinateIndex", -1)
        mesh_key = normalize_asset_path(record.get("sceneMesh"))
        if isinstance(index, int) and index >= 0 and mesh_key:
            known_indices_by_mesh[mesh_key].add(index)

    mesh_index_conflicts = sum(
        1 for values in known_indices_by_mesh.values()
        if len(values) > 1
    )
    mesh_consensus_resolved = 0
    unresolved_effective_uv = 0

    for record in records:
        binding = record.get("binding")
        if record["status"] != "mapped" or not isinstance(binding, dict):
            continue

        raw_index = binding.get("lightMapCoordinateIndex", -1)
        effective_index = raw_index
        resolution = "authored"

        if not isinstance(raw_index, int) or raw_index < 0:
            mesh_key = normalize_asset_path(record.get("sceneMesh"))
            candidates = known_indices_by_mesh.get(mesh_key, set())
            if len(candidates) == 1:
                effective_index = next(iter(candidates))
                resolution = "meshConsensus"
                mesh_consensus_resolved += 1
            else:
                effective_index = -1
                resolution = "unresolved"
                unresolved_effective_uv += 1

        binding["effectiveLightMapCoordinateIndex"] = effective_index
        binding["coordinateIndexResolution"] = resolution

    stats = {
        "instanceCount": len(instances),
        "uniqueSceneComponentCount": len(seen_scene_components),
        "duplicateSceneComponentCount": duplicate_scene_components,
        "bakedStaticComponentCount": len(by_component),
        "staticComponentMetadataCount":
            len(static_component_metadata),
        "mappedInstanceCount": mapped,
        "missingInstanceCount": missing,
        "ambiguousInstanceCount": ambiguous,
        "assetMismatchCount": asset_mismatch,
        "unresolvedLightMapCoordinateIndexCount": unresolved_uv,
        "meshConsensusResolvedCoordinateIndexCount": mesh_consensus_resolved,
        "unresolvedEffectiveCoordinateIndexCount": unresolved_effective_uv,
        "meshCoordinateIndexConflictCount": mesh_index_conflicts,
        "nonLightMap2DCount": non_lightmap2d,
    }

    output = {
        "schemaVersion": 1,
        "format": "xziel_nacht_lightmap_instance_bindings_audit_v1",
        "stats": stats,
        "instanceBindings": records,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2) + "\n",
        encoding="utf-8",
    )

    for record in records:
        binding = record.get("binding")
        unresolved = (
            isinstance(binding, dict)
            and binding.get("effectiveLightMapCoordinateIndex", -1) < 0
        )
        if record["status"] != "mapped" or unresolved:
            print(
                "XZIEL_NACHT_LIGHTMAP_INSTANCE_FINAL_CASE",
                json.dumps(record, sort_keys=True),
            )

    print(
        "XZIEL_NACHT_LIGHTMAP_INSTANCE_JOIN_OK",
        json.dumps(stats, sort_keys=True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
