#!/usr/bin/env python3
import io
import tempfile
import unittest
from pathlib import Path
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apkset_modpack
from apk_modpack import GAME_SO, ORIGINAL_SO


def apk_bytes(entries: dict[str, bytes]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
        zf.writestr("META-INF/MANIFEST.MF", b"old")
        zf.writestr("META-INF/CERT.RSA", b"old")
    return bio.getvalue()


class ApkSetModpackTests(unittest.TestCase):
    def test_patches_only_arm64_split_and_rewrites_all(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root / "ctw.apkm"
            loader = root / "loader.so"
            out = root / "out"
            config = root / "ctw_modhub.ini"
            loader.write_bytes(b"\x7fELF" + b"loader")
            config.write_text("[Camera]\nFOV=72\n", encoding="utf-8")

            with zipfile.ZipFile(bundle, "w") as outer:
                outer.writestr(
                    "base.apk",
                    apk_bytes({
                        "AndroidManifest.xml": b"manifest",
                        "assets/game.pak": b"pak",
                    }),
                )
                outer.writestr(
                    "split_config.arm64_v8a.apk",
                    apk_bytes({
                        GAME_SO: b"\x7fELForiginal",
                        "lib/arm64-v8a/libopenal.so": b"openal",
                    }),
                )

            report = apkset_modpack.build_split_modpack(bundle, loader, out, config)
            self.assertEqual(report["split_count"], 2)
            self.assertEqual(
                report["patched_split"],
                "split_config.arm64_v8a.apk",
            )
            self.assertEqual(report["config_split"], "base.apk")

            with zipfile.ZipFile(out / "split_config.arm64_v8a.apk", "r") as zf:
                self.assertEqual(zf.read(GAME_SO), loader.read_bytes())
                self.assertEqual(zf.read(ORIGINAL_SO), b"\x7fELForiginal")
                self.assertNotIn("META-INF/MANIFEST.MF", zf.namelist())
                self.assertNotIn("META-INF/CERT.RSA", zf.namelist())
                self.assertNotIn("assets/ctw_modhub.ini", zf.namelist())

            with zipfile.ZipFile(out / "base.apk", "r") as zf:
                self.assertEqual(zf.read("assets/game.pak"), b"pak")
                self.assertEqual(
                    zf.read("assets/ctw_modhub.ini"),
                    config.read_bytes(),
                )
                self.assertNotIn("META-INF/MANIFEST.MF", zf.namelist())

    def test_rejects_multiple_arm64_game_splits(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            loader = root / "loader.so"
            loader.write_bytes(b"\x7fELFloader")
            for name in ("a.apk", "b.apk"):
                with zipfile.ZipFile(root / name, "w") as zf:
                    zf.writestr(GAME_SO, b"\x7fELFgame")

            out = root / "out"
            with self.assertRaises(ValueError):
                apkset_modpack.build_split_modpack(root, loader, out)


if __name__ == "__main__":
    unittest.main()
