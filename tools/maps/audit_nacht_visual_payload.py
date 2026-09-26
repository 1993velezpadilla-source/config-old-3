#!/usr/bin/env python3
"""Audit a mounted Pavlov/BO3 Nacht visual payload against the persisted scene reference.

The repository intentionally stores only reference metadata. This tool proves whether
an extracted user-owned/licensed Pavlov payload actually contains every UAsset package
referenced by the 492-mesh Nacht scene inventory. It never silently substitutes stock
NZ:P content for a missing source asset.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSETS = ROOT / "assets/nacht_reference/pavlov_scene_reference/assets.json"
DEFAULT_REPORT = ROOT / "build/nacht_visual_payload_report.json"

UASSET_RE = re.compile(r"(?i)[^\r\n]*?\.uasset")


def expected_uasset(source_path: str) -> str:
    value = source_path.replace("\\", "/").strip()
    if not value.startswith("/Game/"):
        raise ValueError(f"unsupported Unreal source path: {source_path!r}")
    rel = value[len("/Game/"):].lstrip("/")
    return ("Pavlov/Content/" + rel + ".uasset").lower()


def canonical_entry(raw: str) -> str | None:
    value = raw.replace("\\", "/").strip().strip('"').strip("'")
    low = value.lower()
    end = low.find(".uasset")
    if end < 0:
        return None
    value = value[: end + len(".uasset")]
    low = value.lower()

    marker = "pavlov/content/"
    pos = low.find(marker)
    if pos >= 0:
        return value[pos:].lower()

    marker = "custommaps/"
    pos = low.find(marker)
    if pos >= 0:
        return ("Pavlov/Content/" + value[pos:]).lower()

    marker = "/game/"
    pos = low.find(marker)
    if pos >= 0:
        return ("Pavlov/Content/" + value[pos + len(marker):]).lower()

    return value.lstrip("./").lower()


def entries_from_index(path: Path) -> set[str]:
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        entry = canonical_entry(line)
        if entry:
            found.add(entry)
    return found


def entries_from_root(root: Path) -> set[str]:
    found: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".uasset":
            continue
        rel = path.relative_to(root).as_posix()
        entry = canonical_entry(rel)
        if entry:
            found.add(entry)
    return found


def load_reference(path: Path) -> tuple[list[dict], set[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    meshes = payload.get("meshes")
    if not isinstance(meshes, list):
        raise SystemExit("reference assets.json has no meshes list")
    declared = payload.get("uniqueMeshCount")
    ids = [row.get("id") for row in meshes]
    paths = [row.get("sourcePath") for row in meshes]
    if declared != 492:
        raise SystemExit(f"expected 492 declared meshes, got {declared}")
    if len(meshes) != declared or len(set(ids)) != declared or len(set(paths)) != declared:
        raise SystemExit("Nacht visual reference inventory is not uniquely 492 meshes")
    expected = {expected_uasset(p) for p in paths}
    if len(expected) != declared:
        raise SystemExit("normalized visual asset paths collide")
    return meshes, expected


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    ap.add_argument("--content-root", type=Path)
    ap.add_argument("--pak-index", type=Path)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.content_root and args.pak_index:
        raise SystemExit("choose --content-root or --pak-index, not both")

    meshes, expected = load_reference(args.assets)

    if args.self_check and not args.content_root and not args.pak_index:
        print(json.dumps({
            "status": "MANIFEST_OK",
            "expectedUniqueMeshes": len(meshes),
            "payloadMounted": False,
            "note": "Reference metadata is valid; no visual payload was supplied.",
        }, sort_keys=True))
        return 0

    if args.pak_index:
        available = entries_from_index(args.pak_index)
        input_kind = "pak_index"
        input_value = str(args.pak_index)
    elif args.content_root:
        if not args.content_root.is_dir():
            raise SystemExit(f"content root is not a directory: {args.content_root}")
        available = entries_from_root(args.content_root)
        input_kind = "content_root"
        input_value = str(args.content_root)
    else:
        raise SystemExit("supply --content-root, --pak-index, or --self-check")

    resolved = sorted(expected & available)
    missing = sorted(expected - available)
    report = {
        "schemaVersion": 1,
        "mapId": "bo3_nacht_reference",
        "source": {
            "kind": input_kind,
            "value": input_value,
        },
        "policy": {
            "expectedUniqueMeshes": 492,
            "noSilentFallbacks": True,
            "requireAllReferencedUassets": True,
        },
        "summary": {
            "expected": len(expected),
            "resolved": len(resolved),
            "missing": len(missing),
            "payloadReady": not missing,
        },
        "missing": missing,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("XZIEL_NACHT_VISUAL_PAYLOAD", json.dumps(report["summary"], sort_keys=True))

    if args.strict and missing:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
