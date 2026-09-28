#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import emit_runtime_bundle
import loader_variant
import profile_template
from test_profile_verify_binary import make_fixture, make_profile


def enrich_profile(profile: dict) -> dict:
    profile["abi_verification"] = {}
    for key in profile_template.TARGET_KEYS:
        rva = profile["patch_targets_rva"][key]
        profile["abi_verification"][key] = {
            "status": "verified",
            "prototype": f"void {key}(void)",
            "calling_convention": "aarch64_aapcs64",
            "adapter": f"ctw_{key}_adapter_v1",
            "verified_rva": rva,
            "trampoline_strategy": loader_variant.SIMPLE,
            "evidence": [
                {
                    "method": "fixture",
                    "detail": f"ABI {key}",
                }
            ],
            "candidates": [
                {
                    "rva": rva,
                    "function": key,
                    "source": "fixture",
                    "trampoline_strategy_hint": loader_variant.SIMPLE,
                }
            ],
        }
    return profile


def catalog_obj() -> dict:
    return {
        "schema": 1,
        "adapters": [
            {
                "name": f"ctw_{key}_adapter_v1",
                "target": key,
                "native_symbol": f"ctw_{key}_native_v1",
                "implemented": True,
            }
            for key in profile_template.TARGET_KEYS
        ],
    }


class EmitRuntimeBundleTests(unittest.TestCase):
    def setup_fixture(self, root: Path):
        libgame = root / "libGame.so"
        text = make_fixture(libgame)
        profile = enrich_profile(make_profile(libgame, text))
        profile_path = root / "profile.json"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        catalog_path = root / "adapter_catalog.json"
        catalog_path.write_text(
            json.dumps(catalog_obj()),
            encoding="utf-8",
        )
        return libgame, profile_path, catalog_path

    def test_emits_both_headers_from_same_verified_tuple(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame, profile_path, catalog_path = self.setup_fixture(root)
            out_dir = root / "generated"

            report = emit_runtime_bundle.emit_runtime_bundle(
                libgame,
                profile_path,
                catalog_path,
                out_dir,
            )

            profile_header = out_dir / emit_runtime_bundle.PROFILE_HEADER
            adapter_header = out_dir / emit_runtime_bundle.ADAPTER_HEADER
            manifest = out_dir / emit_runtime_bundle.MANIFEST

            self.assertTrue(report["ok"])
            self.assertEqual(report["loader_variant"], "minimal")
            self.assertTrue(profile_header.is_file())
            self.assertTrue(adapter_header.is_file())
            self.assertTrue(manifest.is_file())
            self.assertIn(
                ".adapter_names = {",
                profile_header.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "ctw_projection_setup_native_v1",
                adapter_header.read_text(encoding="utf-8"),
            )

    def test_failure_does_not_replace_existing_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame, profile_path, catalog_path = self.setup_fixture(root)
            out_dir = root / "generated"
            out_dir.mkdir()
            sentinel_profile = "OLD_PROFILE\n"
            sentinel_adapter = "OLD_ADAPTER\n"
            (out_dir / emit_runtime_bundle.PROFILE_HEADER).write_text(
                sentinel_profile,
                encoding="utf-8",
            )
            (out_dir / emit_runtime_bundle.ADAPTER_HEADER).write_text(
                sentinel_adapter,
                encoding="utf-8",
            )

            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["target_verification"]["camera_update"][
                "code_prefix_hex"
            ] = "ff" * 16
            profile_path.write_text(json.dumps(profile), encoding="utf-8")

            with self.assertRaises(ValueError):
                emit_runtime_bundle.emit_runtime_bundle(
                    libgame,
                    profile_path,
                    catalog_path,
                    out_dir,
                )

            self.assertEqual(
                (out_dir / emit_runtime_bundle.PROFILE_HEADER).read_text(
                    encoding="utf-8"
                ),
                sentinel_profile,
            )
            self.assertEqual(
                (out_dir / emit_runtime_bundle.ADAPTER_HEADER).read_text(
                    encoding="utf-8"
                ),
                sentinel_adapter,
            )


if __name__ == "__main__":
    unittest.main()
