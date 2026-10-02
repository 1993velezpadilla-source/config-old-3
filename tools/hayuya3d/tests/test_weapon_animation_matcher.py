from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.hayuya3d.weapon_animation_matcher import compatible


class WeaponAnimationMatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=json.loads(Path("hayuya/standards/hayuya_weapon_animation_v1.json").read_text())

    def test_pump_shotgun_rejects_pistol_mag_reload(self):
        weapon={"family":"shotgun_pump_tube","components":["trigger","pump","tube","loading_gate"]}
        clip={"event":"reload_mag","families":["handgun_semiauto"],"requires_components":["magazine"]}
        out=compatible(self.spec,weapon,clip)
        self.assertFalse(out["compatible"])
        self.assertIn("family_mismatch",out["reasons"])

    def test_pump_shotgun_accepts_shell_reload(self):
        weapon={"family":"shotgun_pump_tube","components":["trigger","pump","tube","loading_gate"]}
        clip={"event":"reload_shell","families":["shotgun_pump_tube"],"requires_components":["tube"]}
        out=compatible(self.spec,weapon,clip)
        self.assertTrue(out["compatible"])

    def test_revolver_rejects_slide_cycle(self):
        weapon={"family":"revolver","components":["trigger","cylinder","hammer"]}
        clip={"event":"slide_cycle","families":["handgun_semiauto"],"requires_components":["slide"]}
        out=compatible(self.spec,weapon,clip)
        self.assertFalse(out["compatible"])

    def test_bolt_action_accepts_bolt_cycle(self):
        weapon={"family":"rifle_bolt_action","components":["trigger","bolt_handle","magazine_or_internal_mag"]}
        clip={"event":"bolt_cycle","families":["rifle_bolt_action"],"requires_components":["bolt_handle"]}
        out=compatible(self.spec,weapon,clip)
        self.assertTrue(out["compatible"])


if __name__=="__main__":
    unittest.main()
