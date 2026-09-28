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
                "trampoline_strategy": "simple_copy_trampoline_candidate",
                "evidence": [{"method": "fixture", "detail": f"ABI {key}"}],
            }
        return obj

    def catalog(self, *, implemented=True):
        return {
            "schema": 1,
            "adapters": [
                {
                    "name": f"ctw_{key}_adapter_v1",
                    "target": key,
                    "native_symbol": f"ctw_{key}_native_v1",
                    "implemented": implemented,
                }
                for key in profile_template.TARGET_KEYS
            ],
        }

    def test_emits_verified_adapter_symbols(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "profile.json"
            path.write_text(json.dumps(self.fixture()), encoding="utf-8")
            bindings = adapter_emit_c.adapters_from_profile(
                path, self.catalog()
            )
            header = adapter_emit_c.emit_header(bindings)

        self.assertEqual(len(bindings), 6)
        self.assertIn(
            "extern void ctw_camera_update_native_v1(void);",
            header,
        )
        self.assertIn(
            '{ "ctw_projection_setup_adapter_v1", '
            '(void *)&ctw_projection_setup_native_v1 },',
            header,
        )

    def test_rejects_pending_abi(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.fixture()
            obj["abi_verification"]["lod_test"]["status"] = "pending"
            path = Path(td) / "profile.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                adapter_emit_c.adapters_from_profile(
                    path, self.catalog()
                )

    def test_rejects_invalid_native_symbol(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "profile.json"
            path.write_text(json.dumps(self.fixture()), encoding="utf-8")
            catalog = self.catalog()
            catalog["adapters"][5]["native_symbol"] = "bad-native-symbol"
            with self.assertRaises(ValueError):
                adapter_emit_c.adapters_from_profile(path, catalog)

    def test_rejects_abi_rva_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            obj = self.fixture()
            obj["abi_verification"]["camera_update"]["verified_rva"] = 0x9999
            path = Path(td) / "profile.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                adapter_emit_c.adapters_from_profile(
                    path, self.catalog()
                )

    def test_rejects_catalog_adapter_not_implemented(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "profile.json"
            path.write_text(json.dumps(self.fixture()), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                "native adapters not ready",
            ):
                adapter_emit_c.adapters_from_profile(
                    path,
                    self.catalog(implemented=False),
                )

    def test_deduplicates_shared_native_symbol_declaration(self):
        obj = self.fixture()
        catalog = self.catalog()
        catalog["adapters"][0]["native_symbol"] = "ctw_shared_native_v1"
        catalog["adapters"][1]["native_symbol"] = "ctw_shared_native_v1"

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "profile.json"
            path.write_text(json.dumps(obj), encoding="utf-8")
            header = adapter_emit_c.emit_header(
                adapter_emit_c.adapters_from_profile(path, catalog)
            )

        self.assertEqual(
            header.count("extern void ctw_shared_native_v1(void);"),
            1,
        )
        self.assertIn(
            '{ "ctw_camera_update_adapter_v1", '
            '(void *)&ctw_shared_native_v1 },',
            header,
        )
        self.assertIn(
            '{ "ctw_projection_setup_adapter_v1", '
            '(void *)&ctw_shared_native_v1 },',
            header,
        )


if __name__ == "__main__":
    unittest.main()
