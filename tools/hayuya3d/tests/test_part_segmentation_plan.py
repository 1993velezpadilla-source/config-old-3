from __future__ import annotations

import unittest

from tools.hayuya3d.part_segmentation_plan import build


class PartSegmentationPlanTests(unittest.TestCase):
    def test_humanoid_required_parts_all_have_prompts(self):
        plan=build("character.humanoid","auto")
        self.assertEqual(plan["status"],"ready")
        missing=[
            part
            for part in plan["required"]
            if part not in plan["prompts"]
        ]
        self.assertEqual(missing,[])
        self.assertFalse(
            any(
                str(item).startswith("required_part_missing_prompt:")
                for item in plan["warnings"]
            )
        )

    def test_explicit_critical_anatomy_promotes_semantic_parts(self):
        plan=build(
            "character.humanoid",
            "auto",
            critical_targets=["eyes","hands","teeth"],
        )
        required=set(plan["required"])
        for part in (
            "left_eye","right_eye",
            "left_hand","right_hand",
            "teeth",
        ):
            self.assertIn(part,required)
            self.assertIn(part,plan["prompts"])
            self.assertIn(
                part,
                set(plan["promoted_critical_parts"]),
            )
        self.assertEqual(
            plan["critical_targets_requested"],
            ["eyes","hands","teeth"],
        )

    def test_unknown_critical_target_is_reported_not_invented(self):
        plan=build(
            "character.humanoid",
            "auto",
            critical_targets=["eyes","unknown_anatomy"],
        )
        self.assertTrue(
            any(
                "unknown_critical_targets:unknown_anatomy"==item
                for item in plan["warnings"]
            )
        )
        self.assertNotIn("unknown_anatomy",plan["required"])

    def test_weapon_plan_remains_unchanged_by_character_targets(self):
        plan=build(
            "weapon.firearm",
            "handgun_semiauto",
            critical_targets=["eyes"],
        )
        self.assertIn("trigger",plan["required"])
        self.assertNotIn("left_eye",plan["required"])


if __name__=="__main__":
    unittest.main()
