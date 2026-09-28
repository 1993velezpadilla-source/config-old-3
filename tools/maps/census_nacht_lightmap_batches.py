#!/usr/bin/env python3
"""Measure the exact Nacht batching cost of grouping instances by mesh + lightmap pair."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

EXPECTED_MESHES = 492
EXPECTED_INSTANCES = 10791
EXPECTED_MAPPED = 10786


def normalize_path(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\\", "/").rstrip("/").lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", type=Path, required=True)
    ap.add_argument("--scene", type=Path, required=True)
    ap.add_argument("--bindings", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    assets = json.loads(args.assets.read_text(encoding="utf-8"))
    scene = json.loads(args.scene.read_text(encoding="utf-8"))
    bindings = json.loads(args.bindings.read_text(encoding="utf-8"))

    meshes = assets.get("meshes", [])
    instances = scene.get("instances", [])
    records = bindings.get("instanceBindings", [])

    if len(meshes) != EXPECTED_MESHES:
        raise SystemExit(f"expected {EXPECTED_MESHES} meshes, got {len(meshes)}")
    if len(instances) != EXPECTED_INSTANCES or len(records) != EXPECTED_INSTANCES:
        raise SystemExit(
            f"instance alignment drift scene={len(instances)} bindings={len(records)}"
        )

    mesh_index: dict[str, int] = {}
    for index, row in enumerate(meshes):
        source = normalize_path(row.get("sourcePath"))
        if not source or source in mesh_index:
            raise SystemExit(f"bad mesh source at {index}: {source!r}")
        mesh_index[source] = index

    pair_counts: Counter[tuple[str, str]] = Counter()
    mesh_pair_counts: Counter[tuple[int, tuple[str, str]]] = Counter()
    pairs_by_mesh: dict[int, set[tuple[str, str]]] = defaultdict(set)
    missing = 0
    mapped = 0

    for index, (instance, record) in enumerate(zip(instances, records)):
        if record.get("instanceIndex") != index:
            raise SystemExit(f"binding alignment drift at instance {index}")
        source = normalize_path(instance.get("mesh"))
        if source not in mesh_index:
            raise SystemExit(f"unknown scene mesh at instance {index}: {source!r}")
        mi = mesh_index[source]

        if record.get("status") != "mapped":
            missing += 1
            continue

        binding = record.get("binding")
        if not isinstance(binding, dict) or not binding.get("runtimePayloadReady"):
            raise SystemExit(f"mapped instance {index} lacks runtime-ready payload")

        textures = binding.get("lightTextures")
        if not isinstance(textures, list) or len(textures) != 2:
            raise SystemExit(f"instance {index} has invalid lightmap pair")
        pair = (str(textures[0]), str(textures[1]))

        mapped += 1
        pair_counts[pair] += 1
        mesh_pair_counts[(mi, pair)] += 1
        pairs_by_mesh[mi].add(pair)

    if mapped != EXPECTED_MAPPED or missing != EXPECTED_INSTANCES - EXPECTED_MAPPED:
        raise SystemExit(f"mapped/missing drift: mapped={mapped} missing={missing}")

    groups_per_mesh = {
        str(mi): len(pairs)
        for mi, pairs in pairs_by_mesh.items()
    }
    group_sizes = list(mesh_pair_counts.values())
    global_pair_sizes = list(pair_counts.values())
    pair_group_count = len(mesh_pair_counts)
    referenced_meshes = len(pairs_by_mesh)

    distribution = Counter(groups_per_mesh.values())

    report = {
        "schemaVersion": 1,
        "format": "xziel_nacht_lightmap_batch_census_v1",
        "meshCount": EXPECTED_MESHES,
        "instanceCount": EXPECTED_INSTANCES,
        "mappedInstanceCount": mapped,
        "missingInstanceCount": missing,
        "referencedMappedMeshCount": referenced_meshes,
        "uniqueLightmapPairCount": len(pair_counts),
        "meshLightmapPairGroupCount": pair_group_count,
        "baselineMeshSpanCount": EXPECTED_MESHES,
        "meshSpanMultiplier": pair_group_count / EXPECTED_MESHES,
        "maxPairsPerMesh": max(groups_per_mesh.values(), default=0),
        "averagePairsPerMappedMesh":
            pair_group_count / referenced_meshes if referenced_meshes else 0.0,
        "maxInstancesPerMeshPairGroup": max(group_sizes, default=0),
        "minInstancesPerMeshPairGroup": min(group_sizes, default=0),
        "averageInstancesPerMeshPairGroup":
            mapped / pair_group_count if pair_group_count else 0.0,
        "maxInstancesPerGlobalPair": max(global_pair_sizes, default=0),
        "groupsPerMeshDistribution": {
            str(k): v for k, v in sorted(distribution.items())
        },
        "topGlobalPairs": [
            {
                "texture0": pair[0],
                "texture1": pair[1],
                "instances": count,
            }
            for pair, count in pair_counts.most_common(12)
        ],
        "topMeshPairGroups": [
            {
                "meshIndex": key[0],
                "texture0": key[1][0],
                "texture1": key[1][1],
                "instances": count,
            }
            for key, count in mesh_pair_counts.most_common(20)
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("XZIEL_NACHT_LIGHTMAP_BATCH_CENSUS_OK", json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
