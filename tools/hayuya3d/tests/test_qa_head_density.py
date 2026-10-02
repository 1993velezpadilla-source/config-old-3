from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from qa import (
    MeshScore,
    _sample_uv_luma_gradients,
    candidate_rank_key,
    head_density_score_from_ratio,
    head_structure_metrics,
    inspect_mesh,
)


class HeadStructureTests(unittest.TestCase):
    def _cloud(self, *, head_width: float, head_depth: float, lower_scale: float=0.82):
        body=[]
        for y in np.linspace(0.0,0.80,12):
            for x in (-0.18,0.18):
                for z in (-0.10,0.10):
                    body.append([x,y,z])
        head=[]
        for y in np.linspace(0.835,0.985,10):
            t=(y-0.835)/(0.985-0.835)
            scale=lower_scale+(1.0-lower_scale)*t
            for x in np.linspace(-head_width*0.5*scale,head_width*0.5*scale,5):
                for z in np.linspace(-head_depth*0.5,head_depth*0.5,4):
                    head.append([x,y,z])
        return np.asarray(body+head,dtype=np.float64)

    def test_normal_humanoid_head_is_not_demoted(self):
        metrics=head_structure_metrics(
            np,self._cloud(head_width=0.16,head_depth=0.12),
            up_axis=1,body_min=0.0,body_span=1.0,
        )
        self.assertIsNotNone(metrics["score"])
        self.assertGreaterEqual(metrics["score"],85.0)

    def test_needle_flat_head_is_detected(self):
        metrics=head_structure_metrics(
            np,self._cloud(head_width=0.045,head_depth=0.009,lower_scale=0.22),
            up_axis=1,body_min=0.0,body_span=1.0,
        )
        self.assertIsNotNone(metrics["score"])
        self.assertLess(metrics["score"],45.0)

    def test_ranking_demotes_structural_head_outlier(self):
        healthy=MeshScore(
            path="healthy.glb",backend="healthy",score=78.0,valid=True,
            head_density_score=90.0,head_texel_density_score=90.0,
            head_texture_detail_score=90.0,head_structure_score=88.0,
        )
        weird=MeshScore(
            path="weird.glb",backend="weird",score=99.0,valid=True,
            head_density_score=100.0,head_texel_density_score=100.0,
            head_texture_detail_score=100.0,head_structure_score=20.0,
        )
        ranked=sorted(
            [weird,healthy],
            key=lambda item:candidate_rank_key(item,mode="character"),
            reverse=True,
        )
        self.assertEqual(ranked[0].backend,"healthy")


