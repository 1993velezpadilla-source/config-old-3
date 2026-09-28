#!/usr/bin/env python3
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sign_modpack


CERT_A = """Signer #1 certificate SHA-256 digest: aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa:aa
Signer #1 certificate SHA-1 digest: bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb:bb
"""

CERT_B = """Signer #1 certificate SHA-256 digest: cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc:cc
Signer #1 certificate SHA-1 digest: dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd:dd
"""


class FakeRunner:
    def __init__(self, verify_outputs):
        self.verify_outputs = list(verify_outputs)
        self.commands = []

    def __call__(self, command):
        self.commands.append(command)
        tool = Path(command[0]).name

        if tool.startswith("zipalign"):
            shutil.copyfile(command[-2], command[-1])
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="",
                stderr="",
            )

        if tool.startswith("apksigner") and command[1] == "sign":
            out_index = command.index("--out") + 1
            shutil.copyfile(command[-1], command[out_index])
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="",
                stderr="",
            )

        if tool.startswith("apksigner") and command[1] == "verify":
            text = self.verify_outputs.pop(0)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=text,
                stderr="",
            )

        raise AssertionError(f"unexpected command: {command}")


class SignModpackTests(unittest.TestCase):
    def make_tools(self, root):
        zipalign = root / "zipalign"
        apksigner = root / "apksigner"
        keystore = root / "ctw.keystore"
        for path in (zipalign, apksigner, keystore):
            path.write_bytes(b"x")
        return zipalign, apksigner, keystore

    def test_signs_single_apk_and_verifies_certificate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "unsigned.apk"
            output = root / "signed.apk"
            source.write_bytes(b"apk")
            zipalign, apksigner, keystore = self.make_tools(root)
            runner = FakeRunner([CERT_A])

            with mock.patch.object(
                sign_modpack,
                "_run",
                side_effect=runner,
            ), mock.patch.dict(
                os.environ,
                {
                    "CTW_KEYSTORE_PASS": "secret",
                    "CTW_KEY_PASS": "secret",
                },
                clear=False,
            ):
                report = sign_modpack.sign_modpack(
                    source,
                    output,
                    keystore=keystore,
                    alias="ctw3d",
                    zipalign_path=zipalign,
                    apksigner_path=apksigner,
                )

        self.assertEqual(report["mode"], "apk")
        self.assertEqual(report["apk_count"], 1)
        self.assertEqual(report["certificate"]["sha1"], "bb" * 20)
        self.assertEqual(report["certificate"]["sha256"], "aa" * 32)

        sign_cmd = next(
            cmd for cmd in runner.commands
            if Path(cmd[0]).name.startswith("apksigner")
            and cmd[1] == "sign"
        )
        self.assertIn("env:CTW_KEYSTORE_PASS", sign_cmd)
        self.assertIn("env:CTW_KEY_PASS", sign_cmd)
        self.assertNotIn("secret", sign_cmd)

    def test_split_set_requires_one_certificate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "unsigned"
            output = root / "signed"
            source.mkdir()
            (source / "base.apk").write_bytes(b"base")
            (source / "split_config.arm64_v8a.apk").write_bytes(b"arm")
            zipalign, apksigner, keystore = self.make_tools(root)

            runner = FakeRunner([CERT_A, CERT_A])
            with mock.patch.object(
                sign_modpack,
                "_run",
                side_effect=runner,
            ), mock.patch.dict(
                os.environ,
                {
                    "CTW_KEYSTORE_PASS": "secret",
                    "CTW_KEY_PASS": "secret",
                },
                clear=False,
            ):
                report = sign_modpack.sign_modpack(
                    source,
                    output,
                    keystore=keystore,
                    alias="ctw3d",
                    zipalign_path=zipalign,
                    apksigner_path=apksigner,
                )

        self.assertEqual(report["mode"], "apkset")
        self.assertEqual(report["apk_count"], 2)
        self.assertTrue((output / "base.apk").is_file())
        self.assertTrue(
            (output / "split_config.arm64_v8a.apk").is_file()
        )

    def test_split_certificate_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "unsigned"
            output = root / "signed"
            source.mkdir()
            (source / "base.apk").write_bytes(b"base")
            (source / "split.apk").write_bytes(b"split")
            zipalign, apksigner, keystore = self.make_tools(root)

            runner = FakeRunner([CERT_A, CERT_B])
            with mock.patch.object(
                sign_modpack,
                "_run",
                side_effect=runner,
            ), mock.patch.dict(
                os.environ,
                {
                    "CTW_KEYSTORE_PASS": "secret",
                    "CTW_KEY_PASS": "secret",
                },
                clear=False,
            ):
                with self.assertRaises(RuntimeError):
                    sign_modpack.sign_modpack(
                        source,
                        output,
                        keystore=keystore,
                        alias="ctw3d",
                        zipalign_path=zipalign,
                        apksigner_path=apksigner,
                    )

    def test_missing_password_environment_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "unsigned.apk"
            output = root / "signed.apk"
            source.write_bytes(b"apk")
            zipalign, apksigner, keystore = self.make_tools(root)

            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError):
                    sign_modpack.sign_modpack(
                        source,
                        output,
                        keystore=keystore,
                        alias="ctw3d",
                        zipalign_path=zipalign,
                        apksigner_path=apksigner,
                    )


if __name__ == "__main__":
    unittest.main()
