from __future__ import annotations

import unittest
from pathlib import Path

from tools.hayuya3d.anatomy_reference import (
    critical_anatomy_evidence,
    infer_anatomy_target,
)


class CriticalAnatomyEvidenceTests(unittest.TestCase):
    def test_infers_conservative_named_targets(self):
        self.assertEqual(
            infer_anatomy_target(Path("/refs/zombie_eye_closeup.png")),
            "eyes",
        )
        self.assertEqual(
            infer_anatomy_target(Path("/refs/left_hand_detail.jpg")),
            "hands",
        )
        self.assertEqual(
            infer_anatomy_target(Path("/refs/broken_teeth_macro.png")),
            "teeth",
        )
        self.assertEqual(
            infer_anatomy_target(Path("/refs/face_wound_detail.png")),
            "wounds",
        )
        self.assertIsNone(
            infer_anatomy_target(Path("/refs/IMG_1234.png"))
        )

    def test_every_explicit_anatomy_reference_must_be_evaluated(self):
        refs=[
            Path("/refs/eye_closeup.png"),
            Path("/refs/teeth_detail.png"),
            Path("/refs/right_hand_detail.png"),
        ]
        details=[
            {
                "source":"/refs/eye_closeup.png",
                "score":96.0,
            },
            {
                "source":"/refs/right_hand_detail.png",
                "score":91.0,
            },
        ]
        report=critical_anatomy_evidence(refs,details)
        self.assertTrue(report.required)
        self.assertFalse(report.ready)
        self.assertEqual(report.expected,3)
        self.assertEqual(report.evaluated,2)
        self.assertEqual(
            report.missing,
            ["/refs/teeth_detail.png"],
        )
        teeth=next(x for x in report.targets if x.target=="teeth")
        self.assertFalse(teeth.ready)
        self.assertEqual(teeth.evaluated,0)

    def test_target_worst_and_mean_scores_are_recorded(self):
        refs=[
            Path("/refs/left_eye_detail.png"),
            Path("/refs/right_eye_detail.png"),
            Path("/refs/mouth_closeup.png"),
        ]
        details=[
            {"source":"left_eye_detail.png","score":94.0},
            {"source":"right_eye_detail.png","score":88.0},
            {"source":"mouth_closeup.png","score":92.0},
        ]
        report=critical_anatomy_evidence(refs,details)
        self.assertTrue(report.ready,report.missing)
        eyes=next(x for x in report.targets if x.target=="eyes")
        self.assertEqual(eyes.expected,2)
        self.assertEqual(eyes.evaluated,2)
        self.assertEqual(eyes.min_score,88.0)
        self.assertEqual(eyes.mean_score,91.0)

    def test_no_explicit_anatomy_reference_is_not_required(self):
        report=critical_anatomy_evidence(
            [Path("/refs/torso_detail.png")],
            [],
        )
        self.assertFalse(report.required)
        self.assertTrue(report.ready)
        self.assertEqual(report.expected,0)


if __name__=="__main__":
    unittest.main()
