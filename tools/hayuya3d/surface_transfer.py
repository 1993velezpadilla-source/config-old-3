#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import heapq


@dataclass
class SurfaceTransferRelation:
    triangle_vertex_ids: object
    barycentric: object
    surface_distance: object
    nearest_vertex_ids: object
    candidate_triangles: int
    fallback_vertices: int
    max_examined_triangles: int = 0
    max_visited_bvh_nodes: int = 0
    ambiguous_skin_vertices: int = 0
    surface_skin_min_gap_ratio: float | None = None
    surface_skin_max_l1: float = 0.0
    method: str = "hayuya-surface-transfer-bvh-barycentric-exact-v2"


@dataclass
class SurfaceCandidate:
    face_index: int
    triangle_vertex_ids: object
    barycentric: object
    distance: float


@dataclass
class SurfaceTransferIndex:
    vertices: object
    faces: object
    nodes: object
    root: int
    vertex_tree: object
    bvh_leaf_size: int
    method: str = "hayuya-surface-transfer-index-bvh-v1"


def _deps():
    import numpy as np
    from scipy.spatial import cKDTree
    return np, cKDTree


def _closest_point_barycentric(point, a, b, c):
    """Closest point on triangle using Ericson region tests.

    Returns (closest_point, barycentric). Degenerate triangles return None.
    """
    np, _ = _deps()
    p = np.asarray(point, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    c = np.asarray(c, dtype=np.float64)

    ab = b - a
    ac = c - a
    normal = np.cross(ab, ac)
    area2 = float(np.dot(normal, normal))
    if not np.isfinite(area2) or area2 <= 1e-24:
        return None

    ap = p - a
    d1 = float(np.dot(ab, ap))
    d2 = float(np.dot(ac, ap))
    if d1 <= 0.0 and d2 <= 0.0:
        return a, np.asarray([1.0, 0.0, 0.0], dtype=np.float64)

    bp = p - b
    d3 = float(np.dot(ab, bp))
    d4 = float(np.dot(ac, bp))
    if d3 >= 0.0 and d4 <= d3:
        return b, np.asarray([0.0, 1.0, 0.0], dtype=np.float64)

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        denom = d1 - d3
        v = 0.0 if abs(denom) <= 1e-24 else d1 / denom
        return a + v * ab, np.asarray([1.0 - v, v, 0.0], dtype=np.float64)

    cp = p - c
    d5 = float(np.dot(ab, cp))
    d6 = float(np.dot(ac, cp))
    if d6 >= 0.0 and d5 <= d6:
        return c, np.asarray([0.0, 0.0, 1.0], dtype=np.float64)

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        denom = d2 - d6
        w = 0.0 if abs(denom) <= 1e-24 else d2 / denom
        return a + w * ac, np.asarray([1.0 - w, 0.0, w], dtype=np.float64)

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        bc = c - b
        denom = (d4 - d3) + (d5 - d6)
        w = 0.0 if abs(denom) <= 1e-24 else (d4 - d3) / denom
        return b + w * bc, np.asarray([0.0, 1.0 - w, w], dtype=np.float64)

    denom = va + vb + vc
    if abs(denom) <= 1e-24:
        return None
    inv = 1.0 / denom
    v = vb * inv
    w = vc * inv
    u = 1.0 - v - w
    bary = np.asarray([u, v, w], dtype=np.float64)
    closest = u * a + v * b + w * c
    return closest, bary


@dataclass
class _BVHNode:
    lo: object
    hi: object
    left: int | None = None
    right: int | None = None
    face_ids: object | None = None


def _point_aabb_distance_sq(point, lo, hi) -> float:
    np, _ = _deps()
    point = np.asarray(point, dtype=np.float64)
    lo = np.asarray(lo, dtype=np.float64)
    hi = np.asarray(hi, dtype=np.float64)
    delta = np.maximum(0.0, np.maximum(lo - point, point - hi))
    return float(np.dot(delta, delta))


def _build_triangle_bvh(triangles, *, leaf_size: int = 8):
    np, _ = _deps()
    triangles = np.asarray(triangles, dtype=np.float64)
    if triangles.ndim != 3 or triangles.shape[1:] != (3, 3):
        raise ValueError("triangle BVH requires Mx3x3 triangles")
    if not len(triangles):
        raise ValueError("triangle BVH requires at least one triangle")

    tri_lo = np.min(triangles, axis=1)
    tri_hi = np.max(triangles, axis=1)
    centroids = (tri_lo + tri_hi) * 0.5
    leaf_size = max(1, int(leaf_size))
    nodes: list[_BVHNode] = []

    def build(face_ids) -> int:
        face_ids = np.asarray(face_ids, dtype=np.int64)
        lo = np.min(tri_lo[face_ids], axis=0)
        hi = np.max(tri_hi[face_ids], axis=0)
        node_index = len(nodes)
        nodes.append(_BVHNode(lo=lo, hi=hi))

        if len(face_ids) <= leaf_size:
            nodes[node_index].face_ids = face_ids
            return node_index

        extent = np.ptp(centroids[face_ids], axis=0)
        axis = int(np.argmax(extent))
        if float(extent[axis]) <= 1e-15:
            nodes[node_index].face_ids = face_ids
            return node_index

        order = face_ids[
            np.argsort(centroids[face_ids, axis], kind="mergesort")
        ]
        split = len(order) // 2
        if split <= 0 or split >= len(order):
            nodes[node_index].face_ids = face_ids
            return node_index

        left = build(order[:split])
        right = build(order[split:])
        nodes[node_index].left = left
        nodes[node_index].right = right
        return node_index

    root = build(np.arange(len(triangles), dtype=np.int64))
    return nodes, root


def _nearest_triangle_bvh(
    point,
    vertices,
    faces,
    nodes,
    root: int,
):
    np, _ = _deps()
    point = np.asarray(point, dtype=np.float64)
    best = None
    examined_triangles = 0
    visited_nodes = 0

    root_node = nodes[int(root)]
    heap = [(
        _point_aabb_distance_sq(point, root_node.lo, root_node.hi),
        int(root),
    )]

    while heap:
        lower_bound_sq, node_index = heapq.heappop(heap)
        if (
            best is not None
            and lower_bound_sq >= float(best[0]) ** 2 - 1e-18
        ):
            break

        node = nodes[int(node_index)]
        visited_nodes += 1

        if node.face_ids is not None:
            for face_index in np.asarray(node.face_ids, dtype=np.int64):
                tri_ids = faces[int(face_index)]
                result = _closest_point_barycentric(
                    point,
                    vertices[int(tri_ids[0])],
                    vertices[int(tri_ids[1])],
                    vertices[int(tri_ids[2])],
                )
                examined_triangles += 1
                if result is None:
                    continue
                closest, bary = result
                distance = float(np.linalg.norm(point - closest))
                if not np.isfinite(distance):
                    continue
                if best is None or distance < best[0]:
                    best = (
                        distance,
                        np.asarray(tri_ids, dtype=np.int64),
                        np.asarray(bary, dtype=np.float64),
                    )
            continue

        for child_index in (node.left, node.right):
            if child_index is None:
                continue
            child = nodes[int(child_index)]
            bound_sq = _point_aabb_distance_sq(
                point,
                child.lo,
                child.hi,
            )
            if (
                best is None
                or bound_sq < float(best[0]) ** 2 - 1e-18
            ):
                heapq.heappush(
                    heap,
                    (bound_sq, int(child_index)),
                )

    return best, examined_triangles, visited_nodes


def build_surface_transfer_index(
    source_positions,
    source_faces,
    *,
    bvh_leaf_size: int = 8,
) -> SurfaceTransferIndex:
    np, cKDTree = _deps()
    vertices = np.asarray(source_positions, dtype=np.float64)
    faces = np.asarray(source_faces, dtype=np.int64)

    if vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices):
        raise ValueError("surface-transfer source positions must be non-empty Nx3")
    if faces.ndim != 2 or faces.shape[1] != 3 or not len(faces):
        raise ValueError("surface-transfer source faces must be non-empty Mx3")
    if int(np.min(faces)) < 0 or int(np.max(faces)) >= len(vertices):
        raise ValueError("surface-transfer faces reference missing vertices")
    if not np.isfinite(vertices).all():
        raise ValueError("surface-transfer source geometry contains non-finite values")

    leaf_size = max(1, int(bvh_leaf_size))
    triangles = vertices[faces]
    nodes, root = _build_triangle_bvh(
        triangles,
        leaf_size=leaf_size,
    )
    vertex_tree = cKDTree(vertices)
    return SurfaceTransferIndex(
        vertices=vertices,
        faces=faces,
        nodes=nodes,
        root=int(root),
        vertex_tree=vertex_tree,
        bvh_leaf_size=leaf_size,
    )


