#!/usr/bin/env python3
"""Fail-closed 4x4 affine audit of EVERY original UE4.21 Nacht actor.

Proof is source JSON -> Meridian Godot GLB node matrix equality, not a
render/vertex equivalence or a claim of original BO3 T7 source provenance.
Read GLB JSON only: the large mesh BIN is irrelevant to this gate.
"""
import argparse
import json
import math
from pathlib import Path
import struct
import sys

C = ((1., 0., 0., 0.), (0., 0., 1., 0.),
     (0., -1., 0., 0.), (0., 0., 0., 1.))
CT = tuple(zip(*C))


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4))
             for j in range(4)] for i in range(4)]


def load_glb_json(path):
    with path.open("rb") as f:
        header = f.read(20)
        if len(header) != 20:
            raise ValueError("truncated GLB header")
        magic, version, total, length, chunk_type = struct.unpack("<IIIII", header)
        if magic != 0x46546C67 or version != 2 or chunk_type != 0x4E4F534A:
            raise ValueError("invalid GLB 2.0 JSON header")
        if length > total or total != path.stat().st_size:
            raise ValueError("invalid GLB chunk length")
        return json.loads(f.read(length))


def matrix_from_source(raw):
    if not isinstance(raw, list) or len(raw) != 16:
        raise ValueError("missing 4x4 source matrix")
    if not all(math.isfinite(float(t)) for t in raw):
        raise ValueError("non-finite source matrix")
    m = [[float(t) for t in raw[4*i:4*i+4]] for i in range(4)]
    if m[3] != [0., 0., 0., 1.]:
        raise ValueError("non-affine source actor")
    return m


def audit(scene, doc, expected_count):
    if scene.get("format") != "xziel_visual_scene_v1" or not scene.get("summary", {}).get("ready"):
        raise ValueError("not an approved UE4.21 source scene")
    actors = scene["instances"]
    if len(actors) != expected_count:
        raise ValueError(f"wrong source count {len(actors)} != {expected_count}")
    types = {int(a["meshIndex"]) for a in actors}
    if types != {int(m["index"]) for m in scene["meshes"]}:
        raise ValueError("some native mesh types absent from source actors")
    if len(types) != 493:
        raise ValueError(f"unexpected native mesh types: {len(types)}")
    rows = {str(a["instanceId"]): matrix_from_source(a["matrixRowMajor"]) for a in actors}
    if len(rows) != len(actors):
        raise ValueError("duplicate source actor IDs")
    nodes = doc["nodes"]
    seen = set()
    max_error = 0.
    mesh_nodes = 0
    missing_mesh = []
    for idx, node in enumerate(nodes):
        name = node.get("name", "")
        if name not in rows:
            continue
        if name in seen:
            raise ValueError(f"duplicate exported actor {name}")
        seen.add(name)
        if "matrix" not in node or any(k in node for k in ("scale", "rotation", "translation")):
            raise ValueError(f"unrestored affine node for {name}")
        target = mul(mul(C, rows[name]), CT)
        actual = node["matrix"]
        if len(actual) != 16:
            raise ValueError(f"bad GLB affine matrix {name}")
        error = max(abs(float(actual[j*4+i]) - target[i][j])
                    for i in range(4) for j in range(4))
        if not math.isfinite(error):
            raise ValueError(f"nonfinite exported affine matrix {name}")
        max_error = max(max_error, error)
        if error > 1e-7:
            raise ValueError(f"affine matrix lost for {name}: abs error {error}")
        # Count actual descendant GLB mesh nodes; transforms alone must not
        # earn GREEN when an actor has lost its source geometry attachment.
        children = list(node.get("children", []))
        visited = set()
        found = 0
        while children:
            child = children.pop()
            if child in visited:
                raise ValueError(f"cyclic or repeated actor subtree {name}")
            visited.add(child)
            item = nodes[child]
            if item.get("name", "") in rows:
                raise ValueError(f"nested source actor under {name}")
            found += int("mesh" in item)
            children.extend(item.get("children", []))
        mesh_nodes += found
        if not found:
            missing_mesh.append(name)
    missing = set(rows) - seen
    if missing or missing_mesh:
        raise ValueError(f"actors missing={sorted(missing)[:8]} no_mesh={missing_mesh[:8]}")
    if mesh_nodes < expected_count:
        raise ValueError(f"GLB mesh attachments missing: {mesh_nodes}/{expected_count}")
    return {
        "authority": "archived Pavlov UE4.21 source, not original BO3 T7",
        "source_actor_count": len(rows),
        "source_distinct_native_mesh_types": len(types),
        "affine_matrices_exact_within_1e-7": True,
        "maximum_absolute_affine_element_error": max_error,
        "exported_actor_nodes": len(seen),
        "exported_glb_mesh_attachments": mesh_nodes,
        "original_BO3_T7_proven": False,
        "full_vertex_parity_proven_by_this_gate": False,
        "godot_gameplay_proven_by_this_gate": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scene", type=Path, required=True)
    p.add_argument("--glb", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--expected-count", type=int, default=10793)
    opts = p.parse_args()
    report = audit(json.loads(opts.scene.read_text()),
                   load_glb_json(opts.glb), opts.expected_count)
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("XZOGOT_NACHT_FULL_SOURCE_AFFINE_PARITY_GREEN",
          "actors", report["source_actor_count"],
          "native_mesh_types", report["source_distinct_native_mesh_types"],
          "mesh_attachments", report["exported_glb_mesh_attachments"],
          "maximum_abs_affine_error", report["maximum_absolute_affine_element_error"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
