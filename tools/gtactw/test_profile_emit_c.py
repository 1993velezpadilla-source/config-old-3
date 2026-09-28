#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile_emit_c


class ProfileEmitCTests(unittest.TestCase):
    def fixture(self):
        return {
            "fingerprint": {
                "sha256": "a" * 64,
                "jni_rvas": {
                    "implOnDrawFrame": 0x1000,
                    "implOnInitialSetup": 0x2000,
                    "implOnGamepadAxesChanged": 0x2500,
                },
            },
            "patch_targets_rva": {
                "camera_update": 0x3000,
                "projection_setup": 0x4000,
                "world_stream_update": 0x5000,
                "sector_visibility": 0x6000,
                "lod_test": 0x7000,
                "player_render": 0x8000,
            },
            "target_verification": {
                "camera_update": {"status": "verified", "rva": 0x3000, "evidence": [{"method": "xref+disassembly", "detail": "fixture camera"}], "code_prefix_hex": "00" * 16},
                "projection_setup": {"status": "verified", "rva": 0x4000, "evidence": [{"method": "xref+disassembly", "detail": "fixture projection"}], "code_prefix_hex": "11" * 16},
                "world_stream_update": {"status": "verified", "rva": 0x5000, "evidence": [{"method": "xref+disassembly", "detail": "fixture streaming"}], "code_prefix_hex": "22" * 16},
                "sector_visibility": {"status": "verified", "rva": 0x6000, "evidence": [{"method": "xref+disassembly", "detail": "fixture sector"}], "code_prefix_hex": "33" * 16},
                "lod_test": {"status": "verified", "rva": 0x7000, "evidence": [{"method": "xref+disassembly", "detail": "fixture lod"}], "code_prefix_hex": "44" * 16},
                "player_render": {"status": "verified", "rva": 0x8000, "evidence": [{"method": "xref+disassembly", "detail": "fixture player"}], "code_prefix_hex": "55" * 16},
            },
        }

    def test_emit_verified_profile_header(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ctw-4.4.243.json"
            path.write_text(json.dumps(self.fixture()), encoding="utf-8")
            p = profile_emit_c.load_verified_profile(path)
            header = profile_emit_c.emit_header([p])

        self.assertIn(".expected_draw_frame_rva = 0x1000u", header)
        self.assertIn(".expected_gamepad_axes_rva = 0x2500u", header)
        self.assertIn(".camera_update = 0x3000u", header)
        self.assertIn(".target_prefixes = {", header)
        self.assertIn("0x11, 0x11, 0x11, 0x11", header)
        self.assertIn("g_ctw_profiles_count", header)

    def test_rejects_unverified_missing_target(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.fixture()
            obj["patch_targets_rva"]["player_render"] = None
            path = Path(td) / "bad.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                profile_emit_c.load_verified_profile(path)


    def test_rejects_target_without_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.fixture()
            obj["target_verification"]["camera_update"]["evidence"] = []
            path = Path(td) / "bad-evidence.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                profile_emit_c.load_verified_profile(path)

    def test_rejects_verification_rva_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.fixture()
            obj["target_verification"]["lod_test"]["rva"] = 0x9999
            path = Path(td) / "bad-rva.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                profile_emit_c.load_verified_profile(path)


    def test_rejects_missing_code_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.fixture()
            obj["target_verification"]["camera_update"]["code_prefix_hex"] = None
            path = Path(td) / "bad-prefix.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                profile_emit_c.load_verified_profile(path)

    def test_rejects_duplicate_runtime_fingerprint(self):
        p = {
            "name": "a",
            "draw": 0x1000,
            "setup": 0x2000,
            "axes": 0x2500,
            "targets": {key: 0x3000 for key in profile_emit_c.TARGET_KEYS},
        }
        with self.assertRaises(ValueError):
            profile_emit_c.emit_header([p, dict(p, name="b")])


if __name__ == "__main__":
    unittest.main()
