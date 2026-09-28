#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apk_modpack


class ApkModpackTests(unittest.TestCase):
    def test_repack_moves_original_and_installs_loader(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "ctw.apk"
            loader = root / "libGame.so"
            out = root / "ctw3d-unsigned.apk"

            loader.write_bytes(b"\x7fELF" + b"L" * 64)
            with zipfile.ZipFile(src, "w") as zf:
                zf.writestr("AndroidManifest.xml", b"manifest")
                zf.writestr(apk_modpack.GAME_SO, b"\x7fELF" + b"ORIGINAL")
                zf.writestr("lib/arm64-v8a/libopenal.so", b"openal")
                zf.writestr("assets/game.pak", b"pak")
                zf.writestr("META-INF/MANIFEST.MF", b"old")
                zf.writestr("META-INF/CERT.RSA", b"old")

            report = apk_modpack.build_mod_apk(src, loader, out)

            self.assertEqual(report["removed_signature_entries"], 2)
            with zipfile.ZipFile(out, "r") as zf:
                self.assertEqual(zf.read(apk_modpack.GAME_SO), loader.read_bytes())
                self.assertEqual(
                    zf.read(apk_modpack.ORIGINAL_SO),
                    b"\x7fELF" + b"ORIGINAL",
                )
                self.assertEqual(zf.read("assets/game.pak"), b"pak")
                self.assertNotIn("META-INF/MANIFEST.MF", zf.namelist())
                self.assertNotIn("META-INF/CERT.RSA", zf.namelist())

    def test_embeds_modhub_config(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "ctw.apk"
            loader = root / "libGame.so"
            config = root / "ctw_modhub.ini"
            out = root / "ctw3d-unsigned.apk"

            loader.write_bytes(b"\x7fELF" + b"L" * 64)
            config.write_text("[Camera]\nFOV=72\n", encoding="utf-8")
            with zipfile.ZipFile(src, "w") as zf:
                zf.writestr(apk_modpack.GAME_SO, b"\x7fELF" + b"ORIGINAL")
                zf.writestr(apk_modpack.CONFIG_ASSET, b"old")

            report = apk_modpack.build_mod_apk(src, loader, out, config)
            self.assertEqual(report["config_asset"], apk_modpack.CONFIG_ASSET)
            with zipfile.ZipFile(out, "r") as zf:
                self.assertEqual(
                    zf.read(apk_modpack.CONFIG_ASSET),
                    config.read_bytes(),
                )

    def test_rejects_non_elf_loader(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "ctw.apk"
            loader = root / "bad.so"
            out = root / "out.apk"

            loader.write_bytes(b"not-elf")
            with zipfile.ZipFile(src, "w") as zf:
                zf.writestr(apk_modpack.GAME_SO, b"\x7fELFgame")

            with self.assertRaises(ValueError):
                apk_modpack.build_mod_apk(src, loader, out)

    def test_refuses_double_repack(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "ctw.apk"
            loader = root / "loader.so"
            out = root / "out.apk"

            loader.write_bytes(b"\x7fELFloader")
            with zipfile.ZipFile(src, "w") as zf:
                zf.writestr(apk_modpack.GAME_SO, b"\x7fELFgame")
                zf.writestr(apk_modpack.ORIGINAL_SO, b"\x7fELFold")

            with self.assertRaises(ValueError):
                apk_modpack.build_mod_apk(src, loader, out)


if __name__ == "__main__":
    unittest.main()