def query_surface_transfer(
    index: SurfaceTransferIndex,
    target_positions,
    *,
    candidate_triangles: int = 32,
) -> SurfaceTransferRelation:
    np, _ = _deps()
    vertices = np.asarray(index.vertices, dtype=np.float64)
    faces = np.asarray(index.faces, dtype=np.int64)
    targets = np.asarray(target_positions, dtype=np.float64)

    if targets.ndim != 2 or targets.shape[1] != 3:
        raise ValueError("surface-transfer targets must be Nx3")
    if not np.isfinite(targets).all():
        raise ValueError("surface-transfer targets contain non-finite values")

    _, nearest_vertices = index.vertex_tree.query(
        targets,
        k=1,
        workers=-1,
    )
    nearest_vertices = np.asarray(nearest_vertices, dtype=np.int64)

    triangle_vertex_ids = np.zeros((len(targets), 3), dtype=np.int64)
    barycentric = np.zeros((len(targets), 3), dtype=np.float64)
    distances = np.zeros(len(targets), dtype=np.float64)
    fallback_vertices = 0
    max_examined_triangles = 0
    max_visited_bvh_nodes = 0

    for row, point in enumerate(targets):
        best, examined, visited = _nearest_triangle_bvh(
            point,
            vertices,
            faces,
            index.nodes,
            index.root,
        )
        max_examined_triangles = max(
            max_examined_triangles,
            int(examined),
        )
        max_visited_bvh_nodes = max(
            max_visited_bvh_nodes,
            int(visited),
        )

        if best is None:
            vertex_id = int(nearest_vertices[row])
            triangle_vertex_ids[row] = [vertex_id, vertex_id, vertex_id]
            barycentric[row] = [1.0, 0.0, 0.0]
            distances[row] = float(
                np.linalg.norm(point - vertices[vertex_id])
            )
            fallback_vertices += 1
            continue

        distance, tri_ids, bary = best
        bary = np.maximum(bary, 0.0)
        total = float(np.sum(bary))
        if total <= 1e-12:
            raise RuntimeError(
                f"surface-transfer target {row} received invalid barycentrics"
            )
        bary /= total
        triangle_vertex_ids[row] = tri_ids
        barycentric[row] = bary
        distances[row] = distance

    return SurfaceTransferRelation(
        triangle_vertex_ids=triangle_vertex_ids,
        barycentric=barycentric,
        surface_distance=distances,
        nearest_vertex_ids=nearest_vertices,
        candidate_triangles=max(1, min(int(candidate_triangles), len(faces))),
        fallback_vertices=int(fallback_vertices),
        max_examined_triangles=int(max_examined_triangles),
        max_visited_bvh_nodes=int(max_visited_bvh_nodes),
    )


