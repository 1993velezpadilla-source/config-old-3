from __future__ import annotations

import unittest

from tools.hayuya3d.semantic_anatomy_qa import (
    aggregate_semantic_reports,
    build_critical_plan,
    required_parts_for_targets,
)


def report(image:str,*detections:dict)->dict:
    return {
        "image":image,
        "detections":list(detections),
    }


def det(part:str,score:float=0.9)->dict:
    return {
        "part":part,
        "grounding_score":score,
        "sam_iou_score":0.88,
        "mask_area_ratio":0.03,
    }


class SemanticAnatomyQATests(unittest.TestCase):
    def test_critical_plan_promotes_only_requested_anatomy(self):
        plan=build_critical_plan(["eyes","hands"])
        self.assertEqual(
            plan["required"],
            ["left_eye","right_eye","left_hand","right_hand"],
        )
        self.assertEqual(plan["status"],"ready")
        self.assertEqual(set(plan["prompts"]),set(plan["required"]))
        self.assertFalse(plan["warnings"])

    def test_all_critical_parts_detected_passes(self):
        result=aggregate_semantic_reports(
            [
                report(
                    "front.png",
                    det("left_eye"),
                    det("right_eye"),
                    det("left_hand"),
                    det("right_hand"),
                ),
            ],
            critical_targets=["eyes","hands"],
        )
        self.assertTrue(result.required)
        self.assertTrue(result.ready,result.errors)
        self.assertEqual(result.missing_parts,[])
        self.assertEqual(
            set(result.detected_parts),
            {"left_eye","right_eye","left_hand","right_hand"},
        )

    def test_missing_one_eye_blocks(self):
        result=aggregate_semantic_reports(
            [
                report(
                    "front.png",
                    det("left_eye"),
                ),
            ],
            critical_targets=["eyes"],
        )
        self.assertFalse(result.ready)
        self.assertEqual(result.missing_parts,["right_eye"])
        right=next(
            item for item in result.parts
            if item.part=="right_eye"
        )
        self.assertFalse(right.ready)
        self.assertEqual(right.detected_views,0)

    def test_evidence_can_be_completed_across_multiple_views(self):
        result=aggregate_semantic_reports(
            [
                report(
                    "front.png",
                    det("left_eye",0.93),
                    det("mouth",0.91),
                ),
                report(
                    "side.png",
                    det("right_eye",0.89),
                ),
            ],
            critical_targets=["eyes","mouth"],
        )
        self.assertTrue(result.ready,result.errors)
        self.assertEqual(result.view_count,2)
        self.assertEqual(result.missing_parts,[])

    def test_minimum_views_per_part_can_require_multiview_confirmation(self):
        result=aggregate_semantic_reports(
            [
                report("front.png",det("teeth")),
                report("side.png"),
            ],
            critical_targets=["teeth"],
            minimum_views_per_part=2,
        )
        self.assertFalse(result.ready)
        self.assertEqual(result.missing_parts,["teeth"])

    def test_no_critical_targets_is_not_required(self):
        result=aggregate_semantic_reports(
            [],
            critical_targets=[],
        )
        self.assertFalse(result.required)
        self.assertTrue(result.ready)

    def test_required_part_mapping_is_stable(self):
        self.assertEqual(
            required_parts_for_targets(
                ["teeth","ears","wounds"]
            ),
            ["teeth","left_ear","right_ear","wounds"],
        )


if __name__=="__main__":
    unittest.main()
