#!/usr/bin/env python3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adapter_catalog
import profile_template


def make_profile():
    profile = {
        "patch_targets_rva": {},
        "abi_verification": {},
    }
    for index, key in enumerate(profile_template.TARGET_KEYS, start=1):
        rva = 0x4000 + index * 0x100
        name = f"ctw_{key}_adapter_v1"
        profile["patch_targets_rva"][key] = rva
        profile["abi_verification"][key] = {
            "status": "verified",
            "prototype": f"void {key}(void)",
            "calling_convention": "aarch64_aapcs64",
            "adapter": name,
            "verified_rva": rva,
            "evidence": [{"method": "fixture", "detail": key}],
        }
    return profile


def make_catalog(*, implemented=True):
    return {
        "schema": 1,
        "adapters": [
            {
                "name": f"ctw_{key}_adapter_v1",
                "target": key,
                "native_symbol": f"ctw_{key}_adapter_v1",
                "implemented": implemented,
            }
            for key in profile_template.TARGET_KEYS
        ],
    }


class AdapterCatalogTests(unittest.TestCase):
    def test_all_verified_adapters_ready(self):
        report = adapter_catalog.validate_profile_adapters(
            make_profile(),
            make_catalog(),
        )
        self.assertTrue(report["ready"])
        self.assertEqual(report["ready_count"], 6)
        self.assertTrue(
            report["targets"]["projection_setup"]["ready"]
        )

    def test_missing_adapter_rejected(self):
        catalog = make_catalog()
        catalog["adapters"] = catalog["adapters"][1:]
        report = adapter_catalog.validate_profile_adapters(
            make_profile(),
            catalog,
        )
        self.assertFalse(report["ready"])
        self.assertIn(
            "adapter_not_in_catalog",
            report["targets"]["camera_update"]["reasons"],
        )

    def test_unimplemented_adapter_rejected(self):
        catalog = make_catalog()
        catalog["adapters"][2]["implemented"] = False
        report = adapter_catalog.validate_profile_adapters(
            make_profile(),
            catalog,
        )
        self.assertFalse(report["ready"])
        self.assertIn(
            "adapter_not_implemented",
            report["targets"]["world_stream_update"]["reasons"],
        )

    def test_wrong_target_rejected(self):
        catalog = make_catalog()
        catalog["adapters"][0]["target"] = "projection_setup"
        report = adapter_catalog.validate_profile_adapters(
            make_profile(),
            catalog,
        )
        self.assertFalse(report["ready"])
        self.assertIn(
            "adapter_target_mismatch",
            report["targets"]["camera_update"]["reasons"],
        )

    def test_verified_rva_must_match_profile_target(self):
        profile = make_profile()
        profile["abi_verification"]["lod_test"]["verified_rva"] = 0x9999
        report = adapter_catalog.validate_profile_adapters(
            profile,
            make_catalog(),
        )
        self.assertFalse(report["ready"])
        self.assertIn(
            "abi_verified_rva_mismatch",
            report["targets"]["lod_test"]["reasons"],
        )


if __name__ == "__main__":
    unittest.main()
