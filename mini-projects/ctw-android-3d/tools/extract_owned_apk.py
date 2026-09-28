#!/usr/bin/env python3
"""Extract the minimum CTW Android 4.4.243 inputs from a user-owned APK.

The script never modifies the source APK. It validates the expected arm64
layout, copies only the files needed by the mod pipeline, and writes SHA-256
hashes so binary patches cannot accidentally be applied to the wrong build.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

REQUIRED = {
    "assets/game.pak": "game.pak",
    "assets/dxt.bin": "dxt.bin",
    "lib/arm64-v8a/libGame.so": "libGame.so",
    "lib/arm64-v8a/libopenal.so": "libopenal.so",
}

OPTIONAL_PREFIXES = (
    "assets/",
)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: extract_owned_apk.py <gtactw.apk> <output-dir>")
        return 2

    apk = Path(sys.argv[1]).expanduser().resolve()
    out = Path(sys.argv[2]).expanduser().resolve()

    if not apk.is_file():
        print(f"ERROR: APK not found: {apk}")
        return 2

    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source_apk": apk.name,
        "files": {},
        "missing": [],
    }

    with zipfile.ZipFile(apk, "r") as zf:
        names = set(zf.namelist())
        for member, dest_name in REQUIRED.items():
            if member not in names:
                manifest["missing"].append(member)
                continue
            dest = out / dest_name
            with zf.open(member) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            manifest["files"][dest_name] = {
                "apk_member": member,
                "size": dest.stat().st_size,
                "sha256": sha256(dest),
            }

        # Record the asset inventory without copying the whole copyrighted data set.
        asset_names = sorted(n for n in names if n.startswith(OPTIONAL_PREFIXES))
        manifest["asset_inventory"] = asset_names

    manifest_path = out / "ctw_input_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if manifest["missing"]:
        print("INPUT_RED")
        for name in manifest["missing"]:
            print(f"missing: {name}")
        print(f"manifest: {manifest_path}")
        return 1

    print("INPUT_GREEN")
    for name, meta in manifest["files"].items():
        print(f"{name}: {meta['size']} bytes sha256={meta['sha256']}")
    print(f"manifest: {manifest_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
