#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, maximum_filter

from gltf_audit import audit_glb
from native_geometry_guard import assert_native_candidate
from visual_judge import (
    _boundary,
    _rotation_matrix,
    build_render_bank,
    extract_source_mask_evidence,
    project_mesh_vertices,
    refine_projection_match,
    render_silhouette,
    score_masks,
)


def _load_editable_scene(path: Path):
    import trimesh

    assert_native_candidate(path, label="native_silhouette_conform")
    gltf = audit_glb(path)
    if not gltf.valid_glb or gltf.errors:
        raise RuntimeError(
            "native silhouette conform requires a structurally valid GLB: "
            + "; ".join(gltf.errors[:4])
        )
    if gltf.skin_count or gltf.animation_count or gltf.morph_target_count:
        raise RuntimeError(
            "native silhouette conform is pre-rig/pre-animation only "
            f"(skins={gltf.skin_count}, animations={gltf.animation_count}, "
            f"morph_targets={gltf.morph_target_count})"
        )

    scene = trimesh.load(path, force="scene", process=False)
    nodes = list(scene.graph.nodes_geometry)

    if not nodes:
        raise RuntimeError("native silhouette conform requires a scene with mesh nodes")

    geometry_use: dict[str, int] = {}
    records = []
    world_chunks = []
    face_chunks = []
    vertex_offset = 0

    for node in nodes:
        transform, geometry_name = scene.graph.get(node)
        geometry = scene.geometry[geometry_name]
        if not (
            hasattr(geometry, "vertices")
            and hasattr(geometry, "faces")
            and len(geometry.vertices)
            and len(geometry.faces)
        ):
            continue

        geometry_use[geometry_name] = geometry_use.get(geometry_name, 0) + 1
        if geometry_use[geometry_name] > 1:
            raise RuntimeError(
                "native silhouette conform does not mutate instanced geometry yet: "
                f"{geometry_name}"
            )

        local = np.asarray(geometry.vertices, dtype=np.float64)
        world = trimesh.transform_points(local, np.asarray(transform, dtype=np.float64))
        faces = np.asarray(geometry.faces, dtype=np.int64)

        start = vertex_offset
        end = start + len(world)
        records.append(
            {
                "node": str(node),
                "geometry_name": str(geometry_name),
                "transform": np.asarray(transform, dtype=np.float64),
                "start": start,
                "end": end,
            }
        )
        world_chunks.append(world)
        face_chunks.append(faces + vertex_offset)
        vertex_offset = end

    if not world_chunks:
        raise RuntimeError(f"no editable triangle geometry in {path}")

    vertices_world = np.concatenate(world_chunks, axis=0)
    faces = np.concatenate(face_chunks, axis=0)
    return scene, records, vertices_world, faces


def _normalized(vertices_world: np.ndarray):
    lo = vertices_world.min(axis=0)
    hi = vertices_world.max(axis=0)
    center = (lo + hi) * 0.5
    scale = float(np.max(hi - lo))
    if not math.isfinite(scale) or scale <= 1e-9:
        raise RuntimeError("collapsed native mesh bounds")
    return (vertices_world - center) / scale, center, scale


