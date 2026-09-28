#!/usr/bin/env python3
import io
import json
import tempfile
import unittest
from pathlib import Path
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_mod_from_profile
import loader_variant
import profile_template
from apk_modpack import GAME_SO


def make_profile(*, advanced_target: str | None = None) -> dict:
    profile = {
        "patch_targets_rva": {},
        "target_verification": {},
        "abi_verification": {},
    }
    for index, key in enumerate(profile_template.TARGET_KEYS, start=1):
        rva = 0x4000 + index * 0x100
        strategy = (
            loader_variant.ADVANCED
            if key == advanced_target
            else loader_variant.SIMPLE
        )
        profile["patch_targets_rva"][key] = rva
        profile["target_verification"][key] = {
            "status": "verified",
            "rva": rva,
            "evidence": [{"method": "fixture", "detail": key}],
            "code_prefix_hex": "aa" * 16,
        }
        profile["abi_verification"][key] = {
            "status": "pending",
            "prototype": None,
            "calling_convention": "aarch64_aapcs64",
            "adapter": None,
            "evidence": [],
            "candidates": [
                {
                    "rva": rva,
                    "function": key,
                    "source": "verified_target",
                    "trampoline_strategy_hint": strategy,
                }
            ],
        }
    return profile


def apk_bytes(entries: dict[str, bytes]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return bio.getvalue()


class BuildModFromProfileTests(unittest.TestCase):
    def loaders(self, root: Path) -> tuple[Path, Path]:
        minimal = root / "minimal.so"
        advanced = root / "shadowhook.so"
        minimal.write_bytes(b"\x7fELFminimal-loader")
        advanced.write_bytes(b"\x7fELFshadowhook-loader")
        return minimal, advanced

    def test_monolithic_selects_minimal_loader(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "ctw.apk"
            output = root / "ctw_mod.apk"
            profile_path = root / "profile.json"
            minimal, advanced = self.loaders(root)

            with zipfile.ZipFile(source, "w") as zf:
                zf.writestr(GAME_SO, b"\x7fELForiginal")

            profile_path.write_text(
                json.dumps(make_profile()),
                encoding="utf-8",
            )

            report = build_mod_from_profile.build_from_profile(
                source,
                profile_path,
                minimal,
                advanced,
                output,
            )

            self.assertEqual(report["source_mode"], "apk")
            self.assertEqual(report["loader_variant"], "minimal")
            with zipfile.ZipFile(output, "r") as zf:
                self.assertEqual(zf.read(GAME_SO), minimal.read_bytes())

    def test_split_set_selects_shadowhook_loader(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "ctw.apkm"
            out = root / "out"
            profile_path = root / "profile.json"
            config = root / "ctw_modhub.ini"
            minimal, advanced = self.loaders(root)
            config.write_text("[Camera]\nFOV=72\n", encoding="utf-8")

            with zipfile.ZipFile(source, "w") as outer:
                outer.writestr(
                    "base.apk",
                    apk_bytes({
                        "assets/game.pak": b"pak",
                    }),
                )
                outer.writestr(
                    "split_config.arm64_v8a.apk",
                    apk_bytes({
                        GAME_SO: b"\x7fELForiginal",
                    }),
                )

            profile_path.write_text(
                json.dumps(make_profile(advanced_target="projection_setup")),
                encoding="utf-8",
            )

            report = build_mod_from_profile.build_from_profile(
                source,
                profile_path,
                minimal,
                advanced,
                out,
                config,
            )

            self.assertEqual(report["source_mode"], "apkset")
            self.assertEqual(report["loader_variant"], "shadowhook")
            with zipfile.ZipFile(
                out / "split_config.arm64_v8a.apk",
                "r",
            ) as zf:
                self.assertEqual(zf.read(GAME_SO), advanced.read_bytes())

    def test_incomplete_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "ctw.apk"
            output = root / "out.apk"
            profile_path = root / "profile.json"
            minimal, advanced = self.loaders(root)

            with zipfile.ZipFile(source, "w") as zf:
                zf.writestr(GAME_SO, b"\x7fELForiginal")

            profile = make_profile()
            profile["target_verification"]["lod_test"]["status"] = "pending"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")

            with self.assertRaises(ValueError):
                build_mod_from_profile.build_from_profile(
                    source,
                    profile_path,
                    minimal,
                    advanced,
                    output,
                )


if __name__ == "__main__":
    unittest.main()
