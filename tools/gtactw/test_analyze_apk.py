#!/usr/bin/env python3
import json
import tempfile
import unittest
from unittest import mock
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
        self.assertIsNone(report["profile_template_error"])
        self.assertIsNotNone(report["profile_template"])
        self.assertEqual(
            report["profile_template"]["fingerprint"]["jni_rvas"]["implOnDrawFrame"],
            0x1000,
        )
        self.assertEqual(
            report["profile_template"]["fingerprint"]["jni_rvas"]["implOnInitialSetup"],
            0x1008,
        )

    def test_reference_build_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            apk = root / "ctw-test.apk"
            so = root / "libGame.so"
            ref = root / "reference.json"
            make_fixture(so)
            ref.write_text(json.dumps({
                "package": "com.rockstargames.gtactw",
                "reference_build": {
                    "version_name": "4.4.243",
                    "version_code": 4277603,
                },
                "android_mod_target": {
                    "preferred_abi": "arm64-v8a",
                },
            }), encoding="utf-8")

            with zipfile.ZipFile(apk, "w") as zf:
                for name in ctw_probe.REQUIRED_APK_FILES:
                    if name == "assets/game.pak":
                        payload = make_small_pak()
                    elif name == "lib/arm64-v8a/libGame.so":
                        payload = so.read_bytes()
                    else:
                        payload = b"fixture"
                    zf.writestr(name, payload)

            identity = {
                "package": "com.rockstargames.gtactw",
                "version_code": 4277603,
                "version_name": "4.4.243",
                "min_sdk": "28",
                "target_sdk": "35",
                "native_code": ["arm64-v8a"],
            }
            with mock.patch.object(
                analyze_apk.apk_identity,
                "inspect_apk_identity",
                return_value=identity,
            ):
                report = analyze_apk.analyze_apk(apk, ref)

        self.assertTrue(report["gates"]["reference_build"])
        self.assertTrue(report["reference_validation"]["ok"])
        self.assertTrue(report["ok"])


if __name__ == "__main__":
    unittest.main()
