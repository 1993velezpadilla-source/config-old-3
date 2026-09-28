import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from aaa_policy import assess_aaa_candidate


class AAAPolicyTests(unittest.TestCase):
    def test_preview_normal_hero_can_never_be_ultra_final(self):
        result = assess_aaa_candidate(
            generator="microsoft/TRELLIS.2-preview-normal-hero",
            hero_master={
                "dense_master_ready": False,
                "native_latent_extraction": False,
                "actual_faces": 1_999_984,
            },
            texture_quality="ultra",
        )
        self.assertFalse(result.eligible)
        self.assertTrue(result.diagnostic_only)
        self.assertIn(
            "preview_reconstruction_is_diagnostic_only",
            result.reasons,
        )
        self.assertIn(
            "native_or_model_generated_geometry_required",
            result.reasons,
        )

    def test_provider_capped_trellis2_is_not_high_final(self):
        result = assess_aaa_candidate(
            generator="microsoft/TRELLIS.2-4B",
            hero_master={
                "dense_master_ready": False,
                "provider_capped": True,
                "refinement_required": True,
            },
            texture_quality="high",
        )
        self.assertFalse(result.eligible)
        self.assertIn(
            "provider_capped_geometry_requires_native_replacement",
            result.reasons,
        )

    def test_native_dense_triposg_can_reach_judge(self):
        result = assess_aaa_candidate(
            generator="VAST-AI/TripoSG",
            hero_master={
                "dense_master_ready": True,
                "provider_capped": False,
                "refinement_required": False,
                "actual_faces": 1_500_000,
            },
            texture_quality="ultra",
        )
        self.assertTrue(result.eligible)
        self.assertFalse(result.diagnostic_only)
        self.assertEqual(result.reasons, ())


if __name__ == "__main__":
    unittest.main()
