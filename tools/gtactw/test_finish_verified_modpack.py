#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finish_verified_modpack


class FinishVerifiedModpackTests(unittest.TestCase):
    def paths(self, root: Path):
        source = root / "ctw.apk"
        libgame = root / "libGame.so"
        profile = root / "profile.json"
        catalog = root / "adapter_catalog.json"
        loader_source = root / "loader-src"
        keystore = root / "ctw.keystore"
        config = root / "ctw_modhub.ini"
        loader_source.mkdir()
        for p in (source, libgame, profile, catalog, keystore, config):
            p.write_bytes(b"x")
        return (
            source,
            libgame,
            profile,
            catalog,
            loader_source,
            keystore,
            config,
        )

    def loader_report(self, loader: Path):
        loader.parent.mkdir(parents=True, exist_ok=True)
        loader.write_bytes(b"profile-specific-loader")
        return {
            "ok": True,
            "loader_variant": "minimal",
            "loader": str(loader),
            "loader_sha256": "aa" * 32,
            "profile_header_sha256": "bb" * 32,
            "adapter_header_sha256": "cc" * 32,
            "binary_fingerprint": {"sha256": "dd" * 32},
            "adapter_count": 6,
        }

    def sign_report(self):
        return {
            "ok": True,
            "certificate": {
                "sha1": "11" * 20,
                "sha256": "22" * 32,
            },
        }

    def test_uses_only_profile_specific_loader(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (
                source,
                libgame,
                profile,
                catalog,
                loader_source,
                keystore,
                config,
            ) = self.paths(root)
            work = root / "work"
            expected_loader = work / "verified-loader/libGame.so"

            with mock.patch.object(
                finish_verified_modpack.build_verified_loader,
                "build_verified_loader",
                return_value=self.loader_report(expected_loader),
            ) as build_loader, mock.patch.object(
                finish_verified_modpack.build_mod_from_profile,
                "build_from_profile",
                return_value={
                    "ok": True,
                    "source_mode": "apk",
                    "loader_variant": "minimal",
                    "selected_loader": str(expected_loader),
                },
            ) as repack, mock.patch.object(
                finish_verified_modpack.sign_modpack,
                "sign_modpack",
                return_value=self.sign_report(),
            ), mock.patch.object(
                finish_verified_modpack.install_modpack,
                "install_signed_modpack",
            ) as install:
                report = finish_verified_modpack.finish_verified_modpack(
                    source,
                    libgame,
                    profile,
                    catalog,
                    loader_source,
                    work,
                    config=config,
                    keystore=keystore,
                    alias="ctw3d",
                )

        self.assertTrue(report["ok"])
        self.assertFalse(report["installed"])
        self.assertEqual(
            report["profile_specific_loader"],
            str(expected_loader),
        )
        build_loader.assert_called_once()
        args = repack.call_args.args
        self.assertEqual(args[2], expected_loader)
        self.assertEqual(args[3], expected_loader)
        self.assertEqual(args[6], catalog)
        install.assert_not_called()

    def test_loader_variant_disagreement_is_rejected_before_signing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (
                source,
                libgame,
                profile,
                catalog,
                loader_source,
                keystore,
                config,
            ) = self.paths(root)
            work = root / "work"
            expected_loader = work / "verified-loader/libGame.so"
            loader_report = self.loader_report(expected_loader)
            loader_report["loader_variant"] = "shadowhook"

            with mock.patch.object(
                finish_verified_modpack.build_verified_loader,
                "build_verified_loader",
                return_value=loader_report,
            ), mock.patch.object(
                finish_verified_modpack.build_mod_from_profile,
                "build_from_profile",
                return_value={
                    "ok": True,
                    "source_mode": "apk",
                    "loader_variant": "minimal",
                    "selected_loader": str(expected_loader),
                },
            ), mock.patch.object(
                finish_verified_modpack.sign_modpack,
                "sign_modpack",
            ) as sign:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "variant disagrees",
                ):
                    finish_verified_modpack.finish_verified_modpack(
                        source,
                        libgame,
                        profile,
                        catalog,
                        loader_source,
                        work,
                        config=config,
                        keystore=keystore,
                        alias="ctw3d",
                    )

        sign.assert_not_called()

    def test_install_remains_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (
                source,
                libgame,
                profile,
                catalog,
                loader_source,
                keystore,
                config,
            ) = self.paths(root)
            work = root / "work"
            expected_loader = work / "verified-loader/libGame.so"

            with mock.patch.object(
                finish_verified_modpack.build_verified_loader,
                "build_verified_loader",
                return_value=self.loader_report(expected_loader),
            ), mock.patch.object(
                finish_verified_modpack.build_mod_from_profile,
                "build_from_profile",
                return_value={
                    "ok": True,
                    "source_mode": "apk",
                    "loader_variant": "minimal",
                    "selected_loader": str(expected_loader),
                },
            ), mock.patch.object(
                finish_verified_modpack.sign_modpack,
                "sign_modpack",
                return_value=self.sign_report(),
            ), mock.patch.object(
                finish_verified_modpack.install_modpack,
                "install_signed_modpack",
                return_value={"ok": True, "serial": "ABC123"},
            ) as install:
                report = finish_verified_modpack.finish_verified_modpack(
                    source,
                    libgame,
                    profile,
                    catalog,
                    loader_source,
                    work,
                    config=config,
                    keystore=keystore,
                    alias="ctw3d",
                    install=True,
                    serial="ABC123",
                )

        self.assertTrue(report["installed"])
        install.assert_called_once()
        self.assertEqual(
            install.call_args.args[0],
            work / "signed-ctw3d.apk",
        )


if __name__ == "__main__":
    unittest.main()
