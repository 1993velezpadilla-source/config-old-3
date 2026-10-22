#!/usr/bin/env python3
"""Validate a user-supplied IW4 installation for the Android compatibility spike.

This tool intentionally does not download, copy, patch, upload, or redistribute
any game file. It only inspects a local path and emits a JSON manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


IMAGE_FILE_MACHINE_I386 = 0x014C
IMAGE_FILE_MACHINE_AMD64 = 0x8664

MACHINE_NAMES = {
    IMAGE_FILE_MACHINE_I386: "x86",
    IMAGE_FILE_MACHINE_AMD64: "x86_64",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pe_identity(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError(f"{path} is not an MZ executable")

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 26 > len(data):
        raise ValueError(f"{path} has a truncated PE header")
    if data[pe_offset : pe_offset + 4] != b"PE\x00\x00":
        raise ValueError(f"{path} is missing the PE signature")

    machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    optional_offset = pe_offset + 24
    if optional_size < 2 or optional_offset + optional_size > len(data):
        raise ValueError(f"{path} has a truncated optional header")

    magic = struct.unpack_from("<H", data, optional_offset)[0]
    if magic == 0x10B:
        pe_kind = "PE32"
    elif magic == 0x20B:
        pe_kind = "PE32+"
    else:
        pe_kind = f"unknown:0x{magic:04x}"

    return {
        "machine": machine,
        "machineName": MACHINE_NAMES.get(machine, f"unknown:0x{machine:04x}"),
        "peKind": pe_kind,
    }


def inspect_install(root: Path, map_name: str) -> dict:
    root = root.expanduser().resolve()
    exe = root / "iw4mp.exe"
    main_dir = root / "main"
    zone_dir = root / "zone"

    missing = [
        str(path.name)
        for path in (exe, main_dir, zone_dir)
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(
            "IW4 install is incomplete; missing: " + ", ".join(missing)
        )
    if not exe.is_file():
        raise FileNotFoundError("iw4mp.exe is not a regular file")
    if not main_dir.is_dir() or not zone_dir.is_dir():
        raise FileNotFoundError("main/ and zone/ must be directories")

    pe = read_pe_identity(exe)

    iw4x_candidates = [
        root / "iw4x.dll",
        root / "iw4x" / "iw4x.dll",
    ]
    iw4x_present = any(path.is_file() for path in iw4x_candidates)

    usermap_dir = root / "usermaps" / map_name
    map_present = usermap_dir.is_dir() and any(usermap_dir.iterdir())

    return {
        "schema": 1,
        "runtime": "IW4",
        "gameRoot": str(root),
        "executable": {
            "name": exe.name,
            "size": exe.stat().st_size,
            "sha256": sha256_file(exe),
            **pe,
        },
        "directories": {
            "main": str(main_dir),
            "zone": str(zone_dir),
            "usermap": str(usermap_dir),
        },
        "iw4xPresent": iw4x_present,
        "churchMapName": map_name,
        "churchMapPresent": map_present,
        "redistributionAllowedByThisTool": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-root", required=True, type=Path)
    parser.add_argument("--map-name", default="xziel_sanctum")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--require-x86",
        action="store_true",
        help="Fail unless iw4mp.exe reports IMAGE_FILE_MACHINE_I386 + PE32.",
    )
    args = parser.parse_args()

    manifest = inspect_install(args.game_root, args.map_name)

    if args.require_x86:
        exe = manifest["executable"]
        if exe["machine"] != IMAGE_FILE_MACHINE_I386 or exe["peKind"] != "PE32":
            raise SystemExit(
                "Expected the IW4 PC runtime to be PE32/x86; got "
                f'{exe["peKind"]}/{exe["machineName"]}'
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
