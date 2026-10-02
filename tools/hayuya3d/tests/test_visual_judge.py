from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

import numpy as np
from visual_judge import (
    aggregate_source_scores,
    aggregate_source_scores_weighted,
    extract_source_mask_evidence,
    infer_view_hint,
    project_mesh_vertices,
    refine_projection_match,
    render_silhouette,
    score_masks,
)


class VisualJudgeTests(unittest.TestCase):
    def test_identical_silhouette_scores_perfect(self):
        a = np.zeros((64, 64), dtype=bool)
        a[12:52, 18:46] = True
        score, iou, edge = score_masks(a, a.copy())
        self.assertAlmostEqual(iou, 1.0, places=6)
        self.assertAlmostEqual(edge, 1.0, places=6)
        self.assertAlmostEqual(score, 100.0, places=6)

    def test_wrong_shape_scores_lower(self):
        a = np.zeros((64, 64), dtype=bool)
        a[10:54, 20:44] = True

        b = np.zeros((64, 64), dtype=bool)
        yy, xx = np.ogrid[:64, :64]
        b[(xx - 32) ** 2 + (yy - 32) ** 2 <= 17 ** 2] = True

        same, _, _ = score_masks(a, a)
        wrong, _, _ = score_masks(a, b)
        self.assertGreater(same, wrong)
        self.assertLess(wrong, 95.0)

    def test_second_photo_can_drag_down_bad_candidate(self):
        strong_both = aggregate_source_scores([92.0, 90.0])
        one_bad = aggregate_source_scores([99.0, 30.0])
        self.assertGreater(strong_both, one_bad)
        self.assertLess(one_bad, 70.0)

    def test_low_confidence_outlier_has_less_power(self):
        fully_trusted = aggregate_source_scores_weighted(
            [92.0, 91.0, 20.0],
            [1.0, 1.0, 1.0],
        )
        uncertain_outlier = aggregate_source_scores_weighted(
            [92.0, 91.0, 20.0],
            [1.0, 1.0, 0.15],
        )
        self.assertGreater(uncertain_outlier, fully_trusted)

    def test_alpha_mask_is_high_confidence(self):
        from PIL import Image
        rgba = np.zeros((64, 64, 4), dtype=np.uint8)
        rgba[12:52, 16:48, :3] = 180
        rgba[12:52, 16:48, 3] = 255
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cutout.png"
            Image.fromarray(rgba, mode="RGBA").save(path)
            mask, confidence, method = extract_source_mask_evidence(path, size=64)
            self.assertEqual(method, "alpha")
            self.assertGreaterEqual(confidence, 0.95)
            self.assertGreater(int(mask.sum()), 0)

    def test_many_reference_aggregation_resists_one_bad_outlier(self):
        mostly_good = [91, 90, 92, 89, 93, 90, 91, 88, 5]
        result = aggregate_source_scores(mostly_good)
        self.assertGreater(result, 65.0)
        self.assertLess(result, sum(mostly_good) / len(mostly_good))

    def test_canonical_filename_hints(self):
        self.assertEqual(infer_view_hint(Path("zombie_front.png")), 0.0)
        self.assertEqual(infer_view_hint(Path("zombie_front_45_right.png")), 45.0)
        self.assertEqual(infer_view_hint(Path("zombie_right_side.png")), 90.0)
        self.assertEqual(infer_view_hint(Path("zombie_back.png")), 180.0)
        self.assertEqual(infer_view_hint(Path("zombie_left_side.png")), 270.0)
        self.assertIsNone(infer_view_hint(Path("random_reference_17.png")))

    def test_perspective_projection_changes_depth_dependent_shape(self):
        vertices = np.array([
            [-0.5, 0.0, 0.0],
            [0.2, 0.2, 0.4],
            [0.5, 0.0, 0.0],
            [0.0, 0.8, -0.2],
        ], dtype=np.float32)
        ortho_xy, _ = project_mesh_vertices(
            vertices, 0.0, 0.0, "y", size=192, projection="orthographic"
        )
        persp_xy, _ = project_mesh_vertices(
            vertices, 0.0, 0.0, "y", size=192,
            projection="perspective", camera_distance=1.4
        )
        self.assertFalse(np.allclose(ortho_xy, persp_xy))

    def test_perspective_refinement_recovers_better_match(self):
        vertices = np.array([
            [-0.5, -0.5, -0.3],
            [0.5, -0.5, 0.3],
            [0.4, 0.5, 0.2],
            [-0.4, 0.5, -0.2],
        ], dtype=np.float32)
        faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
        source = render_silhouette(
            vertices, faces, 0.0, 0.0, "y", size=96,
            projection="perspective", camera_distance=1.4
        )
        base_mask = render_silhouette(
            vertices, faces, 0.0, 0.0, "y", size=96,
            projection="orthographic"
        )
        base_score, base_iou, base_edge = score_masks(source, base_mask)
        refined = refine_projection_match(
            source,
            vertices,
            faces,
            (base_score, base_iou, base_edge, "y", 0.0, 0.0),
            size=96,
            azimuth_step=30,
            cache={},
        )
        self.assertIsNotNone(refined)
        self.assertGreaterEqual(refined[0], base_score)

    def test_partial_overlap_is_not_rewarded_as_identity(self):
        a = np.zeros((64, 64), dtype=bool)
        a[12:52, 12:36] = True
        b = np.zeros((64, 64), dtype=bool)
        b[12:52, 28:52] = True
        score, iou, edge = score_masks(a, b)
        self.assertLess(iou, 0.25)
        self.assertLess(score, 40.0)


if __name__ == "__main__":
    unittest.main()
