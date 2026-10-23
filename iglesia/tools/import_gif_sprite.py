#!/usr/bin/env python3
"""Turn an OWNER-SUPPLIED animated MP40 GIF into individual transparent PNGs.

GIF is an optional authoring source; Godot never decodes GIF per gameplay
frame. This utility does NOT create gun artwork or alter/borrow military assets.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageSequence

PROFILES = {
    12: {"idle":1,"ads_idle":1,"fire":2,"ads_fire":1,"reload":5,"sprint":1,"equip":1},
    15: {"idle":1,"ads_idle":1,"fire":2,"ads_fire":2,"reload":7,"sprint":1,"equip":1},
    24: {"idle":1,"ads_idle":1,"fire":4,"ads_fire":3,"reload":12,"sprint":1,"equip":2},
}
LIMIT = (768, 512)


def convert(source: Path, output: Path, role: str, profile: int) -> int:
    expected = PROFILES[profile][role]
    if not source.is_file():
        raise ValueError(f"OWNER_GIF_NOT_FOUND: {source}")
    if source.suffix.lower() not in (".gif", ".apng", ".png"):
        raise ValueError("ONLY_ANIMATED_GIF_OR_PNG_AUTHORING_FILES")
    with Image.open(source) as movie:
        total = getattr(movie, "n_frames", 1)
        if total != expected:
            raise ValueError(f"FRAME_COUNT_RED: {role} in profile {profile} requires "
                             f"{expected} images, GIF has {total}")
        new_frames = []
        for i in range(total):
            movie.seek(i)
            image = movie.convert("RGBA")
            if image.width > LIMIT[0] or image.height > LIMIT[1]:
                raise ValueError(f"MOBILE_TEXTURE_LIMIT_RED: {image.size} > {LIMIT}")
            alpha = image.getchannel("A")
            if alpha.getextrema()[0] == 255 or alpha.getbbox() is None:
                raise ValueError(f"TRANSPARENT_BACKGROUND_REQUIRED at frame {i}")
            new_frames.append(image.copy())
    output.mkdir(parents=True, exist_ok=True)
    for index, image in enumerate(new_frames):
        target = output / f"{role}_{index:02d}.png"
        image.save(target, optimize=True)
        print(f"IGLESIA_OWNER_2D_FRAME_STAGED {target.name} {image.width}x{image.height}")
    return len(new_frames)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--role", required=True, choices=tuple(PROFILES[24]))
    ap.add_argument("--profile", type=int, choices=tuple(PROFILES), default=15)
    ap.add_argument("--output", type=Path,
                    default=Path("iglesia/assets/weapons/mp40_nun_2d"))
    a = ap.parse_args()
    convert(a.source, a.output, a.role, a.profile)


if __name__ == "__main__":
    main()
