#!/usr/bin/env python3
"""Audit exported Nacht material texture references against image payload files.

The source material audit produces a JSON report with channel values and
Other[] texture references. This tool resolves those names against images
exported by UE Viewer/UModel without assuming a specific image extension.

Third-party image bytes remain external. Only the resolution report is meant
for repository/CI evidence.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

IMAGE_EXTENSIONS = {
    ".tga",
    ".png",
    ".dds",
    ".bmp",
    ".jpg",
    ".jpeg",
}
BUILTIN_TEXTURES = {
    "white",
    "_identitynormalmap",
    "flat_normal",
}


def canonical_name(value: str) -> str:
    text = value.replace("\\", "/").strip().strip('"').strip("'")
    text = text.rsplit("/", 1)[-1]
    return Path(text).stem.lower()


def referenced_textures(report: dict) -> set[str]:
    result: set[str] = set()
    for row in report.get("materials", []):
        if not isinstance(row, dict):
            continue
        channels = row.get("channels", {})
        if isinstance(channels, dict):
            for value in channels.values():
                if isinstance(value, str) and value.strip():
                    result.add(canonical_name(value))
        others = row.get("other_textures", [])
        if isinstance(others, list):
            for value in others:
                if isinstance(value, str) and value.strip():
                    result.add(canonical_name(value))
    return result


def exported_images(root: Path) -> tuple[dict[str, list[str]], Counter]:
    by_name: dict[str, list[str]] = {}
    extensions: Counter = Counter()

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            continue
        extensions[suffix] += 1
        key = path.stem.lower()
        by_name.setdefault(key, []).append(
            path.relative_to(root).as_posix()
        )

    return by_name, extensions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("material_report", type=Path)
    parser.add_argument("export_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = json.loads(
        args.material_report.read_text(encoding="utf-8")
    )
    refs = referenced_textures(report)
    images, extensions = exported_images(args.export_root)

    builtins = sorted(refs & BUILTIN_TEXTURES)
    external_refs = refs - BUILTIN_TEXTURES
    resolved = sorted(name for name in external_refs if name in images)
    missing = sorted(external_refs - images.keys())
    ambiguous = {
        name: paths
        for name, paths in images.items()
        if name in external_refs and len(paths) > 1
    }

    payload = {
        "schemaVersion": 1,
        "format": "xziel_nacht_texture_payload_audit_v1",
        "policy": {
            "sourceTextureNamesPreserved": True,
            "noSilentFallbacks": True,
            "builtinsAreExplicit": sorted(BUILTIN_TEXTURES),
        },
        "summary": {
            "referencedUniqueTextures": len(refs),
            "builtinReferences": len(builtins),
            "externalReferences": len(external_refs),
            "resolvedExternalReferences": len(resolved),
            "missingExternalReferences": len(missing),
            "ambiguousExportNames": len(ambiguous),
            "exportedImageFiles": sum(extensions.values()),
            "exportedUniqueImageStems": len(images),
            "strictReady": not missing and not ambiguous,
        },
        "extensions": dict(sorted(extensions.items())),
        "builtins": builtins,
        "missing": missing,
        "ambiguous": ambiguous,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "XZIEL_NACHT_TEXTURE_PAYLOAD_AUDIT",
        json.dumps(payload["summary"], sort_keys=True),
    )

    if args.strict and (missing or ambiguous):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
