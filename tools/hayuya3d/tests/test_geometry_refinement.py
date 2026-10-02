from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from geometry_refinement import geometry_health


class GeometryRefinementTests(unittest.TestCase):
    def make_score(self, **overrides):
        data = dict(
            valid=True,
            components=1,
            degenerate_ratio=0.0,
            bbox=[1.0, 1.0, 1.0],
            faces=10000,
        )
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_clean_mesh_has_high_geometry_health(self):
        self.assertGreater(geometry_health(self.make_score()), 95.0)

    def test_many_components_are_penalized(self):
        clean = geometry_health(self.make_score())
        broken = geometry_health(self.make_score(components=10))
        self.assertGreater(clean, broken)

    def test_degenerate_mesh_is_penalized(self):
        clean = geometry_health(self.make_score())
        broken = geometry_health(self.make_score(degenerate_ratio=0.05))
        self.assertGreater(clean, broken)

    def test_collapsed_axis_is_heavily_penalized(self):
        clean = geometry_health(self.make_score())
        collapsed = geometry_health(self.make_score(bbox=[1.0, 1.0, 0.0]))
        self.assertGreater(clean, collapsed)

    def test_invalid_mesh_has_zero_health(self):
        self.assertEqual(geometry_health(self.make_score(valid=False)), 0.0)


if __name__ == "__main__":
    unittest.main()
