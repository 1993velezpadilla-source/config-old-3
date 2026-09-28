#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import sparse
from scipy.ndimage import label
from scipy.sparse.linalg import lsqr

from trellis2_preview_recovery import (
    FOV_DEGREES,
    N_VIEWS,
    _build_masks,
    _camera,
    _project,
    load_preview,
)


ROT_ZUP_TO_GLTF_YUP = np.array(
    [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0],
    ],
    dtype=np.float64,
)


def _resize_rgb(array: np.ndarray, size: int) -> np.ndarray:
    return np.asarray(
        Image.fromarray(array).resize(
            (size, size),
            Image.Resampling.BILINEAR,
        ),
        dtype=np.uint8,
    )


def _resize_mask(mask: np.ndarray, size: int) -> np.ndarray:
    return (
        np.asarray(
            Image.fromarray((mask.astype(np.uint8) * 255)).resize(
                (size, size),
                Image.Resampling.NEAREST,
            ),
            dtype=np.uint8,
        )
        > 0
    )


def integrate_perspective_normal_depth(
    normal_rgb: np.ndarray,
    mask: np.ndarray,
    *,
    resolution: int = 256,
) -> dict:
    """Integrate TRELLIS camera-space normals into relative log-depth.

    For perspective surface P=z[x,y,1], camera-space normal n gives:
      d(log z)/dx = -nx / (nx*x + ny*y + nz)
      d(log z)/dy = -ny / (nx*x + ny*y + nz)

    TRELLIS.2's MeshRenderer emits camera-space normals encoded as (n+1)/2.
    The additive integration constant is aligned to the current hull later.
    """
    size = int(resolution)
    normal = _resize_rgb(normal_rgb, size).astype(np.float32) / 255.0
    normal = normal * 2.0 - 1.0
    use = _resize_mask(mask, size)

    norm = np.linalg.norm(normal, axis=2)
    use &= norm > 0.20
    normal = normal / np.maximum(norm[..., None], 1e-8)

    yy, xx = np.mgrid[0:size, 0:size]
    focal = 0.5 / math.tan(math.radians(FOV_DEGREES) / 2.0)
    x = (xx / float(size - 1) - 0.5) / focal
    # TRELLIS camera Y points up while image rows increase downward.
    y = -(yy / float(size - 1) - 0.5) / focal

    nx = normal[..., 0]
    ny = normal[..., 1]
    nz = normal[..., 2]
    denom = nx * x + ny * y + nz
    use &= np.abs(denom) > 0.12

    safe = np.where(np.abs(denom) > 1e-8, denom, 1.0)
    grad_x = (-nx / safe) / (focal * float(size - 1))
    grad_y = (ny / safe) / (focal * float(size - 1))

    magnitudes = np.sqrt(
        grad_x[use] * grad_x[use] + grad_y[use] * grad_y[use]
    )
    clip = 0.02
    if magnitudes.size:
        clip = min(
            0.03,
            max(0.003, float(np.percentile(magnitudes, 98)) * 1.5),
        )
    grad_x = np.clip(grad_x, -clip, clip)
    grad_y = np.clip(grad_y, -clip, clip)

    components, count = label(use)
    if count <= 0:
        raise RuntimeError("normal integration found no foreground component")
    sizes = np.bincount(components.ravel())
    keep = np.flatnonzero(sizes >= 30)
    keep = keep[keep != 0]
    use &= np.isin(components, keep)
    components, count = label(use)

    ids = np.full((size, size), -1, dtype=np.int32)
    coords = np.argwhere(use)
    if len(coords) < 500:
        raise RuntimeError(
            f"normal integration foreground too small: pixels={len(coords)}"
        )
    ids[use] = np.arange(len(coords), dtype=np.int32)

    rows = []
    cols = []
    values = []
    rhs = []
    equation = 0

    horizontal = use[:, :-1] & use[:, 1:]
    hy, hx = np.where(horizontal)
    left = ids[hy, hx]
    right = ids[hy, hx + 1]
    n = len(left)
    rr = np.arange(equation, equation + n, dtype=np.int64)
    rows.append(np.repeat(rr, 2))
    cols.append(np.column_stack([left, right]).ravel())
    values.append(np.tile([-1.0, 1.0], n))
    rhs.append(
        ((grad_x[hy, hx] + grad_x[hy, hx + 1]) * 0.5).astype(
            np.float64
        )
    )
    equation += n

    vertical = use[:-1, :] & use[1:, :]
    vy, vx = np.where(vertical)
    top = ids[vy, vx]
    bottom = ids[vy + 1, vx]
    n = len(top)
    rr = np.arange(equation, equation + n, dtype=np.int64)
    rows.append(np.repeat(rr, 2))
    cols.append(np.column_stack([top, bottom]).ravel())
    values.append(np.tile([-1.0, 1.0], n))
    rhs.append(
        ((grad_y[vy, vx] + grad_y[vy + 1, vx]) * 0.5).astype(
            np.float64
        )
    )
    equation += n

    labels = np.unique(components[use])
    for component in labels:
        cy, cx = np.where(components == component)
        middle = len(cy) // 2
        index = int(ids[cy[middle], cx[middle]])
        rows.append(np.array([equation], dtype=np.int64))
        cols.append(np.array([index], dtype=np.int64))
        values.append(np.array([1.0], dtype=np.float64))
        rhs.append(np.array([0.0], dtype=np.float64))
        equation += 1

    matrix = sparse.coo_matrix(
        (
            np.concatenate(values),
            (np.concatenate(rows), np.concatenate(cols)),
        ),
        shape=(equation, len(coords)),
    ).tocsr()
    solution = lsqr(
        matrix,
        np.concatenate(rhs),
        atol=1e-6,
        btol=1e-6,
        iter_lim=700,
        show=False,
    )[0]

    log_depth = np.full((size, size), np.nan, dtype=np.float32)
    log_depth[use] = solution.astype(np.float32)

    return {
        "log_depth": log_depth,
        "mask": use,
        "components": components,
        "component_count": int(len(labels)),
        "gradient_clip": float(clip),
        "valid_pixels": int(np.count_nonzero(use)),
    }


