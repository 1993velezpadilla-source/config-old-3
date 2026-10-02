from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

import numpy as np
from normal_judge import (
    aggregate_normal_support,
    rasterize_normals,
    score_normal_maps,
)


class NormalJudgeTests(unittest.TestCase):
    def test_identical_normal_maps_score_perfect(self):
        normal = np.zeros((16, 16, 3), dtype=np.float32)
        normal[:, :, 2] = 1.0
        mask = np.ones((16, 16), dtype=bool)
        score, cosine, iou = score_normal_maps(normal, mask, normal.copy(), mask.copy())
        self.assertAlmostEqual(cosine, 1.0, places=6)
        self.assertAlmostEqual(iou, 1.0, places=6)
        self.assertAlmostEqual(score, 100.0, places=6)

    def test_opposite_normals_are_rejected(self):
        a = np.zeros((16, 16, 3), dtype=np.float32)
        b = np.zeros((16, 16, 3), dtype=np.float32)
        a[:, :, 2] = 1.0
        b[:, :, 2] = -1.0
        mask = np.ones((16, 16), dtype=bool)
        score, cosine, _ = score_normal_maps(a, mask, b, mask)
        self.assertLess(cosine, -0.99)
        self.assertLess(score, 20.0)

    def test_normal_support_keeps_weak_tail_relevant(self):
        good = aggregate_normal_support([90, 91, 89, 92, 90])
        weak = aggregate_normal_support([96, 95, 94, 93, 20])
        self.assertGreater(good, weak)

    def test_normal_rasterizer_interpolates_and_normalizes(self):
        xy = np.array([[8, 8], [56, 8], [32, 56]], dtype=np.float32)
        z = np.array([1, 1, 1], dtype=np.float32)
        faces = np.array([[0, 1, 2]], dtype=np.int64)
        normals = np.array([
            [0, 0, 1],
            [0, 0, 1],
            [0, 0, 1],
        ], dtype=np.float32)
        rendered, mask = rasterize_normals(xy, z, faces, normals, size=64)
        self.assertTrue(mask[32, 32])
        self.assertGreater(float(rendered[32, 32, 2]), 0.99)
        self.assertAlmostEqual(float(np.linalg.norm(rendered[32, 32])), 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
