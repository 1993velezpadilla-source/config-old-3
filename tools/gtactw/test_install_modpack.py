#!/usr/bin/env python3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_modpack


class InstallModpackTests(unittest.TestCase):
    def test_installs_single_apk_and_verifies_package(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            apk = root / "ctw.apk"
            adb = root / "adb"
            apk.write_bytes(b"apk")
            adb.write_bytes(b"adb")

            calls = []

            def fake_run(command):
                calls.append(command)
                if "pm" in command:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=(
                            "package:/data/app/pkg/base.apk\n"
                        ),
                        stderr="",
                    )
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="Success\n",
                    stderr="",
                )

            with mock.patch.object(
                install_modpack.adb_collect,
                "choose_serial",
                return_value="ABC123",
            ), mock.patch.object(
                install_modpack,
                "_run",
                side_effect=fake_run,
            ):
                report = install_modpack.install_signed_modpack(
                    apk,
                    adb_path=adb,
                )

        self.assertEqual(report["mode"], "apk")
        self.assertEqual(report["command_mode"], "install")
        self.assertEqual(report["serial"], "ABC123")
        self.assertEqual(
            report["installed_package_paths"],
            ["/data/app/pkg/base.apk"],
        )
        self.assertEqual(
            calls[0],
            [str(adb), "-s", "ABC123", "install", "-r", str(apk)],
        )

    def test_split_set_uses_install_multiple(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "signed"
            source.mkdir()
            (source / "base.apk").write_bytes(b"base")
            (source / "split_config.arm64_v8a.apk").write_bytes(b"arm")
            adb = root / "adb"
            adb.write_bytes(b"adb")

            calls = []

            def fake_run(command):
                calls.append(command)
                if "pm" in command:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=(
                            "package:/data/app/pkg/base.apk\n"
                            "package:/data/app/pkg/split_config.arm64_v8a.apk\n"
                        ),
                        stderr="",
                    )
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="Success\n",
                    stderr="",
                )

            with mock.patch.object(
                install_modpack.adb_collect,
                "choose_serial",
                return_value="ABC123",
            ), mock.patch.object(
                install_modpack,
                "_run",
                side_effect=fake_run,
            ):
                report = install_modpack.install_signed_modpack(
                    source,
                    adb_path=adb,
                    grant_permissions=True,
                )

        self.assertEqual(report["mode"], "apkset")
        self.assertEqual(report["command_mode"], "install-multiple")
        self.assertEqual(report["apk_count"], 2)
        install = calls[0]
        self.assertEqual(
            install[:6],
            [
                str(adb),
                "-s",
                "ABC123",
                "install-multiple",
                "-r",
                "-g",
            ],
        )
        self.assertTrue(install[-2].endswith("base.apk"))
        self.assertTrue(
            install[-1].endswith("split_config.arm64_v8a.apk")
        )

    def test_signature_conflict_never_uninstalls(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            apk = root / "ctw.apk"
            adb = root / "adb"
            apk.write_bytes(b"apk")
            adb.write_bytes(b"adb")

            def fake_run(command):
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr=(
                        "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: "
                        "Package com.rockstargames.gtactw signatures do not match]"
                    ),
                )

            with mock.patch.object(
                install_modpack.adb_collect,
                "choose_serial",
                return_value="ABC123",
            ), mock.patch.object(
                install_modpack,
                "_run",
                side_effect=fake_run,
            ) as run:
                with self.assertRaises(install_modpack.InstallError) as ctx:
                    install_modpack.install_signed_modpack(
                        apk,
                        adb_path=adb,
                    )

        self.assertTrue(ctx.exception.signature_conflict)
        for call in run.call_args_list:
            command = call.args[0]
            self.assertNotIn("uninstall", command)

    def test_missing_pm_path_after_success_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            apk = root / "ctw.apk"
            adb = root / "adb"
            apk.write_bytes(b"apk")
            adb.write_bytes(b"adb")

            responses = [
                subprocess.CompletedProcess(
                    ["adb"], 0, stdout="Success\n", stderr=""
                ),
                subprocess.CompletedProcess(
                    ["adb"], 0, stdout="", stderr=""
                ),
            ]
            with mock.patch.object(
                install_modpack.adb_collect,
                "choose_serial",
                return_value="ABC123",
            ), mock.patch.object(
                install_modpack,
                "_run",
                side_effect=responses,
            ):
                with self.assertRaises(install_modpack.InstallError):
                    install_modpack.install_signed_modpack(
                        apk,
                        adb_path=adb,
                    )


if __name__ == "__main__":
    unittest.main()
