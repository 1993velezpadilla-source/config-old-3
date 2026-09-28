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
import profile_template


def _merged_split_identity(source: Path, temp_root: Path, aapt: Path | None) -> dict:
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


def analyze_apkset(
    source: Path,
    reference: Path | None = None,
    aapt: Path | None = None,
) -> dict:
    if not source.exists():
        raise FileNotFoundError(source)

    report = {
        "ok": False,
        "source": str(source),
        "split_report": None,
        "pak_inventory": None,
        "libgame": None,
        "arm64_xrefs": None,
        "profile_template": None,
        "apk_identity": None,
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

        if so_path.is_file():
            elf = elf_probe.inspect_elf(so_path)
            report["libgame"] = elf
            report["gates"]["arm64_elf"] = elf["elf"]["machine"] == "AArch64"
            report["gates"]["known_jni"] = elf["symbols"]["known_jni_present"] > 0
            xrefs = aarch64_xref.scan_libgame(so_path)
            report["arm64_xrefs"] = xrefs
            report["profile_template"] = profile_template.make_profile(elf, xrefs)

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
                validation = apk_identity.validate_reference(identity, ref_obj)
                report["apk_identity"] = identity
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
    ap.add_argument("--out", type=Path)
    ap.add_argument("--profile-out", type=Path)
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()

    try:
        report = analyze_apkset(args.source, args.reference, args.aapt)
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
