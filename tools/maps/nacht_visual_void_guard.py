#!/usr/bin/env python3
"""Guard Nacht nighttime visual captures against flat near-white void patches.

This deliberately does NOT claim UE/Godot lighting parity. It rejects the
obvious clipped-white regions captured in Stage #208 while keeping interior
captures available as control images. Actual night source fidelity needs a
separate visual comparison with licensed reference screenshots.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def measure(path: Path) -> dict:
    with Image.open(path) as source:
        image = source.convert("RGB")
    width, height = image.size
    if width < 64 or height < 64:
        raise ValueError(f"invalid capture resolution {width}x{height}")
    mask = bytearray(width * height)
    for pos, (red, green, blue) in enumerate(image.getdata()):
        # Large perfectly white areas are evidence of unbound materials,
        # clipped highlights, or open visual gaps. Allow minor RGB variation.
        if min(red, green, blue) >= 250 and max(red, green, blue) - min(red, green, blue) <= 5:
            mask[pos] = 1

    pixels = sum(mask)
    largest = 0
    # Contiguous 4-connected bright regions. A thousand isolated stars or
    # tiny text pixels do not look like the visible Stage #208 map holes.
    for index in range(len(mask)):
        if not mask[index]:
            continue
        size = 0
        stack = [index]
        mask[index] = 0
        while stack:
            current = stack.pop()
            size += 1
            x = current % width
            if x > 0 and mask[current - 1]:
                mask[current - 1] = 0
                stack.append(current - 1)
            if x + 1 < width and mask[current + 1]:
                mask[current + 1] = 0
                stack.append(current + 1)
            if current >= width and mask[current - width]:
                mask[current - width] = 0
                stack.append(current - width)
            if current + width < len(mask) and mask[current + width]:
                mask[current + width] = 0
                stack.append(current + width)
        largest = max(largest, size)
    return {
        "file": path.name,
        "width": width,
        "height": height,
        "near_white_pixels": pixels,
        "near_white_ratio": pixels / (width * height),
        "largest_contiguous_near_white_pixels": largest,
    }


def self_test() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as temp:
        path = Path(temp) / "synthetic.png"
        image = Image.new("RGB", (128, 128), (12, 13, 17))
        # Neutral small specular highlights should not trigger large blob.
        image.putpixel((2, 2), (255, 255, 255))
        image.putpixel((30, 30), (252, 251, 251))
        image.save(path)
        m = measure(path)
        assert m["near_white_pixels"] == 2, m
        assert m["largest_contiguous_near_white_pixels"] == 1, m

        ImageDraw.Draw(image).rectangle((60, 50, 110, 90), fill=(255, 255, 255))
        image.save(path)
        m = measure(path)
        assert m["near_white_pixels"] > 1500, m
        assert m["largest_contiguous_near_white_pixels"] > 1500, m

        # Bright chromatic effects should not be flagged as opaque white.
        image = Image.new("RGB", (128, 128), (255, 250, 128))
        image.save(path)
        assert measure(path)["near_white_pixels"] == 0
    print("XZOGOT_NACHT_VISUAL_GUARD_SELF_TEST_GREEN")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overview", type=Path)
    parser.add_argument("--spawn", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--max-white-ratio", type=float, default=0.005)
    parser.add_argument("--max-white-blob", type=int, default=500)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.overview is None or args.spawn is None or args.report is None:
        parser.error("--overview, --spawn, and --report are required")
    if not (0.0 < args.max_white_ratio < 1.0) or args.max_white_blob < 0:
        parser.error("invalid white-clipping thresholds")
    images = [measure(args.overview), measure(args.spawn)]
    overview, interior = images
    violations = []
    if overview["near_white_ratio"] > args.max_white_ratio:
        violations.append("overview: saturated-white area above threshold")
    if overview["largest_contiguous_near_white_pixels"] > args.max_white_blob:
        violations.append("overview: large contiguous white visual void")
    result = {
        "gate": "nighttime white-void capture guard (not full art parity)",
        "images": images,
        "thresholds": {
            "max_white_ratio": args.max_white_ratio,
            "max_white_blob_pixels": args.max_white_blob,
        },
        "violations": violations,
        "ready": not violations,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("XZOGOT_NACHT_VISUAL_VOID_METRICS " + json.dumps(result, sort_keys=True))
    if violations:
        print("XZOGOT_NACHT_VISUAL_VOID_RED: source screenshot not yet night-art-ready")
        return 3
    print("XZOGOT_NACHT_VISUAL_VOID_GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