def surface_candidates_within_distance(
    index: SurfaceTransferIndex,
    point,
    max_distance: float,
):
    np, _ = _deps()
    point = np.asarray(point, dtype=np.float64)
    max_distance = float(max_distance)
    if point.shape != (3,) or not np.isfinite(point).all():
        raise ValueError("surface candidate point must be finite VEC3")
    if not np.isfinite(max_distance) or max_distance < 0.0:
        raise ValueError("surface candidate max_distance must be finite and non-negative")

    limit_sq = max_distance * max_distance
    heap = [(
        _point_aabb_distance_sq(
            point,
            index.nodes[int(index.root)].lo,
            index.nodes[int(index.root)].hi,
        ),
        int(index.root),
    )]
    output = []

    while heap:
        bound_sq, node_index = heapq.heappop(heap)
        if bound_sq > limit_sq + 1e-18:
            break
        node = index.nodes[int(node_index)]

        if node.face_ids is not None:
            for face_index in np.asarray(node.face_ids, dtype=np.int64):
                tri_ids = index.faces[int(face_index)]
                result = _closest_point_barycentric(
                    point,
                    index.vertices[int(tri_ids[0])],
                    index.vertices[int(tri_ids[1])],
                    index.vertices[int(tri_ids[2])],
                )
                if result is None:
                    continue
                closest, bary = result
                distance = float(np.linalg.norm(point - closest))
                if (
                    np.isfinite(distance)
                    and distance <= max_distance + 1e-12
                ):
                    output.append(SurfaceCandidate(
                        face_index=int(face_index),
                        triangle_vertex_ids=np.asarray(
                            tri_ids,
                            dtype=np.int64,
                        ),
                        barycentric=np.asarray(
                            bary,
                            dtype=np.float64,
                        ),
                        distance=distance,
                    ))
            continue

        for child_index in (node.left, node.right):
            if child_index is None:
                continue
            child = index.nodes[int(child_index)]
            child_bound = _point_aabb_distance_sq(
                point,
                child.lo,
                child.hi,
            )
            if child_bound <= limit_sq + 1e-18:
                heapq.heappush(
                    heap,
                    (child_bound, int(child_index)),
                )

    output.sort(key=lambda item: (item.distance, item.face_index))
    return output


