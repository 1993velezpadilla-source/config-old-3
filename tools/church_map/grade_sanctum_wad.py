#!/usr/bin/env python3
"""Create opt-in Sanctum of Ash WAD textures from the NZ:P originals.

The Android BSP framebuffer exposed fully clipped white floor and burnt-out
stone in a real 2400x1080 screenshot. Keep the existing original texture art,
but pre-grade *copies* for this map only; never alter stock NZ:P WAD files,
the user's Tripo PBR, the weapons, or other maps.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageEnhance, ImageStat

# Quake miptex names MUST fit into 15 ASCII characters plus a NUL terminator.
MATERIALS = {
    "sanctum_floor": ("loop_tile_maju2.png", 0.44, 1.23),
    "sanctum_wall": ("loop_stone_ruff.png", 0.64, 1.05),
    "sanctum_ceiling": ("loop_stone_grav.png", 0.63, 1.12),
}


def build(wad_root: Path) -> dict:
    if not wad_root.is_dir():
        raise FileNotFoundError(f"Expected NZ:P Loop WAD source directory: {wad_root}")
    report = {}
    for target, (origin, brightness, contrast) in MATERIALS.items():
        assert len(target.encode("ascii")) <= 15, "GoldSrc WAD texture name truncated"
        source = wad_root / origin
        if not source.is_file():
            raise FileNotFoundError(f"Missing original NZ:P WAD source: {source}")
        with Image.open(source) as src:
            original = src.convert("RGB")
        # Do not resize: preserve the source grain, UVs and BSP mip layout.
        graded = ImageEnhance.Contrast(original).enhance(contrast)
        graded = ImageEnhance.Brightness(graded).enhance(brightness)
        stats_src = ImageStat.Stat(original)
        stats_new = ImageStat.Stat(graded)
        old_luma = sum(stats_src.mean) / 3
        new_luma = sum(stats_new.mean) / 3
        if not (0.25 * old_luma < new_luma < 0.80 * old_luma):
            raise AssertionError(f"{target}: grading didn't lower overexposed albedo")
        if max(stats_new.stddev) < 5:
            raise AssertionError(f"{target}: flat texture rejected")
        dest = wad_root / f"{target}.png"
        graded.save(dest, format="PNG", optimize=True)
        report[target] = {
            "original": origin,
            "size": list(graded.size),
            "brightness": brightness,
            "contrast": contrast,
            "original_mean": round(old_luma, 2),
            "graded_mean": round(new_luma, 2),
            "graded_stddev": [round(v, 2) for v in stats_new.stddev],
            "bytes": dest.stat().st_size,
        }
        print("SANCTUM_REAL_ART_GRADED", target, report[target], flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wad-root", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = build(args.wad_root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("SANCTUM_NONCLIPPED_WAD_ART_GREEN", flush=True)


if __name__ == "__main__":
    main()
