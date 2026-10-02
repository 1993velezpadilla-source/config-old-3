from __future__ import annotations

import unittest

from tools.hayuya3d.mechanical_part_fitter import fit


class MechanicalPartFitterTests(unittest.TestCase):
    def _map(self, comps):
        return {"components": comps}

    def test_single_component_fails_closed(self):
        pm=self._map([
            {"component_id":0,"face_count":1000,"face_fraction":1.0,"centroid":[0,0,0],"extent":[3,1,1],"main_component":True}
        ])
        out=fit(pm,"handgun_semiauto")
        self.assertFalse(out["mechanical_ready"])
        self.assertEqual(out["status"],"needs_vision_segmentation")

    def test_pistol_can_propose_disconnected_magazine_but_not_full_ready(self):
        pm=self._map([
            {"component_id":0,"face_count":900,"face_fraction":0.90,"centroid":[0,0,0],"extent":[3,1,1],"main_component":True},
            {"component_id":1,"face_count":70,"face_fraction":0.07,"centroid":[0,-0.8,0],"extent":[0.5,1.0,0.4],"main_component":False},
            {"component_id":2,"face_count":30,"face_fraction":0.03,"centroid":[0.1,-0.2,0],"extent":[0.1,0.2,0.1],"main_component":False},
        ])
        out=fit(pm,"handgun_semiauto")
        self.assertIn(out["status"],{"partial_fit","needs_vision_segmentation"})
        self.assertFalse(out["mechanical_ready"])
        # Trigger + slide are deliberately not guessed from disconnected geometry.
        self.assertIn("trigger",out.get("missing_components",[]))
        self.assertIn("slide",out.get("missing_components",[]))

    def test_unknown_family_fails_closed(self):
        out=fit(self._map([]),"mystery_gun")
        self.assertEqual(out["status"],"unknown_family")
        self.assertFalse(out["mechanical_ready"])


if __name__=="__main__":
    unittest.main()
