from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools.hayuya3d.semantic_anatomy_runner import (
    frame_targets,
    infer_critical_targets,
    render_specs,
    run_semantic_anatomy,
)


class SemanticAnatomyRunnerTests(unittest.TestCase):
    def test_head_targets_add_closeup_views(self):
        self.assertEqual(
            render_specs(
                ["eyes","hands"],
                ["front","side","rear"],
            ),
            [
                ("front","full"),
                ("side","full"),
                ("rear","full"),
                ("front","head"),
                ("side","head"),
            ],
        )

    def test_head_only_targets_skip_unnecessary_full_body_views(self):
        self.assertEqual(
            render_specs(
                ["eyes","teeth"],
                ["front","side","rear"],
            ),
            [
                ("front","head"),
                ("side","head"),
            ],
        )
        self.assertEqual(
            frame_targets(["eyes","hands","teeth"],"head"),
            ["eyes","teeth"],
        )
        self.assertEqual(
            frame_targets(["eyes","hands","teeth"],"full"),
            ["hands"],
        )

    def test_non_head_targets_keep_full_body_views_only(self):
        self.assertEqual(
            render_specs(
                ["hands"],
                ["front","side","rear"],
            ),
            [
                ("front","full"),
                ("side","full"),
                ("rear","full"),
            ],
        )

    def test_infers_unique_targets_from_explicit_detail_names(self):
        targets=infer_critical_targets([
            Path("/refs/left_eye_detail.png"),
            Path("/refs/right_eye_detail.png"),
            Path("/refs/hand_closeup.png"),
            Path("/refs/torso_detail.png"),
        ])
        self.assertEqual(targets,["eyes","hands"])

    def test_auto_records_unavailable_stack_without_false_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch(
                "tools.hayuya3d.semantic_anatomy_runner.semantic_stack_ready",
                return_value=(False,["blender","transformers"]),
            ):
                result=run_semantic_anatomy(
                    Path(tmp)/"final.glb",
                    [Path("/refs/eye_detail.png")],
                    Path(tmp)/"semantic",
                    policy="auto",
                )
        self.assertTrue(result.required)
        self.assertFalse(result.attempted)
        self.assertFalse(result.ready)
        self.assertIn("semantic_stack_unavailable",result.error or "")

    def test_no_critical_refs_does_not_require_semantic_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run_semantic_anatomy(
                Path(tmp)/"final.glb",
                [Path("/refs/torso_detail.png")],
                Path(tmp)/"semantic",
                policy="auto",
            )
        self.assertFalse(result.required)
        self.assertFalse(result.attempted)
        self.assertTrue(result.ready)

    def test_mocked_multiview_detector_completes_critical_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            final=root/"final.glb"
            final.write_bytes(b"stub")
            out=root/"semantic"

            def fake_run(argv,**kwargs):
                if any("semantic_part_detector.py" in str(x) for x in argv):
                    out_index=argv.index("--out")+1
                    detector_dir=Path(argv[out_index])
                    detector_dir.mkdir(parents=True,exist_ok=True)
                    image=Path(argv[argv.index("--image")+1])
                    plan_path=Path(argv[argv.index("--plan")+1])
                    plan=json.loads(plan_path.read_text(encoding="utf-8"))
                    if image.stem=="front":
                        self.assertEqual(plan["required"],["left_hand","right_hand"])
                        detections=[
                            {"part":"left_hand","grounding_score":0.91,"sam_iou_score":0.87,"mask_area_ratio":0.03},
                        ]
                    elif image.stem=="side":
                        self.assertEqual(plan["required"],["left_hand","right_hand"])
                        detections=[
                            {"part":"right_hand","grounding_score":0.90,"sam_iou_score":0.86,"mask_area_ratio":0.03},
                        ]
                    elif image.stem=="front_head":
                        self.assertEqual(plan["required"],["left_eye","right_eye"])
                        detections=[
                            {"part":"left_eye","grounding_score":0.94,"sam_iou_score":0.9,"mask_area_ratio":0.01},
                            {"part":"right_eye","grounding_score":0.92,"sam_iou_score":0.88,"mask_area_ratio":0.01},
                        ]
                    else:
                        detections=[]
                    (detector_dir/"semantic_parts.json").write_text(
                        json.dumps({
                            "image":str(image),
                            "detections":detections,
                            "missing_required":[],
                            "passed":True,
                        }),
                        encoding="utf-8",
                    )
                return SimpleNamespace(returncode=0,stdout="ok")

            with (
                mock.patch(
                    "tools.hayuya3d.semantic_anatomy_runner.semantic_stack_ready",
                    return_value=(True,[]),
                ),
                mock.patch(
                    "tools.hayuya3d.semantic_anatomy_runner.subprocess.run",
                    side_effect=fake_run,
                ),
            ):
                result=run_semantic_anatomy(
                    final,
                    [
                        Path("/refs/eyes_closeup.png"),
                        Path("/refs/hands_detail.png"),
                    ],
                    out,
                    policy="required",
                )

            self.assertTrue(result.required)
            self.assertTrue(result.attempted)
            self.assertTrue(result.ready,result.error)
            self.assertEqual(result.critical_targets,["eyes","hands"])
            self.assertEqual(len(result.rendered_views),5)
            self.assertEqual(len(result.detector_reports),5)
            self.assertIsNotNone(result.aggregate)
            self.assertEqual(
                result.aggregate["missing_parts"],
                [],
            )


if __name__=="__main__":
    unittest.main()
