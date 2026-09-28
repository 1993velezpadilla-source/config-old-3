#!/usr/bin/env python3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hook_dossier
import profile_template


class HookDossierTests(unittest.TestCase):
    def fixture(self):
        return {
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
                "present_count": 8,
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
            "target_evidence_rankings": {
                "projection_setup": [
                    {
                        "rva": 0x5000,
                        "function": "FrameProjection",
                        "score": 44,
                        "reasons": [
                            "calls glUniformMatrix4fv through verified PLT mapping",
                            "reachable from implOnDrawFrame in 1 symbol hop(s)",
                        ],
                        "strings": ["matProj"],
                        "plt_imports": [
                            "glUniformMatrix4fv",
                            "glDepthRangef",
                        ],
                        "draw_frame_hops": 1,
                        "draw_frame_path_functions": [
                            profile_template.DRAW,
                            "FrameProjection",
                        ],
                        "function_fingerprint": {
                            "rva": 0x5000,
                            "size": 64,
                            "sha256": "c" * 64,
                            "prefix_hex": "aa" * 16,
                        },
                    }
                ],
            },
            "abi_verification": {
                key: {
                    "status": "pending",
                    "prototype": None,
                    "calling_convention": "aarch64_aapcs64",
                    "adapter": None,
                    "evidence": [],
                    "candidates": [],
                }
                for key in profile_template.TARGET_KEYS
            },
        }

    def test_projection_dossier_merges_ranking_and_abi(self):
        profile = self.fixture()
        profile["abi_verification"]["projection_setup"]["candidates"] = [
            {
                "rva": 0x5000,
                "function": "FrameProjection",
                "source": "evidence_ranking",
                "trampoline_strategy_hint": (
                    "advanced_relocator_required"
                ),
                "abi_evidence": {
                    "stack_frame_bytes_hint": 64,
                    "argument_register_hints": {
                        "analysis": "read_before_write",
                        "likely_gpr_inputs_x0_x7": [0, 1],
                        "overwritten_gpr_early_x0_x7": [2],
                        "likely_fp_inputs_v0_v7": [0, 1, 2],
                        "overwritten_fp_before_read_v0_v7": [3],
                        "first_access": {
                            "x0": {
                                "mode": "read",
                                "address": 0x5004,
                                "mnemonic": "ldr",
                                "operands": "x8, [x0]",
                            },
                            "x2": {
                                "mode": "write",
                                "address": 0x5008,
                                "mnemonic": "mov",
                                "operands": "x2, x9",
                            },
                        },
                    },
                    "calls": [
                        {
                            "symbol": "glUniformMatrix4fv@plt",
                            "address": 0x5040,
                        }
                    ],
                    "prologue_relocation": {
                        "simple_copy_trampoline_safe": False,
                        "instructions": [
                            {
                                "rva": 0x5000,
                                "kind": "adrp",
                                "relocatable_for_simple_copy": False,
                            }
                        ],
                    },
                },
            }
        ]

        report = hook_dossier.build_dossier(profile, top=3)
        projection = report["targets"]["projection_setup"]
        self.assertFalse(projection["verified"])
        self.assertEqual(projection["candidate_count_shown"], 1)

        candidate = projection["candidates"][0]
        self.assertEqual(candidate["rank"], 1)
        self.assertEqual(candidate["rva_hex"], "0x5000")
        self.assertEqual(candidate["draw_frame_hops"], 1)
        self.assertIn("glUniformMatrix4fv", candidate["plt_imports"])
        self.assertEqual(
            candidate["trampoline_strategy_hint"],
            "advanced_relocator_required",
        )
        self.assertFalse(candidate["prologue_simple_copy_safe"])
        self.assertEqual(candidate["stack_frame_bytes_hint"], 64)
        self.assertEqual(candidate["likely_gpr_inputs_x0_x7"], [0, 1])
        self.assertEqual(candidate["likely_fp_inputs_v0_v7"], [0, 1, 2])
        self.assertEqual(candidate["argument_analysis"], "read_before_write")
        self.assertEqual(
            candidate["argument_first_access"]["x0"]["mode"],
            "read",
        )
        self.assertEqual(
            candidate["overwritten_gpr_before_read_x0_x7"],
            [2],
        )
        self.assertEqual(
            candidate["overwritten_fp_before_read_v0_v7"],
            [3],
        )

        self.assertEqual(report["summary"]["targets_verified"], 0)
        self.assertEqual(report["summary"]["targets_with_candidates"], 1)
        self.assertEqual(
            report["public_4243_engine_anchors"]["present_count"],
            8,
        )

    def test_verified_target_is_reported_without_auto_promotion(self):
        profile = self.fixture()
        key = "camera_update"
        profile["patch_targets_rva"][key] = 0x4000
        profile["target_verification"][key] = {
            "status": "verified",
            "rva": 0x4000,
            "evidence": [{"method": "fixture", "detail": "camera"}],
            "code_prefix_hex": "aa" * 16,
        }
        profile["target_evidence_rankings"][key] = [
            {
                "rva": 0x4000,
                "function": "CameraUpdate",
                "score": 20,
                "reasons": ["fixture"],
            }
        ]

        report = hook_dossier.build_dossier(profile)
        self.assertTrue(report["targets"][key]["verified"])
        self.assertEqual(report["summary"]["targets_verified"], 1)

    def test_top_limit(self):
        profile = self.fixture()
        profile["target_evidence_rankings"]["camera_update"] = [
            {
                "rva": 0x4000 + i * 0x100,
                "function": f"Camera{i}",
                "score": 20 - i,
                "reasons": [],
            }
            for i in range(8)
        ]
        report = hook_dossier.build_dossier(profile, top=2)
        self.assertEqual(
            report["targets"]["camera_update"]["candidate_count_shown"],
            2,
        )

    def test_rejects_invalid_top(self):
        with self.assertRaises(ValueError):
            hook_dossier.build_dossier(self.fixture(), top=0)
        with self.assertRaises(ValueError):
            hook_dossier.build_dossier(self.fixture(), top=17)


if __name__ == "__main__":
    unittest.main()
