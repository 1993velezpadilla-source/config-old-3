#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from visual_judge import (
    SourceViewScore,
    aggregate_source_scores_weighted,
    extract_source_mask_evidence,
    score_masks,
)

FRAME_RE = re.compile(r"(?P<offset>\d{3})(?:\.[^.]+)?$")


@dataclass
class TurntableSourceScore:
    source: str
    source_azimuth: float
    expected_offset: float
    selected_offset: float
    selected_frame: str
    angular_error: float
    silhouette_score: float
    silhouette_iou: float
    boundary_f1: float
    color_histogram_score: float
    combined_score: float
    mask_confidence: float
    catastrophic_mismatch: bool


@dataclass
class TurntableQAResult:
    score: float
    coverage: int
    expected_sources: int
    all_sources_mapped: bool
    catastrophic_mismatches: int
    ready: bool
    views: list[TurntableSourceScore]
    method: str = "hayuya-source-to-turntable-v1"


def _deps():
    import numpy as np
    from PIL import Image
    return np, Image


def circular_distance(a: float, b: float) -> float:
    d = abs((float(a) - float(b)) % 360.0)
    return min(d, 360.0 - d)


def frame_offset(path: Path, fallback_index: int) -> float:
    match = FRAME_RE.search(path.stem)
    if match:
        try:
            return float(int(match.group("offset")) % 360)
        except Exception:
            pass
    return float((fallback_index * 15) % 360)


def index_turntable_frames(frames: list[Path]) -> list[tuple[float, Path]]:
    indexed = []
    for index, path in enumerate(frames):
        if path.is_file():
            indexed.append((frame_offset(path, index), path))
    indexed.sort(key=lambda item: item[0])
    return indexed


def select_frame(
    indexed_frames: list[tuple[float, Path]],
    expected_offset: float,
) -> tuple[float, Path, float] | None:
    if not indexed_frames:
        return None
    selected = min(
        indexed_frames,
        key=lambda item: circular_distance(item[0], expected_offset),
    )
    return selected[0], selected[1], circular_distance(selected[0], expected_offset)


def _normalize_rgb_foreground(path: Path, *, size: int = 192):
    np, Image = _deps()
    rgba = Image.open(path).convert("RGBA")
    arr = np.asarray(rgba)
    mask, confidence, _ = extract_source_mask_evidence(path, size=size)

    native_alpha = arr[:, :, 3]
    if int(native_alpha.min()) < 245:
        native_mask = native_alpha > 20
    else:
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
        native_mask = np.linalg.norm(rgb - bg, axis=2) > threshold

    ys, xs = np.nonzero(native_mask)
    if not len(xs):
        image = rgba.convert("RGB").resize((size, size), Image.Resampling.BICUBIC)
        return np.asarray(image), mask, confidence

    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    crop_rgb = arr[y0:y1 + 1, x0:x1 + 1, :3]
    crop_mask = native_mask[y0:y1 + 1, x0:x1 + 1]

    h, w = crop_rgb.shape[:2]
    side = max(h, w)
    canvas = np.full((side, side, 3), 127, dtype=np.uint8)
    mask_canvas = np.zeros((side, side), dtype=bool)
    oy = (side - h) // 2
    ox = (side - w) // 2
    canvas[oy:oy + h, ox:ox + w] = crop_rgb
    mask_canvas[oy:oy + h, ox:ox + w] = crop_mask
    canvas[~mask_canvas] = 127

    image = Image.fromarray(canvas, mode="RGB").resize(
        (size, size),
        Image.Resampling.BICUBIC,
    )
    return np.asarray(image), mask, confidence


def _foreground_histogram(rgb, mask, bins: int = 16):
    np, _ = _deps()
    pixels = rgb[mask]
    if len(pixels) < 8:
        return np.zeros(bins * 3, dtype=np.float32)

    histograms = []
    for channel in range(3):
        hist, _ = np.histogram(
            pixels[:, channel],
            bins=bins,
            range=(0, 256),
            density=False,
        )
        hist = hist.astype(np.float32)
        total = float(hist.sum())
        if total > 0:
            hist /= total
        histograms.append(hist)
    vector = np.concatenate(histograms)
    norm = float(np.linalg.norm(vector))
    if norm > 1e-9:
        vector /= norm
    return vector


def color_histogram_similarity(
    source_path: Path,
    frame_path: Path,
    *,
    size: int = 192,
) -> float:
    np, _ = _deps()
    source_rgb, source_mask, _ = _normalize_rgb_foreground(source_path, size=size)
    frame_rgb, frame_mask, _ = _normalize_rgb_foreground(frame_path, size=size)
    a = _foreground_histogram(source_rgb, source_mask)
    b = _foreground_histogram(frame_rgb, frame_mask)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-9:
        return 0.0
    cosine = float(np.dot(a, b) / denom)
    return max(0.0, min(100.0, cosine * 100.0))


def _as_view(value) -> SourceViewScore:
    if isinstance(value, SourceViewScore):
        return value
    if isinstance(value, dict):
        return SourceViewScore(**value)
    raise TypeError(f"unsupported view evidence: {type(value).__name__}")


