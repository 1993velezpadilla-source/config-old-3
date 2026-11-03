#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/"scripts"))
from iw3_bind_private_weapon import bind_weapon
from iw3_weapon_profiles import generate

class OriginalIW3BindingTest(unittest.TestCase):
    def test_exact_gunmodel_bind_and_original_pose_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            src=root/"common_mp"/"weapons"
            src.mkdir(parents=True)
            (src/"usp_mp").write_text(
                "WEAPONFILE\\gunModel\\viewmodel_usp_mp\\"
                "standMoveF\\3\\standMoveR\\-1\\standMoveU\\2\\"
                "adsAimPitch\\4\\",encoding="utf-8")
            r=bind_weapon(root,"viewmodel_usp_mp_lod0.glb",
                "models/weapons/m1911/v_colt.mdl",root/"private")
            self.assertEqual(r["gunModel"],"viewmodel_usp_mp")
            header=generate(root/"private",root/"private"/"pose_mapping.json")
            self.assertIn("models/weapons/m1911/v_colt.mdl",header)
            self.assertIn("3.0f",header)
            self.assertIn("-1.0f",header)
            self.assertIn("4.0f",header)

    def test_fail_on_nonmatching_weapon(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"weapons").mkdir()
            (root/"weapons"/"a").write_text("gunModel\\viewmodel_ak47",encoding="utf-8")
            with self.assertRaises(ValueError):
                bind_weapon(root,"viewmodel_usp_mp_lod0.glb",
                    "models/weapons/m1911/v_colt.mdl",root/"private")

if __name__=="__main__":
    unittest.main()
