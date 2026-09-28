#!/usr/bin/env python3
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_import


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CaptureImportTests(unittest.TestCase):
    def make_capture(self, root: Path, exact: bool = True):
        apk = b"synthetic base apk"
        lib = b"synthetic libGame payload"
        pak = b"synthetic game pak"

        (root / "base.apk").write_bytes(apk)
        (root / "libGame.so").write_bytes(lib)
        (root / "game.pak").write_bytes(pak)

        signer = (
            capture_import.TARGET_CERT_SHA256
            if exact
            else "00" * 32
        )
        manifest = {
            "schema": 1,
            "package": capture_import.TARGET_PACKAGE,
            "version_name": (
                capture_import.TARGET_VERSION_NAME if exact else "0.0.0"
            ),
            "version_code": (
                capture_import.TARGET_VERSION_CODE if exact else 1
            ),
            "expected_signer_sha256": capture_import.TARGET_CERT_SHA256,
            "signer_sha256": [signer],
            "exact_target_match": exact,
            "apks": [
                {
                    "name": "base.apk",
                    "size_bytes": len(apk),
                    "sha256": sha(apk),
                }
            ],
            "artifacts": [
                {
                    "name": "libGame.so",
                    "source_apk": "base.apk",
                    "zip_entry": "lib/arm64-v8a/libGame.so",
                    "size_bytes": len(lib),
                    "sha256": sha(lib),
                },
                {
                    "name": "game.pak",
                    "source_apk": "base.apk",
                    "zip_entry": "assets/game.pak",
                    "size_bytes": len(pak),
                    "sha256": sha(pak),
                },
            ],
        }
        (root / "capture_manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

    def test_accepts_exact_target_and_hashes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_capture(root)
            report = capture_import.verify_capture(root)

        self.assertTrue(report["ok"])
        self.assertTrue(report["exact_target_match"])
        self.assertEqual(
            report["artifacts"]["libGame.so"]["sha256"],
            sha(b"synthetic libGame payload"),
        )
        self.assertEqual(report["apks"][0]["name"], "base.apk")

    def test_rejects_non_target_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_capture(root, exact=False)
            with self.assertRaises(ValueError) as ctx:
                capture_import.verify_capture(root)

        self.assertIn("not the verified 4.4.243 target", str(ctx.exception))

    def test_allows_non_target_only_with_explicit_override(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_capture(root, exact=False)
            report = capture_import.verify_capture(
                root,
                allow_non_target=True,
            )

        self.assertFalse(report["exact_target_match"])

    def test_rejects_tampered_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_capture(root)
            (root / "libGame.so").write_bytes(b"tampered")
            with self.assertRaises(ValueError) as ctx:
                capture_import.verify_capture(root)

        self.assertIn("libGame.so: size mismatch", str(ctx.exception))

    def test_rejects_unsafe_manifest_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_capture(root)
            path = root / "capture_manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["name"] = "../libGame.so"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                capture_import.verify_capture(root)

        self.assertIn("unsafe capture file name", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
