#!/usr/bin/env python3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile_status
import profile_template


class ProfileStatusTests(unittest.TestCase):
    def fixture(self):
        profile = {
            "fingerprint": {
                "sha256": "a" * 64,
                "text_sha256": "b" * 64,
                "gnu_build_id": "0123456789abcdef",
                "jni_rvas": {
                    "implOnDrawFrame": 0x1000,
                    "implOnInitialSetup": 0x2000,
                    "implOnGamepadAxesChanged": 0x3000,
                },
            },
            "public_4243_engine_anchors": {
                "present_count": 7,
                "total_count": 9,
                "present": [],
            },
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
        }
        return profile

    def test_pending_targets_and_anchor_coverage(self):
        status = profile_status.profile_status(self.fixture())
        self.assertTrue(status["fingerprint_ready"])
        self.assertEqual(status["phase"], "needs_verified_target_rvas")
        self.assertEqual(status["targets_verified"], 0)
        self.assertEqual(
            status["public_4243_engine_anchors"]["present_count"],
            7,
        )
        self.assertEqual(
            status["public_4243_engine_anchors"]["total_count"],
            9,
        )
        self.assertTrue(
            status["public_4243_engine_anchors"]["available"]
        )

    def test_verified_targets_still_require_abis(self):
        profile = self.fixture()
        for index, key in enumerate(profile_template.TARGET_KEYS, start=1):
            rva = 0x4000 + index * 0x100
            profile["patch_targets_rva"][key] = rva
            profile["target_verification"][key] = {
                "status": "verified",
                "rva": rva,
                "evidence": [
                    {"method": "fixture", "detail": f"verified {key}"}
                ],
                "code_prefix_hex": "aa" * 16,
            }

        status = profile_status.profile_status(profile)
        self.assertEqual(status["targets_verified"], 6)
        self.assertEqual(status["abis_verified"], 0)
        self.assertEqual(status["phase"], "needs_verified_hook_abis")

    def test_full_abi_ledger_reaches_adapter_gate_only(self):
        profile = self.fixture()
        for index, key in enumerate(profile_template.TARGET_KEYS, start=1):
            rva = 0x4000 + index * 0x100
            profile["patch_targets_rva"][key] = rva
            profile["target_verification"][key] = {
                "status": "verified",
                "rva": rva,
                "evidence": [
                    {"method": "fixture", "detail": f"verified {key}"}
                ],
                "code_prefix_hex": "aa" * 16,
            }
            profile["abi_verification"][key] = {
                "status": "verified",
                "prototype": f"void {key}(void)",
                "calling_convention": "aarch64_aapcs64",
                "adapter": f"{key}_adapter_v1",
                "evidence": [
                    {"method": "fixture", "detail": f"ABI {key}"}
                ],
            }

        status = profile_status.profile_status(profile)
        self.assertEqual(status["targets_verified"], 6)
        self.assertEqual(status["abis_verified"], 6)
        self.assertEqual(
            status["phase"],
            "abi_verified_ready_for_hook_adapter_gate",
        )
        self.assertFalse(status["runtime_hooks_installed"])
        self.assertFalse(status["playable_3d_mod_ready"])


if __name__ == "__main__":
    unittest.main()
