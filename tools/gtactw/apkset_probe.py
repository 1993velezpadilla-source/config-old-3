#!/usr/bin/env python3
"""Locate CTW runtime files across monolithic APKs and split-APK containers."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

REQUIRED = (
    "assets/game.pak",
    "assets/dxt.bin",
    "assets/buttonconfig",
    "assets/e_ckna01.gxt",
    "assets/ctw_iphone_intro.mp4",
    "lib/arm64-v8a/libGame.so",
    "lib/arm64-v8a/libopenal.so",
)

CONTAINER_SUFFIXES = {".apkm", ".xapk", ".apks", ".zip"}


def sha256_zip_entry(zf: zipfile.ZipFile, name: str) -> str:
    h = hashlib.sha256()
    with zf.open(name, "r") as fp:
        while True:
            chunk = fp.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def collect_apks(source: Path, temp_root: Path) -> list[tuple[str, Path]]:
    if source.is_dir():
        apks = sorted(p for p in source.iterdir() if p.suffix.lower() == ".apk")
        if not apks:
            raise ValueError("split directory contains no .apk files")
        return [(p.name, p) for p in apks]

    suffix = source.suffix.lower()
    if suffix == ".apk":
        return [(source.name, source)]

    if suffix not in CONTAINER_SUFFIXES:
        raise ValueError(
            "input must be an .apk, split directory, .apkm, .xapk, .apks or .zip"
        )

    if not zipfile.is_zipfile(source):
        raise ValueError("bundle container is not a ZIP-compatible archive")

    out = []
    with zipfile.ZipFile(source, "r") as outer:
        apk_infos = [
            info for info in outer.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".apk")
        ]
        if not apk_infos:
            raise ValueError("bundle container contains no nested .apk files")

        for i, info in enumerate(apk_infos):
            safe = f"{i:03d}_{Path(info.filename).name}"
            dest = temp_root / safe
            with outer.open(info, "r") as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            out.append((info.filename, dest))
    return out


def inspect_set(source: Path, extract_dir: Path | None = None) -> dict:
    if not source.exists():
        raise FileNotFoundError(source)

    with tempfile.TemporaryDirectory(prefix="ctw-apkset-") as td:
        temp_root = Path(td)
        apks = collect_apks(source, temp_root)

        found: dict[str, list[dict]] = {name: [] for name in REQUIRED}
        apk_inventory = []

        for display_name, apk_path in apks:
            if not zipfile.is_zipfile(apk_path):
                raise ValueError(f"{display_name} is not a valid APK/ZIP")

            with zipfile.ZipFile(apk_path, "r") as zf:
                names = set(zf.namelist())
                matched = []
                for logical in REQUIRED:
                    if logical not in names:
                        continue
                    info = zf.getinfo(logical)
                    item = {
                        "split": display_name,
                        "entry": logical,
                        "size": info.file_size,
                        "sha256": sha256_zip_entry(zf, logical),
                    }
                    found[logical].append(item)
                    matched.append(logical)

                apk_inventory.append({
                    "split": display_name,
                    "size": apk_path.stat().st_size,
                    "matched_required": matched,
                })

        conflicts = {}
        selected = {}
        for logical, matches in found.items():
            if not matches:
                continue

            hashes = {m["sha256"] for m in matches}
            if len(hashes) > 1:
                conflicts[logical] = matches
                continue

            selected[logical] = matches[0]

        if conflicts:
            raise ValueError(
                "conflicting duplicate runtime files across splits: "
                + ", ".join(sorted(conflicts))
            )

        missing = [name for name in REQUIRED if name not in selected]

        if extract_dir is not None:
            extract_dir.mkdir(parents=True, exist_ok=True)
            source_map = {display: path for display, path in apks}
            for logical, meta in selected.items():
                dest = extract_dir / logical
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(source_map[meta["split"]], "r") as zf:
                    with zf.open(logical, "r") as src, dest.open("wb") as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)

        return {
            "source": str(source),
            "apk_count": len(apks),
            "apks": apk_inventory,
            "selected": selected,
            "missing_required": missing,
            "ok": not missing,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--extract", type=Path)
    ap.add_argument("--allow-missing", action="store_true")
    args = ap.parse_args()

    try:
        report = inspect_set(args.source, args.extract)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    print(json.dumps(report, indent=2))
    if report["missing_required"] and not args.allow_missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
