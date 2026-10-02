from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

import numpy as np
from appearance_judge import (
    aggregate_appearance_scores,
    aggregate_detail_scores,
    aggregate_region_balanced_detail_scores,
    cosine_similarity,
    make_detail_patches,
    rasterize_rgb,
    _encode_dinov2_batch,
    select_detail_candidate_indices,
)


class AppearanceJudgeTests(unittest.TestCase):
    def test_external_dino_worker_path_does_not_require_main_torch(self):
        from PIL import Image

        image = Image.new("RGB", (32, 32), (120, 80, 40))

        def fake_run(cmd, check):
            output = Path(cmd[cmd.index("--output") + 1])
            np.save(output, np.array([[1.0, 0.0, 0.0]], dtype=np.float32))
            return None

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "dinov2"
            repo.mkdir()
            with mock.patch.dict(os.environ, {"HAYUYA_DINOV2_PYTHON": sys.executable}):
                with mock.patch("appearance_judge.subprocess.run", side_effect=fake_run) as run_mock:
                    features = _encode_dinov2_batch(
                        [image],
                        repo_path=repo,
                        device_name="auto",
                        batch_size=4,
                    )

            self.assertEqual(features.shape, (1, 3))
            self.assertAlmostEqual(float(features[0, 0]), 1.0, places=6)
            self.assertTrue(run_mock.called)

    def test_cosine_identity(self):
        a = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        self.assertAlmostEqual(cosine_similarity(a, a), 1.0, places=6)

    def test_cosine_orthogonal(self):
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0, places=6)

    def test_many_view_appearance_penalizes_weak_tail(self):
        good = aggregate_appearance_scores([91, 90, 92, 89, 90])
        mixed = aggregate_appearance_scores([95, 94, 93, 92, 30])
        self.assertGreater(good, mixed)

    def test_detail_view_hint_locks_asymmetric_side(self):
        patch_meta = [
            (0.0, "whole"),
            (45.0, "whole"),
            (90.0, "whole"),
            (135.0, "whole"),
            (180.0, "whole"),
            (225.0, "whole"),
            (270.0, "whole"),
            (315.0, "whole"),
        ]
        allowed, expected, region = select_detail_candidate_indices(
            patch_meta,
            Path("llorona_left_side_detail.png"),
            orientation_offset=0.0,
        )
        self.assertEqual(expected, 270.0)
        self.assertEqual({patch_meta[i][0] for i in allowed}, {225.0, 270.0, 315.0})
        self.assertNotIn(90.0, {patch_meta[i][0] for i in allowed})
        self.assertIsNone(region)

    def test_generic_detail_can_search_all_sides(self):
        patch_meta = [(0.0, "a"), (90.0, "b"), (180.0, "c"), (270.0, "d")]
        allowed, expected, region = select_detail_candidate_indices(
            patch_meta,
            Path("rosary_closeup.png"),
            orientation_offset=35.0,
        )
        self.assertIsNone(expected)
        self.assertEqual(region, "local")
        self.assertEqual(allowed, list(range(len(patch_meta))))

    def test_face_detail_is_locked_to_upper_patch_row(self):
        patch_meta = [
            (0.0, "whole"),
            (0.0, "grid_0_0"),
            (0.0, "grid_0_1"),
            (0.0, "grid_0_2"),
            (0.0, "grid_1_0"),
            (0.0, "grid_1_1"),
            (0.0, "grid_2_1"),
        ]
        allowed, expected, region = select_detail_candidate_indices(
            patch_meta,
            Path("llorona_face_detail.png"),
            orientation_offset=0.0,
        )
        self.assertIsNone(expected)
        self.assertEqual(region, "head")
        self.assertEqual(
            {patch_meta[i][1] for i in allowed},
            {"grid_0_0", "grid_0_1", "grid_0_2"},
        )

    def test_face_fallback_relaxes_view_before_head_region(self):
        patch_meta = [
            (0.0, "grid_1_1"),
            (45.0, "grid_2_1"),
            (180.0, "grid_0_0"),
            (180.0, "grid_0_1"),
        ]
        allowed, expected, region = select_detail_candidate_indices(
            patch_meta,
            Path("zombie_front_face_detail.png"),
            orientation_offset=0.0,
            max_distance=30.0,
        )
        self.assertEqual(expected, 0.0)
        self.assertEqual(region, "head")
        self.assertEqual(
            {patch_meta[i][1] for i in allowed},
            {"grid_0_0", "grid_0_1"},
        )

    def test_hem_detail_is_locked_to_lower_patch_row(self):
        patch_meta = [
            (180.0, "whole"),
            (180.0, "grid_0_1"),
            (180.0, "grid_1_1"),
            (180.0, "grid_2_0"),
            (180.0, "grid_2_1"),
            (180.0, "grid_2_2"),
        ]
        allowed, expected, region = select_detail_candidate_indices(
            patch_meta,
            Path("llorona_back_hem_detail.png"),
            orientation_offset=0.0,
        )
        self.assertEqual(expected, 180.0)
        self.assertEqual(region, "lower")
        self.assertEqual(
            {patch_meta[i][1] for i in allowed},
            {"grid_2_0", "grid_2_1", "grid_2_2"},
        )

    def test_detail_aggregation_keeps_weak_reference_relevant(self):
        strong = aggregate_detail_scores([90, 91, 89])
        weak_tail = aggregate_detail_scores([95, 94, 30])
        self.assertGreater(strong, weak_tail)

    def test_detail_aggregation_balances_semantic_regions(self):
        sparse = aggregate_region_balanced_detail_scores([
            ("middle",95.0),
            ("head",50.0),
        ])
        torso_heavy = aggregate_region_balanced_detail_scores([
            *[("middle",95.0) for _ in range(8)],
            ("head",50.0),
        ])
        face_strong = aggregate_region_balanced_detail_scores([
            *[("middle",95.0) for _ in range(8)],
            ("head",90.0),
        ])
        self.assertAlmostEqual(sparse,torso_heavy,places=6)
        self.assertGreater(face_strong,torso_heavy)

    def test_detail_patch_grid_has_whole_plus_nine_local_crops(self):
        from PIL import Image
        image = Image.new("RGB", (224, 224), (100, 120, 140))
        patches = make_detail_patches(image)
        self.assertEqual(len(patches), 10)
        self.assertEqual(patches[0][0], "whole")
        self.assertTrue(all(patch.size == (224, 224) for _, patch in patches))

    def test_cpu_rasterizer_draws_triangle(self):
        xy = np.array([[8, 8], [56, 8], [32, 56]], dtype=np.float32)
        z = np.array([1, 1, 1], dtype=np.float32)
        faces = np.array([[0, 1, 2]], dtype=np.int64)
        colors = np.array([[255, 0, 0], [255, 0, 0], [255, 0, 0]], dtype=np.float32)
        image = np.asarray(rasterize_rgb(xy, z, faces, colors, size=64))
        self.assertGreater(int(image[:, :, 0].max()), 200)
        self.assertTrue(np.any(np.all(image != np.array([127, 127, 127]), axis=2)))

    def test_uv_texture_overrides_vertex_color(self):
        xy = np.array([[8, 8], [56, 8], [32, 56]], dtype=np.float32)
        z = np.array([1, 1, 1], dtype=np.float32)
        faces = np.array([[0, 1, 2]], dtype=np.int64)
        colors = np.array([[255, 0, 0], [255, 0, 0], [255, 0, 0]], dtype=np.float32)
        uvs = np.array([[0, 0], [1, 0], [0.5, 1]], dtype=np.float32)
        texture = np.full((4, 4, 3), [10, 220, 30], dtype=np.uint8)
        image = np.asarray(
            rasterize_rgb(
                xy,
                z,
                faces,
                colors,
                uvs=uvs,
                face_texture_ids=np.array([0], dtype=np.int32),
                textures=[texture],
                size=64,
            )
        )
        center = image[32, 32]
        self.assertGreater(int(center[1]), 180)
        self.assertLess(int(center[0]), 80)

    def test_zbuffer_prefers_larger_depth(self):
        xy = np.array([
            [8, 8], [56, 8], [32, 56],
            [8, 8], [56, 8], [32, 56],
        ], dtype=np.float32)
        z = np.array([0, 0, 0, 1, 1, 1], dtype=np.float32)
        faces = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int64)
        colors = np.array([
            [255, 0, 0], [255, 0, 0], [255, 0, 0],
            [0, 255, 0], [0, 255, 0], [0, 255, 0],
        ], dtype=np.float32)
        image = np.asarray(rasterize_rgb(xy, z, faces, colors, size=64))
        center = image[32, 32]
        self.assertGreater(int(center[1]), int(center[0]))


if __name__ == "__main__":
    unittest.main()