class HeadDensityScoreTests(unittest.TestCase):
    def test_missing_density_is_neutral_telemetry(self):
        self.assertIsNone(head_density_score_from_ratio(None))

    def test_coarse_head_loses_score_proportionally(self):
        self.assertEqual(head_density_score_from_ratio(0.50), 50.0)
        self.assertEqual(head_density_score_from_ratio(0.875), 87.5)

    def test_equal_or_denser_head_caps_at_full_credit(self):
        self.assertEqual(head_density_score_from_ratio(1.0), 100.0)
        self.assertEqual(head_density_score_from_ratio(1.8), 100.0)

    def test_character_ranking_prefers_complete_surface_evidence(self):
        complete=MeshScore(
            path="complete.glb",
            backend="complete",
            score=80.0,
            valid=True,
            head_density_score=98.0,
            head_texel_density_score=97.0,
            head_texture_detail_score=82.0,
        )
        incomplete=MeshScore(
            path="incomplete.glb",
            backend="incomplete",
            score=99.0,
            valid=True,
            head_density_score=100.0,
            head_texel_density_score=None,
            head_texture_detail_score=100.0,
        )
        ranked=sorted(
            [incomplete,complete],
            key=lambda item:candidate_rank_key(item,mode="character"),
            reverse=True,
        )
        self.assertEqual(ranked[0].backend,"complete")

    def test_face_reference_ranking_requires_identity_evidence(self):
        identity_ready=MeshScore(
            path="identity.glb",
            backend="identity",
            score=80.0,
            valid=True,
            head_density_score=98.0,
            head_texel_density_score=97.0,
            head_texture_detail_score=82.0,
            appearance_face_detail_min_score=88.0,
        )
        missing_identity=MeshScore(
            path="missing.glb",
            backend="missing",
            score=99.0,
            valid=True,
            head_density_score=100.0,
            head_texel_density_score=100.0,
            head_texture_detail_score=100.0,
            appearance_face_detail_min_score=None,
        )
        ranked=sorted(
            [missing_identity,identity_ready],
            key=lambda item:candidate_rank_key(
                item,
                mode="character",
                identity_required=True,
            ),
            reverse=True,
        )
        self.assertEqual(ranked[0].backend,"identity")

    def test_face_texture_gradient_sampler_distinguishes_local_detail(self):
        uniform = Image.fromarray(
            np.full((16, 16, 3), 128, dtype=np.uint8),
            mode="RGB",
        )
        striped = np.zeros((16, 16, 3), dtype=np.uint8)
        striped[:, ::2] = 32
        striped[:, 1::2] = 224
        detailed = Image.fromarray(striped, mode="RGB")
        uv_centers = np.array([
            [0.10, 0.10],
            [0.30, 0.30],
            [0.50, 0.50],
            [0.70, 0.70],
        ], dtype=np.float64)
        mask = np.array([True, True, True, True])
        flat = _sample_uv_luma_gradients(
            np, uniform, uv_centers, mask
        )
        sharp = _sample_uv_luma_gradients(
            np, detailed, uv_centers, mask
        )
        self.assertEqual(float(np.mean(flat)), 0.0)
        self.assertGreater(float(np.mean(sharp)), 50.0)

    def test_head_texel_density_detects_tiny_face_uv_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "face-uv-budget.glb"

            vertices = np.array([
                [-0.5, -0.5, 0.0],
                [ 0.5, -0.5, 0.0],
                [ 0.5,  0.5, 0.0],
                [-0.5,  0.5, 0.0],
                [-0.5, -0.5, 2.0],
                [ 0.5, -0.5, 2.0],
                [ 0.5,  0.5, 2.0],
                [-0.5,  0.5, 2.0],
            ], dtype=np.float64)
            faces = np.array([
                [0, 1, 2], [0, 2, 3],
                [4, 5, 6], [4, 6, 7],
            ], dtype=np.int64)
            # Lower/body plane owns ~81% of UV area. The upper/head plane gets
            # only ~1%, despite equal world-space surface area.
            uvs = np.array([
                [0.00, 0.00], [0.90, 0.00], [0.90, 0.90], [0.00, 0.90],
                [0.90, 0.90], [1.00, 0.90], [1.00, 1.00], [0.90, 1.00],
            ], dtype=np.float64)
            base = Image.fromarray(
                np.full((256, 256, 4), [160, 100, 80, 255], dtype=np.uint8),
                mode="RGBA",
            )
            material = trimesh.visual.material.PBRMaterial(
                baseColorTexture=base,
                roughnessFactor=0.7,
                metallicFactor=0.0,
            )
            mesh = trimesh.Trimesh(
                vertices=vertices,
                faces=faces,
                process=False,
                visual=trimesh.visual.TextureVisuals(uv=uvs, material=material),
            )
            path.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh)))

            score = inspect_mesh(
                path,
                backend="face_uv_test",
                mode="character",
                target_faces=4,
                target_texture_size=256,
            )
            self.assertTrue(score.valid, score.notes)
            self.assertIsNotNone(score.head_texel_density_ratio)
            self.assertLess(score.head_texel_density_ratio, 0.10)
            self.assertIsNotNone(score.head_texel_density_score)
            self.assertLess(score.head_texel_density_score, 10.0)
            self.assertTrue(
                any("texel density" in note for note in score.notes or []),
                score.notes,
            )


if __name__ == "__main__":
    unittest.main()
