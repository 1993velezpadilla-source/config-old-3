#!/usr/bin/env python3
"""Unmodified native UE4.21 GLB vs Meridian GLB: full spatial vertex-cloud parity.

Inspect all vertices, not just AABBs, for one original placed actor of each
of the 493 actual source mesh types. Bidirectional Hausdorff distances are
measured in common Godot world coordinates using cKDTree. Indexed triangles
are counted to detect source primitive losses. This is not a texture/collision
or topological adjacency proof; original BO3 T7 provenance is NOT established.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.spatial import cKDTree

from validate_meridian_source_geometry import (
    identity, load_glb, local, mul, positions_for_mesh
)

BASIS = [[0., -1., 0., 0.], [0., 0., 1., 0.],
         [-1., 0., 0., 0.], [0., 0., 0., 1.]]


def affine(points, mat):
    a = np.asarray(mat, dtype=np.float64)
    return points @ a[:3, :3].T + a[:3, 3]


def mesh_cloud(doc, binary, index):
    points = []
    triangles = 0
    degenerate_triangles = 0
    for prim in doc["meshes"][index]["primitives"]:
        if prim.get("mode", 4) != 4:
            raise ValueError("only source triangle primitives accepted")
        # Each primitive has its own glTF POSITION accessor; do not accidentally
        # concatenate every primitive once per primitive.
        from validate_meridian_source_geometry import vpositions
        coords = np.asarray(
            list(vpositions(doc, binary, prim["attributes"]["POSITION"])),
            dtype=np.float64
        )
        if coords.ndim != 2 or coords.shape[1] != 3 or not len(coords):
            raise ValueError("empty or malformed GLB primitive vertices")
        points.append(coords)
        if "indices" in prim:
            count = int(doc["accessors"][prim["indices"]]["count"])
        else:
            count = len(coords)
        if count % 3:
            raise ValueError("indexed native triangle primitive count not divisible by 3")
        triangles += count // 3
        if "indices" in prim:
            import struct
            idx = doc["accessors"][prim["indices"]]
            bv = doc["bufferViews"][idx["bufferView"]]
            component = idx["componentType"]
            dtypes = {5121: np.dtype("u1"), 5123: np.dtype("<u2"),
                      5125: np.dtype("<u4")}
            if component not in dtypes:
                raise ValueError("unsupported triangle indices componentType")
            start = bv.get("byteOffset", 0) + idx.get("byteOffset", 0)
            stride = bv.get("byteStride", dtypes[component].itemsize)
            if stride == dtypes[component].itemsize:
                source_idx = np.frombuffer(
                    binary, dtype=dtypes[component], count=count,
                    offset=start
                ).astype(np.int64)
            else:
                source_idx = np.array([
                    int.from_bytes(binary[start + k*stride:
                                          start + k*stride + dtypes[component].itemsize],
                                   "little") for k in range(count)
                ], dtype=np.int64)
        else:
            source_idx = np.arange(count, dtype=np.int64)
        if len(source_idx) != count or np.any(source_idx >= len(coords)):
            raise ValueError("invalid native triangle vertex indices")
        triangles_xyz = coords[source_idx.reshape(-1, 3)]
        edge_ab = triangles_xyz[:, 1] - triangles_xyz[:, 0]
        edge_ac = triangles_xyz[:, 2] - triangles_xyz[:, 0]
        doubled_area_sq = np.sum(np.cross(edge_ab, edge_ac)**2, axis=1)
        # Strict zero-area faces, not merely triangles that happen to be
        # very small in source meters.
        degenerate_triangles += int(np.count_nonzero(doubled_area_sq <= 1e-24))
    return np.concatenate(points, axis=0), triangles, degenerate_triangles


def source_for_type(mesh_row, actor, native_dir):
    path = native_dir / (Path(mesh_row["runtimeFile"]).stem + ".glb")
    doc, binary = load_glb(path)
    if doc.get("extras", {}).get("xziel_basis_preserved") is not True:
        raise ValueError("native source GLB axis contract absent: " + path.name)
    # Existing native source converter states glTF chunk transforms identity.
    for node in doc["nodes"]:
        if local(node) != identity():
            raise ValueError("unproven native GLB node matrix: " + path.name)
    all_points = []
    triangles = 0
    degenerate = 0
    for i in range(len(doc["meshes"])):
        pts, tris, degens = mesh_cloud(doc, binary, i)
        all_points.append(pts)
        triangles += tris
        degenerate += degens
    raw = list(map(float, actor["matrixRowMajor"]))
    source_matrix = [raw[4*i:4*i+4] for i in range(4)]
    if source_matrix[3] != [0., 0., 0., 1.]:
        raise ValueError("non-affine original source matrix")
    world = mul(BASIS, source_matrix)
    return affine(np.concatenate(all_points, axis=0), world), triangles, degenerate


def exported_representatives(doc, binary, actor_ids):
    # Recursively map each source identity to the complete emitted GLB
    # mesh payload in *world* coordinates (not raw mesh-local space).
    nodes = doc["nodes"]
    found = defaultdict(list)
    seen = set()
    def walk(i, parent, actor=None):
        if i in seen or i < 0 or i >= len(nodes):
            raise ValueError("duplicate/cyclic GLB node")
        seen.add(i)
        n = nodes[i]
        m = mul(parent, local(n))
        name = n.get("name", "")
        if name in actor_ids:
            if actor is not None:
                raise ValueError("unexpected nested source actors")
            actor = name
        if "mesh" in n and actor in actor_ids:
            found[actor].append((int(n["mesh"]), m))
        for child in n.get("children", []):
            walk(child, m, actor)
    for n in doc["scenes"][doc.get("scene", 0)]["nodes"]:
        walk(n, identity())
    if set(found) != actor_ids:
        raise ValueError(f"missing exported representatives {sorted(actor_ids-set(found))[:10]}")
    return found


def compare_clouds(src, dst):
    # Positions may legitimately be duplicated by glTF material splits,
    # so nearest-neighbour spatial coverage is more robust than byte hashes.
    a = cKDTree(src)
    b = cKDTree(dst)
    source_to_export = float(np.max(b.query(src, k=1, workers=1)[0]))
    export_to_source = float(np.max(a.query(dst, k=1, workers=1)[0]))
    return max(source_to_export, export_to_source)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scene", type=Path, required=True)
    p.add_argument("--native-glb-dir", type=Path, required=True)
    p.add_argument("--meridian-glb", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-distance-mm", type=float, default=0.25)
    args = p.parse_args()
    if not 0 < args.max_distance_mm <= 2.0:
        raise ValueError("vertex distance threshold must be 0..2 millimeters")
    scene = json.loads(args.scene.read_text())
    if scene.get("format") != "xziel_visual_scene_v1" or not scene.get("summary", {}).get("ready"):
        raise ValueError("source not approved")
    mesh_rows = {int(m["index"]): m for m in scene["meshes"]}
    if len(mesh_rows) != 493 or len(scene["instances"]) != 10793:
        raise ValueError("expected original full 10793/493 source only")
    actors = {}
    for actor in scene["instances"]:
        idx = int(actor["meshIndex"])
        if idx not in actors:
            actors[idx] = actor
    if set(actors) != set(mesh_rows):
        raise ValueError("every original mesh type requires its original actor")
    chosen_ids = {str(row["instanceId"]) for row in actors.values()}
    if len(chosen_ids) != 493:
        raise ValueError("duplicate representative actors")
    exported_doc, exported_bytes = load_glb(args.meridian_glb)
    found = exported_representatives(exported_doc, exported_bytes, chosen_ids)
    export_cache = {}
    results = []
    fail = []
    for idx in sorted(actors):
        actor = actors[idx]
        iid = str(actor["instanceId"])
        src, original_triangles, original_degenerate = source_for_type(
            mesh_rows[idx], actor, args.native_glb_dir
        )
        chunks = []
        exported_triangles = 0
        exported_degenerate = 0
        for mesh_idx, matrix in found[iid]:
            if mesh_idx not in export_cache:
                export_cache[mesh_idx] = mesh_cloud(
                    exported_doc, exported_bytes, mesh_idx
                )
            vertices, triangles, degenerate = export_cache[mesh_idx]
            chunks.append(affine(vertices, matrix))
            exported_triangles += triangles
            exported_degenerate += degenerate
        output = np.concatenate(chunks, axis=0)
        delta = compare_clouds(src, output)
        row = {
            "source_mesh_index": idx, "actor": iid,
            "native_vertices": int(len(src)),
            "exported_vertices": int(len(output)),
            "native_triangles": original_triangles,
            "exported_triangles": exported_triangles,
            "native_degenerate_triangles": original_degenerate,
            "exported_degenerate_triangles": exported_degenerate,
            "native_nondegenerate_triangles": original_triangles - original_degenerate,
            "exported_nondegenerate_triangles": exported_triangles - exported_degenerate,
            "bidirectional_hausdorff_mm": delta * 1000.,
        }
        results.append(row)
        if (not math.isfinite(delta) or delta * 1000 > args.max_distance_mm
                or original_triangles != exported_triangles):
            fail.append(row)
    result = {
        "source": "archived Pavlov UE4.21 - NOT BO3 T7",
        "distinct_source_mesh_types_tested": len(results),
        "full_spatial_vertex_coverage": True,
        "bidirectional_vertex_distance_threshold_mm": args.max_distance_mm,
        "max_bidirectional_hausdorff_mm": max(
            row["bidirectional_hausdorff_mm"] for row in results
        ),
        "source_triangles": sum(x["native_triangles"] for x in results),
        "exported_triangles": sum(x["exported_triangles"] for x in results),
        "source_degenerate_triangles": sum(x["native_degenerate_triangles"] for x in results),
        "exported_degenerate_triangles": sum(x["exported_degenerate_triangles"] for x in results),
        "source_nondegenerate_triangles": sum(x["native_nondegenerate_triangles"] for x in results),
        "exported_nondegenerate_triangles": sum(x["exported_nondegenerate_triangles"] for x in results),
        "errors_first_25": fail[:25],
        "error_count": len(fail),
        "worst_15_meshes": sorted(results, key=lambda x: x["bidirectional_hausdorff_mm"], reverse=True)[:15],
        "all_vertex_triangle_adjacency_proven": False,
        "materials_uv_lighting_collisions_proven": False,
        "original_BO3_T7_proven": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if fail:
        print("XZOGOT_NACHT_493_FULL_VERTEX_CLOUD_RED", json.dumps(result)[:3000])
        return 7
    print("XZOGOT_NACHT_493_FULL_VERTEX_CLOUD_GREEN",
          "native_mesh_types", len(results),
          "max_Hausdorff_mm", result["max_bidirectional_hausdorff_mm"],
          "source_triangles", result["source_triangles"],
          "export_triangles", result["exported_triangles"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
