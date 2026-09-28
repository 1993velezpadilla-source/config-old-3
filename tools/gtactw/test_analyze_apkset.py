#!/usr/bin/env python3
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_apkset
import ctw_probe
from test_ctw_probe import make_small_pak
from test_elf_probe import make_fixture


def apk_bytes(entries: dict[str, bytes]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return bio.getvalue()


class AnalyzeApkSetTests(unittest.TestCase):
    def make_bundle(self, root: Path) -> Path:
        so = root / "libGame.so"
        make_fixture(so)
        bundle = root / "ctw.apkm"

        base_entries = {
            "assets/game.pak": make_small_pak(),
            "assets/dxt.bin": b"dxt",
            "assets/buttonconfig": b"buttons",
            "assets/e_ckna01.gxt": b"gxt",
            "assets/ctw_iphone_intro.mp4": b"movie",
        }
        arm_entries = {
            "lib/arm64-v8a/libGame.so": so.read_bytes(),
            "lib/arm64-v8a/libopenal.so": b"openal",
        }
        with zipfile.ZipFile(bundle, "w") as outer:
            outer.writestr("base.apk", apk_bytes(base_entries))
            outer.writestr(
                "splits/split_config.arm64_v8a.apk",
                apk_bytes(arm_entries),
            )
        return bundle

    def test_split_end_to_end_analysis(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = self.make_bundle(root)
            report = analyze_apkset.analyze_apkset(bundle)

        self.assertTrue(report["gates"]["split_runtime"])
        self.assertTrue(report["gates"]["pak_inventory"])
        self.assertTrue(report["gates"]["arm64_elf"])
        self.assertTrue(report["gates"]["known_jni"])
        self.assertTrue(report["ok"])
        self.assertIsNotNone(report["profile_template"])
        self.assertEqual(
            report["profile_template"]["fingerprint"]["jni_rvas"]["implOnDrawFrame"],
            0x1000,
        )

    def test_split_reference_identity_merges_arm64_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = self.make_bundle(root)
            ref = root / "reference.json"
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

            identity = {
                "package": "com.rockstargames.gtactw",
                "version_code": 4277603,
                "version_name": "4.4.243",
                "min_sdk": "28",
                "target_sdk": "35",
                "native_code": [],
            }
            with mock.patch.object(
                analyze_apkset.apk_identity,
                "inspect_apk_identity",
                return_value=identity,
            ):
                report = analyze_apkset.analyze_apkset(bundle, ref)

        self.assertTrue(report["gates"]["reference_build"])
        self.assertIn("arm64-v8a", report["apk_identity"]["native_code"])
        self.assertTrue(report["ok"])


if __name__ == "__main__":
    unittest.main()
