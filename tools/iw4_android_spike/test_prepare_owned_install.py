#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import struct
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "prepare_owned_install.py"
spec = importlib.util.spec_from_file_location("prepare_owned_install", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def make_pe32_i386(path: Path) -> None:
    pe_offset = 0x80
    blob = bytearray(0x200)
    blob[0:2] = b"MZ"
    struct.pack_into("<I", blob, 0x3C, pe_offset)
    blob[pe_offset : pe_offset + 4] = b"PE\x00\x00"
    struct.pack_into("<H", blob, pe_offset + 4, module.IMAGE_FILE_MACHINE_I386)
    struct.pack_into("<H", blob, pe_offset + 20, 0xE0)
    struct.pack_into("<H", blob, pe_offset + 24, 0x10B)
    path.write_bytes(blob)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="iw4-spike-test-") as tmp:
        root = Path(tmp)
        (root / "main").mkdir()
        (root / "zone").mkdir()
        (root / "usermaps" / "xziel_sanctum").mkdir(parents=True)
        (root / "usermaps" / "xziel_sanctum" / "README.txt").write_text(
            "synthetic fixture", encoding="utf-8"
        )
        (root / "iw4x.dll").write_bytes(b"synthetic-not-a-real-dll")
        make_pe32_i386(root / "iw4mp.exe")

        result = module.inspect_install(root, "xziel_sanctum")
        assert result["runtime"] == "IW4"
        assert result["executable"]["machineName"] == "x86"
        assert result["executable"]["peKind"] == "PE32"
        assert result["iw4xPresent"] is True
        assert result["churchMapPresent"] is True
        assert result["redistributionAllowedByThisTool"] is False

        encoded = json.dumps(result)
        assert "synthetic-not-a-real-dll" not in encoded

    print("IW4 Android compatibility input gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
