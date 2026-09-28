#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finish_modpack


class FinishModpackTests(unittest.TestCase):
    def paths(self, root: Path):
        source = root / "ctw.apk"
        profile = root / "profile.json"
        minimal = root / "minimal.so"
        shadowhook = root / "shadowhook.so"
        keystore = root / "ctw.keystore"
        config = root / "ctw_modhub.ini"
        for p in (source, profile, minimal, shadowhook, keystore, config):
            p.write_bytes(b"x")
        return source, profile, minimal, shadowhook, keystore, config

    def fake_build_report(self, loader):
        return {
            "ok": True,
            "source_mode": "apk",
            "profile": "profile.json",
            "loader_variant": "minimal",
            "selected_loader": str(loader),
            "variant_plan": {"ready": True, "loader_variant": "minimal"},
            "repack": {},
        }

    def fake_sign_report(self):
        return {
            "ok": True,
            "mode": "apk",
            "certificate": {
                "sha1": "aa" * 20,
                "sha256": "bb" * 32,
            },
            "signed_apks": [],
        }

    def test_build_sign_without_install_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (
                source,
                profile,
                minimal,
                shadowhook,
                keystore,
                config,
            ) = self.paths(root)
            work = root / "work"

            with mock.patch.object(
                finish_modpack.build_mod_from_profile,
                "_source_mode",
                return_value="apk",
            ), mock.patch.object(
                finish_modpack.build_mod_from_profile,
                "build_from_profile",
                return_value=self.fake_build_report(minimal),
            ) as build, mock.patch.object(
                finish_modpack.sign_modpack,
                "sign_modpack",
                return_value=self.fake_sign_report(),
            ) as sign, mock.patch.object(
                finish_modpack.install_modpack,
                "install_signed_modpack",
            ) as install:
                report = finish_modpack.finish_modpack(
                    source,
                    profile,
                    minimal,
                    shadowhook,
                    work,
                    config=config,
                    keystore=keystore,
                    alias="ctw3d",
                    install=False,
                )

        self.assertTrue(report["ok"])
        self.assertEqual(report["loader_variant"], "minimal")
        self.assertFalse(report["installed"])
        build.assert_called_once()
        sign.assert_called_once()
        install.assert_not_called()

    def test_install_is_explicit_and_uses_signed_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (
                source,
                profile,
                minimal,
                shadowhook,
                keystore,
                config,
            ) = self.paths(root)
            work = root / "work"
            install_report = {
                "ok": True,
                "serial": "ABC123",
                "package": "com.rockstargames.gtactw",
            }

            with mock.patch.object(
                finish_modpack.build_mod_from_profile,
                "_source_mode",
                return_value="apk",
            ), mock.patch.object(
                finish_modpack.build_mod_from_profile,
                "build_from_profile",
                return_value=self.fake_build_report(minimal),
            ), mock.patch.object(
                finish_modpack.sign_modpack,
                "sign_modpack",
                return_value=self.fake_sign_report(),
            ), mock.patch.object(
                finish_modpack.install_modpack,
                "install_signed_modpack",
                return_value=install_report,
            ) as install:
                report = finish_modpack.finish_modpack(
                    source,
                    profile,
                    minimal,
                    shadowhook,
                    work,
                    config=config,
                    keystore=keystore,
                    alias="ctw3d",
                    install=True,
                    serial="ABC123",
                    grant_permissions=True,
                )

        self.assertTrue(report["installed"])
        self.assertEqual(report["install"], install_report)
        args, kwargs = install.call_args
        self.assertEqual(args[0], work / "signed-ctw3d.apk")
        self.assertEqual(kwargs["serial"], "ABC123")
        self.assertTrue(kwargs["grant_permissions"])

    def test_split_mode_uses_directories(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "splits"
            source.mkdir()
            profile = root / "profile.json"
            minimal = root / "minimal.so"
            shadowhook = root / "shadowhook.so"
            keystore = root / "ctw.keystore"
            for p in (profile, minimal, shadowhook, keystore):
                p.write_bytes(b"x")
            work = root / "work"

            build_report = self.fake_build_report(shadowhook)
            build_report["source_mode"] = "apkset"
            build_report["loader_variant"] = "shadowhook"

            with mock.patch.object(
                finish_modpack.build_mod_from_profile,
                "_source_mode",
                return_value="apkset",
            ), mock.patch.object(
                finish_modpack.build_mod_from_profile,
                "build_from_profile",
                return_value=build_report,
            ) as build, mock.patch.object(
                finish_modpack.sign_modpack,
                "sign_modpack",
                return_value={
                    **self.fake_sign_report(),
                    "mode": "apkset",
                },
            ) as sign:
                report = finish_modpack.finish_modpack(
                    source,
                    profile,
                    minimal,
                    shadowhook,
                    work,
                    config=None,
                    keystore=keystore,
                    alias="ctw3d",
                )

        self.assertEqual(report["source_mode"], "apkset")
        self.assertEqual(report["loader_variant"], "shadowhook")
        build_args = build.call_args.args
        self.assertEqual(build_args[4], work / "unsigned-splits")
        sign_args = sign.call_args.args
        self.assertEqual(sign_args[0], work / "unsigned-splits")
        self.assertEqual(sign_args[1], work / "signed-splits")


if __name__ == "__main__":
    unittest.main()
