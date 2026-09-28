#!/usr/bin/env python3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loader_variant
import profile_template


class LoaderVariantTests(unittest.TestCase):
    def fixture(self):
        profile = {
            "patch_targets_rva": {},
            "target_verification": {},
            "abi_verification": {},
        }
        for index, key in enumerate(profile_template.TARGET_KEYS, start=1):
            rva = 0x4000 + index * 0x100
            profile["patch_targets_rva"][key] = rva
            profile["target_verification"][key] = {
                "status": "verified",
                "rva": rva,
                "evidence": [{"method": "fixture", "detail": key}],
                "code_prefix_hex": "aa" * 16,
            }
            profile["abi_verification"][key] = {
                "status": "pending",
                "prototype": None,
                "calling_convention": "aarch64_aapcs64",
                "adapter": None,
                "evidence": [],
                "candidates": [
                    {
                        "rva": rva,
                        "function": key,
                        "source": "verified_target",
                        "trampoline_strategy_hint": (
                            loader_variant.SIMPLE
                        ),
                    }
                ],
            }
        return profile

    def test_all_simple_selects_minimal(self):
        report = loader_variant.select_loader_variant(self.fixture())
        self.assertTrue(report["ready"])
        self.assertEqual(report["loader_variant"], "minimal")
        self.assertEqual(
            len(report["simple_copy_targets"]),
            len(profile_template.TARGET_KEYS),
        )
        self.assertEqual(report["advanced_relocator_targets"], [])

    def test_one_advanced_selects_shadowhook(self):
        profile = self.fixture()
        key = "projection_setup"
        profile["abi_verification"][key]["candidates"][0][
            "trampoline_strategy_hint"
        ] = loader_variant.ADVANCED

        report = loader_variant.select_loader_variant(profile)
        self.assertTrue(report["ready"])
        self.assertEqual(report["loader_variant"], "shadowhook")
        self.assertEqual(
            report["advanced_relocator_targets"],
            ["projection_setup"],
        )

    def test_unverified_target_is_undetermined(self):
        profile = self.fixture()
        profile["target_verification"]["lod_test"]["status"] = "pending"

        report = loader_variant.select_loader_variant(profile)
        self.assertFalse(report["ready"])
        self.assertEqual(report["loader_variant"], "undetermined")
        self.assertIn("lod_test", report["undetermined_targets"])

    def test_missing_matching_strategy_is_undetermined(self):
        profile = self.fixture()
        profile["abi_verification"]["player_render"]["candidates"][0][
            "rva"
        ] = 0x9999

        report = loader_variant.select_loader_variant(profile)
        self.assertFalse(report["ready"])
        self.assertEqual(report["loader_variant"], "undetermined")
        self.assertEqual(
            report["targets"]["player_render"]["reason"],
            "missing_strategy_for_verified_rva",
        )

    def test_duplicate_matching_strategy_is_ambiguous(self):
        profile = self.fixture()
        key = "camera_update"
        duplicate = dict(profile["abi_verification"][key]["candidates"][0])
        profile["abi_verification"][key]["candidates"].append(duplicate)

        report = loader_variant.select_loader_variant(profile)
        self.assertFalse(report["ready"])
        self.assertEqual(
            report["targets"][key]["reason"],
            "ambiguous_strategy_for_verified_rva",
        )


if __name__ == "__main__":
    unittest.main()
