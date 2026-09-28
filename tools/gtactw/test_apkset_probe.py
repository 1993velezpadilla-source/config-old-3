#!/usr/bin/env python3
import io
import tempfile
import unittest
from pathlib import Path
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apkset_probe


def apk_bytes(entries: dict[str, bytes]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return bio.getvalue()


class ApkSetProbeTests(unittest.TestCase):
    def test_apkm_resolves_assets_and_arm64_split(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root / "ctw.apkm"
            extract = root / "out"

            base_entries = {
                "assets/game.pak": b"pak",
                "assets/dxt.bin": b"dxt",
                "assets/buttonconfig": b"buttons",
                "assets/e_ckna01.gxt": b"gxt",
                "assets/ctw_iphone_intro.mp4": b"movie",
            }
            arm_entries = {
                "lib/arm64-v8a/libGame.so": b"game",
                "lib/arm64-v8a/libopenal.so": b"openal",
            }

            with zipfile.ZipFile(bundle, "w") as outer:
                outer.writestr("base.apk", apk_bytes(base_entries))
                outer.writestr(
                    "splits/split_config.arm64_v8a.apk",
                    apk_bytes(arm_entries),
                )

            report = apkset_probe.inspect_set(bundle, extract)

            self.assertTrue(report["ok"])
            self.assertEqual(report["apk_count"], 2)
            self.assertEqual(
                report["selected"]["assets/game.pak"]["split"],
                "base.apk",
            )
            self.assertEqual(
                report["selected"]["lib/arm64-v8a/libGame.so"]["split"],
                "splits/split_config.arm64_v8a.apk",
            )
            self.assertEqual(
                (extract / "lib/arm64-v8a/libGame.so").read_bytes(),
                b"game",
            )

    def test_directory_split_set(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i, entries in enumerate((
                {
                    "assets/game.pak": b"pak",
                    "assets/dxt.bin": b"dxt",
                    "assets/buttonconfig": b"buttons",
                    "assets/e_ckna01.gxt": b"gxt",
                    "assets/ctw_iphone_intro.mp4": b"movie",
                },
                {
                    "lib/arm64-v8a/libGame.so": b"game",
                    "lib/arm64-v8a/libopenal.so": b"openal",
                },
            )):
                (root / f"split{i}.apk").write_bytes(apk_bytes(entries))

            report = apkset_probe.inspect_set(root)
            self.assertTrue(report["ok"])
            self.assertEqual(report["apk_count"], 2)

    def test_conflicting_duplicates_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.apk").write_bytes(
                apk_bytes({"assets/game.pak": b"A"})
            )
            (root / "b.apk").write_bytes(
                apk_bytes({"assets/game.pak": b"B"})
            )
            with self.assertRaises(ValueError):
                apkset_probe.inspect_set(root)


if __name__ == "__main__":
    unittest.main()
