#!/usr/bin/env python3
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_apk
import ctw_probe
from test_ctw_probe import make_small_pak
from test_elf_probe import make_fixture


class AnalyzeApkTests(unittest.TestCase):
    def test_end_to_end_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            apk = root / "ctw-test.apk"
            so = root / "libGame.so"
            make_fixture(so)

            with zipfile.ZipFile(apk, "w") as zf:
                for name in ctw_probe.REQUIRED_APK_FILES:
                    if name == "assets/game.pak":
                        payload = make_small_pak()
                    elif name == "lib/arm64-v8a/libGame.so":
                        payload = so.read_bytes()
                    else:
                        payload = b"fixture"
                    zf.writestr(name, payload)

            report = analyze_apk.analyze_apk(apk)

        self.assertTrue(report["gates"]["apk_inventory"])
        self.assertTrue(report["gates"]["pak_inventory"])
        self.assertTrue(report["gates"]["arm64_elf"])
        self.assertTrue(report["gates"]["known_jni"])
        self.assertTrue(report["ok"])
        self.assertEqual(report["pak_inventory"]["resource_count"], 4)
        self.assertEqual(report["libgame"]["elf"]["machine"], "AArch64")


if __name__ == "__main__":
    unittest.main()
