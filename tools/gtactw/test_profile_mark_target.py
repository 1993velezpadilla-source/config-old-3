#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile_mark_target
import profile_template
from test_profile_verify_binary import make_fixture


class ProfileMarkTargetTests(unittest.TestCase):
    def profile(self):
        return {
            "patch_targets_rva": {
                key: None for key in profile_template.TARGET_KEYS
            },
            "target_verification": {
                key: {
                    "status": "pending",
                    "rva": None,
                    "evidence": [],
                    "code_prefix_hex": None,
                }
                for key in profile_template.TARGET_KEYS
            },
            "abi_verification": {
                key: {
                    "status": "pending",
                    "prototype": None,
                    "calling_convention": "aarch64_aapcs64",
                    "adapter": None,
                    "evidence": [],
                }
                for key in profile_template.TARGET_KEYS
            },
            "target_evidence_rankings": {
                key: [] for key in profile_template.TARGET_KEYS
            },
        }

    def test_marks_ranked_target_and_captures_binary_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame = root / "libGame.so"
            text = make_fixture(libgame)
            profile = self.profile()
            profile["target_evidence_rankings"]["camera_update"] = [
                {
                    "rva": 0x1040,
                    "function": "CameraUpdate",
                    "score": 20,
                    "reasons": ["fixture"],
                }
            ]

            updated = profile_mark_target.mark_target_verified(
                libgame,
                profile,
                target="camera_update",
                rva=0x1040,
                method="manual-disassembly",
                detail="camera pose writes verified",
            )

        expected = text[0x40:0x50].hex()
        self.assertEqual(updated["patch_targets_rva"]["camera_update"], 0x1040)
        item = updated["target_verification"]["camera_update"]
        self.assertEqual(item["status"], "verified")
        self.assertEqual(item["rva"], 0x1040)
        self.assertEqual(item["code_prefix_hex"], expected)
        self.assertEqual(
            item["evidence"][0]["method"],
            "manual-disassembly",
        )
        self.assertEqual(
            updated["abi_verification"]["camera_update"]["status"],
            "pending",
        )
        self.assertIsNone(
            profile["patch_targets_rva"]["camera_update"]
        )

    def test_rejects_unranked_target_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame = root / "libGame.so"
            make_fixture(libgame)
            with self.assertRaises(ValueError):
                profile_mark_target.mark_target_verified(
                    libgame,
                    self.profile(),
                    target="lod_test",
                    rva=0x1080,
                    method="manual",
                    detail="fixture",
                )

    def test_allows_explicit_unranked_manual_verification(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame = root / "libGame.so"
            make_fixture(libgame)
            updated = profile_mark_target.mark_target_verified(
                libgame,
                self.profile(),
                target="lod_test",
                rva=0x1080,
                method="manual-control-flow-review",
                detail="independently verified target",
                allow_unranked=True,
            )

        self.assertEqual(
            updated["target_verification"]["lod_test"]["status"],
            "verified",
        )

    def test_rejects_non_executable_rva(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame = root / "libGame.so"
            make_fixture(libgame)
            profile = self.profile()
            profile["target_evidence_rankings"]["player_render"] = [
                {"rva": 0x5000, "score": 10}
            ]
            with self.assertRaises(ValueError):
                profile_mark_target.mark_target_verified(
                    libgame,
                    profile,
                    target="player_render",
                    rva=0x5000,
                    method="manual",
                    detail="fixture",
                )


if __name__ == "__main__":
    unittest.main()
