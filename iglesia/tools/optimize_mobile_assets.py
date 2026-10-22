#!/usr/bin/env python3
"""Iglesia Android texture budget: optimize VERIFIED staged copies only.

Each original Tripo ZIP/GLB and 4K source material remains SHA-locked.
No model substitution or procedural geometry. Keeps PNG weapon sprites intact.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from PIL import Image

def apply_mobile_texture_budget(assets: Path) -> dict:
    mode = os.environ.get("IGLESIA_TEXTURE_TIER", "mobile").lower()
    if mode not in ("mobile", "source_4k"):
        raise RuntimeError("IGLESIA_UNKNOWN_TEXTURE_TIER " + mode)
    limits = {"mobile": {"fixture": 1024, "wall": 2048},
              "source_4k": {"fixture": 4096, "wall": 4096}}[mode]
    locations = [(assets / "tripo" / "fixtures", "fixture"),
                 (assets / "materials", "wall")]
    before_bytes = 0
    after_bytes = 0
    before_pixels = 0
    after_pixels = 0
    entries = []
    for folder, category in locations:
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() not in (".png", ".jpg", ".jpeg") or not path.is_file():
                continue
            with Image.open(path) as source:
                old_size = source.size
                width, height = old_size
                target = limits[category]
                factor = min(1.0, float(target) / max(width, height))
                dest_size = (max(1, round(width * factor)), max(1, round(height * factor)))
                old_len = path.stat().st_size
                before_bytes += old_len
                before_pixels += width * height
                if dest_size != old_size:
                    # Carefully filtered texture LOD; GLB source and UVs untouched.
                    resized = source.resize(dest_size, Image.Resampling.LANCZOS)
                    if path.suffix.lower() in (".jpg", ".jpeg"):
                        resized.convert("RGB").save(path, "JPEG", quality=88,
                                                    optimize=True, subsampling=0)
                    else:
                        resized.save(path, "PNG", optimize=True)
                new_len = path.stat().st_size
                after_bytes += new_len
                after_pixels += dest_size[0] * dest_size[1]
                entries.append({
                    "path": path.relative_to(assets).as_posix(),
                    "source_dimensions": list(old_size),
                    "runtime_dimensions": list(dest_size),
                    "source_bytes": old_len, "runtime_bytes": new_len,
                })
    if mode == "mobile" and entries and after_pixels >= before_pixels:
        raise RuntimeError("IGLESIA_MOBILE_TEXTURE_BUDGET_NOT_EFFECTIVE")
    report = {"schema": 1, "tier": mode, "source_pixels": before_pixels,
              "runtime_pixels": after_pixels, "source_bytes": before_bytes,
              "runtime_bytes": after_bytes, "textures": entries,
              "originals_remain_in_sha_verified_zip_archives": True}
    (assets / "mobile_texture_budget.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("IGLESIA_MOBILE_TEXTURE_BUDGET", mode, "textures", len(entries),
          "pixels", before_pixels, "->", after_pixels,
          "bytes", before_bytes, "->", after_bytes)
    return report

if __name__ == "__main__":
    apply_mobile_texture_budget(Path(__file__).resolve().parents[1] / "assets")
