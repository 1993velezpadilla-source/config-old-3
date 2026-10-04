#!/usr/bin/env python3
"""Install validated split gift packs into a Xogot project.

Usage:
  python tools/gifts/install_runtime_packs.py \
      --packs-dir /path/to/gift_runtime_packs \
      --project-root xogot

The manifest is authoritative. Every archive is SHA-256 verified before
extraction, and every expected Model_XX.glb must be present afterward.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from dequantize_godot_glb import convert as dequantize_glb

MANIFEST_REL = Path("assets/gifts/gift_runtime_pack_manifest.json")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(message: str) -> None:
    raise SystemExit("XZOGOT_GIFT_PACK_INSTALL_FAIL: " + message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packs-dir", type=Path, required=True)
    ap.add_argument("--project-root", type=Path, default=Path("xogot"))
    args = ap.parse_args()

    project = args.project_root.resolve()
    packs_dir = args.packs_dir.resolve()
    manifest_path = project / MANIFEST_REL
    if not manifest_path.is_file():
        fail(f"manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    target_root = project / "assets" / "gifts_split"
    target_root.mkdir(parents=True, exist_ok=True)

    godot_fixed = 0
    with tempfile.TemporaryDirectory(prefix="xzogot-gifts-") as td:
        staging = Path(td)
        for pack in manifest["packs"]:
            archive = packs_dir / pack["archive"]
            if not archive.is_file():
                fail(f"archive missing: {archive.name}")
            actual_size = archive.stat().st_size
            if actual_size != int(pack["archive_bytes"]):
                fail(f"size mismatch {archive.name}: {actual_size}")
            actual_hash = sha256(archive)
            if actual_hash.lower() != str(pack["sha256"]).lower():
                fail(f"sha256 mismatch: {archive.name}")

            bundle = str(pack["bundle"])
            bundle_stage = staging / bundle
            bundle_stage.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as zf:
                bad = zf.testzip()
                if bad:
                    fail(f"corrupt zip entry {archive.name}: {bad}")
                zf.extractall(staging)

            extracted = staging / bundle
            if not extracted.is_dir():
                fail(f"bundle root missing after extraction: {bundle}")
            expected = int(pack["models"])
            for i in range(1, expected + 1):
                model = extracted / f"Model_{i:02d}.glb"
                if not model.is_file() or model.stat().st_size <= 0:
                    fail(f"missing model {bundle}/{model.name}")

            destination = target_root / bundle
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(extracted, destination)
            # Godot 4.6.x cannot import KHR_mesh_quantization. Expand only the
            # quantized vertex attributes to FLOAT; topology/UVs/textures stay exact.
            for model in sorted(destination.glob("Model_*.glb")):
                converted_attrs, _converted_values = dequantize_glb(model)
                if converted_attrs > 0:
                    godot_fixed += 1
            print(
                "XZOGOT_GIFT_PACK_INSTALLED",
                bundle,
                f"{expected}/{expected}",
                actual_hash,
            )

    installed = 0
    for pack in manifest["packs"]:
        bundle = target_root / str(pack["bundle"])
        installed += len(list(bundle.glob("Model_*.glb")))
    expected_total = int(manifest["totals"]["models"])
    if installed != expected_total:
        fail(f"model count {installed}/{expected_total}")

    print("XZOGOT_GIFT_GODOT_COMPAT_READY", godot_fixed, installed)
    print("XZOGOT_GIFT_PACK_INSTALL_GREEN", installed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
