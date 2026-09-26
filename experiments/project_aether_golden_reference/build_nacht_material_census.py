#!/usr/bin/env python3
"""Build a metadata-only Nacht material/texture census from retoc list output.

No cooked payload is copied into the repository. This consumes the textual
IoStore listing produced by the already-verified Project Aether audit workflow
and emits a compact JSON index suitable for cross-source comparison against
XZIEL/Pavlov material slot names.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

NACHT_TOKENS = (
    "zombie_cod5_prototype",
    "nacht",
    "prototype",
)

MATERIAL_TOKENS = (
    "material",
    "mtl_",
    "_mat",
    "_mi",
    "t7_",
    "berlin_",
    "okinawa_",
    "peleliu_",
    "eb_art_",
)

TEXTURE_TOKENS = (
    "texture",
    "diffuse",
    "albedo",
    "basecolor",
    "base_color",
    "normal",
    "specular",
    "rough",
    "metal",
    "emissive",
    "opacity",
    "decal",
)

PATH_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_./\\-]+\.(?:uasset|uexp|ubulk|uptnl|umap))",
    re.IGNORECASE,
)


def normalized_path(line: str) -> str | None:
    matches = PATH_RE.findall(line)
    if not matches:
        return None
    return matches[-1].replace("\\", "/")


def base_name(path: str) -> str:
    return Path(path).stem.lower()


def classify(path: str) -> tuple[bool, bool, bool]:
    low = path.lower()
    nacht = any(token in low for token in NACHT_TOKENS)
    material = any(token in low for token in MATERIAL_TOKENS)
    texture = any(token in low for token in TEXTURE_TOKENS)
    return nacht, material, texture


def build(lines: list[str]) -> dict:
    all_paths: set[str] = set()
    nacht_paths: set[str] = set()
    material_paths: set[str] = set()
    texture_paths: set[str] = set()

    for line in lines:
        path = normalized_path(line)
        if not path:
            continue
        all_paths.add(path)
        nacht, material, texture = classify(path)
        if nacht:
            nacht_paths.add(path)
        if nacht and material:
            material_paths.add(path)
        if nacht and texture:
            texture_paths.add(path)

    by_basename: dict[str, list[str]] = {}
    for path in sorted(nacht_paths):
        by_basename.setdefault(base_name(path), []).append(path)

    return {
        "format": "xziel_aether_nacht_material_census_v1",
        "source": "Project Aether public cooked build / retoc list",
        "policy": {
            "payloadCommitted": False,
            "metadataOnly": True,
            "authority": "reference-only until cross-source validation",
        },
        "summary": {
            "allPackagePaths": len(all_paths),
            "nachtPackagePaths": len(nacht_paths),
            "nachtMaterialCandidates": len(material_paths),
            "nachtTextureCandidates": len(texture_paths),
            "uniqueNachtBasenames": len(by_basename),
        },
        "nachtMaterialCandidates": sorted(material_paths),
        "nachtTextureCandidates": sorted(texture_paths),
        "nachtByBasename": {
            key: value
            for key, value in sorted(by_basename.items())
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("retoc_list", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    lines = args.retoc_list.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()
    report = build(lines)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "XZIEL_AETHER_NACHT_MATERIAL_CENSUS",
        json.dumps(report["summary"], sort_keys=True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
