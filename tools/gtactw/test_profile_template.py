#!/usr/bin/env python3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile_template


class ProfileTemplateTests(unittest.TestCase):
    def make_report(self):
        p = "Java_com_rockstargames_oswrapper_GameNative_"
        return {
            "file_size": 123456,
            "sha256": "a" * 64,
            "elf": {
                "machine": "AArch64",
                "build_id": "0123456789abcdef",
            },
            "text": {"sha256": "b" * 64},
            "symbols": {
                "known_jni_details": {
                    p + "implOnDrawFrame": {
                        "present": True,
                        "value": 0x1000,
                        "size": 16,
                    },
                    p + "implOnInitialSetup": {
                        "present": True,
                        "value": 0x2000,
                        "size": 16,
                    },
                    p + "implOnGamepadAxesChanged": {
                        "present": True,
                        "value": 0x3000,
                        "size": 16,
                    },
                },
                "candidate_groups": {
                    "camera": [
                        {
                            "source": "symbol",
                            "name": "CameraUpdate",
                            "value": 0x4000,
                            "size": 64,
                        }
                    ],
                    "streaming": [],
                    "lod_culling": [],
                    "player_render": [],
                },
            },
        }

    def test_profile_uses_jni_rvas_and_empty_patch_targets(self):
        profile = profile_template.make_profile(self.make_report())
        self.assertEqual(
            profile["fingerprint"]["jni_rvas"]["implOnDrawFrame"],
            0x1000,
        )
        self.assertEqual(
            profile["candidate_symbols"]["camera"][0]["name"],
            "CameraUpdate",
        )
        self.assertTrue(
            all(v is None for v in profile["patch_targets_rva"].values())
        )
        self.assertEqual(
            profile["status"],
            "template_needs_verified_internal_rvas",
        )

    def test_rejects_missing_required_jni(self):
        report = self.make_report()
        p = "Java_com_rockstargames_oswrapper_GameNative_"
        report["symbols"]["known_jni_details"][
            p + "implOnDrawFrame"
        ]["present"] = False
        with self.assertRaises(ValueError):
            profile_template.make_profile(report)


if __name__ == "__main__":
    unittest.main()
