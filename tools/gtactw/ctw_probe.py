#!/usr/bin/env python3
"""Probe a user-owned GTA Chinatown Wars Android APK and its game.pak.

No game data is bundled or downloaded by this tool.

PAK layout follows the public CTW-Mobile-Explorer implementation:
- first 24 bytes: six little-endian uint32 fields
- first 2036 uint16 resource offsets immediately follow the header
- remaining uint16 offsets start at resourceBlocksCount * 4096
- each table value is a 4096-byte block index with a range-selected base
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import zipfile

REQUIRED_APK_FILES = (
    "assets/game.pak",
    "assets/dxt.bin",
    "assets/buttonconfig",
    "assets/e_ckna01.gxt",
    "assets/ctw_iphone_intro.mp4",
    "lib/arm64-v8a/libGame.so",
    "lib/arm64-v8a/libopenal.so",
)

PAK_HEADER = struct.Struct("<6I")
FIRST_OFFSET_COUNT = 2036
BLOCK_SIZE = 4096
RANGE_BASES = (0x00000000, 0x10000000, 0x20000000, 0x30000000)


def sha256_stream(fp, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    while True:
        chunk = fp.read(chunk_size)
        if not chunk:
            break
        h.update(chunk)
    return h.hexdigest()


def parse_pak(fp) -> dict:
    fp.seek(0, os.SEEK_END)
    file_size = fp.tell()
    fp.seek(0)
    raw = fp.read(PAK_HEADER.size)
    if len(raw) != PAK_HEADER.size:
        raise ValueError("game.pak is smaller than its 24-byte header")

    version, r0, r1, r2, resource_count, resource_blocks = PAK_HEADER.unpack(raw)
    ranges = (r0, r1, r2)

    if resource_count == 0:
        raise ValueError("game.pak reports zero resources")
    if not (r0 <= r1 <= r2 <= resource_count):
        raise ValueError(
            f"invalid PAK ranges {ranges} for resource_count={resource_count}"
        )

    offsets: list[int] = []
    first_count = min(resource_count, FIRST_OFFSET_COUNT)
    raw_first = fp.read(first_count * 2)
    if len(raw_first) != first_count * 2:
        raise ValueError("truncated first PAK resource-offset table")
    if first_count:
        offsets.extend(struct.unpack(f"<{first_count}H", raw_first))

    if resource_count > FIRST_OFFSET_COUNT:
        second_count = resource_count - FIRST_OFFSET_COUNT
        second_table_pos = resource_blocks * BLOCK_SIZE
        if second_table_pos >= file_size:
            raise ValueError(
                "second resource-offset table lies outside game.pak: "
                f"0x{second_table_pos:X} >= 0x{file_size:X}"
            )
        fp.seek(second_table_pos)
        raw_second = fp.read(second_count * 2)
        if len(raw_second) != second_count * 2:
            raise ValueError("truncated second PAK resource-offset table")
        offsets.extend(struct.unpack(f"<{second_count}H", raw_second))

    logical_offsets: list[int] = []
    for resource_id, block_index in enumerate(offsets):
        base = RANGE_BASES[0]
        if resource_id >= r0:
            base = RANGE_BASES[1]
            if resource_id >= r1:
                base = RANGE_BASES[2]
                if resource_id >= r2:
                    base = RANGE_BASES[3]
        logical_offsets.append(base + block_index * BLOCK_SIZE)

    return {
        "version_signature": version,
        "version_signature_hex": f"0x{version:08X}",
        "ranges": list(ranges),
        "resource_count": resource_count,
        "resource_blocks_count": resource_blocks,
        "file_size": file_size,
        "offset_table_entries": len(offsets),
        "first_resource_offsets": logical_offsets[:16],
        "last_resource_offsets": logical_offsets[-16:] if logical_offsets else [],
    }


def inspect_apk(apk: Path, extract_dir: Path | None = None) -> dict:
    if not apk.is_file():
        raise FileNotFoundError(apk)

    result: dict = {
        "apk": str(apk),
        "apk_size": apk.stat().st_size,
        "required": {},
        "pak": None,
    }

    with zipfile.ZipFile(apk, "r") as zf:
        names = set(zf.namelist())
        for name in REQUIRED_APK_FILES:
            result["required"][name] = name in names

        missing = [name for name in REQUIRED_APK_FILES if name not in names]
        result["missing_required"] = missing

        if "assets/game.pak" in names:
            with zf.open("assets/game.pak", "r") as pak:
                result["pak"] = parse_pak(pak)

        if extract_dir is not None:
            extract_dir.mkdir(parents=True, exist_ok=True)
            for name in REQUIRED_APK_FILES:
                if name not in names:
                    continue
                dest = extract_dir / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name, "r") as src, open(dest, "wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path, help="Path to a user-owned CTW Android APK")
    parser.add_argument(
        "--extract",
        type=Path,
        help="Extract only the required runtime files to this local directory",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Return success even if expected files are absent",
    )
    args = parser.parse_args()

    try:
        report = inspect_apk(args.apk, args.extract)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    missing = report["missing_required"]
    report["ok"] = not missing
    print(json.dumps(report, indent=2))

    if missing and not args.allow_missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
