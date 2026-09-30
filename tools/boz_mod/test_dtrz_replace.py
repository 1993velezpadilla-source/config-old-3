#!/usr/bin/env python3
from __future__ import annotations

import lzma
import struct
import subprocess
import sys
from pathlib import Path


def cstr(value: str) -> bytes:
    return value.encode("utf-8") + b"\0"


def compress(data: bytes) -> bytes:
    filters = [{
        "id": lzma.FILTER_LZMA1,
        "dict_size": 1 << 23,
        "lc": 3,
        "lp": 0,
        "pb": 2,
    }]
    return lzma.compress(data, format=lzma.FORMAT_ALONE, filters=filters)


def build_archive(path: Path) -> None:
    names = ["map_probe.group.bin", "keep.bin"]
    directories = ["data-etc"]
    payloads = [b"STOCK_MAP_RESOURCE", b"UNCHANGED_SECOND_RESOURCE"]
    compressed = [compress(p) for p in payloads]
    slot_size = 256

    header = bytearray()
    header += b"DTRZ"
    header += struct.pack("<H", 2)
    header += struct.pack("<H", 1)
    header += b"\0"

    for name in names:
        header += cstr(name)

    for directory in directories:
        header += cstr(directory)

    ref_pos = len(header)
    header += struct.pack("<HHH", 1, 0, 0xFFFF)
    header += struct.pack("<HHH", 1, 1, 0xFFFF)

    header += struct.pack("<HH", 1, 2)
    meta_pos = len(header)
    header += bytes(2 * 16)

    payload_start = ((len(header) + 15) // 16) * 16
    header += bytes(payload_start - len(header))

    offsets = [payload_start, payload_start + slot_size]
    for i, payload in enumerate(payloads):
        struct.pack_into(
            "<IIII",
            header,
            meta_pos + i * 16,
            offsets[i],
            len(payload),
            len(payload),
            0x100,
        )

    body = bytearray(header)
    for blob in compressed:
        if len(blob) > slot_size:
            raise RuntimeError("synthetic payload too large")
        body += blob + bytes(slot_size - len(blob))

    path.write_bytes(body)


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    out = root / "boz_mod_out" / "dtrz_gate"
    out.mkdir(parents=True, exist_ok=True)

    before = out / "synthetic_before.dz"
    after = out / "synthetic_after.dz"
    replacement = out / "replacement.group.bin"
    build_archive(before)
    replacement.write_bytes(b"XZIEL_ORIGINAL_MAP_PROBE_V1")

    cmd = [
        sys.executable,
        str(root / "tools/boz_mod/dtrz_replace.py"),
        "-i", str(before),
        "-o", str(after),
        "-e", "data-etc/map_probe.group.bin",
        "-r", str(replacement),
        "--list",
    ]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    print(result.stdout, end="")

    print("XZIEL_DTRZ_SYNTHETIC_BUILD_OK")
    print(f"before={before}")
    print(f"after={after}")
    print(f"replacement={replacement}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
