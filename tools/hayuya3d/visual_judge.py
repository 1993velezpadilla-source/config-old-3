#!/usr/bin/env python3
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from reference_pool import infer_view_hint


@dataclass
class SourceViewScore:
    source: str
    best_score: float
    best_azimuth: float
    best_elevation: float
    best_up_axis: str
    silhouette_iou: float
    boundary_f1: float
    projection: str = "orthographic"
    camera_distance: float | None = None
    mask_confidence: float = 1.0
    mask_method: str = "unknown"


@dataclass
class VisualScore:
    score: float
    views: list[SourceViewScore]
    method: str = "hayuya-silhouette-camera-search-v2"


def _deps():
    import numpy as np
    from PIL import Image, ImageDraw
    return np, Image, ImageDraw


def _trimesh():
    import trimesh
    return trimesh


def _binary_bbox(mask):
    np, _, _ = _deps()
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _normalize_mask(mask, size: int = 192, margin: int = 10):
    np, Image, _ = _deps()
    bbox = _binary_bbox(mask)
    if bbox is None:
        return np.zeros((size, size), dtype=bool)
    x0, y0, x1, y1 = bbox
    crop = mask[y0:y1 + 1, x0:x1 + 1].astype(np.uint8) * 255
    h, w = crop.shape
    if h <= 0 or w <= 0:
        return np.zeros((size, size), dtype=bool)
    scale = min((size - 2 * margin) / w, (size - 2 * margin) / h)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    im = Image.fromarray(crop, mode="L").resize((nw, nh), Image.Resampling.NEAREST)
    canvas = Image.new("L", (size, size), 0)
    canvas.paste(im, ((size - nw) // 2, (size - nh) // 2))
    return np.asarray(canvas) > 127


def _mask_quality(mask, corners, *, fallback: bool) -> float:
    np, _, _ = _deps()
    occupancy = float(mask.mean())
    if occupancy <= 0.0:
        return 0.05

    # Healthy whole-object masks are usually neither tiny nor nearly full-frame.
    if 0.06 <= occupancy <= 0.82:
        occupancy_score = 1.0
    elif occupancy < 0.06:
        occupancy_score = max(0.0, occupancy / 0.06)
    else:
        occupancy_score = max(0.0, (0.98 - occupancy) / 0.16)

    h, w = mask.shape
    band = max(1, min(h, w) // 50)
    border = np.concatenate([
        mask[:band, :].reshape(-1),
        mask[-band:, :].reshape(-1),
        mask[:, :band].reshape(-1),
        mask[:, -band:].reshape(-1),
    ])
    border_fg = float(border.mean())
    border_score = max(0.0, 1.0 - border_fg / 0.45)

    corner_luma = corners.mean(axis=1)
    corner_std = float(np.std(corner_luma))
    bg_uniformity = 1.0 / (1.0 + corner_std / 28.0)

    confidence = (
        0.42
        + 0.30 * occupancy_score
        + 0.18 * border_score
        + 0.10 * bg_uniformity
    )
    if fallback:
        confidence *= 0.72
    return max(0.10, min(1.0, confidence))


def extract_source_mask_evidence(path: Path, size: int = 192):
    np, Image, _ = _deps()
    im = Image.open(path).convert("RGBA")
    arr = np.asarray(im)
    alpha = arr[:, :, 3]

    # Best case: real transparency is explicit foreground evidence.
    if int(alpha.min()) < 245:
        mask = alpha > 20
        occupancy = float(mask.mean())
        confidence = 1.0 if 0.02 < occupancy < 0.98 else 0.82
        return _normalize_mask(mask, size=size), confidence, "alpha"

    rgb = arr[:, :, :3].astype(np.float32)
    h, w, _ = rgb.shape
    patch = max(2, min(h, w) // 20)
    corners = np.concatenate([
        rgb[:patch, :patch].reshape(-1, 3),
        rgb[:patch, -patch:].reshape(-1, 3),
        rgb[-patch:, :patch].reshape(-1, 3),
        rgb[-patch:, -patch:].reshape(-1, 3),
    ], axis=0)
    bg = np.median(corners, axis=0)
    corner_dist = np.linalg.norm(corners - bg, axis=1)
    threshold = max(22.0, float(np.percentile(corner_dist, 95)) * 2.5 + 8.0)
    dist = np.linalg.norm(rgb - bg, axis=2)
    mask = dist > threshold

    occupancy = float(mask.mean())
    fallback = occupancy < 0.03 or occupancy > 0.92
    method = "corner_background"
    if fallback:
        lum = rgb.mean(axis=2)
        bg_lum = float(bg.mean())
        lum_threshold = max(18.0, float(np.std(corners.mean(axis=1))) * 3.0 + 8.0)
        mask = np.abs(lum - bg_lum) > lum_threshold
        method = "luminance_fallback"

    confidence = _mask_quality(mask, corners, fallback=fallback)
    return _normalize_mask(mask, size=size), confidence, method


def extract_source_mask(path: Path, size: int = 192):
    mask, _, _ = extract_source_mask_evidence(path, size=size)
    return mask


def _rotation_matrix(azimuth_deg: float, elevation_deg: float, up_axis: str):
    np, _, _ = _deps()
    a = math.radians(azimuth_deg)
    e = math.radians(elevation_deg)

    if up_axis == "y":
        yaw = np.array([
            [math.cos(a), 0.0, math.sin(a)],
            [0.0, 1.0, 0.0],
            [-math.sin(a), 0.0, math.cos(a)],
        ], dtype=np.float32)
        pitch = np.array([
            [1.0, 0.0, 0.0],
            [0.0, math.cos(e), -math.sin(e)],
            [0.0, math.sin(e), math.cos(e)],
        ], dtype=np.float32)
    else:
        yaw = np.array([
            [math.cos(a), -math.sin(a), 0.0],
            [math.sin(a), math.cos(a), 0.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float32)
        pitch = np.array([
            [1.0, 0.0, 0.0],
            [0.0, math.cos(e), -math.sin(e)],
            [0.0, math.sin(e), math.cos(e)],
        ], dtype=np.float32)
    return pitch @ yaw


def _load_mesh_arrays(path: Path, max_faces: int = 9000):
    np, _, _ = _deps()
    trimesh = _trimesh()
    loaded = trimesh.load(path, force="scene", process=False)
    geoms = list(loaded.geometry.values()) if hasattr(loaded, "geometry") else [loaded]
    meshes = [g for g in geoms if hasattr(g, "faces") and len(g.faces)]
    if not meshes:
        raise ValueError("no triangle mesh geometry")
    mesh = trimesh.util.concatenate(meshes)
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(faces) > max_faces:
        # Deterministic coverage across the complete face array.
        ids = np.linspace(0, len(faces) - 1, max_faces, dtype=np.int64)
        faces = faces[ids]

    center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
    vertices = vertices - center
    scale = float(np.max(vertices.max(axis=0) - vertices.min(axis=0)))
    if not math.isfinite(scale) or scale <= 1e-9:
        raise ValueError("collapsed mesh bounds")
    vertices = vertices / scale
    return vertices, faces


def project_mesh_vertices(
    vertices,
    azimuth: float,
    elevation: float,
    up_axis: str,
    *,
    size: int,
    projection: str = "orthographic",
    camera_distance: float | None = None,
):
    np, _, _ = _deps()
    rot = _rotation_matrix(azimuth, elevation, up_axis)
    v = vertices @ rot.T

    if projection == "perspective":
        distance = float(camera_distance if camera_distance is not None else 2.4)
        if distance <= 0.55:
            raise ValueError("camera_distance must be > 0.55 for normalized Hayuya geometry")
        denom = np.maximum(distance - v[:, 2], 0.05)
        xy = v[:, :2] / denom[:, None]
    elif projection == "orthographic":
        xy = v[:, :2]
    else:
        raise ValueError(f"unknown projection: {projection}")

    min_xy = xy.min(axis=0)
    max_xy = xy.max(axis=0)
    span = np.maximum(max_xy - min_xy, 1e-7)
    uniform = float(max(span[0], span[1]))
    xy = (xy - (min_xy + max_xy) * 0.5) / uniform
    xy = xy * (size * 0.82) + size * 0.5
    return xy.astype(np.float32), v[:, 2].astype(np.float32)


def render_silhouette(
    vertices,
    faces,
    azimuth: float,
    elevation: float,
    up_axis: str,
    size: int = 192,
    *,
    projection: str = "orthographic",
    camera_distance: float | None = None,
):
    np, Image, ImageDraw = _deps()
    xy, _ = project_mesh_vertices(
        vertices,
        azimuth,
        elevation,
        up_axis,
        size=size,
        projection=projection,
        camera_distance=camera_distance,
    )

    canvas = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(canvas)
    for tri in faces:
        pts = [
            (float(xy[int(tri[0]), 0]), float(size - 1 - xy[int(tri[0]), 1])),
            (float(xy[int(tri[1]), 0]), float(size - 1 - xy[int(tri[1]), 1])),
            (float(xy[int(tri[2]), 0]), float(size - 1 - xy[int(tri[2]), 1])),
        ]
        draw.polygon(pts, fill=255)
    return _normalize_mask(np.asarray(canvas) > 127, size=size)


def _erode(mask):
    np, _, _ = _deps()
    p = np.pad(mask, 1, constant_values=False)
    out = np.ones_like(mask, dtype=bool)
    for dy in range(3):
        for dx in range(3):
            out &= p[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
    return out


def _boundary(mask):
    return mask & ~_erode(mask)


def _iou(a, b) -> float:
    np, _, _ = _deps()
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return float(inter / union) if union else 0.0


def _dilate(mask, radius: int = 2):
    np, _, _ = _deps()
    p = np.pad(mask, radius, constant_values=False)
    out = np.zeros_like(mask, dtype=bool)
    for dy in range(radius * 2 + 1):
        for dx in range(radius * 2 + 1):
            out |= p[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
    return out


def _boundary_f1(a, b) -> float:
    np, _, _ = _deps()
    ea, eb = _boundary(a), _boundary(b)
    na, nb = int(ea.sum()), int(eb.sum())
    if na == 0 or nb == 0:
        return 0.0
    precision = float((ea & _dilate(eb)).sum() / na)
    recall = float((eb & _dilate(ea)).sum() / nb)
    return 2.0 * precision * recall / max(precision + recall, 1e-9)


def score_masks(source_mask, candidate_mask) -> tuple[float, float, float]:
    iou = _iou(source_mask, candidate_mask)
    edge = _boundary_f1(source_mask, candidate_mask)
    # IoU dominates; edge fidelity catches shape-specific contours.
    score = 100.0 * (0.72 * iou + 0.28 * edge)
    return score, iou, edge


def aggregate_source_scores(values: list[float]) -> float:
    """
    Robust N-view aggregation.

    Every source contributes through the mean. Small pools keep a strong weakest-anchor
    penalty. Larger pools use a lower-quartile term plus a smaller absolute-minimum term
    so one damaged/poorly segmented photo cannot dominate dozens of good references.
    """
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    mean = sum(ordered) / len(ordered)
    if len(ordered) <= 2:
        return 0.70 * mean + 0.30 * ordered[0]

    q_count = max(1, math.ceil(len(ordered) * 0.25))
    lower_quartile_mean = sum(ordered[:q_count]) / q_count
    return 0.65 * mean + 0.25 * lower_quartile_mean + 0.10 * ordered[0]


def aggregate_source_scores_weighted(
    values: list[float],
    confidences: list[float],
) -> float:
    if not values:
        return 0.0
    if len(values) != len(confidences):
        raise ValueError("values/confidences length mismatch")

    weights = [max(0.05, min(1.0, float(w))) for w in confidences]
    weighted_mean = sum(v * w for v, w in zip(values, weights)) / sum(weights)

    # Pull uncertain references toward the weighted consensus before computing the
    # weak-tail penalty. A bad low-confidence mask can still matter, but not dominate.
    adjusted = [
        weighted_mean + w * (float(v) - weighted_mean)
        for v, w in zip(values, weights)
    ]
    ordered = sorted(adjusted)
    if len(ordered) <= 2:
        return 0.72 * weighted_mean + 0.28 * ordered[0]

    q_count = max(1, math.ceil(len(ordered) * 0.25))
    low = sum(ordered[:q_count]) / q_count
    return 0.68 * weighted_mean + 0.23 * low + 0.09 * ordered[0]


def circular_distance(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def build_render_bank(vertices, faces, *, size: int, azimuth_step: int):
    bank = {}
    for up_axis in ("y", "z"):
        for elevation in (-15.0, 0.0, 15.0):
            for azimuth in range(0, 360, azimuth_step):
                key = (up_axis, elevation, float(azimuth))
                bank[key] = render_silhouette(
                    vertices, faces, float(azimuth), elevation, up_axis, size=size
                )
    return bank


def refine_projection_match(
    source_mask,
    vertices,
    faces,
    base_match,
    *,
    size: int,
    azimuth_step: int,
    cache: dict,
):
    """
    Refine the coarse orthographic camera locally.

    The global bank stays cheap. Around the winning orientation we try +/- half an
    azimuth step and several perspective strengths, caching renders shared by sources.
    """
    if base_match is None:
        return None

    score, iou, edge, up_axis, elevation, azimuth = base_match
    best = (
        score,
        iou,
        edge,
        up_axis,
        elevation,
        azimuth,
        "orthographic",
        None,
    )

    half_step = max(5.0, azimuth_step / 2.0)
    azimuths = [
        float((azimuth - half_step) % 360.0),
        float(azimuth % 360.0),
        float((azimuth + half_step) % 360.0),
    ]
    projection_hypotheses = [
        ("orthographic", None),
        ("perspective", 1.4),
        ("perspective", 2.4),
        ("perspective", 4.0),
    ]

    for refined_azimuth in azimuths:
        for projection, distance in projection_hypotheses:
            key = (
                up_axis,
                float(elevation),
                refined_azimuth,
                projection,
                distance,
                size,
            )
            candidate_mask = cache.get(key)
            if candidate_mask is None:
                candidate_mask = render_silhouette(
                    vertices,
                    faces,
                    refined_azimuth,
                    elevation,
                    up_axis,
                    size=size,
                    projection=projection,
                    camera_distance=distance,
                )
                cache[key] = candidate_mask

            candidate_score, candidate_iou, candidate_edge = score_masks(
                source_mask,
                candidate_mask,
            )
            if candidate_score > best[0]:
                best = (
                    candidate_score,
                    candidate_iou,
                    candidate_edge,
                    up_axis,
                    elevation,
                    refined_azimuth,
                    projection,
                    distance,
                )

    return best


def score_candidate(
    mesh_path: Path,
    source_images: list[Path],
    *,
    size: int = 192,
    azimuth_step: int = 30,
) -> VisualScore:
    vertices, faces = _load_mesh_arrays(mesh_path)
    source_evidence = [
        extract_source_mask_evidence(p, size=size)
        for p in source_images
    ]
    source_masks = [item[0] for item in source_evidence]
    source_confidences = [item[1] for item in source_evidence]
    source_mask_methods = [item[2] for item in source_evidence]

    # Render candidate geometry once. N source photos reuse the same camera bank.
    bank = build_render_bank(
        vertices,
        faces,
        size=size,
        azimuth_step=azimuth_step,
    )
    bank_keys = list(bank)

    hints = [infer_view_hint(p) for p in source_images]
    anchor_index = next((i for i, hint in enumerate(hints) if hint is not None), None)
    anchor_hint = hints[anchor_index] if anchor_index is not None else None
    anchor_key = None

    def best_match(source_mask, allowed_keys):
        best = None
        for up_axis, elevation, azimuth in allowed_keys:
            candidate_mask = bank[(up_axis, elevation, azimuth)]
            score, iou, edge = score_masks(source_mask, candidate_mask)
            if best is None or score > best[0]:
                best = (score, iou, edge, up_axis, elevation, azimuth)
        return best

    # Establish one global orientation offset when canonical filenames are available.
    if anchor_index is not None:
        anchor_best = best_match(source_masks[anchor_index], bank_keys)
        if anchor_best is not None:
            anchor_key = (anchor_best[3], anchor_best[4], anchor_best[5])

    views: list[SourceViewScore] = []
    refinement_cache: dict = {}
    for idx, (source_path, source_mask) in enumerate(zip(source_images, source_masks)):
        hint = hints[idx]
        allowed = bank_keys

        if anchor_key is not None and anchor_hint is not None and hint is not None:
            anchor_axis, _, anchor_azimuth = anchor_key
            expected = (anchor_azimuth + (hint - anchor_hint)) % 360.0
            constrained = [
                key for key in bank_keys
                if key[0] == anchor_axis
                and circular_distance(key[2], expected) <= max(azimuth_step, 30)
            ]
            if constrained:
                allowed = constrained

        best = best_match(source_mask, allowed)
        if best is None:
            continue

        refined = refine_projection_match(
            source_mask,
            vertices,
            faces,
            best,
            size=size,
            azimuth_step=azimuth_step,
            cache=refinement_cache,
        )
        if refined is None:
            continue

        score, iou, edge, up_axis, elevation, azimuth, projection, camera_distance = refined
        views.append(
            SourceViewScore(
                source=str(source_path),
                best_score=round(score, 3),
                best_azimuth=float(azimuth),
                best_elevation=float(elevation),
                best_up_axis=up_axis,
                silhouette_iou=round(iou, 6),
                boundary_f1=round(edge, 6),
                projection=projection,
                camera_distance=camera_distance,
                mask_confidence=round(float(source_confidences[idx]), 4),
                mask_method=source_mask_methods[idx],
            )
        )

    vals = [x.best_score for x in views]
    confs = [x.mask_confidence for x in views]
    final = aggregate_source_scores_weighted(vals, confs)
    return VisualScore(score=round(final, 3), views=views)


def main() -> int:
    import argparse
    import json
    from dataclasses import asdict

    parser = argparse.ArgumentParser(description="HAYUYA Judge v2 source-image silhouette scorer.")
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--size", type=int, default=192)
    parser.add_argument("--azimuth-step", type=int, default=30)
    args = parser.parse_args()

    result = score_candidate(
        args.mesh,
        args.source,
        size=args.size,
        azimuth_step=args.azimuth_step,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
