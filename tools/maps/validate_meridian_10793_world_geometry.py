#!/usr/bin/env python3
"""Compare world-space bounds of all 10,793 real original UE421 source actors.

Uses the previous original-native-GLB versus Meridian GLB proof helpers.
Streams output mesh node positions per actor instead of constructing one giant
duplicate vertex list for the whole scene. Research-only; NOT original BO3 T7.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

from validate_meridian_source_geometry import (
    box, identity, load_glb, local, mul, positions_for_mesh,
    source_actor_boxes, xform
)


def streamed_meridian_actor_boxes(path, actor_ids):
    doc, payload = load_glb(path)
    vertices = {}
    bounds = {}
    visited = set()
    mesh_node_count = Counter()

    def add(actor, point):
        if actor not in bounds:
            bounds[actor] = {"min": list(point), "max": list(point)}
            return
        current = bounds[actor]
        for j in range(3):
            value = point[j]
            if value < current["min"][j]:
                current["min"][j] = value
            if value > current["max"][j]:
                current["max"][j] = value

    def walk(index, parent, actor=None):
        if index < 0 or index >= len(doc["nodes"]) or index in visited:
            raise ValueError("cyclic, repeated or invalid GLB scene graph node")
        visited.add(index)
        node = doc["nodes"][index]
        world = mul(parent, local(node))
        name = node.get("name", "")
        if name in actor_ids:
            if actor is not None:
                raise ValueError("unexpected nested original actors: " + name)
            actor = name
        if "mesh" in node:
            if actor is None:
                raise ValueError("orphaned exported geometry: " + name)
            index_mesh = int(node["mesh"])
            if index_mesh not in vertices:
                vertices[index_mesh] = [
                    p for p in positions_for_mesh(doc, payload, index_mesh)
                ]
            mesh_node_count[actor] += 1
            for p in vertices[index_mesh]:
                add(actor, xform(world, p))
        for child in node.get("children", []):
            walk(child, world, actor)

    for node_index in doc["scenes"][doc.get("scene", 0)]["nodes"]:
        walk(node_index, identity())

    return bounds, mesh_node_count, len(vertices)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scene", type=Path, required=True)
    p.add_argument("--native-glb-dir", type=Path, required=True)
    p.add_argument("--meridian-glb", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--tolerance-mm", type=float, default=0.25)
    a = p.parse_args()
    if not 0 < a.tolerance_mm <= 2:
        raise ValueError("tolerance must be in (0,2] millimeters")
    scene = json.loads(a.scene.read_text())
    if scene.get("format") != "xziel_visual_scene_v1" or not scene.get("summary", {}).get("ready"):
        raise ValueError("source scene authority not ready")
    actors = scene["instances"]
    ids = [str(row["instanceId"]) for row in actors]
    if len(ids) != 10793 or len(set(ids)) != len(ids):
        raise ValueError("expected 10793 uniquely identified original scene actors")
    types = {int(row["meshIndex"]) for row in actors}
    if len(types) != 493 or len(scene["meshes"]) != 493:
        raise ValueError("all 493 native mesh types required")

    original = source_actor_boxes(scene, a.native_glb_dir, set(ids))
    exported, mesh_counts, exported_unique_meshes = streamed_meridian_actor_boxes(
        a.meridian_glb, set(ids)
    )
    if set(original) != set(ids) or set(exported) != set(ids):
        raise ValueError(
            f"lost original actors or exported meshes: "
            f"source={len(original)} output={len(exported)} expected={len(ids)} "
            f"missing={sorted(set(ids) - set(exported))[:10]}"
        )
    if sum(mesh_counts.values()) < 10793:
        raise ValueError("missing output mesh attachments")
    errors = []
    ranked = []
    for iid in ids:
        if mesh_counts[iid] == 0:
            errors.append([iid, "no attached GLB mesh"])
            continue
        if not all(math.isfinite(v)
                   for b in (original[iid], exported[iid])
                   for key in ("min", "max") for v in b[key]):
            errors.append([iid, "nonfinite mesh bounds"])
            continue
        delta_m = max(
            abs(original[iid][key][axis] - exported[iid][key][axis])
            for key in ("min", "max") for axis in range(3)
        )
        ranked.append((delta_m, iid))
        if delta_m > a.tolerance_mm / 1000.:
            errors.append([iid, round(delta_m * 1000, 7)])
    ranked.sort(reverse=True)
    result = {
        "source": "archived Pavlov UE4.21, NOT Black Ops III T7",
        "scene_actor_count": len(ids),
        "source_native_mesh_types": len(types),
        "exported_unique_glb_meshes": exported_unique_meshes,
        "exported_mesh_node_attachments": sum(mesh_counts.values()),
        "compared_actor_world_AABBs": len(ranked),
        "tolerance_mm": a.tolerance_mm,
        "maximum_world_aabb_boundary_error_mm": ranked[0][0] * 1000 if ranked else None,
        "worst_12": [{"actor": iid, "error_mm": err * 1000} for err, iid in ranked[:12]],
        "errors_first_25": errors[:25],
        "error_count": len(errors),
        "claims_full_vertex_parity": False,
        "claims_original_bo3_t7_assets": False,
        "claims_collision_or_gameplay_parity": False,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    if errors:
        print("XZOGOT_NACHT_10793_SOURCE_WORLD_BOUNDS_RED",
              json.dumps(result, separators=(",", ":"))[:4000])
        return 6
    print("XZOGOT_NACHT_10793_SOURCE_WORLD_BOUNDS_GREEN",
          "actors", len(ranked), "native_types", len(types),
          "max_error_mm", result["maximum_world_aabb_boundary_error_mm"],
          "mesh_nodes", result["exported_mesh_node_attachments"],
          "tolerance_mm", a.tolerance_mm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