def build_depth_guides(
    images: dict[tuple[int, int], np.ndarray],
    *,
    resolution: int = 256,
) -> list[dict]:
    masks = _build_masks(images, dilation=1)
    guides = []
    for step in range(N_VIEWS):
        guide = integrate_perspective_normal_depth(
            images[(0, step)],
            masks[step],
            resolution=resolution,
        )
        guide["step"] = int(step)
        guides.append(guide)
    return guides


def _refine_vertices(
    mesh,
    guides: list[dict],
    *,
    resolution: int,
    alpha: float = 0.22,
    max_step: float = 0.012,
    iterations: int = 2,
):
    import trimesh

    cameras = [_camera(step) for step in range(N_VIEWS)]
    focal = 0.5 / math.tan(math.radians(FOV_DEGREES) / 2.0)
    stage_reports = []

    for iteration in range(int(iterations)):
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        vertex_normals = np.asarray(mesh.vertex_normals, dtype=np.float64)
        accumulator = np.zeros_like(vertices)
        weight_sum = np.zeros(len(vertices), dtype=np.float64)
        used_views = []

        for step, camera in enumerate(cameras):
            origin, right, up, forward = camera
            px, py, depth = _project(
                vertices,
                camera,
                resolution,
                resolution,
            )
            ix = np.rint(px).astype(np.int32)
            iy = np.rint(py).astype(np.int32)

            to_camera = origin[None, :] - vertices
            to_camera /= np.maximum(
                np.linalg.norm(to_camera, axis=1, keepdims=True),
                1e-9,
            )
            facing = np.einsum(
                "ij,ij->i",
                vertex_normals,
                to_camera,
            )

            inside = (
                (depth > 0)
                & (ix >= 0)
                & (ix < resolution)
                & (iy >= 0)
                & (iy < resolution)
                & (facing > 0.20)
            )
            ids = np.flatnonzero(inside)
            if len(ids) == 0:
                continue

            guide = guides[step]
            ids = ids[guide["mask"][iy[ids], ix[ids]]]
            if len(ids) == 0:
                continue

            # Low-resolution vertex z-buffer rejects back-facing/occluded
            # vertices before applying a view's normal-derived depth.
            pixels = iy[ids] * resolution + ix[ids]
            z_buffer = np.full(
                resolution * resolution,
                np.inf,
                dtype=np.float64,
            )
            np.minimum.at(z_buffer, pixels, depth[ids])
            visible = depth[ids] <= z_buffer[pixels] + 0.012
            ids = ids[visible]
            if len(ids) == 0:
                continue

            rel_depth = guide["log_depth"][iy[ids], ix[ids]].astype(
                np.float64
            )
            labels = guide["components"][iy[ids], ix[ids]]
            target_depth = np.empty_like(rel_depth)

            # Normal integration is determined up to one multiplicative depth
            # constant per connected component. Align that constant to the
            # current silhouette hull using a robust median.
            for component in np.unique(labels):
                selected = labels == component
                offset = np.median(
                    np.log(np.maximum(depth[ids[selected]], 1e-6))
                    - rel_depth[selected]
                )
                target_depth[selected] = np.exp(
                    rel_depth[selected] + offset
                )

            x = (px[ids] / float(resolution - 1) - 0.5) / focal
            y = -(py[ids] / float(resolution - 1) - 0.5) / focal
            rays = (
                forward[None, :]
                + x[:, None] * right[None, :]
                + y[:, None] * up[None, :]
            )
            targets = origin[None, :] + target_depth[:, None] * rays

            displacement = targets - vertices[ids]
            length = np.linalg.norm(displacement, axis=1)
            scale = np.minimum(
                1.0,
                float(max_step) / np.maximum(length, 1e-9),
            )
            targets = vertices[ids] + displacement * scale[:, None]

            weights = np.clip(
                (facing[ids] - 0.20) / 0.80,
                0.0,
                1.0,
            ) ** 3
            accumulator[ids] += targets * weights[:, None]
            weight_sum[ids] += weights
            used_views.append(
                {
                    "step": int(step),
                    "vertices": int(len(ids)),
                }
            )

        selected = weight_sum > 1e-8
        proposal = vertices.copy()
        proposal[selected] = (
            accumulator[selected] / weight_sum[selected, None]
        )
        updated = vertices.copy()
        updated[selected] = (
            (1.0 - float(alpha)) * vertices[selected]
            + float(alpha) * proposal[selected]
        )
        mesh.vertices = updated

        # A tiny regularization pass suppresses per-pixel stair stepping while
        # retaining the normal-map displacement signal.
        try:
            trimesh.smoothing.filter_taubin(
                mesh,
                lamb=0.12,
                nu=0.125,
                iterations=1,
            )
        except Exception as exc:
            print(
                "::warning::normal Hero smoothing unavailable: "
                f"{type(exc).__name__}: {exc}"
            )

        moved = np.linalg.norm(
            np.asarray(mesh.vertices, dtype=np.float64) - vertices,
            axis=1,
        )
        stage_reports.append(
            {
                "iteration": int(iteration),
                "updated_vertices": int(np.count_nonzero(selected)),
                "median_displacement": float(np.median(moved[selected]))
                if np.any(selected)
                else 0.0,
                "p99_displacement": float(np.percentile(moved[selected], 99))
                if np.any(selected)
                else 0.0,
                "views": used_views,
            }
        )
    return stage_reports


