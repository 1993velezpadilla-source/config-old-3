#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adapter_emit_c
import profile_template


class AdapterEmitCTests(unittest.TestCase):
    def fixture(self):
        obj = {
            "patch_targets_rva": {},
            "target_verification": {},
            "abi_verification": {},
        }
        for index, key in enumerate(profile_template.TARGET_KEYS, start=1):
            rva = 0x4000 + index * 0x100
            obj["patch_targets_rva"][key] = rva
            obj["target_verification"][key] = {
                "status": "verified",
                "rva": rva,
                "evidence": [{"method": "fixture", "detail": key}],
                "code_prefix_hex": "aa" * 16,
            }
            obj["abi_verification"][key] = {
                "status": "verified",
                "prototype": f"void {key}(void)",
                "calling_convention": "aarch64_aapcs64",
                "adapter": f"ctw_{key}_adapter_v1",
                "verified_rva": rva,
                "trampoline_strategy": (
                    "simple_copy_trampoline_candidate"
                ),
                "evidence": [
                    {
                        "method": "fixture",
                        "detail": f"ABI {key}",
                    }
                ],
            }
        return obj

    def test_emits_verified_adapter_symbols(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "profile.json"
            path.write_text(
                json.dumps(self.fixture()),
                encoding="utf-8",
            )
            bindings = adapter_emit_c.adapters_from_profile(path)
            header = adapter_emit_c.emit_header(bindings)

        self.assertEqual(len(bindings), 6)
        self.assertIn(
            "extern void ctw_camera_update_adapter_v1(void);",
            header,
        )
        self.assertIn(
            '{ "ctw_projection_setup_adapter_v1", '
            '(void *)&ctw_projection_setup_adapter_v1 },',
            header,
        )
        self.assertIn("g_ctw_adapter_bindings_count", header)

    def test_rejects_pending_abi(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            obj = self.fixture()
            obj["abi_verification"]["lod_test"]["status"] = "pending"
            path = root / "profile.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                adapter_emit_c.adapters_from_profile(path)

    def test_rejects_invalid_c_identifier(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            obj = self.fixture()
            obj["abi_verification"]["player_render"]["adapter"] = (
                "bad-adapter-name"
            )
            path = root / "profile.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                adapter_emit_c.adapters_from_profile(path)

    def test_rejects_abi_rva_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            obj = self.fixture()
            obj["abi_verification"]["camera_update"]["verified_rva"] = 0x9999
            path = root / "profile.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                adapter_emit_c.adapters_from_profile(path)

    def test_deduplicates_adapter_symbols(self):
        obj = self.fixture()
        shared = "ctw_shared_adapter_v1"
        obj["abi_verification"]["camera_update"]["adapter"] = shared
        obj["abi_verification"]["projection_setup"]["adapter"] = shared

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "profile.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            header = adapter_emit_c.emit_header(
                adapter_emit_c.adapters_from_profile(path)
            )

        self.assertEqual(
            header.count(f"extern void {shared}(void);"),
            1,
        )
        self.assertEqual(
            header.count(f'{{ "{shared}", (void *)&{shared} }}'),
            1,
        )


if __name__ == "__main__":
    unittest.main()
