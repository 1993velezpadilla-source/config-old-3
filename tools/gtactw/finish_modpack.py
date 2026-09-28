#!/usr/bin/env python3
"""End-to-end CTW modpack build/sign/optional-install orchestration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_mod_from_profile
import install_modpack
import sign_modpack


def finish_modpack(
    source: Path,
    profile: Path,
    minimal_loader: Path,
    shadowhook_loader: Path,
    work_dir: Path,
    *,
    config: Path | None,
    keystore: Path,
    alias: str,
    ks_pass_env: str = "CTW_KEYSTORE_PASS",
    key_pass_env: str = "CTW_KEY_PASS",
    zipalign: Path | None = None,
    apksigner: Path | None = None,
    install: bool = False,
    adb: Path | None = None,
    serial: str | None = None,
    grant_permissions: bool = False,
    adapter_catalog: Path | None = None,
) -> dict:
    mode = build_mod_from_profile._source_mode(source)
    work_dir.mkdir(parents=True, exist_ok=True)

    if mode == "apk":
        unsigned_output = work_dir / "unsigned-ctw3d.apk"
        signed_output = work_dir / "signed-ctw3d.apk"
    else:
        unsigned_output = work_dir / "unsigned-splits"
        signed_output = work_dir / "signed-splits"

    build_report = build_mod_from_profile.build_from_profile(
        source,
        profile,
        minimal_loader,
        shadowhook_loader,
        unsigned_output,
        config,
        adapter_catalog,
    )

    sign_report = sign_modpack.sign_modpack(
        unsigned_output,
        signed_output,
        keystore=keystore,
        alias=alias,
        ks_pass_env=ks_pass_env,
        key_pass_env=key_pass_env,
        zipalign_path=zipalign,
        apksigner_path=apksigner,
    )

    install_report = None
    if install:
        install_report = install_modpack.install_signed_modpack(
            signed_output,
            adb_path=adb,
            serial=serial,
            grant_permissions=grant_permissions,
        )

    return {
        "ok": True,
        "source_mode": mode,
        "loader_variant": build_report["loader_variant"],
        "selected_loader": build_report["selected_loader"],
        "unsigned_output": str(unsigned_output),
        "signed_output": str(signed_output),
        "signing_certificate": sign_report["certificate"],
        "installed": install_report is not None,
        "build": build_report,
        "sign": sign_report,
        "install": install_report,
        "note": (
            "Installation is opt-in only. This orchestration never uninstalls "
            "the existing CTW app or deletes its data automatically."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument("--minimal-loader", type=Path, required=True)
    ap.add_argument("--shadowhook-loader", type=Path, required=True)
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--config", type=Path)
    ap.add_argument("--keystore", type=Path, required=True)
    ap.add_argument("--alias", required=True)
    ap.add_argument("--ks-pass-env", default="CTW_KEYSTORE_PASS")
    ap.add_argument("--key-pass-env", default="CTW_KEY_PASS")
    ap.add_argument("--zipalign", type=Path)
    ap.add_argument("--apksigner", type=Path)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--adb", type=Path)
    ap.add_argument("--serial")
    ap.add_argument("--grant-permissions", action="store_true")
    ap.add_argument(
        "--adapter-catalog",
        type=Path,
        default=build_mod_from_profile.DEFAULT_ADAPTER_CATALOG,
    )
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    try:
        report = finish_modpack(
            args.source,
            args.profile,
            args.minimal_loader,
            args.shadowhook_loader,
            args.work_dir,
            config=args.config,
            keystore=args.keystore,
            alias=args.alias,
            ks_pass_env=args.ks_pass_env,
            key_pass_env=args.key_pass_env,
            zipalign=args.zipalign,
            apksigner=args.apksigner,
            install=args.install,
            adb=args.adb,
            serial=args.serial,
            grant_permissions=args.grant_permissions,
            adapter_catalog=args.adapter_catalog,
        )
    except install_modpack.InstallError as exc:
        payload = {
            "ok": False,
            "stage": "install",
            "error": str(exc),
            "signature_conflict": exc.signature_conflict,
        }
        print(json.dumps(payload, indent=2))
        return 3 if exc.signature_conflict else 2
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
