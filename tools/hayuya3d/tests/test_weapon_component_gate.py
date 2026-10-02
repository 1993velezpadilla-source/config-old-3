from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.hayuya3d.weapon_component_gate import infer_components, inspect


class WeaponComponentGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=json.loads(Path("hayuya/standards/hayuya_weapon_animation_v1.json").read_text())

    def test_pistol_detects_slide_mag_trigger(self):
        report={"bone_names":["Control","Magazine","Slide","Trigger"],"family_guess":"handgun_semiauto"}
        out=inspect(report,self.spec)
        self.assertIn("slide",out["detected_components"])
        self.assertIn("magazine",out["detected_components"])
        self.assertIn("trigger",out["detected_components"])

    def test_revolver_drum_maps_to_cylinder(self):
        report={"bone_names":["Control","Drum","Hammer","Trigger"],"family_guess":"revolver"}
        out=inspect(report,self.spec)
        self.assertIn("cylinder",out["detected_components"])
        self.assertIn("hammer",out["detected_components"])

    def test_unknown_family_fails_closed(self):
        report={"bone_names":["Control","Trigger"]}
        out=inspect(report,self.spec)
        self.assertFalse(out["passed"])
        self.assertEqual(out["reason"],"unknown_weapon_family")


if __name__=="__main__":
    unittest.main()
