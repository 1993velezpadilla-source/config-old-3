#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import json
import math
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
from PIL import Image


# Mirrors microsoft/TRELLIS.2 trellis2/utils/render_utils.py::render_snapshot.
YAW_OFFSET = math.radians(-16.0)
PITCH = math.radians(20.0)
RADIUS = 2.0
FOV_DEGREES = 36.0
N_VIEWS = 8
AABB_MIN = -0.505
AABB_MAX = 0.505


@dataclass
class RecoveryReport:
    schema: int
    preview_html: str
    output_glb: str
    recovery: str
    grid_resolution: int
    texture_size: int
    vertices_before_unwrap: int
    faces_before_unwrap: int
    vertices_final: int
    faces_final: int
    preview_width: int
    preview_height: int
    view_count: int
    source_modes: list[str]
    source_max_edge: int
    texture_baked_from: str
    approximation: str


class _PreviewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources: dict[tuple[int, int], str] = {}

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() != "img":
            return
        raw = dict(attrs)
        element_id = str(raw.get("id") or "")
        if not element_id.startswith("view-m") or "-s" not in element_id:
            return
        try:
            left, step = element_id.rsplit("-s", 1)
            mode = left.rsplit("m", 1)[1]
            key = (int(mode), int(step))
        except Exception:
            return
        src = str(raw.get("src") or "")
        if src.startswith("data:image/") and ";base64," in src:
            self.sources[key] = src


def _decode_data_image(src: str) -> Image.Image:
    _, payload = src.split(",", 1)
    return Image.open(io.BytesIO(base64.b64decode(payload))).convert("RGB")


def load_preview(preview_html: Path) -> dict[tuple[int, int], np.ndarray]:
    parser = _PreviewParser()
    parser.feed(preview_html.read_text(encoding="utf-8"))
    if len(parser.sources) < 24:
        raise RuntimeError(
            f"TRELLIS.2 preview recovery needs static multi-view images; found {len(parser.sources)}"
        )
    decoded = {
        key: np.asarray(_decode_data_image(src), dtype=np.uint8)
        for key, src in parser.sources.items()
    }
    for mode in (0, 1, 2):
        missing = [step for step in range(N_VIEWS) if (mode, step) not in decoded]
        if missing:
            raise RuntimeError(
                f"TRELLIS.2 preview missing required mode={mode} views={missing}"
            )
    sizes = {(img.shape[1], img.shape[0]) for img in decoded.values()}
    if len(sizes) != 1:
        raise RuntimeError(
            f"TRELLIS.2 preview has inconsistent image sizes: {sorted(sizes)}"
        )
    return decoded


def _camera(step: int):
    yaw = YAW_OFFSET + step * 2.0 * math.pi / N_VIEWS
    pitch = PITCH
    origin = np.array([
        math.sin(yaw) * math.cos(pitch),
        math.cos(yaw) * math.cos(pitch),
        math.sin(pitch),
    ], dtype=np.float64) * RADIUS
    forward = -origin / np.linalg.norm(origin)
    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    up /= np.linalg.norm(up)
    return origin, right, up, forward


def _project(points: np.ndarray, camera, width: int, height: int):
    origin, right, up, forward = camera
    rel = points - origin
    z = rel @ forward
    x = rel @ right
    y = rel @ up
    focal = 0.5 / math.tan(math.radians(FOV_DEGREES) / 2.0)
    u = 0.5 + focal * x / np.maximum(z, 1e-12)
    v = 0.5 - focal * y / np.maximum(z, 1e-12)
    px = u * (width - 1)
    py = v * (height - 1)
    return px, py, z


def _build_masks(
    images: dict[tuple[int, int], np.ndarray],
    dilation: int = 2,
):
    from scipy.ndimage import binary_dilation

    masks = []
    for step in range(N_VIEWS):
        # Clay is near-black only outside the mesh; baseColor protects very dark
        # hood/cloth pixels that can sit close to the clay threshold.
        clay = images[(1, step)]
        base = images[(2, step)]
        mask = (clay.max(axis=2) > 7) | (base.max(axis=2) > 7)
        if dilation > 0:
            mask = binary_dilation(mask, iterations=int(dilation))
        masks.append(mask)
    return masks


