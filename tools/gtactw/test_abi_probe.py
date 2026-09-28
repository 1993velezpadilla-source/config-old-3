#!/usr/bin/env python3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abi_probe


CAMERA_OBJDUMP = """
0000000000004000 <CameraUpdate>:
    4000: stp x29, x30, [sp, #-0x40]!
    4004: mov x29, sp
    4008: ldr s0, [x1, #0x10]
    400c: ldr x8, [x0, #0x20]
    4010: bl 0x8000 <RaycastWorld>
    4014: cbz w0, 0x4020 <CameraUpdate+0x20>
    4018: add x2, x1, #0x10
    401c: ret
"""

PROJECTION_OBJDUMP = """
0000000000005000 <ProjectionSetup>:
    5000: sub sp, sp, #0x20
    5004: fmov s8, s0
    5008: fmul s9, s1, s2
    500c: mov w8, w0
    5010: bl 0x9000 <glUniformMatrix4fv@plt>
    5014: add sp, sp, #0x20
    5018: ret
"""


class AbiProbeTests(unittest.TestCase):
    def test_camera_evidence_parser(self):
        report = abi_probe.parse_objdump(
            CAMERA_OBJDUMP,
            requested_rva=0x4000,
        )

        self.assertEqual(report["requested_rva"], 0x4000)
        self.assertEqual(report["instruction_count"], 8)
        self.assertEqual(report["stack_frame_bytes_hint"], 0x40)
        self.assertIn("x29", report["saved_registers"])
        self.assertIn("x30", report["saved_registers"])
        self.assertIn(
            0,
            report["argument_register_hints"]["likely_gpr_inputs_x0_x7"],
        )
        self.assertIn(
            1,
            report["argument_register_hints"]["likely_gpr_inputs_x0_x7"],
        )
        self.assertEqual(report["calls"][0]["target_rva"], 0x8000)
        self.assertEqual(report["calls"][0]["symbol"], "RaycastWorld")
        self.assertEqual(report["returns"], [0x401C])
        self.assertEqual(report["verification_status"], "abi_hint_only")

    def test_projection_fp_register_evidence(self):
        report = abi_probe.parse_objdump(
            PROJECTION_OBJDUMP,
            requested_rva=0x5000,
        )

        self.assertEqual(report["stack_frame_bytes_hint"], 0x20)
        fp = report["argument_register_hints"]["likely_fp_inputs_v0_v7"]
        self.assertIn(0, fp)
        self.assertIn(1, fp)
        self.assertIn(2, fp)
        self.assertEqual(
            report["calls"][0]["symbol"],
            "glUniformMatrix4fv@plt",
        )

    def test_candidate_selection_prefers_verified_target(self):
        profile = {
            "patch_targets_rva": {
                "camera_update": 0x4000,
                "projection_setup": None,
                "world_stream_update": None,
                "sector_visibility": None,
                "lod_test": None,
                "player_render": None,
            },
            "target_verification": {
                "camera_update": {
                    "status": "verified",
                    "rva": 0x4000,
                }
            },
            "target_evidence_rankings": {
                "camera_update": [
                    {"rva": 0x4100, "score": 99, "function": "Wrong"}
                ],
                "projection_setup": [
                    {
                        "rva": 0x5000,
                        "score": 20,
                        "function": "ProjectionSetup",
                        "reasons": ["fixture"],
                    },
                    {
                        "rva": 0x5100,
                        "score": 10,
                        "function": "Other",
                        "reasons": [],
                    },
                ],
            },
        }

        out = abi_probe._candidate_targets(profile, 1)
        self.assertEqual(out["camera_update"][0]["rva"], 0x4000)
        self.assertEqual(
            out["camera_update"][0]["source"],
            "verified_target",
        )
        self.assertEqual(out["projection_setup"][0]["rva"], 0x5000)
        self.assertEqual(
            out["projection_setup"][0]["source"],
            "evidence_ranking",
        )


    def test_attach_abi_evidence_keeps_status_pending(self):
        profile = {
            "patch_targets_rva": {
                key: None for key in abi_probe.profile_template.TARGET_KEYS
            },
            "abi_verification": {
                key: {
                    "status": "pending",
                    "prototype": None,
                    "calling_convention": "aarch64_aapcs64",
                    "adapter": None,
                    "evidence": [],
                }
                for key in abi_probe.profile_template.TARGET_KEYS
            },
        }
        report = {
            "targets": {
                "camera_update": [
                    {
                        "rva": 0x4000,
                        "source": "evidence_ranking",
                        "function": "CameraUpdate",
                        "score": 42,
                        "reasons": ["fixture"],
                        "abi_evidence": {
                            "verification_status": "abi_hint_only",
                            "argument_register_hints": {
                                "likely_gpr_inputs_x0_x7": [0, 1],
                            },
                            "prologue_relocation": {
                                "simple_copy_trampoline_safe": True,
                                "instructions": [],
                            },
                        },
                    }
                ]
            },
            "note": "fixture evidence only",
        }

        updated = abi_probe.attach_abi_evidence(profile, report)
        item = updated["abi_verification"]["camera_update"]
        self.assertEqual(item["status"], "pending")
        self.assertIsNone(item["prototype"])
        self.assertIsNone(item["adapter"])
        self.assertEqual(item["last_probe_status"], "evidence_collected")
        self.assertEqual(item["candidates"][0]["rva"], 0x4000)
        self.assertEqual(
            item["candidates"][0]["abi_evidence"]["verification_status"],
            "abi_hint_only",
        )
        self.assertEqual(
            item["candidates"][0]["trampoline_strategy_hint"],
            "simple_copy_trampoline_candidate",
        )
        self.assertIsNone(profile["abi_verification"]["camera_update"].get("candidates"))


    def test_attach_abi_marks_unsafe_prologue_for_advanced_relocator(self):
        profile = {
            "patch_targets_rva": {
                key: None for key in abi_probe.profile_template.TARGET_KEYS
            },
            "abi_verification": {
                key: {
                    "status": "pending",
                    "prototype": None,
                    "calling_convention": "aarch64_aapcs64",
                    "adapter": None,
                    "evidence": [],
                }
                for key in abi_probe.profile_template.TARGET_KEYS
            },
        }
        report = {
            "targets": {
                "projection_setup": [
                    {
                        "rva": 0x5000,
                        "source": "evidence_ranking",
                        "function": "ProjectionSetup",
                        "score": 20,
                        "reasons": ["fixture"],
                        "abi_evidence": {
                            "verification_status": "abi_hint_only",
                            "prologue_relocation": {
                                "simple_copy_trampoline_safe": False,
                                "instructions": [
                                    {
                                        "kind": "adrp",
                                        "relocatable_for_simple_copy": False,
                                    }
                                ],
                            },
                        },
                    }
                ]
            }
        }
        updated = abi_probe.attach_abi_evidence(profile, report)
        candidate = updated["abi_verification"]["projection_setup"][
            "candidates"
        ][0]
        self.assertEqual(
            candidate["trampoline_strategy_hint"],
            "advanced_relocator_required",
        )

    def test_rejects_empty_disassembly(self):
        with self.assertRaises(ValueError):
            abi_probe.parse_objdump("nothing here")


if __name__ == "__main__":
    unittest.main()