def build_surface_transfer_relation(
    source_positions,
    source_faces,
    target_positions,
    *,
    candidate_triangles: int = 32,
    bvh_leaf_size: int = 8,
) -> SurfaceTransferRelation:
    index = build_surface_transfer_index(
        source_positions,
        source_faces,
        bvh_leaf_size=bvh_leaf_size,
    )
    return query_surface_transfer(
        index,
        target_positions,
        candidate_triangles=candidate_triangles,
    )


def blend_joint_weights_from_relation(
    source_joints,
    source_weights,
    relation: SurfaceTransferRelation,
):
    np, _ = _deps()
    joints = np.asarray(source_joints, dtype=np.int64)
    weights = np.asarray(source_weights, dtype=np.float64)
    triangles = np.asarray(
        relation.triangle_vertex_ids,
        dtype=np.int64,
    )
    bary = np.asarray(relation.barycentric, dtype=np.float64)

    out_joints = np.zeros((len(triangles), 4), dtype=np.int64)
    out_weights = np.zeros((len(triangles), 4), dtype=np.float64)

    for row, (tri_ids, tri_weights) in enumerate(zip(triangles, bary)):
        accumulated: dict[int, float] = {}
        for vertex_id, spatial_weight in zip(tri_ids, tri_weights):
            for joint, skin_weight in zip(
                joints[int(vertex_id)],
                weights[int(vertex_id)],
            ):
                contribution = float(spatial_weight) * float(skin_weight)
                if contribution <= 1e-12:
                    continue
                accumulated[int(joint)] = (
                    accumulated.get(int(joint), 0.0) + contribution
                )

        strongest = sorted(
            accumulated.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:4]
        total = sum(weight for _, weight in strongest)
        if total <= 1e-12:
            raise RuntimeError(
                f"surface-transfer target {row} received no skin influence"
            )
        for slot, (joint, weight) in enumerate(strongest):
            out_joints[row, slot] = int(joint)
            out_weights[row, slot] = float(weight / total)

    return out_joints, out_weights


def interpolate_vertex_values(values, relation: SurfaceTransferRelation):
    np, _ = _deps()
    source = np.asarray(values, dtype=np.float64)
    triangles = np.asarray(
        relation.triangle_vertex_ids,
        dtype=np.int64,
    )
    bary = np.asarray(relation.barycentric, dtype=np.float64)
    if source.ndim < 2 or len(source) <= int(np.max(triangles)):
        raise ValueError(
            "surface-transfer source values do not cover relation vertices"
        )
    gathered = source[triangles]
    shape = (len(bary), 3) + (1,) * (gathered.ndim - 2)
    return np.sum(gathered * bary.reshape(shape), axis=1)
