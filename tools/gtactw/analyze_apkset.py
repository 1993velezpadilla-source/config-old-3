#!/usr/bin/env python3
"""End-to-end CTW analysis for user-owned split APK sets/APKM/XAPK/APKS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

import aarch64_xref
import apk_identity
import apkset_probe
import elf_probe
import pak_inventory
import ped_probe
import profile_template
import plt_calls
import world_census


def _merged_split_identity(source: Path, temp_root: Path, aapt: Path | None) -> dict:
    temp_root.mkdir(parents=True, exist_ok=True)
    apks = apkset_probe.collect_apks(source, temp_root)
    identities = []
    for display, path in apks:
        ident = apk_identity.inspect_apk_identity(path, aapt)
        ident = dict(ident)
        ident["split"] = display
        identities.append(ident)

    if not identities:
        raise ValueError("split set contains no APK identities")

    packages = {x["package"] for x in identities}
    version_codes = {x["version_code"] for x in identities}
    version_names = {x["version_name"] for x in identities}
    if len(packages) != 1 or len(version_codes) != 1 or len(version_names) != 1:
        raise ValueError("split APK identities disagree on package/version")

    native = set()
    for item in identities:
        native.update(item.get("native_code", []))

    return {
        "package": identities[0]["package"],
        "version_code": identities[0]["version_code"],
        "version_name": identities[0]["version_name"],
        "min_sdk": identities[0].get("min_sdk"),
        "target_sdk": identities[0].get("target_sdk"),
        "native_code": sorted(native),
        "splits": identities,
    }



def _merged_split_certificate(
    source: Path,
    temp_root: Path,
    apksigner: Path | None,
) -> dict:
    temp_root.mkdir(parents=True, exist_ok=True)
    apks = apkset_probe.collect_apks(source, temp_root)
    certs = []
    for display, path in apks:
        cert = apk_identity.inspect_apk_certificate(path, apksigner)
        cert = dict(cert)
        cert["split"] = display
        certs.append(cert)

    if not certs:
        raise ValueError("split set contains no APK certificates")

    sha1s = {x["sha1"] for x in certs}
    sha256s = {x["sha256"] for x in certs}
    if len(sha1s) != 1 or len(sha256s) != 1:
        raise ValueError("split APK signatures disagree")

    return {
        "sha1": certs[0]["sha1"],
        "sha256": certs[0]["sha256"],
        "splits": certs,
    }

def analyze_apkset(
    source: Path,
    reference: Path | None = None,
    aapt: Path | None = None,
    apksigner: Path | None = None,
) -> dict:
    if not source.exists():
        raise FileNotFoundError(source)

    report = {
        "ok": False,
        "source": str(source),
        "split_report": None,
        "pak_inventory": None,
        "ped_models": None,
        "ped_models_error": None,
        "world_census": None,
        "world_census_error": None,
        "libgame": None,
        "arm64_xrefs": None,
        "plt_calls": None,
        "plt_calls_error": None,
        "profile_template": None,
        "apk_identity": None,
        "apk_certificate": None,
        "reference_validation": None,
        "errors": [],
        "gates": {
            "split_runtime": False,
            "pak_inventory": False,
            "arm64_elf": False,
            "known_jni": False,
        },
    }

    with tempfile.TemporaryDirectory(prefix="gtactw_apkset_analysis_") as td:
        root = Path(td)
        runtime = root / "runtime"
        set_report = apkset_probe.inspect_set(source, runtime)
        report["split_report"] = set_report
        report["gates"]["split_runtime"] = set_report["ok"]

        pak_path = runtime / "assets/game.pak"
        so_path = runtime / "lib/arm64-v8a/libGame.so"

        if pak_path.is_file():
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
                    "clean": (
                        census["worldblocks_parsed"] > 0
                        and not census["parse_errors"]
                    ),
                }
            except Exception as exc:
                report["world_census_error"] = str(exc)

        if so_path.is_file():
            elf = elf_probe.inspect_elf(so_path)
            report["libgame"] = elf
            report["gates"]["arm64_elf"] = elf["elf"]["machine"] == "AArch64"
            report["gates"]["known_jni"] = elf["symbols"]["known_jni_present"] > 0
            xrefs = aarch64_xref.scan_libgame(so_path)
            report["arm64_xrefs"] = xrefs
            plt_report = plt_calls.scan_plt_calls(so_path)
            report["plt_calls"] = plt_report
            report["profile_template"] = profile_template.make_profile(
                elf,
                xrefs,
                plt_report,
            )

        if reference is not None:
            try:
                identity = _merged_split_identity(source, root / "identity_apks", aapt)
                # Runtime selection itself proves the arm64 native split exists,
                # even when aapt on the base APK does not list split ABIs.
                if set_report["selected"].get("lib/arm64-v8a/libGame.so"):
                    native = set(identity.get("native_code", []))
                    native.add("arm64-v8a")
                    identity["native_code"] = sorted(native)
                ref_obj = json.loads(reference.read_text(encoding="utf-8"))
                certificate = None
                if ref_obj.get("verification", {}).get(
                    "require_signing_certificate_match"
                ):
                    certificate = _merged_split_certificate(
                        source,
                        root / "certificate_apks",
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
                report["errors"].append(f"identity: {exc}")
                report["gates"]["reference_build"] = False

    report["ok"] = all(report["gates"].values())
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--reference", type=Path)
    ap.add_argument("--aapt", type=Path)
    ap.add_argument("--apksigner", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--profile-out", type=Path)
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()

    try:
        report = analyze_apkset(
            args.source,
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
    return 0 if report["ok"] or args.allow_partial else 1


if __name__ == "__main__":
    raise SystemExit(main())
