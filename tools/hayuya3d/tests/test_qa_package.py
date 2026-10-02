from __future__ import annotations

import sys
import tempfile
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

import numpy as np
import trimesh
from PIL import Image

from gameprep import build_gameprep
from qa_package import (
    build_qa_package,
    face_quality_evidence_chain,
    material_rebake_channel_summary,
    unresolved_material_rebakes,
)
from visual_judge import SourceViewScore


class QAPackageTests(unittest.TestCase):
    def test_structural_defects_block_geometry_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final_glb = root / "broken_prop.glb"

            vertices = np.array([
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ], dtype=np.float64)
            faces = np.array([
                [0, 1, 2],
                [0, 1, 2],  # duplicate
                [0, 0, 3],  # degenerate
            ], dtype=np.int64)
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            rgba = np.tile(
                np.array([[100, 140, 180, 255]], dtype=np.uint8),
                (len(mesh.vertices), 1),
            )
            mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=rgba)
            final_glb.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
            )

            result = build_qa_package(
                final_glb,
                root / "qa",
                champion={"backend": "broken", "visual_views": []},
                mode="prop",
                profile="game",
                source_images=[],
                detail_images=[],
                gameprep=None,
                target_faces=500,
            )

            self.assertFalse(result.geometry_ready)
            self.assertFalse(result.production_ready)
            self.assertTrue(
                any("structural defects" in warning for warning in result.warnings),
                result.warnings,
            )

    def test_floating_accessory_is_reported_by_final_qa_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final_glb = root / "floating_accessory.glb"

            body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
            charm = trimesh.creation.icosphere(subdivisions=0, radius=0.08)
            charm.apply_translation([4.0, 0.0, 0.0])
            scene = trimesh.Scene()
            scene.add_geometry(body, node_name="body", geom_name="body")
            scene.add_geometry(charm, node_name="charm", geom_name="charm")
            final_glb.write_bytes(trimesh.exchange.gltf.export_glb(scene))

            result = build_qa_package(
                final_glb,
                root / "qa",
                champion={"backend": "fixture", "visual_views": []},
                mode="prop",
                profile="game",
                source_images=[],
                detail_images=[],
                gameprep=None,
                target_faces=500,
            )

            report = json.loads(Path(result.report).read_text(encoding="utf-8"))
            attachment = report["composite_attachment"]
            self.assertFalse(result.composite_attachment_ready)
            self.assertEqual(result.composite_attachment_components, 2)
            self.assertEqual(result.composite_attachment_accessories, 1)
            self.assertEqual(result.composite_attachment_floating, 1)
            self.assertEqual(result.composite_attachment_oversized_floating, 0)
            self.assertFalse(attachment["ready"])
            self.assertEqual(attachment["floating_components"], 1)
            self.assertFalse(result.production_ready)
            self.assertTrue(
                any(
                    "floating accessory" in warning
                    for warning in result.warnings
                ),
                result.warnings,
            )

    def test_face_reference_requires_face_identity_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final_glb = root / "face_asset.glb"
            face_ref = root / "face_detail-closeup.jpg"

            mesh = trimesh.creation.icosphere(subdivisions=2, radius=0.5)
            rgba = np.tile(
                np.array([[130, 90, 70, 255]], dtype=np.uint8),
                (len(mesh.vertices), 1),
            )
            mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=rgba)
            final_glb.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
            )
            Image.new("RGB", (256, 256), (130, 90, 70)).save(face_ref)

            missing = build_qa_package(
                final_glb,
                root / "qa-missing",
                champion={"backend": "test"},
                mode="character",
                profile="monster",
                source_images=[],
                detail_images=[face_ref],
                gameprep=None,
                target_faces=500,
            )
            self.assertFalse(missing.face_evidence_ready)
            self.assertTrue(
                any("face references were supplied" in w for w in missing.warnings),
                missing.warnings,
            )

            evaluated = build_qa_package(
                final_glb,
                root / "qa-evaluated",
                champion={
                    "backend": "test",
                    "appearance_face_detail_score": 94.0,
                    "appearance_details": [{
                        "source": str(face_ref),
                        "score": 94.0,
                        "region_hint": "head",
                    }],
                },
                mode="character",
                profile="monster",
                source_images=[],
                detail_images=[face_ref],
                gameprep=None,
                target_faces=500,
            )
            self.assertTrue(evaluated.face_evidence_ready)
            self.assertEqual(evaluated.face_evidence_expected,1)
            self.assertEqual(evaluated.face_evidence_evaluated,1)
            self.assertEqual(evaluated.face_evidence_missing,[])
            self.assertEqual(evaluated.face_evidence_min_score,94.0)
            self.assertFalse(evaluated.face_quality_evidence_ready)
            self.assertTrue(evaluated.face_quality_evidence_missing)

    def test_face_reference_requires_complete_per_reference_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            final_glb=root/"face_asset.glb"
            face_front=root/"face_detail-front.jpg"
            face_profile=root/"face_detail-profile.jpg"

            mesh=trimesh.creation.icosphere(subdivisions=2,radius=0.5)
            rgba=np.tile(
                np.array([[130,90,70,255]],dtype=np.uint8),
                (len(mesh.vertices),1),
            )
            mesh.visual=trimesh.visual.ColorVisuals(
                mesh,
                vertex_colors=rgba,
            )
            final_glb.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
            )
            Image.new("RGB",(256,256),(130,90,70)).save(face_front)
            Image.new("RGB",(256,256),(125,85,65)).save(face_profile)

            partial=build_qa_package(
                final_glb,
                root/"qa-partial",
                champion={
                    "backend":"test",
                    "appearance_face_detail_score":92.0,
                    "appearance_details":[{
                        "source":str(face_front),
                        "score":93.0,
                        "region_hint":"head",
                    }],
                },
                mode="character",
                profile="monster",
                source_images=[],
                detail_images=[face_front,face_profile],
                gameprep=None,
                target_faces=500,
            )
            self.assertFalse(partial.face_evidence_ready)
            self.assertEqual(partial.face_evidence_expected,2)
            self.assertEqual(partial.face_evidence_evaluated,1)
            self.assertEqual(
                partial.face_evidence_missing,
                [str(face_profile)],
            )
            self.assertEqual(partial.face_evidence_min_score,93.0)
            self.assertTrue(
                any("coverage incomplete" in w for w in partial.warnings),
                partial.warnings,
            )

            complete=build_qa_package(
                final_glb,
                root/"qa-complete",
                champion={
                    "backend":"test",
                    "appearance_face_detail_score":92.0,
                    "appearance_details":[
                        {
                            "source":str(face_front),
                            "score":93.0,
                            "region_hint":"head",
                        },
                        {
                            "source":str(face_profile),
                            "score":91.0,
                            "region_hint":"head",
                        },
                    ],
                },
                mode="character",
                profile="monster",
                source_images=[],
                detail_images=[face_front,face_profile],
                gameprep=None,
                target_faces=500,
            )
            self.assertTrue(complete.face_evidence_ready)
            self.assertEqual(complete.face_evidence_evaluated,2)
            self.assertEqual(complete.face_evidence_missing,[])
            self.assertEqual(complete.face_evidence_min_score,91.0)


    def test_face_quality_evidence_chain_requires_all_dimensions(self):
        ready, missing = face_quality_evidence_chain(
            required=True,
            face_min_score=91.0,
            head_density_score=98.0,
            head_texel_density_score=None,
            head_texture_detail_score=82.0,
        )
        self.assertFalse(ready)
        self.assertEqual(missing,["head_texel_density_score"])

        ready, missing = face_quality_evidence_chain(
            required=True,
            face_min_score=91.0,
            head_density_score=98.0,
            head_texel_density_score=97.0,
            head_texture_detail_score=82.0,
        )
        self.assertTrue(ready)
        self.assertEqual(missing,[])

        ready, missing = face_quality_evidence_chain(
            required=True,
            identity_required=False,
            face_min_score=None,
            head_density_score=98.0,
            head_texel_density_score=97.0,
            head_texture_detail_score=82.0,
        )
        self.assertTrue(ready)
        self.assertEqual(missing,[])

        ready, missing = face_quality_evidence_chain(
            required=False,
            face_min_score=None,
            head_density_score=None,
            head_texel_density_score=None,
            head_texture_detail_score=None,
        )
        self.assertTrue(ready)
        self.assertEqual(missing,[])

    def test_unresolved_material_rebakes_are_detected_per_lod(self):
        data = {
            "lods": [
                {"name": "LOD0", "rebake_required": []},
                {"name": "LOD1", "rebake_required": ["normal", "occlusion"]},
                {"name": "LOD2", "rebake_required": ["normal"]},
            ]
        }
        unresolved = unresolved_material_rebakes(data)
        self.assertEqual(unresolved, [
            {"lod": "LOD1", "channels": ["normal", "occlusion"]},
            {"lod": "LOD2", "channels": ["normal"]},
        ])
        self.assertEqual(unresolved_material_rebakes({"lods": []}), [])
        self.assertEqual(unresolved_material_rebakes(None), [])

    def test_material_rebake_summary_requires_every_lod_complete(self):
        data = {
            "lods": [
                {
                    "name": "LOD0",
                    "rebaked_channels": ["normal", "occlusion"],
                    "rebake_required": [],
                },
                {
                    "name": "LOD1",
                    "rebaked_channels": ["normal"],
                    "rebake_required": ["occlusion"],
                },
                {
                    "name": "LOD2",
                    "rebaked_channels": ["normal", "occlusion"],
                    "rebake_required": [],
                },
            ]
        }
        resolved, pending = material_rebake_channel_summary(data)
        self.assertEqual(resolved, ["normal"])
        self.assertEqual(pending, ["occlusion"])


    def test_character_without_skin_is_not_production_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final_glb = root / "character.glb"
            source_img = root / "character_front.png"

            mesh = trimesh.creation.icosphere(subdivisions=2, radius=0.5)
            rgba = np.tile(
                np.array([[120, 80, 60, 255]], dtype=np.uint8),
                (len(mesh.vertices), 1),
            )
            mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=rgba)
            final_glb.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
            )
            Image.new("RGB", (128, 256), (120, 80, 60)).save(source_img)

            anchor = SourceViewScore(
                source=str(source_img),
                best_score=90.0,
                best_azimuth=0.0,
                best_elevation=0.0,
                best_up_axis="y",
                silhouette_iou=0.9,
                boundary_f1=0.9,
            )
            gameprep = build_gameprep(
                final_glb,
                root / "gameprep",
                target_faces=500,
                anchor_view=anchor,
                material_samples=3000,
            )

            champion = {
                "backend": "test",
                "score": 90.0,
                "visual_views": [{
                    "source": str(source_img),
                    "best_score": 90.0,
                    "best_azimuth": 0.0,
                    "best_elevation": 0.0,
                    "best_up_axis": "y",
                    "silhouette_iou": 0.9,
                    "boundary_f1": 0.9,
                    "projection": "orthographic",
                    "camera_distance": None,
                    "mask_confidence": 1.0,
                    "mask_method": "alpha",
                }],
            }

            result = build_qa_package(
                final_glb,
                root / "qa",
                champion=champion,
                mode="character",
                profile="game",
                source_images=[source_img],
                detail_images=[],
                gameprep=gameprep,
                target_faces=500,
            )

            self.assertTrue(Path(result.report).is_file())
            report = json.loads(Path(result.report).read_text(encoding="utf-8"))
            self.assertIn("head_density_score", report["geometry"])
            self.assertTrue(result.contact_sheet and Path(result.contact_sheet).is_file())
            self.assertTrue(result.geometry_ready)
            self.assertFalse(result.face_quality_evidence_ready)
            self.assertIn(
                "head_texel_density_score",
                result.face_quality_evidence_missing,
            )
            self.assertFalse(result.rig_ready)
            self.assertFalse(result.animation_ready)
            self.assertFalse(result.production_ready)
            self.assertTrue(any("unrigged" in warning for warning in result.warnings))


if __name__ == "__main__":
    unittest.main()
