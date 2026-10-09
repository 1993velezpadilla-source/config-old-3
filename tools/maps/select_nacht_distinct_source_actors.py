#!/usr/bin/env python3
"""Choose source-original Nacht actors by distinct *real* native mesh types.

For CI only: no synthetic geometry, no new transforms, no source coordinate edits.
Picks one instance per GLB mesh identity; cost-aware so CI need not import GBs.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def choose(scene, source_root, count, max_file_bytes):
    if scene.get("format") != "xziel_visual_scene_v1" or not scene.get("summary", {}).get("ready"):
        raise ValueError("unverified source scene")
    if "T7" in str(scene.get("sourceGameName", "")):
        raise ValueError("not a BO3 source extractor")
    meshes = {int(m["index"]): m for m in scene["meshes"]}
    representatives = {}
    source_distribution = Counter()
    for row in scene["instances"]:
        idx = int(row["meshIndex"])
        source_distribution[idx] += 1
        if idx not in representatives:
            representatives[idx] = row
    source_usable = []
    for idx, row in representatives.items():
        src = meshes[idx]
        path = source_root / (Path(src["runtimeFile"]).stem + ".glb")
        if path.is_file() and path.stat().st_size > 100:
            size = path.stat().st_size
            source_usable.append((size, idx, row, path.name))
    # First cover distinct geometries cheaply. Original instances and positions
    # retain their precise source values with zero global or per-actor tweaks.
    source_usable.sort(key=lambda x: (x[0], x[1]))
    selected = [x for x in source_usable if x[0] <= max_file_bytes][:count]
    if len(selected) != count:
        raise ValueError("not enough distinct real GLBs under size cap: %d/%d; "
                         "change budget explicitly and rerun" % (len(selected), count))
    chosen = {idx: row for _, idx, row, _ in selected}
    selected_rows = [row for row in scene["instances"] if int(row["meshIndex"]) in chosen
                     and row["instanceId"] == chosen[int(row["meshIndex"])]["instanceId"]]
    if len(selected_rows) != count or len({r["meshIndex"] for r in selected_rows}) != count:
        raise ValueError("failed to preserve one distinct original instance per native GLB")
    bytes_total = sum(x[0] for x in selected)
    if bytes_total > 180_000_000:
        raise ValueError("selected source memory budget exceeded: %d" % bytes_total)
    out = dict(scene)
    out["instances"] = selected_rows
    out["sourceFullSceneSummary"] = dict(scene["summary"])
    out["summary"] = dict(scene["summary"])
    out["summary"]["sceneInstanceCount"] = count
    out["summary"]["referencedNativeMeshCount"] = count
    out["selectionProof"] = {
        "type": "one_native_real_mesh_per_original_source_actor",
        "original_actor_count": len(scene["instances"]),
        "original_native_mesh_types": len(scene["meshes"]),
        "selected_actor_count": count,
        "selected_distinct_mesh_types": len(chosen),
        "source_glb_bytes_total": bytes_total,
        "source_glb_largest": max(x[0] for x in selected),
        "original_instance_ids": [r["instanceId"] for r in selected_rows],
        "original_mesh_indices": [r["meshIndex"] for r in selected_rows],
        "native_source_identity_modified": False,
        "is_original_BO3_T7": False,
    }
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--mesh-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=128)
    parser.add_argument("--max-individual-glb-bytes", type=int, default=6_000_000)
    args = parser.parse_args()
    original = args.scene.read_bytes()
    output = choose(json.loads(original), args.mesh_root, args.count,
                    args.max_individual_glb_bytes)
    output["selectionProof"]["source_sha256"] = hashlib.sha256(original).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    receipt = output["selectionProof"]
    print("XZOGOT_NACHT_DISTINCT_UE_NATIVE_SOURCE_SELECTION_GREEN",
          "objects", receipt["selected_actor_count"],
          "distinct_native_meshes", receipt["selected_distinct_mesh_types"],
          "mesh_bytes", receipt["source_glb_bytes_total"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
