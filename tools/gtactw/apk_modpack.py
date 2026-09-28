#!/usr/bin/env python3
"""Build a local CTW Android 3D mod APK from a user-owned APK.

The script never downloads or bundles Rockstar data. It replaces only the
ARM64 libGame.so entry:
  original libGame.so -> libGame_orig.so
  CTW3D proxy loader  -> libGame.so

Existing APK signature metadata is removed because any modification invalidates
it. The output must then be zipaligned and signed with Android build tools.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile

GAME_SO = "lib/arm64-v8a/libGame.so"
ORIGINAL_SO = "lib/arm64-v8a/libGame_orig.so"

SIGNATURE_SUFFIXES = (
    ".SF", ".RSA", ".DSA", ".EC",
)


def is_signature_entry(name: str) -> bool:
    upper = name.upper()
    if not upper.startswith("META-INF/"):
        return False
    leaf = upper.rsplit("/", 1)[-1]
    return leaf == "MANIFEST.MF" or leaf.endswith(SIGNATURE_SUFFIXES)


def clone_info(info: zipfile.ZipInfo, *, filename: str | None = None) -> zipfile.ZipInfo:
    out = zipfile.ZipInfo(filename or info.filename, date_time=info.date_time)
    out.compress_type = info.compress_type
    out.comment = info.comment
    out.extra = info.extra
    out.create_system = info.create_system
    out.create_version = info.create_version
    out.extract_version = info.extract_version
    out.flag_bits = info.flag_bits
    out.volume = info.volume
    out.internal_attr = info.internal_attr
    out.external_attr = info.external_attr
    return out


def build_mod_apk(source_apk: Path, loader_so: Path, output_apk: Path) -> dict:
    if not source_apk.is_file():
        raise FileNotFoundError(source_apk)
    if not loader_so.is_file():
        raise FileNotFoundError(loader_so)

    loader_bytes = loader_so.read_bytes()
    if not loader_bytes.startswith(b"\x7fELF"):
        raise ValueError("loader is not an ELF shared object")

    output_apk.parent.mkdir(parents=True, exist_ok=True)

    found_game = False
    removed_signatures = 0
    with zipfile.ZipFile(source_apk, "r") as src, zipfile.ZipFile(
        output_apk, "w", allowZip64=True
    ) as dst:
        names = set(src.namelist())
        if ORIGINAL_SO in names:
            raise ValueError(
                "source APK already contains libGame_orig.so; refusing ambiguous repack"
            )
        if GAME_SO not in names:
            raise ValueError(f"source APK is missing {GAME_SO}")

        for info in src.infolist():
            name = info.filename
            if is_signature_entry(name):
                removed_signatures += 1
                continue

            data = src.read(name)
            if name == GAME_SO:
                found_game = True
                orig_info = clone_info(info, filename=ORIGINAL_SO)
                # Native libraries should be stored; zipalign handles final alignment.
                orig_info.compress_type = zipfile.ZIP_STORED
                dst.writestr(orig_info, data)
                continue

            dst.writestr(clone_info(info), data)

        loader_info = zipfile.ZipInfo(GAME_SO)
        loader_info.compress_type = zipfile.ZIP_STORED
        loader_info.external_attr = 0o100755 << 16
        dst.writestr(loader_info, loader_bytes)

    if not found_game:
        raise RuntimeError("internal error: original libGame.so was not copied")

    with zipfile.ZipFile(output_apk, "r") as check:
        names = set(check.namelist())
        if GAME_SO not in names or ORIGINAL_SO not in names:
            raise RuntimeError("repacked APK failed native-library layout verification")
        if any(is_signature_entry(n) for n in names):
            raise RuntimeError("repacked APK still contains stale signature metadata")

    return {
        "source_apk": str(source_apk),
        "output_apk": str(output_apk),
        "loader_size": len(loader_bytes),
        "removed_signature_entries": removed_signatures,
        "native_layout": {
            "proxy": GAME_SO,
            "original": ORIGINAL_SO,
        },
        "next_steps": [
            "zipalign -P 16 -f 4 INPUT.apk ALIGNED.apk",
            "apksigner sign --ks YOUR_KEYSTORE --out SIGNED.apk ALIGNED.apk",
            "apksigner verify --verbose SIGNED.apk",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", type=Path, help="User-owned GTA CTW Android APK")
    ap.add_argument("--loader-so", type=Path, required=True, help="Built CTW3D libGame.so proxy")
    ap.add_argument("--out", type=Path, required=True, help="Unsigned repacked APK")
    args = ap.parse_args()

    try:
        report = build_mod_apk(args.apk, args.loader_so, args.out)
    except Exception as exc:
        print(f"error: {exc}")
        return 2

    for key, value in report.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
