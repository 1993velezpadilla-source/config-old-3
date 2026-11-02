#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("iw3", ROOT/"scripts/iw3_weapon_profiles.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class IW3WeaponTests(unittest.TestCase):
    def test_real_weaponfile_kisak_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d/"ak47.weapon").write_text(
                "WEAPONFILE\\standMoveF\\2.5\\standMoveR\\-3\\standMoveU\\4\\"
                "standRotP\\10\\standRotY\\0\\standRotR\\-5\\adsAimPitch\\1.75\\",
                encoding="utf-8")
            mapping=d/"map.json"
            mapping.write_text(json.dumps([{
                "definition":"ak47.weapon",
                "viewmodel":"models/weapons/iw3/v_ak47.mdl"
            }]),encoding="utf-8")
            header=module.generate(d,mapping)
            self.assertIn("#define IW3_POSE_TABLE_SIZE 1u",header)
            self.assertIn("models/weapons/iw3/v_ak47.mdl",header)
            self.assertIn("2.5f",header)
            self.assertNotIn(" -3f",header)
            self.assertIn("-3.0f",header)
            self.assertIn("1.75f",header)

    def test_original_nzp_sprint_is_not_treated_as_aim_down_sights(self):
        # STAT_ZOOM 3 is sprint, unlike CoD ADS; the bridge must not
        # force original IW3 ADS offsets onto the sprint pose.
        bridge=(ROOT/"scripts/patch_viril_iw3_weapon_pose.py").read_text()
        self.assertIn("cl.stats[STAT_ZOOM] == 1",bridge)
        self.assertIn("cl.stats[STAT_ZOOM] == 2",bridge)
        self.assertNotIn("cl.stats[STAT_ZOOM] ? 1.0f",bridge)

    def test_empty_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            mapping=d/"map.json"
            mapping.write_text("[]",encoding="utf-8")
            self.assertIn("#define IW3_POSE_TABLE_SIZE 0u",module.generate(d,mapping))

    def test_refuse_invalid_asset_and_numeric(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            (d/"ak47.weapon").write_text("standMoveF = NaN",encoding="utf-8")
            mapping=d/"map.json"
            mapping.write_text(json.dumps([{
                "definition":"ak47.weapon",
                "viewmodel":"models/weapons/iw3/gun.mdl"
            }]),encoding="utf-8")
            with self.assertRaises(ValueError):
                module.generate(d,mapping)
            mapping.write_text(json.dumps([{
                "definition":"../../private.weapon",
                "viewmodel":"models/weapons/iw3/gun.mdl"
            }]),encoding="utf-8")
            with self.assertRaises(ValueError):
                module.generate(d,mapping)
if __name__ == "__main__":
    unittest.main()
