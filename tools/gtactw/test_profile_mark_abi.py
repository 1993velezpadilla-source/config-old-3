#!/usr/bin/env python3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loader_variant
import profile_mark_abi
import profile_template


class ProfileMarkAbiTests(unittest.TestCase):
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
                        "trampoline_strategy_hint": loader_variant.SIMPLE,
                        "abi_evidence": {
                            "verification_status": "abi_hint_only",
                            "prologue_relocation": {
                                "simple_copy_trampoline_safe": True,
                            },
                        },
                    }
                ],
            }
        return profile

    def test_marks_matching_probed_abi(self):
        profile = self.fixture()
        updated = profile_mark_abi.mark_abi_verified(
            profile,
            target="camera_update",
            prototype="void camera_update(void *camera, float dt)",
            adapter="ctw_camera_update_adapter_v1",
            method="manual-disassembly",
            detail="x0 camera pointer; s0 dt verified at callers",
        )

        item = updated["abi_verification"]["camera_update"]
        self.assertEqual(item["status"], "verified")
        self.assertEqual(
            item["prototype"],
            "void camera_update(void *camera, float dt)",
        )
        self.assertEqual(item["adapter"], "ctw_camera_update_adapter_v1")
        self.assertEqual(item["verified_rva"], 0x4100)
        self.assertEqual(
            item["trampoline_strategy"],
            loader_variant.SIMPLE,
        )
        self.assertEqual(
            item["evidence"][0]["trampoline_strategy"],
            loader_variant.SIMPLE,
        )
        self.assertEqual(
            profile["abi_verification"]["camera_update"]["status"],
            "pending",
        )

    def test_requires_verified_target_first(self):
        profile = self.fixture()
        profile["target_verification"]["lod_test"]["status"] = "pending"
        with self.assertRaises(ValueError):
            profile_mark_abi.mark_abi_verified(
                profile,
                target="lod_test",
                prototype="int lod_test(void *)",
                adapter="ctw_lod_adapter_v1",
                method="manual",
                detail="fixture",
            )

    def test_rejects_missing_probe_by_default(self):
        profile = self.fixture()
        profile["abi_verification"]["player_render"]["candidates"] = []
        with self.assertRaises(ValueError):
            profile_mark_abi.mark_abi_verified(
                profile,
                target="player_render",
                prototype="void player_render(void *)",
                adapter="ctw_player_render_adapter_v1",
                method="manual",
                detail="fixture",
            )

    def test_allow_unprobed_requires_explicit_strategy(self):
        profile = self.fixture()
        profile["abi_verification"]["player_render"]["candidates"] = []
        with self.assertRaises(ValueError):
            profile_mark_abi.mark_abi_verified(
                profile,
                target="player_render",
                prototype="void player_render(void *)",
                adapter="ctw_player_render_adapter_v1",
                method="manual",
                detail="fixture",
                allow_unprobed=True,
            )

        updated = profile_mark_abi.mark_abi_verified(
            profile,
            target="player_render",
            prototype="void player_render(void *)",
            adapter="ctw_player_render_adapter_v1",
            method="manual-runtime-trace",
            detail="independent ABI review",
            allow_unprobed=True,
            strategy=loader_variant.ADVANCED,
        )
        self.assertEqual(
            updated["abi_verification"]["player_render"][
                "trampoline_strategy"
            ],
            loader_variant.ADVANCED,
        )

    def test_rejects_strategy_conflict_with_probe(self):
        profile = self.fixture()
        with self.assertRaises(ValueError):
            profile_mark_abi.mark_abi_verified(
                profile,
                target="projection_setup",
                prototype="void projection_setup(void *)",
                adapter="ctw_projection_adapter_v1",
                method="manual",
                detail="fixture",
                strategy=loader_variant.ADVANCED,
            )


if __name__ == "__main__":
    unittest.main()
