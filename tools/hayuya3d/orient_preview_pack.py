#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def parse_args():
    p = argparse.ArgumentParser(
        description="Orient HAYUYA preview front/back labels from a source front reference."
    )
    p.add_argument("--reference", required=True, type=Path)
    p.add_argument("--render-dir", required=True, type=Path)
    return p.parse_args()


def _foreground_mask(img: Image.Image) -> np.ndarray:
    rgba = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    alpha = rgba[..., 3]
    if int(alpha.max()) - int(alpha.min()) > 32 and np.count_nonzero(alpha > 20):
        return alpha > 20

    rgb = rgba[..., :3].astype(np.float32)
    h, w, _ = rgb.shape
    s = max(4, min(h, w) // 24)
    corners = np.concatenate([
        rgb[:s, :s].reshape(-1, 3),
        rgb[:s, -s:].reshape(-1, 3),
        rgb[-s:, :s].reshape(-1, 3),
        rgb[-s:, -s:].reshape(-1, 3),
    ], axis=0)
    bg = np.median(corners, axis=0)
    dist = np.linalg.norm(rgb - bg[None, None, :], axis=2)
    return dist > max(14.0, float(np.percentile(dist, 60)) * 0.45)


def _normalized(path: Path, size: int = 192):
    img = Image.open(path).convert("RGBA")
    mask = _foreground_mask(img)
    ys, xs = np.where(mask)
    if not len(xs):
        raise RuntimeError(f"no foreground: {path}")

    pad_x = max(2, int((xs.max() - xs.min() + 1) * 0.04))
    pad_y = max(2, int((ys.max() - ys.min() + 1) * 0.04))
    x0 = max(0, int(xs.min()) - pad_x)
    x1 = min(img.width, int(xs.max()) + pad_x + 1)
    y0 = max(0, int(ys.min()) - pad_y)
    y1 = min(img.height, int(ys.max()) + pad_y + 1)

    crop = img.crop((x0, y0, x1, y1))
    crop_mask = Image.fromarray((mask[y0:y1, x0:x1] * 255).astype(np.uint8), "L")

    scale = min((size * 0.90) / crop.width, (size * 0.90) / crop.height)
    nw = max(1, int(round(crop.width * scale)))
    nh = max(1, int(round(crop.height * scale)))
    crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)
    crop_mask = crop_mask.resize((nw, nh), Image.Resampling.NEAREST)

    canvas = Image.new("RGB", (size, size), (127, 127, 127))
    mask_canvas = Image.new("L", (size, size), 0)
    ox = (size - nw) // 2
    oy = (size - nh) // 2
    canvas.paste(crop.convert("RGB"), (ox, oy), crop_mask)
    mask_canvas.paste(crop_mask, (ox, oy))

    gray = np.asarray(canvas.convert("L"), dtype=np.float32) / 255.0
    edge = np.asarray(
        canvas.convert("L").filter(ImageFilter.FIND_EDGES),
        dtype=np.float32,
    ) / 255.0
    m = np.asarray(mask_canvas, dtype=np.uint8) > 0
    rgb = np.asarray(canvas, dtype=np.float32) / 255.0
    return rgb, gray, edge, m


def _corr(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    av = a[mask].astype(np.float32).reshape(-1)
    bv = b[mask].astype(np.float32).reshape(-1)
    if len(av) < 64:
        return 0.0
    av -= float(av.mean())
    bv -= float(bv.mean())
    den = float(np.linalg.norm(av) * np.linalg.norm(bv))
    return float(np.dot(av, bv) / den) if den > 1e-8 else 0.0


def _hist(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    vals = rgb[mask]
    if not len(vals):
        return np.zeros(48, dtype=np.float32)
    chunks = []
    for c in range(3):
        h, _ = np.histogram(vals[:, c], bins=16, range=(0.0, 1.0), density=True)
        chunks.append(h.astype(np.float32))
    out = np.concatenate(chunks)
    n = float(np.linalg.norm(out))
    return out / n if n > 1e-8 else out


def score_pair(reference: Path, candidate: Path) -> dict:
    rr, rg, re, rm = _normalized(reference)
    cr, cg, ce, cm = _normalized(candidate)
    joint = rm | cm
    inter = float(np.count_nonzero(rm & cm))
    union = float(np.count_nonzero(joint))
    mask_iou = inter / union if union else 0.0
    gray_corr = (_corr(rg, cg, joint) + 1.0) * 0.5
    edge_corr = (_corr(re, ce, joint) + 1.0) * 0.5
    hist_corr = float(np.dot(_hist(rr, rm), _hist(cr, cm)))
    score = (
        0.35 * mask_iou
        + 0.30 * gray_corr
        + 0.20 * edge_corr
        + 0.15 * hist_corr
    )
    return {
        "score": round(float(score), 6),
        "mask_iou": round(mask_iou, 6),
        "gray_corr": round(gray_corr, 6),
        "edge_corr": round(edge_corr, 6),
        "hist_corr": round(hist_corr, 6),
    }


def _swap(render_dir: Path, a: str, b: str):
    pa = render_dir / f"{a}.png"
    pb = render_dir / f"{b}.png"
    if not pa.is_file() or not pb.is_file():
        return
    tmp = render_dir / f".__swap_{a}_{b}.png"
    pa.replace(tmp)
    pb.replace(pa)
    tmp.replace(pb)


def main():
    a = parse_args()
    reference = a.reference.resolve()
    render_dir = a.render_dir.resolve()
    if not reference.is_file():
        raise FileNotFoundError(reference)

    pos_y = score_pair(reference, render_dir / "front.png")
    neg_y = score_pair(reference, render_dir / "opposite.png")
    swapped = neg_y["score"] > pos_y["score"]
    if swapped:
        for left, right in (
            ("front", "opposite"),
            ("three_quarter", "three_quarter_opposite"),
            ("face", "face_opposite"),
        ):
            _swap(render_dir, left, right)

    confidence = abs(float(pos_y["score"]) - float(neg_y["score"]))
    manifest_path = render_dir / "preview_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["orientation"] = {
        "method": "source_front_reference_v1",
        "reference": str(a.reference),
        "raw_positive_y": pos_y,
        "raw_negative_y": neg_y,
        "selected_raw_axis": "-Y" if swapped else "+Y",
        "swapped_front_back": swapped,
        "confidence_delta": round(confidence, 6),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print("HAYUYA_PREVIEW_ORIENTATION", json.dumps(manifest["orientation"]))


if __name__ == "__main__":
    main()
