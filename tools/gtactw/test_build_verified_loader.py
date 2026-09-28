#!/usr/bin/env python3
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_verified_loader
import loader_variant
import profile_template
from test_emit_runtime_bundle import catalog_obj, enrich_profile
from test_profile_verify_binary import make_fixture, make_profile


class BuildVerifiedLoaderTests(unittest.TestCase):
    def setup_fixture(self, root: Path):
        libgame = root / "libGame.so"
        text = make_fixture(libgame)
        profile = enrich_profile(make_profile(libgame, text))
        profile_path = root / "profile.json"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        catalog = root / "adapter_catalog.json"
        catalog.write_text(json.dumps(catalog_obj()), encoding="utf-8")
        ndk = root / "ndk"
        toolchain = ndk / "build/cmake/android.toolchain.cmake"
        toolchain.parent.mkdir(parents=True)
        toolchain.write_text("# fixture\n", encoding="utf-8")
        source = root / "loader-src"
        source.mkdir()
        return libgame, profile_path, catalog, ndk, source

    def fake_runner(self, built_path: Path, calls: list[list[str]]):
        def run(command, check):
            self.assertTrue(check)
            calls.append(list(command))
            if "--build" in command:
                built_path.parent.mkdir(parents=True, exist_ok=True)
                built_path.write_bytes(b"PROFILE_SPECIFIC_ARM64_PROXY")
            return 0
        return run

    def test_minimal_loader_build_uses_generated_headers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame, profile, catalog, ndk, source = self.setup_fixture(root)
            work = root / "work"
            out = root / "out/libGame.so"
            calls = []

            report = build_verified_loader.build_verified_loader(
                libgame,
                profile,
                catalog,
                source,
                work,
                out,
                ndk=ndk,
                run=self.fake_runner(work / "cmake/libGame.so", calls),
            )

            self.assertEqual(report["loader_variant"], "minimal")
            self.assertTrue(out.is_file())
            self.assertEqual(
                report["loader_sha256"],
                hashlib.sha256(out.read_bytes()).hexdigest(),
            )
            configure = calls[0]
            self.assertIn(
                f"-DCTW_GENERATED_DIR={work / 'generated'}",
                configure,
            )
            self.assertIn("-DCTW_USE_SHADOWHOOK=OFF", configure)
            self.assertNotIn(
                "-DCTW_GENERATED_DIR="
                + str(source),
                configure,
            )
            self.assertTrue(
                (work / "generated/ctw_profiles_generated.h").is_file()
            )
            self.assertTrue(
                (work / "generated/ctw_adapters_generated.h").is_file()
            )

    def test_advanced_profile_requires_shadowhook_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame, profile_path, catalog, ndk, source = self.setup_fixture(root)
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            key = "projection_setup"
            rva = profile["patch_targets_rva"][key]
            profile["abi_verification"][key]["trampoline_strategy"] = (
                loader_variant.ADVANCED
            )
            profile["abi_verification"][key]["candidates"] = [
                {
                    "rva": rva,
                    "function": key,
                    "source": "fixture",
                    "trampoline_strategy_hint": loader_variant.ADVANCED,
                }
            ]
            profile_path.write_text(json.dumps(profile), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "requires ShadowHook",
            ):
                build_verified_loader.build_verified_loader(
                    libgame,
                    profile_path,
                    catalog,
                    source,
                    root / "work",
                    root / "out/libGame.so",
                    ndk=ndk,
                    run=lambda *args, **kwargs: 0,
                )

    def test_find_ndk_accepts_explicit_toolchain(self):
        with tempfile.TemporaryDirectory() as td:
            ndk = Path(td) / "ndk"
            toolchain = ndk / "build/cmake/android.toolchain.cmake"
            toolchain.parent.mkdir(parents=True)
            toolchain.write_text("# fixture\n", encoding="utf-8")
            self.assertEqual(build_verified_loader.find_ndk(ndk), ndk)


if __name__ == "__main__":
    unittest.main()
