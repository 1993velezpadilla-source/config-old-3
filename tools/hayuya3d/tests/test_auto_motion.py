from __future__ import annotations

import json
import unittest
from tools.hayuya3d.auto_motion_planner import plan
from tools.hayuya3d.internet_asset_research import infer_family


class HayuyaAutoMotionTests(unittest.TestCase):
    def test_pump_shotgun_research_inference(self):
        fam,conf,_=infer_family("This is a pump-action shotgun with a tubular magazine and sliding fore-end.")
        self.assertEqual(fam,"shotgun_pump_tube")
        self.assertGreaterEqual(conf,0.72)

    def test_explicit_family_beats_research(self):
        research={"inferred_weapon_family":"revolver","confidence":0.95,"sources":[{"url":"x"}]}
        out=plan("weapon.firearm",True,"hayuya_auto","shotgun_pump_tube",research)
        self.assertEqual(out["weapon_family"],"shotgun_pump_tube")
        self.assertEqual(out["family_source"],"explicit")
        self.assertIn("pump",out["required_components"])

    def test_ambiguous_firearm_fails_closed(self):
        research={"inferred_weapon_family":"auto","confidence":0.0,"sources":[]}
        out=plan("weapon.firearm",True,"hayuya_auto","auto",research)
        self.assertEqual(out["status"],"needs_family_confirmation")
        self.assertEqual(out["preview_set"],[])

    def test_grass_uses_vertex_wind(self):
        out=plan("foliage.grass",True,"hayuya_auto","auto",{})
        self.assertEqual(out["motion_system"],"vertex_wind")
        self.assertEqual(out["status"],"plan_ready")

    def test_manual_override_disables_auto(self):
        out=plan("character.humanoid",True,"manual","auto",{})
        self.assertFalse(out["enabled"])
        self.assertEqual(out["status"],"disabled")


if __name__=="__main__":
    unittest.main()
