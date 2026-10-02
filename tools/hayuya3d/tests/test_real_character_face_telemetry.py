from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TOOLS))

from qa import inspect_mesh


class RealCharacterFaceTelemetryTests(unittest.TestCase):
    """Keep face-quality telemetry alive on the checked-in known-good characters.

    This deliberately checks structural invariants rather than inventing new visual
    thresholds.  A future quality floor should be calibrated from these measurements,
    but the telemetry itself must never silently disappear or become nonsensical.
    """

    MODELS = (
        ROOT / "hayuya/models/zombie-iglesia-001/model.glb",
        ROOT / "hayuya/models/candy-zombie-001/model.glb",
        ROOT / "hayuya/models/zombitest1-muetjpwb/model.glb",
    )

    def test_face_mesh_and_texel_telemetry_is_finite_and_consistent(self) -> None:
        for path in self.MODELS:
            with self.subTest(model=path.name):
                score = inspect_mesh(
                    path,
                    backend="face_telemetry_regression",
                    mode="character",
                    target_faces=250_000,
                    target_texture_size=4096,
                )
                self.assertTrue(score.valid, score.notes)
                self.assertGreater(score.faces, 0)
                self.assertGreater(score.head_region_faces, 0)
                self.assertLessEqual(score.head_region_faces, score.faces)
                self.assertGreater(score.head_region_vertices, 0)

                for name in (
                    "head_region_face_fraction",
                    "head_region_density_ratio",
                    "head_density_score",
                    "head_texel_density_ratio",
                    "head_texel_density_score",
                    "texture_resolution_score",
                ):
                    value = getattr(score, name)
                    self.assertIsNotNone(value, f"{path}: missing {name}")
                    self.assertTrue(math.isfinite(float(value)), f"{path}: non-finite {name}={value}")
                    self.assertGreaterEqual(float(value), 0.0, f"{path}: negative {name}={value}")

                self.assertLessEqual(float(score.head_region_face_fraction), 1.0)
                self.assertLessEqual(float(score.head_density_score), 100.0)
                self.assertLessEqual(float(score.head_texel_density_score), 100.0)
                self.assertLessEqual(float(score.texture_resolution_score), 100.0)

                self.assertGreater(score.base_color_min_edge, 0, f"{path}: no visible baseColor atlas")
                self.assertGreaterEqual(score.base_color_max_edge, score.base_color_min_edge)


if __name__ == "__main__":
    unittest.main()
