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
import ped_probe
import profile_template
import plt_calls
import world_census


def analyze_apk(
    apk: Path,
    reference: Path | None = None,
    aapt: Path | None = None,
    apksigner: Path | None = None,
) -> dict:
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
        "ped_models": None,
        "ped_models_error": None,
        "world_census": None,
        "world_census_error": None,
        "libgame": None,
        "profile_template": None,
        "profile_template_error": None,
        "arm64_xrefs": None,
        "plt_calls": None,
        "plt_calls_error": None,
        "arm64_xrefs_error": None,
        "apk_identity": None,
        "apk_certificate": None,
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
            certificate = None
            if ref_obj.get("verification", {}).get(
                "require_signing_certificate_match"
            ):
                certificate = apk_identity.inspect_apk_certificate(
                    apk,
                    apksigner,
                )
            validation = apk_identity.validate_reference(
                identity,
                ref_obj,
                certificate,
            )
            report["apk_identity"] = identity
            report["apk_certificate"] = certificate
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
            try:
                ped = ped_probe.inspect_ped_models(pak_path)
                report["ped_models"] = {
                    "pedinfos_resource_id": ped["pedinfos_resource_id"],
                    "pedinfos_size": ped["pedinfos_size"],
                    "model_resource_count": ped["model_resource_count"],
                    "layout_confidence": ped["layout_inference"]["confidence"],
                    "layout_best": ped["layout_inference"]["best"],
                    "linked_model_count": ped["linked_model_count"],
                    "linked_models_by_skeleton_complexity": ped[
                        "linked_models_by_skeleton_complexity"
                    ][:64],
                    "note": ped["note"],
                }
            except Exception as exc:
                report["ped_models_error"] = str(exc)
            try:
                census = world_census.census_pak(pak_path)
                report["world_census"] = {
                    "worldblocks_named": census["worldblocks_named"],
                    "worldblocks_parsed": census["worldblocks_parsed"],
                    "parse_error_count": len(census["parse_errors"]),
                    "totals": census["totals"],
                    "instance_stats_per_worldblock": census[
                        "instance_stats_per_worldblock"
                    ],
                    "level_stats_per_worldblock": census[
                        "level_stats_per_worldblock"
                    ],
                    "densest_worldblocks": census["densest_worldblocks"][:16],
                    "streaming_pressure_model": census[
                        "streaming_pressure_model"
                    ],
                }
                report["world_census"]["clean"] = (
                    census["worldblocks_parsed"] > 0
                    and not census["parse_errors"]
                )
            except Exception as exc:
                report["world_census_error"] = str(exc)

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
                report["plt_calls"] = plt_calls.scan_plt_calls(so_path)
            except Exception as exc:
                report["plt_calls_error"] = str(exc)
            try:
                report["profile_template"] = profile_template.make_profile(
                    elf,
                    report["arm64_xrefs"],
                    report["plt_calls"],
                )
            except Exception as exc:
                report["profile_template_error"] = str(exc)

    report["ok"] = all(report["gates"].values())
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", type=Path, help="Path to a user-owned CTW Android APK")
    ap.add_argument("--out", type=Path, help="Write full JSON analysis here")
    ap.add_argument("--profile-out", type=Path, help="Write patch profile template here")
    ap.add_argument("--reference", type=Path, help="Pinned CTW reference-build JSON")
    ap.add_argument("--aapt", type=Path, help="Optional explicit Android aapt/aapt2 path")
    ap.add_argument("--apksigner", type=Path, help="Optional explicit Android apksigner path")
    ap.add_argument(
        "--allow-partial",
        action="store_true",
        help="Return success even when one or more analysis gates are not met",
    )
    args = ap.parse_args()

    try:
        report = analyze_apk(
            args.apk,
            args.reference,
            args.aapt,
            args.apksigner,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    if args.profile_out and report.get("profile_template") is not None:
        args.profile_out.parent.mkdir(parents=True, exist_ok=True)
        args.profile_out.write_text(
            json.dumps(report["profile_template"], indent=2) + "\n",
            encoding="utf-8",
        )
    print(payload)

    if report["ok"] or args.allow_partial:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