def build_visual_hull(
    images: dict[tuple[int, int], np.ndarray],
    *,
    grid_resolution: int = 224,
    dilation: int = 2,
    smoothing_iterations: int = 5,
    face_target: int = 120_000,
):
    import trimesh
    from skimage.measure import marching_cubes

    if grid_resolution < 96:
        raise ValueError("grid_resolution must be >= 96")
    masks = _build_masks(images, dilation=dilation)
    h, w = masks[0].shape
    cameras = [_camera(step) for step in range(N_VIEWS)]
    coords = np.linspace(
        AABB_MIN, AABB_MAX, grid_resolution, dtype=np.float32
    )
    occupancy = np.zeros(
        (grid_resolution, grid_resolution, grid_resolution),
        dtype=bool,
    )
    xx, yy = np.meshgrid(coords, coords, indexing="xy")
    xy = np.stack([xx.ravel(), yy.ravel()], axis=1)

    for zi, z_value in enumerate(coords):
        points = np.column_stack([
            xy,
            np.full(len(xy), z_value, dtype=np.float32),
        ])
        keep = np.ones(len(points), dtype=bool)
        for step, camera in enumerate(cameras):
            px, py, depth = _project(points, camera, w, h)
            ix = np.rint(px).astype(np.int32)
            iy = np.rint(py).astype(np.int32)
            inside = (
                (depth > 0)
                & (ix >= 0) & (ix < w)
                & (iy >= 0) & (iy < h)
            )
            accepted = np.zeros(len(points), dtype=bool)
            ids = np.flatnonzero(inside)
            accepted[ids] = masks[step][iy[ids], ix[ids]]
            keep &= accepted
            if not np.any(keep):
                break
        occupancy[zi] = keep.reshape(
            grid_resolution, grid_resolution
        )

    filled = int(np.count_nonzero(occupancy))
    if filled < max(1000, grid_resolution * grid_resolution // 2):
        raise RuntimeError(
            "TRELLIS.2 preview visual hull collapsed: "
            f"occupied_voxels={filled}"
        )

    raw_vertices, faces, _, _ = marching_cubes(
        occupancy.astype(np.uint8), 0.5
    )
    step_size = (
        float(coords[-1] - coords[0]) / float(grid_resolution - 1)
    )
    vertices = np.empty_like(raw_vertices, dtype=np.float32)
    # marching_cubes sees occupancy as Z,Y,X; restore TRELLIS X,Y,Z.
    vertices[:, 0] = coords[0] + raw_vertices[:, 2] * step_size
    vertices[:, 1] = coords[0] + raw_vertices[:, 1] * step_size
    vertices[:, 2] = coords[0] + raw_vertices[:, 0] * step_size

    mesh = trimesh.Trimesh(
        vertices=vertices, faces=faces, process=True
    )
    try:
        mesh.fix_normals(multibody=True)
    except TypeError:
        mesh.fix_normals()
    if smoothing_iterations > 0:
        trimesh.smoothing.filter_taubin(
            mesh,
            lamb=0.45,
            nu=0.5,
            iterations=int(smoothing_iterations),
        )
    if face_target > 0 and len(mesh.faces) > face_target:
        try:
            mesh = mesh.simplify_quadric_decimation(
                face_count=int(face_target)
            )
            try:
                mesh.fix_normals(multibody=True)
            except TypeError:
                mesh.fix_normals()
        except Exception as exc:
            print(
                "::warning::TRELLIS.2 preview hull simplification unavailable; "
                f"keeping {len(mesh.faces)} faces: "
                f"{type(exc).__name__}: {exc}"
            )
    return mesh, masks, cameras


def _face_camera_indices(mesh, masks, cameras):
    centers = np.asarray(mesh.triangles_center, dtype=np.float64)
    normals = np.asarray(mesh.face_normals, dtype=np.float64)
    h, w = masks[0].shape
    all_scores = np.full(
        (len(centers), N_VIEWS), -1e9, dtype=np.float32
    )
    facing_only = np.full_like(all_scores, -1e9)
    for step, camera in enumerate(cameras):
        origin = camera[0]
        view_dir = origin[None, :] - centers
        view_dir /= np.maximum(
            np.linalg.norm(view_dir, axis=1, keepdims=True), 1e-12
        )
        score = np.einsum(
            "ij,ij->i", normals, view_dir
        ).astype(np.float32)
        facing_only[:, step] = score
        px, py, depth = _project(centers, camera, w, h)
        ix = np.rint(px).astype(np.int32)
        iy = np.rint(py).astype(np.int32)
        inside = (
            (depth > 0)
            & (ix >= 0) & (ix < w)
            & (iy >= 0) & (iy < h)
        )
        visible = np.zeros(len(centers), dtype=bool)
        ids = np.flatnonzero(inside)
        visible[ids] = masks[step][iy[ids], ix[ids]]
        score[~visible] = -1e9
        all_scores[:, step] = score
    selected = np.argmax(all_scores, axis=1)
    bad = np.max(all_scores, axis=1) < -1e8
    if np.any(bad):
        selected[bad] = np.argmax(facing_only[bad], axis=1)
    return selected.astype(np.int16)


def _bilinear(
    image: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
):
    h, w = image.shape[:2]
    x = np.clip(x, 0, w - 1.001)
    y = np.clip(y, 0, h - 1.001)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    wx = (x - x0)[:, None]
    wy = (y - y0)[:, None]
    a = image[y0, x0].astype(np.float32)
    b = image[y0, x1].astype(np.float32)
    c = image[y1, x0].astype(np.float32)
    d = image[y1, x1].astype(np.float32)
    return (
        a * (1 - wx) * (1 - wy)
        + b * wx * (1 - wy)
        + c * (1 - wx) * wy
        + d * wx * wy
    )


def _pad_texture(
    texture: np.ndarray,
    valid: np.ndarray,
    iterations: int = 8,
):
    out = texture.copy()
    known = valid.copy()
    h, w = known.shape
    for _ in range(iterations):
        acc = np.zeros_like(out, dtype=np.float32)
        count = np.zeros((h, w), dtype=np.float32)
        for dy, dx in (
            (-1, 0), (1, 0), (0, -1), (0, 1)
        ):
            src_y0 = max(0, -dy)
            src_y1 = min(h, h - dy)
            src_x0 = max(0, -dx)
            src_x1 = min(w, w - dx)
            dst_y0 = src_y0 + dy
            dst_y1 = src_y1 + dy
            dst_x0 = src_x0 + dx
            dst_x1 = src_x1 + dx
            src_known = known[
                src_y0:src_y1, src_x0:src_x1
            ]
            acc[
                dst_y0:dst_y1, dst_x0:dst_x1
            ] += (
                out[src_y0:src_y1, src_x0:src_x1]
                * src_known[..., None]
            )
            count[
                dst_y0:dst_y1, dst_x0:dst_x1
            ] += src_known
        fill = (~known) & (count > 0)
        if not np.any(fill):
            break
        out[fill] = acc[fill] / count[fill, None]
        known[fill] = True
    return np.clip(out, 0, 255).astype(np.uint8)


def bake_base_color(
    mesh,
    images,
    masks,
    cameras,
    texture_size: int = 2048,
):
    import trimesh
    import xatlas

    source_vertices = np.asarray(
        mesh.vertices, dtype=np.float64
    )
    source_faces = np.asarray(
        mesh.faces, dtype=np.int32
    )
    vmapping, indices, uvs = xatlas.parametrize(
        source_vertices, source_faces
    )
    vertices = source_vertices[
        np.asarray(vmapping, dtype=np.int64)
    ]
    faces = np.asarray(indices, dtype=np.int32)
    uvs = np.asarray(uvs, dtype=np.float64)
    unwrapped = trimesh.Trimesh(
        vertices=vertices, faces=faces, process=False
    )
    try:
        unwrapped.fix_normals(multibody=True)
    except TypeError:
        unwrapped.fix_normals()
    selected_views = _face_camera_indices(
        unwrapped, masks, cameras
    )

    size = int(texture_size)
    accum = np.zeros(
        (size, size, 3), dtype=np.float32
    )
    weights = np.zeros(
        (size, size), dtype=np.float32
    )
    base_images = [
        images[(2, step)] for step in range(N_VIEWS)
    ]
    h, w = base_images[0].shape[:2]

    for face_index, face in enumerate(faces):
        uv = uvs[face]
        tri = np.column_stack([
            uv[:, 0] * (size - 1),
            (1.0 - uv[:, 1]) * (size - 1),
        ])
        min_x = max(
            0, int(math.floor(float(np.min(tri[:, 0]))))
        )
        max_x = min(
            size - 1,
            int(math.ceil(float(np.max(tri[:, 0])))),
        )
        min_y = max(
            0, int(math.floor(float(np.min(tri[:, 1]))))
        )
        max_y = min(
            size - 1,
            int(math.ceil(float(np.max(tri[:, 1])))),
        )
        if min_x > max_x or min_y > max_y:
            continue
        x0, y0 = tri[0]
        x1, y1 = tri[1]
        x2, y2 = tri[2]
        denom = (
            (y1 - y2) * (x0 - x2)
            + (x2 - x1) * (y0 - y2)
        )
        if abs(float(denom)) < 1e-10:
            continue
        yy, xx = np.mgrid[
            min_y:max_y + 1,
            min_x:max_x + 1,
        ]
        sx = xx.ravel().astype(np.float64) + 0.5
        sy = yy.ravel().astype(np.float64) + 0.5
        b0 = (
            (y1 - y2) * (sx - x2)
            + (x2 - x1) * (sy - y2)
        ) / denom
        b1 = (
            (y2 - y0) * (sx - x2)
            + (x0 - x2) * (sy - y2)
        ) / denom
        b2 = 1.0 - b0 - b1
        inside = (
            (b0 >= -1e-5)
            & (b1 >= -1e-5)
            & (b2 >= -1e-5)
        )
        if not np.any(inside):
            continue
        tx = xx.ravel()[inside]
        ty = yy.ravel()[inside]
        bary = np.column_stack([
            b0[inside], b1[inside], b2[inside]
        ])
        points = bary @ vertices[face]
        view = int(selected_views[face_index])
        px, py, depth = _project(
            points, cameras[view], w, h
        )
        src_ok = (
            (depth > 0)
            & (px >= 0) & (px < w - 1)
            & (py >= 0) & (py < h - 1)
        )
        if not np.any(src_ok):
            continue
        tx = tx[src_ok]
        ty = ty[src_ok]
        px = px[src_ok]
        py = py[src_ok]
        sampled = _bilinear(
            base_images[view], px, py
        )
        accum[ty, tx] += sampled
        weights[ty, tx] += 1.0

    valid = weights > 0
    painted = int(np.count_nonzero(valid))
    if painted < size * size * 0.01:
        raise RuntimeError(
            "TRELLIS.2 preview texture bake produced "
            "insufficient atlas coverage: "
            f"{painted}/{size*size}"
        )
    texture = np.zeros_like(accum)
    texture[valid] = (
        accum[valid] / weights[valid, None]
    )
    texture = _pad_texture(
        texture, valid, iterations=10
    )
    return (
        vertices,
        faces,
        uvs,
        Image.fromarray(texture, "RGB"),
    )


def recover(
    preview_html: Path,
    output_glb: Path,
    *,
    grid_resolution: int = 224,
    texture_size: int = 2048,
    face_target: int = 120_000,
    geometry_only: bool = False,
) -> dict:
    import trimesh

    images = load_preview(preview_html)
    h, w = images[(1, 0)].shape[:2]
    mesh, masks, cameras = build_visual_hull(
        images,
        grid_resolution=grid_resolution,
        dilation=2,
        smoothing_iterations=5,
        face_target=face_target,
    )
    vertices_before = len(mesh.vertices)
    faces_before = len(mesh.faces)

    if geometry_only:
        # Local/debug route; production never promotes geometry-only recovery.
        rgb = np.full(
            (len(mesh.vertices), 4), 220, dtype=np.uint8
        )
        rgb[:, 3] = 255
        mesh.visual = trimesh.visual.ColorVisuals(
            mesh, vertex_colors=rgb
        )
        final = mesh
        final_texture_size = 0
    else:
        vertices, faces, uvs, texture = bake_base_color(
            mesh,
            images,
            masks,
            cameras,
            texture_size=texture_size,
        )
        # glTF is Y-up. TRELLIS preview geometry is Z-up.
        rot = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 0.0, -1.0],
            [0.0, 1.0, 0.0],
        ], dtype=np.float64)
        vertices = vertices @ rot
        material = trimesh.visual.material.PBRMaterial(
            roughnessFactor=1.0,
            metallicFactor=0.0,
            baseColorTexture=texture,
            baseColorFactor=np.array(
                [255, 255, 255, 255],
                dtype=np.uint8,
            ),
        )
        final = trimesh.Trimesh(
            vertices=vertices,
            faces=faces,
            process=False,
            visual=trimesh.visual.TextureVisuals(
                uv=uvs,
                material=material,
            ),
        )
        final_texture_size = int(texture_size)

    output_glb.parent.mkdir(
        parents=True, exist_ok=True
    )
    output_glb.write_bytes(
        trimesh.exchange.gltf.export_glb(
            trimesh.Scene(final)
        )
    )
    data = output_glb.read_bytes()
    if data[:4] != b"glTF" or len(data) < 1024:
        raise RuntimeError(
            "TRELLIS.2 preview recovery produced invalid GLB: "
            f"bytes={len(data)}"
        )

    report = RecoveryReport(
        schema=1,
        preview_html=str(preview_html),
        output_glb=str(output_glb),
        recovery="trellis2_static_preview_visual_hull",
        grid_resolution=int(grid_resolution),
        texture_size=final_texture_size,
        vertices_before_unwrap=int(vertices_before),
        faces_before_unwrap=int(faces_before),
        vertices_final=int(len(final.vertices)),
        faces_final=int(len(final.faces)),
        preview_width=int(w),
        preview_height=int(h),
        view_count=N_VIEWS,
        source_modes=[
            "normal", "clay", "base_color"
        ],
        source_max_edge=max(w, h),
        texture_baked_from=(
            "TRELLIS.2 Base color turntable views"
        ),
        approximation=(
            "CPU visual hull reconstructed from the exact "
            "TRELLIS.2 8-view preview; hidden concavities "
            "are approximate until native latent extraction succeeds"
        ),
    )
    report_path = output_glb.with_suffix(
        ".recovery.json"
    )
    report_path.write_text(
        json.dumps(asdict(report), indent=2) + "\n",
        encoding="utf-8",
    )
    payload = asdict(report)
    payload["path"] = str(output_glb)
    payload["metadata"] = str(report_path)
    payload["generator"] = (
        "microsoft/TRELLIS.2-preview-recovery"
    )
    payload["compute"] = (
        "GitHub-hosted CPU visual hull + xatlas texture bake"
    )
    payload["bytes"] = len(data)
    print(
        "HAYUYA_TRELLIS2_PREVIEW_RECOVERY_PASS",
        json.dumps(payload, separators=(",", ":")),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recover a textured CPU fallback GLB from "
            "TRELLIS.2 static preview turntable views."
        )
    )
    parser.add_argument(
        "--preview", type=Path, required=True
    )
    parser.add_argument(
        "--output", type=Path, required=True
    )
    parser.add_argument(
        "--grid", type=int, default=224
    )
    parser.add_argument(
        "--texture-size", type=int, default=2048
    )
    parser.add_argument(
        "--face-target", type=int, default=120000
    )
    parser.add_argument(
        "--geometry-only", action="store_true"
    )
    args = parser.parse_args()
    recover(
        args.preview,
        args.output,
        grid_resolution=args.grid,
        texture_size=args.texture_size,
        face_target=args.face_target,
        geometry_only=args.geometry_only,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
