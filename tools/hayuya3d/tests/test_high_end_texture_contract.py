from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

from tools.hayuya3d import hayuya


class HighEndTextureContractTests(unittest.TestCase):
    def test_monster_and_ultra_require_native_4k_visible_textures(self):
        self.assertEqual(hayuya.PROFILES["monster"].texture_size, 4096)
        self.assertEqual(hayuya.PROFILES["ultra"].texture_size, 4096)

    def test_high_end_profiles_keep_dense_hero_master_before_runtime_retopology(self):
        self.assertEqual(hayuya.PROFILES["monster"].faces, 250_000)
        self.assertEqual(hayuya.PROFILES["monster"].hero_faces, 1_500_000)
        self.assertEqual(hayuya.PROFILES["ultra"].faces, 500_000)
        self.assertEqual(hayuya.PROFILES["ultra"].hero_faces, 2_000_000)
        self.assertGreater(
            hayuya.PROFILES["monster"].hero_faces,
            hayuya.PROFILES["monster"].faces,
        )

    def test_texture_superres_only_targets_high_end_under_resolved_visible_color(self):
        self.assertTrue(hayuya.needs_texture_superres("monster", 2048, 4096))
        self.assertTrue(hayuya.needs_texture_superres("ultra", 1024, 4096))
        self.assertFalse(hayuya.needs_texture_superres("game", 1024, 2048))
        self.assertFalse(hayuya.needs_texture_superres("monster", 4096, 4096))
        self.assertFalse(hayuya.needs_texture_superres("monster", 0, 4096))
        self.assertFalse(hayuya.needs_texture_superres("monster", None, 4096))

    def test_build_plan_documents_texture_superres_as_challenger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            image=root/"front.png"
            from PIL import Image
            Image.new("RGB",(32,32),(120,80,60)).save(image)
            plan=hayuya.make_job_plan(
                [image],
                profile_name="monster",
                mode="character",
                seed=1993,
                selected_backends=["trellis2"],
                model_root=root/"models",
                texture_superres_mode="auto",
            )
        self.assertEqual(plan["texture_superres"]["mode"],"auto")
        self.assertIn("challenger",plan["texture_superres"]["policy"])
        self.assertEqual(plan["texture_superres"]["model"],"realesrgan-x4plus")

    def test_texture_refinement_guard_rejects_fidelity_regression(self):
        source = SimpleNamespace(
            vertices=100,
            faces=200,
            components=1,
            bbox=[1.0, 2.0, 1.0],
            pbr_channels=["baseColor", "normal", "roughness"],
            head_texture_detail_score=76.856,
            visual_score=91.0,
            appearance_score=88.0,
            appearance_face_detail_score=86.0,
            base_color_min_edge=2048,
        )
        challenger = SimpleNamespace(
            vertices=100,
            faces=200,
            components=1,
            bbox=[1.0, 2.0, 1.0],
            pbr_channels=["baseColor", "normal", "roughness"],
            head_texture_detail_score=90.0,
            visual_score=91.0,
            appearance_score=87.5,
            appearance_face_detail_score=86.0,
            base_color_min_edge=4096,
        )
        reasons = hayuya.texture_refinement_regressions(source, challenger)
        self.assertTrue(
            any("appearance_score" in reason for reason in reasons),
            reasons,
        )

    def test_texture_refinement_guard_rejects_weakest_face_regression(self):
        source = SimpleNamespace(
            vertices=100,
            faces=200,
            components=1,
            bbox=[1.0, 2.0, 1.0],
            pbr_channels=["baseColor", "normal", "roughness"],
            head_texture_detail_score=80.0,
            visual_score=92.0,
            appearance_score=90.0,
            appearance_face_detail_score=90.0,
            appearance_face_detail_min_score=84.0,
            base_color_min_edge=2048,
        )
        challenger = SimpleNamespace(
            vertices=100,
            faces=200,
            components=1,
            bbox=[1.0, 2.0, 1.0],
            pbr_channels=["baseColor", "normal", "roughness"],
            head_texture_detail_score=85.0,
            visual_score=92.0,
            appearance_score=90.0,
            appearance_face_detail_score=90.0,
            appearance_face_detail_min_score=70.0,
            base_color_min_edge=4096,
        )
        reasons = hayuya.texture_refinement_regressions(source, challenger)
        self.assertTrue(
            any("appearance_face_detail_min_score" in reason for reason in reasons),
            reasons,
        )

    def test_texture_refinement_guard_accepts_monotonic_image_only_upgrade(self):
        source = SimpleNamespace(
            vertices=100,
            faces=200,
            components=1,
            bbox=[1.0, 2.0, 1.0],
            pbr_channels=["baseColor", "normal", "roughness"],
            head_texture_detail_score=76.856,
            visual_score=91.0,
            appearance_score=None,
            appearance_face_detail_score=None,
            base_color_min_edge=2048,
        )
        challenger = SimpleNamespace(
            vertices=100,
            faces=200,
            components=1,
            bbox=[1.0, 2.0, 1.0],
            pbr_channels=["baseColor", "normal", "roughness"],
            head_texture_detail_score=88.0,
            visual_score=91.0,
            appearance_score=None,
            appearance_face_detail_score=None,
            base_color_min_edge=4096,
        )
        self.assertEqual(
            hayuya.texture_refinement_regressions(source, challenger),
            [],
        )

    def test_texture_refinement_guard_rejects_geometry_or_pbr_loss(self):
        source = SimpleNamespace(
            vertices=100,
            faces=200,
            components=1,
            bbox=[1.0, 2.0, 1.0],
            pbr_channels=["baseColor", "normal", "occlusion"],
            head_texture_detail_score=None,
            visual_score=None,
            appearance_score=None,
            appearance_face_detail_score=None,
            base_color_min_edge=2048,
        )
        challenger = SimpleNamespace(
            vertices=99,
            faces=200,
            components=1,
            bbox=[1.0, 2.0, 1.0],
            pbr_channels=["baseColor", "normal"],
            head_texture_detail_score=None,
            visual_score=None,
            appearance_score=None,
            appearance_face_detail_score=None,
            base_color_min_edge=4096,
        )
        reasons = hayuya.texture_refinement_regressions(source, challenger)
        self.assertTrue(any("vertices" in reason for reason in reasons), reasons)
        self.assertTrue(any("occlusion" in reason for reason in reasons), reasons)

    def test_trellis2_receives_profile_texture_target_without_downshift(self):
        calls = {}

        def fake_generator(image, out_dir, **kwargs):
            calls.update(kwargs)
            return object()

        original = hayuya.GENERATORS["trellis2"]
        hayuya.GENERATORS["trellis2"] = fake_generator
        try:
            with tempfile.TemporaryDirectory() as tmp:
                hayuya.run_single_backend(
                    "trellis2",
                    Path(tmp) / "face.png",
                    Path(tmp) / "out",
                    profile=hayuya.PROFILES["monster"],
                    seed=1993,
                    model_root=Path(tmp) / "models",
                )
            self.assertEqual(calls["texture_size"], 4096)
            self.assertEqual(calls["resolution"], 1024)
            self.assertEqual(calls["faces"], 1_500_000)
        finally:
            hayuya.GENERATORS["trellis2"] = original


if __name__ == "__main__":
    unittest.main()
