#!/usr/bin/env python3
"""Atomically emit the CTW native runtime profile + adapter binding headers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import adapter_catalog
import adapter_emit_c
import loader_variant
import profile_emit_c
import profile_verify_binary


PROFILE_HEADER = "ctw_profiles_generated.h"
ADAPTER_HEADER = "ctw_adapters_generated.h"
MANIFEST = "ctw_runtime_bundle.json"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def emit_runtime_bundle(
    libgame: Path,
    profile_path: Path,
    catalog_path: Path,
    out_dir: Path,
) -> dict:
    profile_obj = json.loads(profile_path.read_text(encoding="utf-8"))
    catalog_obj = adapter_catalog.load_catalog(catalog_path)

    binary = profile_verify_binary.verify_profile(libgame, profile_path)
    if not binary["ok"]:
        raise ValueError("profile does not match the exact libGame.so")

    adapters = adapter_catalog.validate_profile_adapters(
        profile_obj,
        catalog_obj,
    )
    if not adapters["ready"]:
        missing = [
            key
            for key, item in adapters["targets"].items()
            if not item["ready"]
        ]
        raise ValueError(
            "native adapters not ready for: " + ", ".join(missing)
        )

    variant = loader_variant.select_loader_variant(profile_obj)
    if not variant["ready"]:
        raise ValueError(
            "verified hook backend strategy is incomplete"
        )

    native_profile = profile_emit_c.load_verified_profile(profile_path)
    profile_header = profile_emit_c.emit_header([native_profile])

    bindings = adapter_emit_c.adapters_from_profile(
        profile_path,
        catalog_obj,
    )
    adapter_header = adapter_emit_c.emit_header(bindings)

    manifest = {
        "ok": True,
        "libgame": str(libgame),
        "profile": str(profile_path),
        "adapter_catalog": str(catalog_path),
        "loader_variant": variant["loader_variant"],
        "profile_header_sha256": _sha256_text(profile_header),
        "adapter_header_sha256": _sha256_text(adapter_header),
        "adapter_count": len({
            item["adapter"] for item in bindings
        }),
        "targets": list(profile_emit_c.TARGET_KEYS),
        "binary_fingerprint": binary["actual_fingerprint"],
        "note": (
            "Both generated headers were validated from the same exact "
            "profile/binary/catalog tuple and written as one bundle."
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="ctw_runtime_bundle_",
        dir=out_dir,
    ) as td:
        stage = Path(td)
        (stage / PROFILE_HEADER).write_text(
            profile_header,
            encoding="utf-8",
        )
        (stage / ADAPTER_HEADER).write_text(
            adapter_header,
            encoding="utf-8",
        )
        (stage / MANIFEST).write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        for name in (PROFILE_HEADER, ADAPTER_HEADER, MANIFEST):
            (stage / name).replace(out_dir / name)

    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument(
        "--catalog",
        type=Path,
        default=adapter_emit_c.DEFAULT_CATALOG,
    )
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    try:
        report = emit_runtime_bundle(
            args.libgame,
            args.profile,
            args.catalog,
            args.out_dir,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
