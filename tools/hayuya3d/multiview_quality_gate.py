#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

from software_glb_preview import (
    _load_scene,
    _normalize_visible_to_canvas,
    _render_uv_region,
)


ANGLE_LABELS = {
    0: "front_000",
    30: "right_030",
    45: "right_045",
    90: "right_profile_090",
    180: "back_180",
    -90: "left_profile_m090",
    -45: "left_m045",
    -30: "left_m030",
}


def _bounds(vertices: np.ndarray, overscan: float = 1.42):
    lo = vertices.min(axis=0)
    hi = vertices.max(axis=0)
    span = max(float(hi[0] - lo[0]), float(hi[1] - lo[1])) * float(overscan)
    cx = float((lo[0] + hi[0]) * 0.5)
    cy = float((lo[1] + hi[1]) * 0.5)
    return (
        cx - span * 0.5,
        cx + span * 0.5,
        cy - span * 0.5,
        cy + span * 0.5,
    )


def _rotate(geometries, angle_deg: float, center: np.ndarray):
    matrix = trimesh.transformations.rotation_matrix(
        math.radians(float(angle_deg)),
        [0.0, 1.0, 0.0],
        point=np.asarray(center, dtype=np.float64),
    )
    for geometry in geometries:
        geometry.apply_transform(matrix)


def _mask_pixels(mask: Image.Image) -> int:
    return int(np.count_nonzero(np.asarray(mask, dtype=np.uint8) > 0))


def render_multiview(
    input_glb: Path,
    output_dir: Path,
    *,
    size: int = 1024,
    supersample: int = 2,
    angles: list[int],
):
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    rendered = []

    for angle in angles:
        geometries, vertices, source_front, support = _load_scene(input_glb)
        center = np.asarray(
            [
                float((vertices[:, 0].min() + vertices[:, 0].max()) * 0.5),
                float((vertices[:, 1].min() + vertices[:, 1].max()) * 0.5),
                float((vertices[:, 2].min() + vertices[:, 2].max()) * 0.5),
            ],
            dtype=np.float64,
        )
        _rotate(geometries, angle, center)
        vertices_rot = np.concatenate(
            [np.asarray(g.vertices, dtype=np.float32) for g in geometries],
            axis=0,
        )
        bounds = _bounds(vertices_rot, overscan=1.42)

        image, mask = _render_uv_region(
            geometries,
            bounds,
            int(size),
            int(supersample),
        )
        normalized, normalized_mask, framing = _normalize_visible_to_canvas(
            image,
            mask,
            int(size),
            0.12,
        )

        source_pixels = 0
        support_pixels = 0
        if source_front:
            _, source_mask = _render_uv_region(
                source_front,
                bounds,
                int(size),
                1,
            )
            source_pixels = _mask_pixels(source_mask)
        if support:
            _, support_mask = _render_uv_region(
                support,
                bounds,
                int(size),
                1,
            )
            support_pixels = _mask_pixels(support_mask)

        total_pixels = max(_mask_pixels(mask), 1)
        label = ANGLE_LABELS.get(int(angle), f"yaw_{int(angle):+04d}")
        path = output_dir / f"{label}.png"
        normalized.save(path)

        record = {
            "angle_deg": int(angle),
            "label": label,
            "image": str(path),
            "render_size": int(size),
            "supersample": int(supersample),
            "visible_pixels_raw": int(total_pixels),
            "source_front_pixels_raw": int(source_pixels),
            "support_pixels_raw": int(support_pixels),
            "source_front_ratio_proxy": float(source_pixels / total_pixels),
            "support_ratio_proxy": float(support_pixels / total_pixels),
            "framing": framing,
            "bounds": [float(x) for x in bounds],
        }
        records.append(record)
        rendered.append((label, normalized.copy()))

    # A single contact sheet makes regressions obvious while individual 1024
    # renders remain available for zoom inspection.
    tile = 512
    cols = 4
    rows = 2
    sheet = Image.new("RGB", (cols * tile, rows * tile), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(rendered):
        x = (index % cols) * tile
        y = (index // cols) * tile
        thumb = image.resize((tile, tile), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))
        draw.rectangle((x + 6, y + 6, x + 190, y + 34), fill=(18, 18, 18))
        draw.text((x + 12, y + 12), label, fill=(235, 235, 235))
    sheet_path = output_dir / "multiview_contact_sheet.png"
    sheet.save(sheet_path)

    payload = {
        "schema": 1,
        "policy": "hayuya-multiview-material-evidence-v1",
        "input": str(input_glb),
        "size": int(size),
        "supersample": int(supersample),
        "angles": [int(a) for a in angles],
        "views": records,
        "contact_sheet": str(sheet_path),
        "diagnostic_only": True,
        "notes": (
            "Rotates copies of the exported GLB around Y and renders its authored "
            "UV/baseColor materials with the CPU z-buffer. Source-front/support "
            "ratios are evidence proxies, not perceptual quality scores."
        ),
    }
    report = output_dir / "multiview_quality_report.json"
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("HAYUYA_MULTIVIEW_QUALITY_GATE", json.dumps(payload, separators=(",", ":")))
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--size", type=int, default=1024)
    parser.add_argument("--supersample", type=int, default=2)
    parser.add_argument(
        "--angles",
        default="0,30,45,90,180,-90,-45,-30",
        help="comma-separated Y-axis yaw angles in degrees",
    )
    args = parser.parse_args()
    angles = [int(x.strip()) for x in args.angles.split(",") if x.strip()]
    if len(angles) != 8:
        raise SystemExit(f"expected 8 multiview angles, got {angles}")
    render_multiview(
        args.input,
        args.output_dir,
        size=args.size,
        supersample=args.supersample,
        angles=angles,
    )


if __name__ == "__main__":
    main()
