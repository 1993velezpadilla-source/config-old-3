#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abi_probe
import caller_abi_probe
from test_aarch64_xref import make_xref_fixture


CALL_CONTEXT_OBJDUMP = """
0000000000008000 <Caller>:
    8000: mov x0, x19
    8004: add x1, sp, #0x20
    8008: fmov s0, s8
    800c: bl 0x9000 <Target>
    8010: cbz w0, 0x8020 <Caller+0x20>
    8014: fmov s0, s9
    8018: ret
"""


class CallerAbiProbeTests(unittest.TestCase):
    def test_direct_call_sites_find_exact_bl_target(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libGame.so"
            make_xref_fixture(path)
            sites = caller_abi_probe.direct_call_sites(path, 0x1000)

        self.assertEqual(len(sites), 1)
        self.assertEqual(sites[0]["call_site_rva"], 0x1010)
        self.assertEqual(sites[0]["caller"], "MainLoopCaller")
        self.assertEqual(sites[0]["caller_rva"], 0x1010)

    def test_call_context_tracks_prepared_args_and_return_use(self):
        instructions = abi_probe.parse_objdump(
            CALL_CONTEXT_OBJDUMP,
            requested_rva=0x8000,
        )["instructions"]
        context = caller_abi_probe._call_context(
            instructions,
            0x800C,
        )

        self.assertIn(
            "x0",
            context["locally_prepared_argument_registers"],
        )
        self.assertIn(
            "x1",
            context["locally_prepared_argument_registers"],
        )
        self.assertIn(
            "v0",
            context["locally_prepared_argument_registers"],
        )
        self.assertEqual(
            context["return_use"]["x0"]["status"],
            "consumed",
        )
        self.assertEqual(
            context["return_use"]["x0"]["mnemonic"],
            "cbz",
        )
        self.assertEqual(
            context["return_use"]["v0"]["status"],
            "overwritten_without_read",
        )

    def test_call_context_keeps_passthrough_registers_separate(self):
        text = """
0000000000008100 <Caller>:
    8100: str x0, [sp, #0x10]
    8104: mov x1, x20
    8108: bl 0x9000 <Target>
    810c: ret
"""
        instructions = abi_probe.parse_objdump(
            text,
            requested_rva=0x8100,
        )["instructions"]
        context = caller_abi_probe._call_context(
            instructions,
            0x8108,
        )

        self.assertIn(
            "x0",
            context["possible_passthrough_argument_registers"],
        )
        self.assertIn(
            "x1",
            context["locally_prepared_argument_registers"],
        )


    def test_attach_caller_evidence_matches_exact_candidate_rva(self):
        profile = {
            "abi_verification": {
                key: {
                    "status": "pending",
                    "prototype": None,
                    "adapter": None,
                    "candidates": [],
                }
                for key in caller_abi_probe.profile_template.TARGET_KEYS
            }
        }
        profile["abi_verification"]["camera_update"]["candidates"] = [
            {"rva": 0x4000, "function": "CameraUpdate"},
            {"rva": 0x4100, "function": "OtherCamera"},
        ]
        report = {
            "targets": {
                "camera_update": [
                    {
                        "rva": 0x4000,
                        "caller_abi_evidence": {
                            "direct_call_site_count": 2,
                            "callers_analyzed": 2,
                            "callers": [{"caller": "FrameUpdate"}],
                        },
                    }
                ]
            },
            "note": "fixture",
        }

        updated = caller_abi_probe.attach_caller_abi_evidence(
            profile,
            report,
        )
        first, second = updated["abi_verification"]["camera_update"][
            "candidates"
        ]
        self.assertEqual(
            first["caller_abi_evidence"]["direct_call_site_count"],
            2,
        )
        self.assertNotIn("caller_abi_evidence", second)
        self.assertNotIn(
            "caller_abi_evidence",
            profile["abi_verification"]["camera_update"]["candidates"][0],
        )


if __name__ == "__main__":
    unittest.main()
