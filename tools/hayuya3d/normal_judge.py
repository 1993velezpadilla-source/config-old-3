#!/usr/bin/env python3
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path

from visual_judge import SourceViewScore, _rotation_matrix, project_mesh_vertices

VIEW_OFFSETS = {
    "front": 0.0,
    "front_right": 45.0,
    "right": 90.0,
    "back": 180.0,
    "left": 270.0,
    "front_left": 315.0,
}


@dataclass
class NormalViewScore:
    view: str
    score: float
    cosine: float
    overlap_iou: float
    source: str


@dataclass
class NormalSupportScore:
    score: float
    views: list[NormalViewScore]
    method: str = "hayuya-wonder3d-front-system-normal-support-v1"
    evidence_class: str = "synthetic_support"


def _deps():
    import numpy as np
    from PIL import Image
    return np, Image


def _bbox(mask):
    np, _ = _deps()
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def load_normal_reference(path: Path, *, size: int = 128):
    np, Image = _deps()
    rgba = Image.open(path).convert("RGBA")
    arr = np.asarray(rgba)
    alpha = arr[:, :, 3]
    mask = alpha > 32

    # Defensive fallback for normal maps that lost alpha.
    if float(mask.mean()) > 0.98:
        rgb = arr[:, :, :3]
        mask = np.any(rgb < 248, axis=2)

    bbox = _bbox(mask)
    if bbox is None:
        raise ValueError(f"empty normal reference: {path}")

    x0, y0, x1, y1 = bbox
    crop = rgba.crop((x0, y0, x1 + 1, y1 + 1))
    w, h = crop.size
    scale = min((size - 12) / max(w, 1), (size - 12) / max(h, 1))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    crop = crop.resize((nw, nh), Image.Resampling.BILINEAR)

    canvas = Image.new("RGBA", (size, size), (127, 127, 127, 0))
    canvas.paste(crop, ((size - nw) // 2, (size - nh) // 2), crop)
    out = np.asarray(canvas)
    out_mask = out[:, :, 3] > 32
    normals = out[:, :, :3].astype(np.float32) / 255.0 * 2.0 - 1.0
    mag = np.linalg.norm(normals, axis=2, keepdims=True)
    normals = normals / np.maximum(mag, 1e-6)
    normals[~out_mask] = 0.0
    return normals, out_mask


def load_mesh_normal_arrays(mesh_path: Path, max_faces: int = 12000):
    np, _ = _deps()
    import trimesh

    loaded = trimesh.load(mesh_path, force="scene", process=False)
    geoms = list(loaded.geometry.values()) if hasattr(loaded, "geometry") else [loaded]

    vertices_parts = []
    faces_parts = []
    normals_parts = []
    offset = 0

    for mesh in geoms:
        if not hasattr(mesh, "faces") or not len(mesh.faces):
            continue
        vertices = np.asarray(mesh.vertices, dtype=np.float32)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        normals = np.asarray(mesh.vertex_normals, dtype=np.float32)
        if len(normals) != len(vertices):
            raise ValueError("vertex-normal count mismatch")

        vertices_parts.append(vertices)
        faces_parts.append(faces + offset)
        normals_parts.append(normals)
        offset += len(vertices)

    if not vertices_parts:
        raise ValueError("no triangle mesh geometry")

    vertices = np.concatenate(vertices_parts, axis=0)
    faces = np.concatenate(faces_parts, axis=0)
    normals = np.concatenate(normals_parts, axis=0)

    if len(faces) > max_faces:
        ids = np.linspace(0, len(faces) - 1, max_faces, dtype=np.int64)
        faces = faces[ids]

    center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
    vertices = vertices - center
    scale = float(np.max(vertices.max(axis=0) - vertices.min(axis=0)))
    if not math.isfinite(scale) or scale <= 1e-9:
        raise ValueError("collapsed mesh bounds")
    vertices = vertices / scale

    mag = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.maximum(mag, 1e-6)
    return vertices, faces, normals


def rasterize_normals(
    xy,
    z,
    faces,
    normals_front,
    *,
    size: int = 128,
):
    np, _ = _deps()
    out = np.zeros((size, size, 3), dtype=np.float32)
    depth = np.full((size, size), -np.inf, dtype=np.float32)
    mask = np.zeros((size, size), dtype=bool)

    for tri in faces:
        ids = np.asarray(tri, dtype=np.int64)
        pts = xy[ids]
        zs = z[ids]
        ns = normals_front[ids]

        min_x = max(0, int(math.floor(float(pts[:, 0].min()))))
        max_x = min(size - 1, int(math.ceil(float(pts[:, 0].max()))))
        ypts = size - 1 - pts[:, 1]
        min_y = max(0, int(math.floor(float(ypts.min()))))
        max_y = min(size - 1, int(math.ceil(float(ypts.max()))))
        if min_x > max_x or min_y > max_y:
            continue

        p0 = np.array([pts[0, 0], ypts[0]], dtype=np.float32)
        p1 = np.array([pts[1, 0], ypts[1]], dtype=np.float32)
        p2 = np.array([pts[2, 0], ypts[2]], dtype=np.float32)
        denom = (
            (p1[1] - p2[1]) * (p0[0] - p2[0])
            + (p2[0] - p1[0]) * (p0[1] - p2[1])
        )
        if abs(float(denom)) <= 1e-7:
            continue

        yy, xx = np.mgrid[min_y:max_y + 1, min_x:max_x + 1]
        px = xx.astype(np.float32) + 0.5
        py = yy.astype(np.float32) + 0.5

        w0 = ((p1[1] - p2[1]) * (px - p2[0]) + (p2[0] - p1[0]) * (py - p2[1])) / denom
        w1 = ((p2[1] - p0[1]) * (px - p2[0]) + (p0[0] - p2[0]) * (py - p2[1])) / denom
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-5) & (w1 >= -1e-5) & (w2 >= -1e-5)
        if not inside.any():
            continue

        zz = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
        region_depth = depth[min_y:max_y + 1, min_x:max_x + 1]
        visible = inside & (zz > region_depth)
        if not visible.any():
            continue

        nn = (
            w0[..., None] * ns[0]
            + w1[..., None] * ns[1]
            + w2[..., None] * ns[2]
        )
        mag = np.linalg.norm(nn, axis=2, keepdims=True)
        nn = nn / np.maximum(mag, 1e-6)

        region = out[min_y:max_y + 1, min_x:max_x + 1]
        region_mask = mask[min_y:max_y + 1, min_x:max_x + 1]
        region[visible] = nn[visible]
        region_depth[visible] = zz[visible]
        region_mask[visible] = True

    return out, mask


def render_candidate_front_system_normal(
    vertices,
    faces,
    vertex_normals,
    anchor: SourceViewScore,
    *,
    view_offset: float,
    size: int = 128,
):
    np, _ = _deps()

    # Wonder3D's generated PNG normals are encoded in the coordinate system of the
    # input/front view. Keep candidate normals in that same conceptual frame.
    front_rot = _rotation_matrix(
        anchor.best_azimuth,
        anchor.best_elevation,
        anchor.best_up_axis,
    )
    normals_front = vertex_normals @ front_rot.T
    normals_front = normals_front / np.maximum(
        np.linalg.norm(normals_front, axis=1, keepdims=True),
        1e-6,
    )

    view_azimuth = (anchor.best_azimuth + view_offset) % 360.0
    xy, z = project_mesh_vertices(
        vertices,
        view_azimuth,
        anchor.best_elevation,
        anchor.best_up_axis,
        size=size,
        projection="orthographic",
    )
    return rasterize_normals(
        xy,
        z,
        faces,
        normals_front,
        size=size,
    )


def score_normal_maps(candidate, candidate_mask, reference, reference_mask):
    np, _ = _deps()
    overlap = candidate_mask & reference_mask
    union = candidate_mask | reference_mask
    if not overlap.any() or not union.any():
        return 0.0, 0.0, 0.0

    dots = np.sum(candidate[overlap] * reference[overlap], axis=1)
    cosine = float(np.mean(np.clip(dots, -1.0, 1.0)))
    positive_cosine = max(0.0, cosine)
    iou = float(overlap.sum() / union.sum())
    score = 100.0 * (0.85 * positive_cosine + 0.15 * iou)
    return score, cosine, iou


def aggregate_normal_support(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    mean = sum(ordered) / len(ordered)
    if len(ordered) == 1:
        return mean
    return 0.82 * mean + 0.18 * ordered[0]


def score_candidate_normals(
    mesh_path: Path,
    normal_views: dict[str, Path],
    anchor: SourceViewScore,
    *,
    size: int = 128,
) -> NormalSupportScore:
    vertices, faces, vertex_normals = load_mesh_normal_arrays(mesh_path)
    scores: list[NormalViewScore] = []

    for view, offset in VIEW_OFFSETS.items():
        path = normal_views.get(view)
        if path is None or not Path(path).is_file():
            continue

        candidate, candidate_mask = render_candidate_front_system_normal(
            vertices,
            faces,
            vertex_normals,
            anchor,
            view_offset=offset,
            size=size,
        )
        reference, reference_mask = load_normal_reference(Path(path), size=size)
        score, cosine, iou = score_normal_maps(
            candidate,
            candidate_mask,
            reference,
            reference_mask,
        )
        scores.append(
            NormalViewScore(
                view=view,
                score=round(score, 3),
                cosine=round(cosine, 6),
                overlap_iou=round(iou, 6),
                source=str(path),
            )
        )

    final = aggregate_normal_support([x.score for x in scores])
    return NormalSupportScore(score=round(final, 3), views=scores)


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="HAYUYA synthetic normal support Judge.")
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--normal", action="append", default=[], help="view=path")
    parser.add_argument("--anchor-azimuth", type=float, required=True)
    parser.add_argument("--anchor-elevation", type=float, default=0.0)
    parser.add_argument("--anchor-up-axis", choices=["y", "z"], default="y")
    args = parser.parse_args()

    normal_views = {}
    for item in args.normal:
        name, raw = item.split("=", 1)
        normal_views[name] = Path(raw)

    anchor = SourceViewScore(
        source="cli",
        best_score=0.0,
        best_azimuth=args.anchor_azimuth,
        best_elevation=args.anchor_elevation,
        best_up_axis=args.anchor_up_axis,
        silhouette_iou=0.0,
        boundary_f1=0.0,
    )
    result = score_candidate_normals(args.mesh, normal_views, anchor)
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
