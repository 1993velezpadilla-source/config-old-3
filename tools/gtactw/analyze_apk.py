#!/usr/bin/env python3
"""End-to-end analyzer for a user-owned GTA Chinatown Wars Android APK.

Produces one JSON report containing:
- expected runtime-file inventory;
- game.pak resource inventory;
- libGame.so ARM64 fingerprint and candidate groups.

No proprietary game data is embedded, fetched, or committed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

import aarch64_xref
import apk_identity
import ctw_probe
import elf_probe
import pak_inventory
import profile_template


def analyze_apk(apk: Path, reference: Path | None = None, aapt: Path | None = None) -> dict:
    if not apk.is_file():
        raise FileNotFoundError(apk)

    base = ctw_probe.inspect_apk(apk)

    report = {
        "ok": False,
        "apk": str(apk),
        "apk_size": apk.stat().st_size,
        "required": base["required"],
        "missing_required": base["missing_required"],
        "pak_header": base["pak"],
        "pak_inventory": None,
        "libgame": None,
        "profile_template": None,
        "profile_template_error": None,
        "arm64_xrefs": None,
        "arm64_xrefs_error": None,
        "apk_identity": None,
        "apk_identity_error": None,
        "reference_validation": None,
        "gates": {
            "apk_inventory": not base["missing_required"],
            "pak_inventory": False,
            "arm64_elf": False,
            "known_jni": False,
        },
    }

    if reference is not None:
        try:
            identity = apk_identity.inspect_apk_identity(apk, aapt)
            ref_obj = json.loads(reference.read_text(encoding="utf-8"))
            validation = apk_identity.validate_reference(identity, ref_obj)
            report["apk_identity"] = identity
            report["reference_validation"] = validation
            report["gates"]["reference_build"] = validation["ok"]
        except Exception as exc:
            report["apk_identity_error"] = str(exc)
            report["gates"]["reference_build"] = False

    with zipfile.ZipFile(apk, "r") as zf, tempfile.TemporaryDirectory(prefix="gtactw_analyze_") as td:
        root = Path(td)

        if "assets/game.pak" in zf.namelist():
            pak_path = root / "game.pak"
            with zf.open("assets/game.pak") as src, pak_path.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            inv = pak_inventory.inventory_pak(pak_path)
            report["pak_inventory"] = {
                "version_signature": inv["version_signature"],
                "version_signature_hex": inv["version_signature_hex"],
                "resource_count": inv["resource_count"],
                "counts": inv["counts"],
                "named_resources": [
                    r for r in inv["resources"] if r["name"] is not None
                ][:256],
            }
            report["gates"]["pak_inventory"] = True

        if "lib/arm64-v8a/libGame.so" in zf.namelist():
            so_path = root / "libGame.so"
            with zf.open("lib/arm64-v8a/libGame.so") as src, so_path.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            elf = elf_probe.inspect_elf(so_path)
            report["libgame"] = elf
            report["gates"]["arm64_elf"] = elf["elf"]["machine"] == "AArch64"
            report["gates"]["known_jni"] = elf["symbols"]["known_jni_present"] > 0
            try:
                report["arm64_xrefs"] = aarch64_xref.scan_libgame(so_path)
            except Exception as exc:
                report["arm64_xrefs_error"] = str(exc)
            try:
                report["profile_template"] = profile_template.make_profile(elf)
            except Exception as exc:
                report["profile_template_error"] = str(exc)

    report["ok"] = all(report["gates"].values())
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", type=Path, help="Path to a user-owned CTW Android APK")
    ap.add_argument("--out", type=Path, help="Write full JSON analysis here")
    ap.add_argument("--reference", type=Path, help="Pinned CTW reference-build JSON")
    ap.add_argument("--aapt", type=Path, help="Optional explicit Android aapt/aapt2 path")
    ap.add_argument(
        "--allow-partial",
        action="store_true",
        help="Return success even when one or more analysis gates are not met",
    )
    args = ap.parse_args()

    try:
        report = analyze_apk(args.apk, args.reference, args.aapt)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)

    if report["ok"] or args.allow_partial:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
