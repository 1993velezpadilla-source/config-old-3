#!/usr/bin/env python3
"""Verified CTW build -> profile-specific proxy -> repack -> sign -> optional install."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_mod_from_profile
import build_verified_loader
import install_modpack
import sign_modpack


def finish_verified_modpack(
    source: Path,
    libgame: Path,
    profile: Path,
    catalog: Path,
    loader_source_dir: Path,
    work_dir: Path,
    *,
    config: Path | None,
    keystore: Path,
    alias: str,
    ndk: Path | None = None,
    shadowhook_dir: Path | None = None,
    cmake: str = "cmake",
    ks_pass_env: str = "CTW_KEYSTORE_PASS",
    key_pass_env: str = "CTW_KEY_PASS",
    zipalign: Path | None = None,
    apksigner: Path | None = None,
    install: bool = False,
    adb: Path | None = None,
    serial: str | None = None,
    grant_permissions: bool = False,
) -> dict:
    mode = build_mod_from_profile._source_mode(source)
    work_dir.mkdir(parents=True, exist_ok=True)

    loader_work = work_dir / "verified-loader-build"
    loader_out = work_dir / "verified-loader/libGame.so"

    loader_report = build_verified_loader.build_verified_loader(
        libgame,
        profile,
        catalog,
        loader_source_dir,
        loader_work,
        loader_out,
        ndk=ndk,
        shadowhook_dir=shadowhook_dir,
        cmake=cmake,
    )

    if mode == "apk":
        unsigned_output = work_dir / "unsigned-ctw3d.apk"
        signed_output = work_dir / "signed-ctw3d.apk"
    else:
        unsigned_output = work_dir / "unsigned-splits"
        signed_output = work_dir / "signed-splits"

    # The loader is already built for the exact verified variant, so pass the
    # same profile-specific binary into both selector slots. The selector still
    # independently validates the profile and must agree on the variant.
    build_report = build_mod_from_profile.build_from_profile(
        source,
        profile,
        loader_out,
        loader_out,
        unsigned_output,
        config,
        catalog,
    )
    if build_report["loader_variant"] != loader_report["loader_variant"]:
        raise RuntimeError(
            "loader build variant disagrees with modpack selector"
        )
    if Path(build_report["selected_loader"]) != loader_out:
        raise RuntimeError(
            "modpack selector did not use the profile-specific loader"
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
        "loader_variant": loader_report["loader_variant"],
        "profile_specific_loader": str(loader_out),
        "profile_specific_loader_sha256": loader_report["loader_sha256"],
        "runtime_profile_header_sha256": (
            loader_report["profile_header_sha256"]
        ),
        "runtime_adapter_header_sha256": (
            loader_report["adapter_header_sha256"]
        ),
        "unsigned_output": str(unsigned_output),
        "signed_output": str(signed_output),
        "signing_certificate": sign_report["certificate"],
        "installed": install_report is not None,
        "loader_build": loader_report,
        "repack": build_report,
        "sign": sign_report,
        "install": install_report,
        "note": (
            "The packaged proxy was compiled from the exact verified CTW "
            "profile + adapter catalog. Generic template proxy artifacts are "
            "not used by this workflow."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--libgame", type=Path, required=True)
    ap.add_argument("--profile", type=Path, required=True)
    ap.add_argument(
        "--catalog",
        type=Path,
        default=build_mod_from_profile.DEFAULT_ADAPTER_CATALOG,
    )
    ap.add_argument(
        "--loader-source-dir",
        type=Path,
        default=Path("projects/gtactw-android-3d/android-loader"),
    )
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--config", type=Path)
    ap.add_argument("--keystore", type=Path, required=True)
    ap.add_argument("--alias", required=True)
    ap.add_argument("--ndk", type=Path)
    ap.add_argument("--shadowhook-dir", type=Path)
    ap.add_argument("--cmake", default="cmake")
    ap.add_argument("--ks-pass-env", default="CTW_KEYSTORE_PASS")
    ap.add_argument("--key-pass-env", default="CTW_KEY_PASS")
    ap.add_argument("--zipalign", type=Path)
    ap.add_argument("--apksigner", type=Path)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--adb", type=Path)
    ap.add_argument("--serial")
    ap.add_argument("--grant-permissions", action="store_true")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    try:
        report = finish_verified_modpack(
            args.source,
            args.libgame,
            args.profile,
            args.catalog,
            args.loader_source_dir,
            args.work_dir,
            config=args.config,
            keystore=args.keystore,
            alias=args.alias,
            ndk=args.ndk,
            shadowhook_dir=args.shadowhook_dir,
            cmake=args.cmake,
            ks_pass_env=args.ks_pass_env,
            key_pass_env=args.key_pass_env,
            zipalign=args.zipalign,
            apksigner=args.apksigner,
            install=args.install,
            adb=args.adb,
            serial=args.serial,
            grant_permissions=args.grant_permissions,
        )
    except install_modpack.InstallError as exc:
        print(json.dumps({
            "ok": False,
            "stage": "install",
            "error": str(exc),
            "signature_conflict": exc.signature_conflict,
        }, indent=2))
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
