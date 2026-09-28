#!/usr/bin/env python3
import io
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("ctw_probe", HERE / "ctw_probe.py")
ctw_probe = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ctw_probe)


def make_small_pak() -> bytes:
    # 4 resources. All resource IDs are below r0, so no high-range base is added.
    header = struct.pack("<6I", 0x12345678, 4, 4, 4, 4, 1)
    table = struct.pack("<4H", 1, 2, 3, 4)
    return header + table + bytes(5 * 4096)


class PakTests(unittest.TestCase):
    def test_small_pak_header_and_offsets(self):
        data = make_small_pak()
        report = ctw_probe.parse_pak(io.BytesIO(data))
        self.assertEqual(report["version_signature"], 0x12345678)
        self.assertEqual(report["resource_count"], 4)
        self.assertEqual(report["offset_table_entries"], 4)
        self.assertEqual(report["first_resource_offsets"][:4], [4096, 8192, 12288, 16384])

    def test_apk_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            apk = Path(td) / "ctw-test.apk"
            with zipfile.ZipFile(apk, "w") as zf:
                for name in ctw_probe.REQUIRED_APK_FILES:
                    payload = make_small_pak() if name == "assets/game.pak" else b"fixture"
                    zf.writestr(name, payload)

            report = ctw_probe.inspect_apk(apk)
            self.assertEqual(report["missing_required"], [])
            self.assertEqual(report["pak"]["resource_count"], 4)


if __name__ == "__main__":
    unittest.main()