def _subdivide_textured(mesh):
    import trimesh

    uv = getattr(mesh.visual, "uv", None)
    material = getattr(mesh.visual, "material", None)
    attributes = None
    if uv is not None and len(uv) == len(mesh.vertices):
        attributes = {"uv": np.asarray(uv, dtype=np.float64)}

    if attributes is None:
        vertices, faces = trimesh.remesh.subdivide(
            np.asarray(mesh.vertices),
            np.asarray(mesh.faces),
        )
        result = trimesh.Trimesh(
            vertices=vertices,
            faces=faces,
            process=False,
        )
    else:
        vertices, faces, new_attributes = trimesh.remesh.subdivide(
            np.asarray(mesh.vertices),
            np.asarray(mesh.faces),
            vertex_attributes=attributes,
        )
        result = trimesh.Trimesh(
            vertices=vertices,
            faces=faces,
            process=False,
            visual=trimesh.visual.TextureVisuals(
                uv=new_attributes["uv"],
                material=material,
            ),
        )
    return result


def build_normal_informed_hero(
    preview_html: Path,
    recovered_glb: Path,
    output_glb: Path,
    *,
    normal_resolution: int = 256,
    subdivision_levels: int = 2,
    max_faces: int = 2_000_000,
) -> dict:
    import trimesh

    images = load_preview(preview_html)
    guides = build_depth_guides(
        images,
        resolution=int(normal_resolution),
    )

    loaded = trimesh.load(
        recovered_glb,
        force="scene",
        process=False,
    )
    geometries = list(loaded.geometry.values())
    if len(geometries) != 1:
        raise RuntimeError(
            "normal Hero recovery expects one recovered textured mesh; "
            f"found={len(geometries)}"
        )
    mesh = geometries[0].copy()

    # Recovery GLB is already Y-up; TRELLIS preview cameras are Z-up.
    mesh.vertices = (
        np.asarray(mesh.vertices, dtype=np.float64)
        @ ROT_ZUP_TO_GLTF_YUP.T
    )

    base_faces = int(len(mesh.faces))
    projected_faces = base_faces * (4 ** int(subdivision_levels))
    if projected_faces > int(max_faces):
        raise RuntimeError(
            "normal Hero subdivision would exceed ceiling: "
            f"base={base_faces} levels={subdivision_levels} "
            f"projected={projected_faces}>{max_faces}"
        )

    refinement = []
    refinement.append(
        {
            "stage": "base",
            "faces": int(len(mesh.faces)),
            "vertices": int(len(mesh.vertices)),
            "iterations": _refine_vertices(
                mesh,
                guides,
                resolution=int(normal_resolution),
                alpha=0.22,
                max_step=0.012,
                iterations=2,
            ),
        }
    )

    for level_index in range(int(subdivision_levels)):
        mesh = _subdivide_textured(mesh)
        stage = {
            "stage": f"subdivision_{level_index + 1}",
            "faces": int(len(mesh.faces)),
            "vertices": int(len(mesh.vertices)),
        }
        # Refine after the first subdivision. The final subdivision interpolates
        # already-refined geometry and avoids an expensive million-vertex solve.
        if level_index == 0:
            stage["iterations"] = _refine_vertices(
                mesh,
                guides,
                resolution=int(normal_resolution),
                alpha=0.16,
                max_step=0.008,
                iterations=1,
            )
        refinement.append(stage)

    mesh.vertices = (
        np.asarray(mesh.vertices, dtype=np.float64)
        @ ROT_ZUP_TO_GLTF_YUP
    )

    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_glb.write_bytes(
        trimesh.exchange.gltf.export_glb(
            trimesh.Scene(mesh)
        )
    )
    blob = output_glb.read_bytes()
    if blob[:4] != b"glTF" or len(blob) < 1024:
        raise RuntimeError(
            f"normal Hero recovery produced invalid GLB: bytes={len(blob)}"
        )

    guide_report = []
    for guide in guides:
        values = guide["log_depth"][guide["mask"]]
        guide_report.append(
            {
                "step": int(guide["step"]),
                "valid_pixels": int(guide["valid_pixels"]),
                "components": int(guide["component_count"]),
                "gradient_clip": float(guide["gradient_clip"]),
                "log_depth_std": float(np.std(values)),
            }
        )

    report = {
        "schema": 1,
        "recovery": "trellis2_preview_normal_informed_hero_v1",
        "preview_html": str(preview_html),
        "input_glb": str(recovered_glb),
        "output_glb": str(output_glb),
        "normal_resolution": int(normal_resolution),
        "source_normal_views": int(N_VIEWS),
        "base_faces": int(base_faces),
        "subdivision_levels": int(subdivision_levels),
        "faces_final": int(len(mesh.faces)),
        "vertices_final": int(len(mesh.vertices)),
        "face_ceiling": int(max_faces),
        "normal_guides": guide_report,
        "refinement": refinement,
        "native_latent_extraction": False,
        "optimization_deferred": True,
        "approximation": (
            "Dense CPU reconstruction derived from the exact TRELLIS.2 "
            "preview silhouette, base-color and camera-space normal renders. "
            "Visible-surface depth is normal-informed; unseen concavities remain "
            "approximate until native TRELLIS.2 latent extraction succeeds."
        ),
        "generator": "microsoft/TRELLIS.2-preview-normal-hero",
        "compute": "GitHub-hosted CPU normal integration + textured subdivision",
        "bytes": int(len(blob)),
        "path": str(output_glb),
    }
    report_path = output_glb.with_suffix(".normal_hero.json")
    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    report["metadata"] = str(report_path)
    print(
        "HAYUYA_TRELLIS2_PREVIEW_NORMAL_HERO_PASS",
        json.dumps(report, separators=(",", ":")),
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a dense normal-informed Hero challenger from the exact "
            "TRELLIS.2 static preview when native GLB extraction is unavailable."
        )
    )
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--input-glb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--normal-resolution", type=int, default=256)
    parser.add_argument("--subdivision-levels", type=int, default=2)
    parser.add_argument("--max-faces", type=int, default=2_000_000)
    args = parser.parse_args()

    build_normal_informed_hero(
        args.preview,
        args.input_glb,
        args.output,
        normal_resolution=args.normal_resolution,
        subdivision_levels=args.subdivision_levels,
        max_faces=args.max_faces,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