def score_source_to_turntable(
    source_images: list[Path],
    matched_views: list[SourceViewScore | dict],
    turntable_frames: list[Path],
    *,
    size: int = 192,
) -> TurntableQAResult:
    if len(source_images) != len(matched_views):
        raise ValueError("source_images and matched_views must have equal length")

    indexed = index_turntable_frames(turntable_frames)
    views = [_as_view(v) for v in matched_views]
    if not source_images:
        return TurntableQAResult(
            score=100.0,
            coverage=0,
            expected_sources=0,
            all_sources_mapped=True,
            catastrophic_mismatches=0,
            ready=True,
            views=[],
        )
    if not indexed or not views:
        return TurntableQAResult(
            score=0.0,
            coverage=0,
            expected_sources=len(source_images),
            all_sources_mapped=False,
            catastrophic_mismatches=0,
            ready=False,
            views=[],
        )

    anchor_azimuth = float(views[0].best_azimuth)
    scored: list[TurntableSourceScore] = []

    for source, view in zip(source_images, views):
        expected = (float(view.best_azimuth) - anchor_azimuth) % 360.0
        selected = select_frame(indexed, expected)
        if selected is None:
            continue
        selected_offset, frame, angular_error = selected

        source_mask, confidence, _ = extract_source_mask_evidence(source, size=size)
        frame_mask, _, _ = extract_source_mask_evidence(frame, size=size)
        silhouette, iou, boundary = score_masks(source_mask, frame_mask)
        color = color_histogram_similarity(source, frame, size=size)

        # Shape remains dominant. Color is deliberately light because lighting and
        # exposure differences between a real photo and renderer are expected.
        combined = 0.82 * silhouette + 0.18 * color

        catastrophic = bool(
            confidence >= 0.70
            and (
                combined < 25.0
                or silhouette < 20.0
                or angular_error > 30.0
            )
        )
        scored.append(
            TurntableSourceScore(
                source=str(source),
                source_azimuth=round(float(view.best_azimuth), 3),
                expected_offset=round(expected, 3),
                selected_offset=round(selected_offset, 3),
                selected_frame=str(frame),
                angular_error=round(angular_error, 3),
                silhouette_score=round(silhouette, 3),
                silhouette_iou=round(iou, 6),
                boundary_f1=round(boundary, 6),
                color_histogram_score=round(color, 3),
                combined_score=round(combined, 3),
                mask_confidence=round(confidence, 4),
                catastrophic_mismatch=catastrophic,
            )
        )

    values = [item.combined_score for item in scored]
    confidences = [item.mask_confidence for item in scored]
    score = (
        aggregate_source_scores_weighted(values, confidences)
        if values
        else 0.0
    )
    catastrophic_count = sum(1 for item in scored if item.catastrophic_mismatch)
    all_mapped = len(scored) == len(source_images)

    # This is a catastrophic-output gate, not a beauty-score gate. It is designed
    # to catch wrong orientation, corrupted turntables and severe source mismatch
    # without rejecting plausible assets for ordinary lighting differences.
    ready = bool(
        all_mapped
        and catastrophic_count == 0
        and score >= 38.0
    )
    return TurntableQAResult(
        score=round(score, 3),
        coverage=len(scored),
        expected_sources=len(source_images),
        all_sources_mapped=all_mapped,
        catastrophic_mismatches=catastrophic_count,
        ready=ready,
        views=scored,
    )


def build_turntable_comparison_sheet(
    result: TurntableQAResult,
    output: Path,
    *,
    cell_size: tuple[int, int] = (280, 280),
) -> Path | None:
    from PIL import Image, ImageDraw, ImageOps

    if not result.views:
        return None

    width = cell_size[0] * 2
    row_height = cell_size[1] + 54
    sheet = Image.new(
        "RGB",
        (width, row_height * len(result.views)),
        (20, 20, 20),
    )
    draw = ImageDraw.Draw(sheet)

    for row, item in enumerate(result.views):
        y = row * row_height
        source = ImageOps.fit(
            Image.open(item.source).convert("RGB"),
            cell_size,
            method=Image.Resampling.LANCZOS,
        )
        frame = ImageOps.fit(
            Image.open(item.selected_frame).convert("RGB"),
            cell_size,
            method=Image.Resampling.LANCZOS,
        )
        sheet.paste(source, (0, y + 54))
        sheet.paste(frame, (cell_size[0], y + 54))

        status = "FAIL" if item.catastrophic_mismatch else "PASS"
        draw.text(
            (8, y + 6),
            (
                f"{status}  score={item.combined_score:.1f}  "
                f"expected={item.expected_offset:.0f} deg  "
                f"frame={item.selected_offset:.0f} deg  "
                f"angular_err={item.angular_error:.1f}"
            ),
            fill=(240, 240, 240),
        )
        draw.text((8, y + 28), "REAL SOURCE", fill=(190, 190, 190))
        draw.text(
            (cell_size[0] + 8, y + 28),
            "FINAL TURNTABLE",
            fill=(190, 190, 190),
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG")
    return output


def write_turntable_report(
    result: TurntableQAResult,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="HAYUYA source-vs-turntable QA.")
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--view-json", type=Path, required=True)
    parser.add_argument("--turntable", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw_views = json.loads(args.view_json.read_text(encoding="utf-8"))
    result = score_source_to_turntable(
        args.source,
        raw_views,
        args.turntable,
    )
    write_turntable_report(result, args.output)
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
