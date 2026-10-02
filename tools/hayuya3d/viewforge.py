#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from adapters import DEFAULT_MODEL_ROOT, backend_python, require_backend

WONDER3D_VIEWS = ("front", "front_right", "right", "back", "left", "front_left")


@dataclass
class ViewForgeOutput:
    backend: str
    source: str
    rgb_views: dict[str, str]
    normal_views: dict[str, str]
    synthetic_reconstruction_views: list[str]
    manifest_path: str


def _native_foreground_rgba(source: Path):
    import numpy as np
    from PIL import Image

    image = Image.open(source).convert("RGBA")
    arr = np.asarray(image).copy()
    alpha = arr[:, :, 3]

    if int(alpha.min()) < 245:
        return image

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
    mask = np.linalg.norm(rgb - bg, axis=2) > threshold

    occupancy = float(mask.mean())
    if occupancy < 0.03 or occupancy > 0.92:
        lum = rgb.mean(axis=2)
        bg_lum = float(bg.mean())
        lum_threshold = max(18.0, float(np.std(corners.mean(axis=1))) * 3.0 + 8.0)
        mask = np.abs(lum - bg_lum) > lum_threshold

    arr[:, :, 3] = mask.astype(np.uint8) * 255
    return Image.fromarray(arr, mode="RGBA")


def prepare_wonder3d_input(source: Path, staging_dir: Path) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    dst = staging_dir / "source.png"
    rgba = _native_foreground_rgba(source)
    rgba.save(dst)
    return dst


def _best_match(raw_root: Path, pattern: str, *, prefer_token: str | None = None) -> Path | None:
    matches = list(raw_root.rglob(pattern))
    if not matches:
        return None
    if prefer_token:
        preferred = [p for p in matches if prefer_token in {part.lower() for part in p.parts}]
        if preferred:
            matches = preferred
    return sorted(matches, key=lambda p: (len(p.parts), str(p)))[0]


def collect_wonder3d_outputs(raw_root: Path, stable_root: Path, source: Path) -> ViewForgeOutput:
    rgb_dir = stable_root / "rgb"
    normal_dir = stable_root / "normals"
    anchor_dir = stable_root / "anchors"
    rgb_dir.mkdir(parents=True, exist_ok=True)
    normal_dir.mkdir(parents=True, exist_ok=True)
    anchor_dir.mkdir(parents=True, exist_ok=True)

    anchor_path = anchor_dir / "source_real.png"
    from PIL import Image
    Image.open(source).convert("RGBA").save(anchor_path, format="PNG")

    rgb_views: dict[str, str] = {}
    normal_views: dict[str, str] = {}

    for view in WONDER3D_VIEWS:
        # Prefer rembg outputs in masked_colors for RGB and scene-level rembg normals.
        rgb = _best_match(raw_root, f"rgb_000_{view}.png", prefer_token="masked_colors")
        if rgb is None:
            rgb = _best_match(raw_root, f"rgb_000_{view}.png")

        normal_candidates = [
            p for p in raw_root.rglob(f"normals_000_{view}.png")
            if "normals" not in {part.lower() for part in p.parts[-2:-1]}
        ]
        normal = sorted(normal_candidates, key=str)[0] if normal_candidates else None
        if normal is None:
            normal = _best_match(raw_root, f"normals_000_{view}.png")

        if rgb is not None:
            dst = rgb_dir / f"{view}_synthetic.png"
            shutil.copy2(rgb, dst)
            rgb_views[view] = str(dst)
        if normal is not None:
            dst = normal_dir / f"{view}_synthetic.png"
            shutil.copy2(normal, dst)
            normal_views[view] = str(dst)

    # Never feed Wonder3D's synthesized front as if it were the user's real anchor.
    synthetic_reconstruction_views = [
        rgb_views[view]
        for view in WONDER3D_VIEWS
        if view != "front" and view in rgb_views
    ]

    manifest = {
        "engine": "HAYUYA ViewForge",
        "backend": "wonder3d",
        "source_real": str(source),
        "source_anchor_copy": str(anchor_path),
        "real_source_overrides_synthetic_front": True,
        "rgb_views": rgb_views,
        "normal_views": normal_views,
        "synthetic_reconstruction_views": synthetic_reconstruction_views,
        "provenance": {
            "real": [str(source)],
            "synthetic_rgb": list(rgb_views.values()),
            "synthetic_normals": list(normal_views.values()),
        },
    }
    manifest_path = stable_root / "viewforge_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if len(rgb_views) < 4:
        raise RuntimeError(
            f"Wonder3D output incomplete: expected >=4 RGB views, found {len(rgb_views)} under {raw_root}"
        )

    return ViewForgeOutput(
        backend="wonder3d",
        source=str(source),
        rgb_views=rgb_views,
        normal_views=normal_views,
        synthetic_reconstruction_views=synthetic_reconstruction_views,
        manifest_path=str(manifest_path),
    )


def generate_wonder3d_views(
    source: Path,
    out_dir: Path,
    *,
    seed: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> ViewForgeOutput:
    repo = require_backend("wonder3d", model_root)
    source = source.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = out_dir / "input"
    raw_dir = out_dir / "raw"
    stable_dir = out_dir / "stable"
    prepared = prepare_wonder3d_input(source, staging_dir)

    cmd = [
        backend_python("wonder3d"),
        "-m",
        "accelerate.commands.launch",
        "--config_file",
        str((repo / "1gpu.yaml").resolve()),
        str((repo / "test_mvdiffusion_seq.py").resolve()),
        "--config",
        str((repo / "configs" / "mvdiffusion-joint-ortho-6views.yaml").resolve()),
        f"validation_dataset.root_dir={staging_dir.resolve()}",
        "validation_dataset.filepaths=['source.png']",
        f"save_dir={raw_dir.resolve()}",
        f"seed={seed}",
    ]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=repo, check=True)

    return collect_wonder3d_outputs(raw_dir, stable_dir, source)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="HAYUYA ViewForge: one-image RGB+normal expansion.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1993)
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    args = parser.parse_args()

    result = generate_wonder3d_views(
        args.input,
        args.output,
        seed=args.seed,
        model_root=args.model_root,
    )
    print("HAYUYA_VIEWFORGE_READY")
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