def _bounded_render_faces(
    vertices: np.ndarray,
    faces: np.ndarray,
    max_faces: int,
):
    """Build a deterministic surface proxy while preserving exported topology.

    Random/uniform face subsampling creates a perforated silhouette on dense
    Hero Masters. Instead, cluster nearby vertices, remap every original face to
    representative *original* vertex indices, then drop only collapsed/duplicate
    proxy triangles. The proxy follows later vertex deformation automatically
    because it still indexes the real editable vertex array.
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    budget = max(32, int(max_faces))
    total = int(len(faces))
    if total <= budget:
        return faces, {
            "input_faces": total,
            "render_faces": total,
            "budget": budget,
            "subsampled": False,
            "policy": "full-face-render",
            "proxy_grid": None,
            "proxy_vertices_used": int(len(np.unique(faces))),
        }

    lo = vertices.min(axis=0)
    hi = vertices.max(axis=0)
    span = np.maximum(hi - lo, 1e-9)

    def build_proxy(grid: int):
        scaled = (vertices - lo) / span
        cells = np.clip(
            np.floor(scaled * float(grid)).astype(np.int64),
            0,
            int(grid) - 1,
        )
        keys = (
            cells[:, 0]
            + int(grid) * (
                cells[:, 1]
                + int(grid) * cells[:, 2]
            )
        )
        _unique, first, inverse = np.unique(
            keys,
            return_index=True,
            return_inverse=True,
        )
        representative = first[inverse]
        remapped = representative[faces]
        nondegenerate = (
            (remapped[:, 0] != remapped[:, 1])
            & (remapped[:, 1] != remapped[:, 2])
            & (remapped[:, 0] != remapped[:, 2])
        )
        remapped = remapped[nondegenerate]
        if not len(remapped):
            return remapped

        canonical = np.sort(remapped, axis=1)
        _rows, keep = np.unique(
            canonical,
            axis=0,
            return_index=True,
        )
        return remapped[np.sort(keep)]

    start_grid = max(6, int(round(math.sqrt(float(budget) / 4.0))))
    grids = []
    value = int(round(start_grid * 1.6))
    while value >= 4:
        if value not in grids:
            grids.append(value)
        next_value = int(math.floor(value * 0.80))
        if next_value >= value:
            next_value = value - 1
        value = next_value
    for tail in (3, 2):
        if tail not in grids:
            grids.append(tail)

    best = None
    best_grid = None
    attempts = []
    for grid in grids:
        proxy = build_proxy(int(grid))
        count = int(len(proxy))
        attempts.append({"grid": int(grid), "faces": count})
        if count == 0:
            continue
        if count <= budget:
            best = proxy
            best_grid = int(grid)
            break

    if best is None:
        raise RuntimeError(
            "could not build non-empty bounded render proxy "
            f"(input_faces={total}, budget={budget}, attempts={attempts})"
        )

    used_vertices = int(len(np.unique(best)))
    return best, {
        "input_faces": total,
        "render_faces": int(len(best)),
        "budget": budget,
        "subsampled": True,
        "policy": "deterministic-vertex-clustered-surface-proxy",
        "proxy_grid": best_grid,
        "proxy_vertices_used": used_vertices,
        "attempts": attempts,
    }


def _best_camera(vertices_norm, faces, source_mask, *, size: int, azimuth_step: int):
    bank = build_render_bank(
        vertices_norm,
        faces,
        size=int(size),
        azimuth_step=int(azimuth_step),
    )
    best = None
    for up_axis, elevation, azimuth in bank:
        score, iou, edge = score_masks(
            source_mask,
            bank[(up_axis, elevation, azimuth)],
        )
        item = (score, iou, edge, up_axis, elevation, azimuth)
        if best is None or item[0] > best[0]:
            best = item

    refined = refine_projection_match(
        source_mask,
        vertices_norm,
        faces,
        best,
        size=int(size),
        azimuth_step=int(azimuth_step),
        cache={},
    )
    if refined is None:
        raise RuntimeError("could not solve a source-to-native camera")
    return refined


def _project_state(
    vertices_norm,
    faces,
    source_mask,
    camera,
    *,
    size: int,
):
    (
        _score,
        _iou,
        _edge,
        up_axis,
        elevation,
        azimuth,
        projection,
        camera_distance,
    ) = camera
    xy, depth = project_mesh_vertices(
        vertices_norm,
        azimuth,
        elevation,
        up_axis,
        size=int(size),
        projection=projection,
        camera_distance=camera_distance,
    )
    candidate = render_silhouette(
        vertices_norm,
        faces,
        azimuth,
        elevation,
        up_axis,
        size=int(size),
        projection=projection,
        camera_distance=camera_distance,
    )
    score, iou, edge = score_masks(source_mask, candidate)
    return {
        "xy": xy,
        "depth": depth,
        "mask": candidate,
        "score": float(score),
        "iou": float(iou),
        "boundary_f1": float(edge),
    }


def _screen_to_camera_delta(
    vertices_norm,
    xy,
    delta_px,
    camera,
    *,
    size: int,
):
    (
        _score,
        _iou,
        _edge,
        up_axis,
        elevation,
        azimuth,
        projection,
        camera_distance,
    ) = camera

    rot = _rotation_matrix(azimuth, elevation, up_axis).astype(np.float64)
    camera_vertices = np.asarray(vertices_norm, dtype=np.float64) @ rot.T

    if projection == "perspective":
        distance = float(camera_distance if camera_distance is not None else 2.4)
        denom = np.maximum(distance - camera_vertices[:, 2], 0.05)
        raw_xy = camera_vertices[:, :2] / denom[:, None]
    else:
        denom = np.ones((len(camera_vertices),), dtype=np.float64)
        raw_xy = camera_vertices[:, :2]

    raw_span = np.maximum(raw_xy.max(axis=0) - raw_xy.min(axis=0), 1e-9)
    uniform = float(max(raw_span[0], raw_span[1]))
    raw_delta = (
        np.asarray(delta_px, dtype=np.float64)
        / max(float(size) * 0.82, 1e-9)
        * uniform
    )
    if projection == "perspective":
        camera_delta_xy = raw_delta * denom[:, None]
    else:
        camera_delta_xy = raw_delta

    camera_delta = np.zeros_like(camera_vertices, dtype=np.float64)
    camera_delta[:, :2] = camera_delta_xy

    # v_camera = v_world @ rot.T, therefore delta_world = delta_camera @ rot.
    return camera_delta @ rot


def _front_surface_vertex_mask(
    depth,
    px,
    py,
    *,
    size: int,
    depth_tolerance_ratio: float,
    neighborhood_px: int,
):
    """Keep only vertices on the camera-visible shell.

    A source silhouette is front-view evidence. Moving rear/occluded vertices that
    merely project to the same contour can damage valid 360 geometry, so conform
    edits are restricted to the locally front-most projected vertex layer.
    """
    depth = np.asarray(depth, dtype=np.float64)
    px = np.asarray(px, dtype=np.int64)
    py = np.asarray(py, dtype=np.int64)
    if len(depth) != len(px) or len(depth) != len(py):
        raise ValueError("depth/pixel coordinate length mismatch")
    if not len(depth):
        return np.zeros((0,), dtype=bool), {
            "visible_vertices": 0,
            "occluded_vertices": 0,
            "depth_tolerance": 0.0,
            "neighborhood_px": int(neighborhood_px),
        }

    front_depth = np.full((int(size), int(size)), -np.inf, dtype=np.float64)
    np.maximum.at(front_depth, (py, px), depth)

    neighborhood = max(0, int(neighborhood_px))
    if neighborhood:
        front_depth = maximum_filter(
            front_depth,
            size=neighborhood * 2 + 1,
            mode="constant",
            cval=-np.inf,
        )

    robust_lo = float(np.percentile(depth, 2.0))
    robust_hi = float(np.percentile(depth, 98.0))
    depth_span = max(robust_hi - robust_lo, 1e-9)
    tolerance = max(
        1e-6,
        depth_span * max(0.0, float(depth_tolerance_ratio)),
    )
    local_front = front_depth[py, px]
    visible = depth >= (local_front - tolerance)
    return visible, {
        "visible_vertices": int(np.count_nonzero(visible)),
        "occluded_vertices": int(np.count_nonzero(~visible)),
        "depth_tolerance": float(tolerance),
        "depth_span": float(depth_span),
        "depth_tolerance_ratio": float(depth_tolerance_ratio),
        "neighborhood_px": int(neighborhood),
    }


def _smooth_topology_displacements(
    delta_px: np.ndarray,
    faces: np.ndarray,
    active: np.ndarray,
    *,
    iterations: int,
    blend: float,
):
    """Blend already-authorized contour motion across active mesh neighbors.

    The smoother never activates a new vertex. Only vertices already approved by
    both the source-boundary test and front-surface visibility gate can move.
    """
    delta = np.asarray(delta_px, dtype=np.float64).copy()
    faces = np.asarray(faces, dtype=np.int64)
    active = np.asarray(active, dtype=bool)
    passes = max(0, int(iterations))
    mix = min(1.0, max(0.0, float(blend)))
    active_count = int(np.count_nonzero(active))

    if passes == 0 or mix <= 0.0 or active_count < 2 or len(faces) == 0:
        return delta, {
            "iterations": 0,
            "blend": mix,
            "active_vertices": active_count,
            "active_vertices_with_neighbors": 0,
            "active_edges": 0,
        }

    touched = np.any(active[faces], axis=1)
    local_faces = faces[touched]
    if not len(local_faces):
        return delta, {
            "iterations": 0,
            "blend": mix,
            "active_vertices": active_count,
            "active_vertices_with_neighbors": 0,
            "active_edges": 0,
        }

    edges = np.concatenate(
        [
            local_faces[:, [0, 1]],
            local_faces[:, [1, 2]],
            local_faces[:, [2, 0]],
        ],
        axis=0,
    )
    edge_mask = active[edges[:, 0]] & active[edges[:, 1]]
    edges = edges[edge_mask]
    if not len(edges):
        return delta, {
            "iterations": 0,
            "blend": mix,
            "active_vertices": active_count,
            "active_vertices_with_neighbors": 0,
            "active_edges": 0,
            "local_faces_considered": int(len(local_faces)),
        }

    src = np.concatenate([edges[:, 0], edges[:, 1]])
    dst = np.concatenate([edges[:, 1], edges[:, 0]])
    last_counts = np.zeros((len(delta),), dtype=np.int32)
    executed = 0

    for _ in range(passes):
        sums = np.zeros_like(delta)
        counts = np.zeros((len(delta),), dtype=np.int32)
        np.add.at(sums, src, delta[dst])
        np.add.at(counts, src, 1)
        has_neighbors = active & (counts > 0)
        if not np.any(has_neighbors):
            break
        averaged = sums[has_neighbors] / counts[has_neighbors, None]
        delta[has_neighbors] = (
            delta[has_neighbors] * (1.0 - mix)
            + averaged * mix
        )
        last_counts = counts
        executed += 1

    delta[~active] = 0.0
    return delta, {
        "iterations": int(executed),
        "blend": mix,
        "active_vertices": active_count,
        "active_vertices_with_neighbors": int(
            np.count_nonzero(active & (last_counts > 0))
        ),
        "active_edges": int(len(edges)),
        "local_faces_considered": int(len(local_faces)),
        "can_activate_new_vertices": False,
    }


def _conform_iteration(
    vertices_norm,
    render_faces,
    topology_faces,
    source_mask,
    camera,
    *,
    size: int,
    boundary_band_px: float,
    max_target_px: float,
    per_vertex_cap_px: float,
    visibility_depth_tolerance_ratio: float,
    visibility_neighborhood_px: int,
    topology_smoothing_iterations: int,
    topology_smoothing_blend: float,
):
    state = _project_state(
        vertices_norm,
        render_faces,
        source_mask,
        camera,
        size=size,
    )
    candidate = state["mask"]
    source_boundary = _boundary(source_mask)
    candidate_boundary = _boundary(candidate)

    if not np.any(source_boundary) or not np.any(candidate_boundary):
        return vertices_norm.copy(), {
            "accepted": False,
            "reason": "empty source/candidate boundary",
            "before_score": state["score"],
            "after_score": state["score"],
        }

    distance_to_candidate_boundary = distance_transform_edt(~candidate_boundary)
    distance_to_source_boundary, source_indices = distance_transform_edt(
        ~source_boundary,
        return_indices=True,
    )

    xy = np.asarray(state["xy"], dtype=np.float64)
    px = np.clip(np.rint(xy[:, 0]).astype(np.int64), 0, int(size) - 1)
    py = np.clip(
        np.rint((int(size) - 1) - xy[:, 1]).astype(np.int64),
        0,
        int(size) - 1,
    )

    boundary_distance = distance_to_candidate_boundary[py, px]
    target_distance = distance_to_source_boundary[py, px]
    front_surface, visibility = _front_surface_vertex_mask(
        state["depth"],
        px,
        py,
        size=int(size),
        depth_tolerance_ratio=float(visibility_depth_tolerance_ratio),
        neighborhood_px=int(visibility_neighborhood_px),
    )
    boundary_target = (
        (boundary_distance <= float(boundary_band_px))
        & (target_distance > 0.35)
        & (target_distance <= float(max_target_px))
    )
    active = boundary_target & front_surface
    occluded_boundary_vertices = int(
        np.count_nonzero(boundary_target & ~front_surface)
    )

    if not np.any(active):
        return vertices_norm.copy(), {
            "accepted": False,
            "reason": (
                "no camera-visible boundary vertices inside safe source target band"
            ),
            "before_score": state["score"],
            "after_score": state["score"],
            "active_vertices": 0,
            "occluded_boundary_vertices_blocked": occluded_boundary_vertices,
            "visibility": visibility,
        }

    target_y = source_indices[0, py, px].astype(np.float64)
    target_x = source_indices[1, py, px].astype(np.float64)
    delta_px = np.stack(
        [
            target_x - px.astype(np.float64),
            -(target_y - py.astype(np.float64)),
        ],
        axis=1,
    )
    magnitude = np.linalg.norm(delta_px, axis=1)
    over = magnitude > float(per_vertex_cap_px)
    if np.any(over):
        delta_px[over] *= (
            float(per_vertex_cap_px) / np.maximum(magnitude[over], 1e-9)
        )[:, None]

    weight = np.clip(
        1.0 - boundary_distance / max(float(boundary_band_px), 1e-6),
        0.0,
        1.0,
    )
    delta_px *= weight[:, None]
    delta_px[~active] = 0.0
    delta_px, smoothing = _smooth_topology_displacements(
        delta_px,
        topology_faces,
        active,
        iterations=int(topology_smoothing_iterations),
        blend=float(topology_smoothing_blend),
    )

    world_delta_norm = _screen_to_camera_delta(
        vertices_norm,
        xy,
        delta_px,
        camera,
        size=size,
    )

    base_vertices = np.asarray(vertices_norm, dtype=np.float64)
    best_vertices = base_vertices.copy()
    best_state = state
    accepted_scale = 0.0
    trials = []

    # Full contour steps can overshoot on coarse or irregular topology. Search a
    # few conservative fractions and keep only a measured improvement.
    for step_scale in (1.0, 0.65, 0.40, 0.20):
        trial_vertices = base_vertices + world_delta_norm * float(step_scale)
        trial_state = _project_state(
            trial_vertices,
            render_faces,
            source_mask,
            camera,
            size=size,
        )
        trials.append(
            {
                "scale": float(step_scale),
                "score": float(trial_state["score"]),
                "iou": float(trial_state["iou"]),
                "boundary_f1": float(trial_state["boundary_f1"]),
            }
        )
        if trial_state["score"] > best_state["score"] + 1e-6:
            best_vertices = trial_vertices
            best_state = trial_state
            accepted_scale = float(step_scale)

    accepted = bool(accepted_scale > 0.0)
    candidate_vertices = best_vertices if accepted else base_vertices.copy()
    after = best_state if accepted else state

    return candidate_vertices, {
        "accepted": accepted,
        "accepted_step_scale": float(accepted_scale),
        "line_search_trials": trials,
        "before_score": state["score"],
        "after_score": after["score"] if accepted else state["score"],
        "before_iou": state["iou"],
        "after_iou": after["iou"] if accepted else state["iou"],
        "before_boundary_f1": state["boundary_f1"],
        "after_boundary_f1": (
            after["boundary_f1"] if accepted else state["boundary_f1"]
        ),
        "active_vertices": int(np.count_nonzero(active)),
        "occluded_boundary_vertices_blocked": occluded_boundary_vertices,
        "visibility": visibility,
        "topology_smoothing": smoothing,
        "max_requested_target_px": float(
            target_distance[active].max(initial=0.0)
        ),
        "max_applied_screen_delta_px": float(
            np.linalg.norm(delta_px[active], axis=1).max(initial=0.0)
        ),
        "max_normalized_world_delta": float(
            np.linalg.norm(world_delta_norm[active], axis=1).max(initial=0.0)
        ),
    }


def _mesh_structural_signature(path: Path) -> dict:
    import trimesh

    scene = trimesh.load(path, force="scene", process=False)
    nodes = list(scene.graph.nodes_geometry)
    total_vertices = 0
    total_faces = 0
    uv_nodes = 0
    material_nodes = 0
    uv_fingerprints = []
    texture_fingerprints = []

    for node in nodes:
        _transform, geometry_name = scene.graph.get(node)
        geometry = scene.geometry[geometry_name]
        if not hasattr(geometry, "vertices") or not hasattr(geometry, "faces"):
            continue
        vertices = np.asarray(geometry.vertices)
        faces = np.asarray(geometry.faces)
        total_vertices += int(len(vertices))
        total_faces += int(len(faces))

        visual = getattr(geometry, "visual", None)
        uv = getattr(visual, "uv", None) if visual is not None else None
        if uv is not None and len(uv) == len(vertices) and len(vertices):
            uv_nodes += 1
            uv_arr = np.asarray(uv, dtype=np.float64)
            uv_quantized = np.round(uv_arr, decimals=7).astype("<f8", copy=False)
            uv_fingerprints.append(
                hashlib.sha256(uv_quantized.tobytes()).hexdigest()
            )
        material = getattr(visual, "material", None) if visual is not None else None
        if material is not None:
            material_nodes += 1
            texture = getattr(material, "baseColorTexture", None)
            if texture is not None:
                try:
                    rgba = np.asarray(texture.convert("RGBA"), dtype=np.uint8)
                    texture_fingerprints.append(
                        hashlib.sha256(rgba.tobytes()).hexdigest()
                    )
                except Exception:
                    texture_fingerprints.append("unreadable-texture")

    return {
        "mesh_nodes": int(len(nodes)),
        "vertices": int(total_vertices),
        "faces": int(total_faces),
        "uv_mesh_nodes": int(uv_nodes),
        "material_mesh_nodes": int(material_nodes),
        "uv_fingerprints": sorted(uv_fingerprints),
        "base_color_texture_fingerprints": sorted(texture_fingerprints),
    }


def _assert_roundtrip_preserved(input_glb: Path, output_glb: Path) -> dict:
    before_mesh = _mesh_structural_signature(input_glb)
    after_mesh = _mesh_structural_signature(output_glb)
    before_gltf = audit_glb(input_glb)
    after_gltf = audit_glb(output_glb)

    regressions = []
    for key in ("mesh_nodes", "vertices", "faces"):
        if int(after_mesh[key]) != int(before_mesh[key]):
            regressions.append(
                f"{key}:{before_mesh[key]}->{after_mesh[key]}"
            )
    for key in ("uv_mesh_nodes", "material_mesh_nodes"):
        if int(after_mesh[key]) < int(before_mesh[key]):
            regressions.append(
                f"{key}:{before_mesh[key]}->{after_mesh[key]}"
            )

    if (
        after_mesh["uv_fingerprints"]
        != before_mesh["uv_fingerprints"]
    ):
        regressions.append("uv_coordinates_changed")
    if (
        after_mesh["base_color_texture_fingerprints"]
        != before_mesh["base_color_texture_fingerprints"]
    ):
        regressions.append("base_color_texture_pixels_changed")

    for key in ("mesh_count", "material_count", "texture_count"):
        before_value = int(getattr(before_gltf, key))
        after_value = int(getattr(after_gltf, key))
        if after_value < before_value:
            regressions.append(
                f"{key}:{before_value}->{after_value}"
            )

    missing_channels = sorted(
        set(before_gltf.material_channels) - set(after_gltf.material_channels)
    )
    if missing_channels:
        regressions.append(
            "material_channels_missing:" + ",".join(missing_channels)
        )
    if not after_gltf.valid_glb or after_gltf.errors:
        regressions.append(
            "output_gltf_invalid:"
            + ";".join(after_gltf.errors[:4])
        )

    payload = {
        "policy": "native-glb-roundtrip-preservation-v1",
        "before_mesh": before_mesh,
        "after_mesh": after_mesh,
        "before_gltf": {
            "mesh_count": int(before_gltf.mesh_count),
            "material_count": int(before_gltf.material_count),
            "texture_count": int(before_gltf.texture_count),
            "material_channels": list(before_gltf.material_channels),
        },
        "after_gltf": {
            "mesh_count": int(after_gltf.mesh_count),
            "material_count": int(after_gltf.material_count),
            "texture_count": int(after_gltf.texture_count),
            "material_channels": list(after_gltf.material_channels),
        },
        "regressions": regressions,
        "preserved": not regressions,
    }
    if regressions:
        raise RuntimeError(
            "native silhouette conform GLB round-trip regression: "
            + " | ".join(regressions)
        )
    return payload


def _write_world_vertices(scene, records, vertices_world: np.ndarray, output: Path):
    import trimesh

    for record in records:
        start = int(record["start"])
        end = int(record["end"])
        transform = np.asarray(record["transform"], dtype=np.float64)
        inv = np.linalg.inv(transform)
        local = trimesh.transform_points(vertices_world[start:end], inv)
        geometry = scene.geometry[record["geometry_name"]]
        geometry.vertices = np.asarray(local, dtype=np.float64)

    output.parent.mkdir(parents=True, exist_ok=True)
    blob = scene.export(file_type="glb")
    output.write_bytes(blob)
    if output.read_bytes()[:4] != b"glTF":
        raise RuntimeError("native silhouette conform output is not a valid GLB")


def conform_native_silhouette(
    input_glb: Path,
    source_image: Path,
    output_glb: Path,
    *,
    report: Path | None = None,
    size: int = 256,
    azimuth_step: int = 30,
    iterations: int = 3,
    boundary_band_px: float = 5.0,
    max_target_px: float = 14.0,
    per_vertex_cap_px: float = 3.0,
    visibility_depth_tolerance_ratio: float = 0.025,
    visibility_neighborhood_px: int = 1,
    render_face_budget: int = 12000,
    topology_smoothing_iterations: int = 2,
    topology_smoothing_blend: float = 0.35,
):
    scene, records, vertices_world, faces = _load_editable_scene(input_glb)
    vertices_norm, center, scale = _normalized(vertices_world)
    render_faces, render_budget = _bounded_render_faces(
        vertices_norm,
        faces,
        max_faces=int(render_face_budget),
    )

    source_mask, source_confidence, source_mask_method = (
        extract_source_mask_evidence(source_image, size=int(size))
    )
    if float(source_confidence) < 0.20:
        raise RuntimeError(
            f"source silhouette confidence too low: {source_confidence}"
        )

    camera = _best_camera(
        vertices_norm,
        render_faces,
        source_mask,
        size=int(size),
        azimuth_step=int(azimuth_step),
    )
    initial = _project_state(
        vertices_norm,
        render_faces,
        source_mask,
        camera,
        size=int(size),
    )

    original_norm = np.asarray(vertices_norm, dtype=np.float64).copy()
    passes = []
    current = original_norm.copy()

    for index in range(max(1, int(iterations))):
        proposed, item = _conform_iteration(
            current,
            render_faces,
            faces,
            source_mask,
            camera,
            size=int(size),
            boundary_band_px=float(boundary_band_px),
            max_target_px=float(max_target_px),
            per_vertex_cap_px=float(per_vertex_cap_px),
            visibility_depth_tolerance_ratio=float(
                visibility_depth_tolerance_ratio
            ),
            visibility_neighborhood_px=int(visibility_neighborhood_px),
            topology_smoothing_iterations=int(
                topology_smoothing_iterations
            ),
            topology_smoothing_blend=float(topology_smoothing_blend),
        )
        item["iteration"] = index + 1
        passes.append(item)
        if not item["accepted"]:
            break
        current = proposed

    final = _project_state(
        current,
        render_faces,
        source_mask,
        camera,
        size=int(size),
    )

    displacement_norm = np.linalg.norm(current - original_norm, axis=1)
    max_displacement_ratio = float(displacement_norm.max(initial=0.0))
    if max_displacement_ratio > 0.075:
        raise RuntimeError(
            "native silhouette conform exceeded global safety cap: "
            f"{max_displacement_ratio}"
        )
    if final["score"] + 1e-6 < initial["score"]:
        raise RuntimeError(
            "native silhouette conform regressed source silhouette score"
        )

    geometry_changed = bool(max_displacement_ratio > 1e-10)
    accepted_passes = int(sum(1 for item in passes if item.get("accepted")))

    if geometry_changed:
        vertices_world_out = current * scale + center
        _write_world_vertices(scene, records, vertices_world_out, output_glb)
    else:
        # Do not round-trip a perfect/no-op native candidate through trimesh.
        # Preserve the exact original GLB bytes when no vertex change won.
        output_glb.parent.mkdir(parents=True, exist_ok=True)
        output_glb.write_bytes(input_glb.read_bytes())

    assert_native_candidate(output_glb, label="native_silhouette_conform_output")
    roundtrip_preservation = _assert_roundtrip_preserved(
        input_glb,
        output_glb,
    )

    payload = {
        "schema": 1,
        "policy": "hayuya-native-source-driven-silhouette-conform-v1",
        "input": str(input_glb),
        "source_image": str(source_image),
        "output": str(output_glb),
        "source_mask": {
            "confidence": float(source_confidence),
            "method": str(source_mask_method),
        },
        "camera": {
            "up_axis": camera[3],
            "elevation": float(camera[4]),
            "azimuth": float(camera[5]),
            "projection": str(camera[6]),
            "camera_distance": (
                None if camera[7] is None else float(camera[7])
            ),
        },
        "initial": {
            "score": float(initial["score"]),
            "iou": float(initial["iou"]),
            "boundary_f1": float(initial["boundary_f1"]),
        },
        "final": {
            "score": float(final["score"]),
            "iou": float(final["iou"]),
            "boundary_f1": float(final["boundary_f1"]),
        },
        "passes": passes,
        "accepted_passes": accepted_passes,
        "geometry_changed": geometry_changed,
        "no_op_preserves_exact_input_bytes": bool(not geometry_changed),
        "render_budget": render_budget,
        "roundtrip_preservation": roundtrip_preservation,
        "topology_smoothing": {
            "mode": "active-visible-one-ring-only",
            "iterations": int(topology_smoothing_iterations),
            "blend": float(topology_smoothing_blend),
            "can_activate_new_vertices": False,
        },
        "visibility_policy": {
            "mode": "camera-front-surface-only",
            "depth_tolerance_ratio": float(
                visibility_depth_tolerance_ratio
            ),
            "neighborhood_px": int(visibility_neighborhood_px),
            "rear_occluded_vertices_are_editable": False,
        },
        "max_displacement_body_span_ratio": max_displacement_ratio,
        "native_geometry_preserved": True,
        "projection_proxy_created": False,
        "asset_specific_coordinates": False,
        "notes": (
            "Conforms the current native mesh to the current source silhouette. "
            "No Monja profile, fixed body rectangle, source_visible_front shell, "
            "or occluded_low_frequency support node is used."
        ),
    }

    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        "HAYUYA_NATIVE_SILHOUETTE_CONFORM_PASS",
        json.dumps(payload, separators=(",", ":")),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Conservatively conform a native HAYUYA 3D candidate to the current "
            "source image silhouette without creating a projection proxy."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--azimuth-step", type=int, default=30)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--boundary-band-px", type=float, default=5.0)
    parser.add_argument("--max-target-px", type=float, default=14.0)
    parser.add_argument("--per-vertex-cap-px", type=float, default=3.0)
    parser.add_argument(
        "--visibility-depth-tolerance-ratio",
        type=float,
        default=0.025,
    )
    parser.add_argument(
        "--visibility-neighborhood-px",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--render-face-budget",
        type=int,
        default=12000,
    )
    parser.add_argument(
        "--topology-smoothing-iterations",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--topology-smoothing-blend",
        type=float,
        default=0.35,
    )
    args = parser.parse_args()

    conform_native_silhouette(
        args.input,
        args.source,
        args.output,
        report=args.report,
        size=args.size,
        azimuth_step=args.azimuth_step,
        iterations=args.iterations,
        boundary_band_px=args.boundary_band_px,
        max_target_px=args.max_target_px,
        per_vertex_cap_px=args.per_vertex_cap_px,
        visibility_depth_tolerance_ratio=(
            args.visibility_depth_tolerance_ratio
        ),
        visibility_neighborhood_px=args.visibility_neighborhood_px,
        render_face_budget=args.render_face_budget,
        topology_smoothing_iterations=args.topology_smoothing_iterations,
        topology_smoothing_blend=args.topology_smoothing_blend,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
