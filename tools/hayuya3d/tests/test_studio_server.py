from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from studio_server import JobState, hydrate_candidate_ranking, parse_multipart, parse_pipeline_line


class StudioServerTests(unittest.TestCase):
    def make_job(self, root: Path) -> JobState:
        return JobState(id="test-job", root=str(root))

    def test_parse_candidate_and_final_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "output" / "candidate.glb"
            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(b"glTF" + b"x" * 32)
            final = root / "output" / "hayuya_final.glb"
            final.write_bytes(b"glTF" + b"y" * 32)

            job = self.make_job(root)
            parse_pipeline_line(
                job,
                f"HAYUYA_CANDIDATE_READY trellis2 {candidate} source=front.png",
            )
            self.assertIn("trellis2", job.candidates)
            self.assertEqual(job.stage, "generating")
            self.assertTrue(job.candidates["trellis2"].url.endswith("output/candidate.glb"))

            parse_pipeline_line(
                job,
                "HAYUYA_JUDGE_SCORE backend=trellis2 score=88.75 valid=true rank=1 pass=1",
            )
            self.assertEqual(job.stage, "judge")
            self.assertEqual(job.candidates["trellis2"].score, 88.75)
            self.assertEqual(job.events[-1]["kind"], "judge_score")

            parse_pipeline_line(
                job,
                "HAYUYA_CHAMPION backend=trellis2 score=91.25 references=4",
            )
            self.assertEqual(job.champion, "trellis2")
            self.assertTrue(job.candidates["trellis2"].is_champion)
            self.assertEqual(job.candidates["trellis2"].score, 91.25)

            parse_pipeline_line(job, f"HAYUYA_MONSTER_READY {final}")
            self.assertTrue(job.final_model_url.endswith("output/hayuya_final.glb"))

    def test_live_judge_metrics_hydrate_candidate_and_emit_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate.glb"
            candidate.write_bytes(b"glTF" + b"x" * 32)
            job = self.make_job(root)
            parse_pipeline_line(
                job,
                f"HAYUYA_CANDIDATE_READY trellis2 {candidate} source=front.png",
            )
            metrics = {
                "backend": "trellis2",
                "production_score": 89.0,
                "visual_score": 95.0,
                "appearance_score": 94.0,
                "appearance_detail_score": 92.0,
                "appearance_face_detail_score": 97.0,
                "appearance_face_detail_min_score": 91.0,
                "material_score": 90.0,
                "texture_resolution_score": 100.0,
                "base_color_max_edge": 4096,
                "base_color_min_edge": 2048,
                "head_region_faces": 20000,
                "head_region_vertices": 11000,
                "head_region_face_fraction": 0.09,
                "global_median_edge_normalized": 0.0013,
                "head_region_median_edge_normalized": 0.0011,
                "head_region_density_ratio": 1.1818,
                "head_density_score": 100.0,
                "head_texture_detail_ratio": 1.24,
                "head_texture_detail_score": 100.0,
                "head_texture_detail_mean": 18.5,
                "pbr_channels": ["baseColor", "normal", "roughness"],
            }
            parse_pipeline_line(
                job,
                "HAYUYA_JUDGE_METRICS " + json.dumps(metrics,separators=(",",":")),
            )
            item = job.candidates["trellis2"]
            self.assertEqual(item.face_detail_score, 97.0)
            self.assertEqual(item.face_detail_min_score, 91.0)
            self.assertEqual(item.base_color_max_edge, 4096)
            self.assertEqual(item.base_color_min_edge, 2048)
            self.assertEqual(item.head_region_faces, 20000)
            self.assertAlmostEqual(item.head_region_density_ratio, 1.1818)
            self.assertEqual(item.head_density_score, 100.0)
            self.assertAlmostEqual(item.head_texture_detail_ratio, 1.24)
            self.assertEqual(item.head_texture_detail_score, 100.0)
            self.assertEqual(job.events[-1]["kind"], "judge_metrics")
            self.assertEqual(job.events[-1]["candidate"]["face_detail_score"], 97.0)
            self.assertEqual(
                job.events[-1]["candidate"]["face_detail_min_score"],
                91.0,
            )

    def test_ranking_hydration_keeps_face_texture_and_head_geometry_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "candidate.glb"
            candidate.write_bytes(b"glTF" + b"x" * 32)
            job = self.make_job(root)
            parse_pipeline_line(
                job,
                f"HAYUYA_CANDIDATE_READY trellis2 {candidate} source=front.png",
            )

            hydrate_candidate_ranking(job, [{
                "backend": "trellis2",
                "score": 93.5,
                "production_score": 88.0,
                "visual_score": 94.0,
                "appearance_score": 91.0,
                "appearance_detail_score": 90.0,
                "appearance_face_detail_score": 96.0,
                "appearance_face_detail_min_score": 88.0,
                "material_score": 87.0,
                "texture_resolution_score": 100.0,
                "base_color_max_edge": 4096,
                "base_color_min_edge": 2048,
                "head_region_faces": 18240,
                "head_region_vertices": 10420,
                "head_region_face_fraction": 0.082,
                "global_median_edge_normalized": 0.00140,
                "head_region_median_edge_normalized": 0.00123,
                "head_region_density_ratio": 1.1382,
                "head_density_score": 100.0,
                "head_texture_detail_ratio": 1.18,
                "head_texture_detail_score": 100.0,
                "head_texture_detail_mean": 17.2,
                "pbr_channels": ["baseColor", "normal", "roughness"],
            }])

            item = job.candidates["trellis2"]
            self.assertEqual(item.face_detail_score, 96.0)
            self.assertEqual(item.face_detail_min_score, 88.0)
            self.assertEqual(item.texture_resolution_score, 100.0)
            self.assertEqual(item.base_color_max_edge, 4096)
            self.assertEqual(item.base_color_min_edge, 2048)
            self.assertEqual(item.head_region_faces, 18240)
            self.assertAlmostEqual(item.head_region_median_edge_normalized, 0.00123)
            self.assertAlmostEqual(item.head_region_density_ratio, 1.1382)
            self.assertEqual(item.head_density_score, 100.0)
            self.assertAlmostEqual(item.head_texture_detail_ratio, 1.18)
            self.assertEqual(item.head_texture_detail_score, 100.0)
            self.assertIn("normal", item.pbr_channels or [])

    def test_pipeline_stage_events_are_real_stage_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "qa_report.json"
            report.write_text(
                json.dumps({
                    "warnings": [
                        "weakest visible baseColor resolution 2048px is below profile target 4096px",
                        "runtime LOD material rebake is incomplete: LOD1:occlusion",
                    ]
                }),
                encoding="utf-8",
            )
            job = self.make_job(root)
            composite = root / "composite_champion_plan.json"
            composite.write_text(json.dumps({
                "base_backend": "trellis2_seed01",
                "composite_required": True,
                "finalist_backends": ["trellis2_seed01","trellis2_seed02"],
                "donors": [{
                    "region": "face_identity",
                    "donor_backend": "trellis2_seed02",
                    "donor_score": 98.0,
                    "strategy": "surface_wrap_plus_identity_texture_projection",
                    "seam_risk": "high",
                    "rig_risk": "high",
                }],
                "executable_now": [],
                "deferred_transfers": ["face_identity"],
            }), encoding="utf-8")
            lines = [
                ("HAYUYA_VIEWFORGE_READY backend=wonder3d synthetic_views=5", "viewforge"),
                ("HAYUYA_REFINEMENT_READY source=x preferred=y improvement=2", "refinement"),
                ("HAYUYA_MESH_DOCTOR_CLEAN defect_score=0", "mesh_doctor"),
                ("HAYUYA_RETOPO_READY style=pure_quad quad_fraction=1 obj=x", "retopo"),
                (f"HAYUYA_COMPOSITE_PLAN_READY base=trellis2_seed01 required=true finalists=2 donors=face_identity:trellis2_seed02 plan={composite}", "composite"),
                ("HAYUYA_GAMEPREP_READY lods=4 collision=True turntable=8", "gameprep"),
                ("HAYUYA_PORTABLE_PACK_READY tiers=4 complete_lods=True lod_parity_ready=True manifest=x", "portable"),
                (f"HAYUYA_QA_READY production_ready=True material_ready=True texture_ready=True texture_score=100.0 basecolor_min=4096 basecolor_max=4096 texture_target=4096 rebake_ready=True rebaked=normal,occlusion rebake_pending=none rig_ready=False morph_ready=True morph_targets=0 crossing_ready=True crossing_pairs=0 self_intersection_ready=True self_intersection_pairs=0 composite_attachment_ready=True composite_components=6 composite_accessories=5 composite_floating=0 composite_oversized_floating=0 uv_tangent_ready=True uv_missing=0 uv_degenerate=0 shading_basis_ready=True shading_missing_normals=0 shading_missing_tangents=0 shading_bad_handedness=0 shading_nonorthogonal=0 skin_weights_ready=False animation_ready=False animation_integrity_ready=False animation_channels=0 animation_keyframes=0 deformation_ready=False deformation_frames=0 deformation_max_disp=none deformation_max_edge=none face_ready=True face_quality_ready=True anatomy_ready=True anatomy_expected=2 anatomy_evaluated=2 face_score=94.5 face_min=89.0 face_expected=2 face_evaluated=2 facemesh_score=88.0 facetex_score=91.0 facedetail_score=87.5 report={report}", "qa"),
            ]
            last_progress = -1
            for line, expected in lines:
                parse_pipeline_line(job, line)
                self.assertEqual(job.stage, expected)
                self.assertGreater(job.progress, last_progress)
                last_progress = job.progress
            self.assertIsNotNone(job.composite_plan)
            self.assertEqual(
                job.composite_plan["base_backend"],
                "trellis2_seed01",
            )
            self.assertTrue(job.composite_plan["composite_required"])
            self.assertEqual(
                job.composite_plan["donors"][0]["donor_backend"],
                "trellis2_seed02",
            )
            self.assertEqual(job.final_qa["facemesh_score"], 88.0)
            self.assertTrue(job.final_qa["morph_ready"])
            self.assertEqual(job.final_qa["morph_targets"],0)
            self.assertTrue(job.final_qa["crossing_ready"])
            self.assertEqual(job.final_qa["crossing_pairs"],0)
            self.assertTrue(job.final_qa["self_intersection_ready"])
            self.assertEqual(job.final_qa["self_intersection_pairs"],0)
            self.assertTrue(job.final_qa["composite_attachment_ready"])
            self.assertEqual(job.final_qa["composite_components"],6)
            self.assertEqual(job.final_qa["composite_accessories"],5)
            self.assertEqual(job.final_qa["composite_floating"],0)
            self.assertEqual(job.final_qa["composite_oversized_floating"],0)
            self.assertTrue(job.final_qa["uv_tangent_ready"])
            self.assertEqual(job.final_qa["uv_missing"],0)
            self.assertEqual(job.final_qa["uv_degenerate"],0)
            self.assertTrue(job.final_qa["shading_basis_ready"])
            self.assertEqual(job.final_qa["shading_missing_normals"],0)
            self.assertEqual(job.final_qa["shading_missing_tangents"],0)
            self.assertEqual(job.final_qa["shading_bad_handedness"],0)
            self.assertEqual(job.final_qa["shading_nonorthogonal"],0)
            self.assertFalse(job.final_qa["skin_weights_ready"])
            self.assertFalse(job.final_qa["animation_integrity_ready"])
            self.assertEqual(job.final_qa["animation_channels"],0)
            self.assertEqual(job.final_qa["animation_keyframes"],0)
            self.assertFalse(job.final_qa["deformation_ready"])
            self.assertEqual(job.final_qa["deformation_frames"],0)
            self.assertIsNone(job.final_qa["deformation_max_disp"])
            self.assertIsNone(job.final_qa["deformation_max_edge"])
            self.assertTrue(job.final_qa["face_quality_ready"])
            self.assertTrue(job.final_qa["anatomy_ready"])
            self.assertEqual(job.final_qa["anatomy_expected"],2)
            self.assertEqual(job.final_qa["anatomy_evaluated"],2)
            self.assertEqual(job.final_qa["face_score"], 94.5)
            self.assertEqual(job.final_qa["face_min"], 89.0)
            self.assertEqual(job.final_qa["face_expected"], 2)
            self.assertEqual(job.final_qa["face_evaluated"], 2)
            self.assertEqual(job.final_qa["facetex_score"], 91.0)
            self.assertEqual(job.final_qa["facedetail_score"], 87.5)
            self.assertTrue(job.final_qa["texture_ready"])
            self.assertEqual(job.final_qa["texture_score"], 100.0)
            self.assertEqual(job.final_qa["basecolor_min"], 4096)
            self.assertEqual(job.final_qa["texture_target"], 4096)
            self.assertEqual(job.final_qa["rebaked_channels"], ["normal", "occlusion"])
            self.assertEqual(job.final_qa["rebake_pending_channels"], [])
            self.assertEqual(len(job.final_qa["warnings"]), 2)
            self.assertIn("baseColor", job.final_qa["warnings"][0])

    def test_composite_detail_seam_state_is_streamed(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=self.make_job(Path(tmp))
            parse_pipeline_line(
                job,
                "HAYUYA_COMPOSITE_DETAIL_READY "
                "label=composite_detail_head_face "
                "base=base donor=face region=head "
                "source=scar.png strategy=texture_fusion changed=0.184 "
                "seam_p95=3.2 seam_max=7.5 accessory_confidence=none "
                f"path={Path(tmp)/'detail.glb'}",
            )
            self.assertEqual(job.stage,"composite")
            self.assertEqual(len(job.composite_details),1)
            detail=job.composite_details[0]
            self.assertEqual(detail["label"],"composite_detail_head_face")
            self.assertEqual(detail["status"],"challenger")
            self.assertEqual(detail["strategy"],"texture_fusion")
            self.assertEqual(detail["changed_fraction"],0.184)
            self.assertIsNone(detail["accessory_confidence"])
            self.assertEqual(detail["seam_p95"],3.2)
            self.assertEqual(detail["seam_max"],7.5)
            self.assertEqual(job.events[-1]["kind"],"composite_detail")

            parse_pipeline_line(
                job,
                "HAYUYA_COMPOSITE_DETAIL_GUARD_PASS "
                "label=composite_detail_head_face "
                "source=scar.png canonical=true",
            )
            self.assertEqual(
                job.composite_details[0]["status"],
                "accepted",
            )
            self.assertEqual(
                job.events[-1]["kind"],
                "composite_detail_state",
            )

            parse_pipeline_line(
                job,
                "HAYUYA_COMPOSITE_DETAIL_REJECTED "
                "label=composite_detail_head_face "
                "source=scar.png reason=guard_failed",
            )
            self.assertEqual(
                job.composite_details[0]["status"],
                "rejected",
            )
            self.assertEqual(
                job.composite_details[0]["reason"],
                "guard_failed",
            )

    def test_composite_accessory_evidence_is_streamed(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=self.make_job(Path(tmp))
            parse_pipeline_line(
                job,
                "HAYUYA_COMPOSITE_DETAIL_READY "
                "label=composite_accessory_donor_rosary "
                "base=base donor=donor region=local "
                "source=rosary.png strategy=accessory_swap "
                "changed=none seam_p95=none seam_max=none "
                "accessory_confidence=0.873 "
                f"path={Path(tmp)/'accessory.glb'}",
            )
            detail=job.composite_details[-1]
            self.assertEqual(detail["strategy"],"accessory_swap")
            self.assertEqual(detail["accessory_confidence"],0.873)
            self.assertIsNone(detail["changed_fraction"])
            self.assertIsNone(detail["seam_p95"])
            self.assertEqual(detail["region"],"local")

    def test_rigged_accessory_runtime_proof_is_streamed(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=self.make_job(Path(tmp))
            parse_pipeline_line(
                job,
                "HAYUYA_COMPOSITE_DETAIL_READY "
                "label=composite_accessory_donor_rosary "
                "base=base donor=donor region=local "
                "source=rosary.png strategy=rigged_accessory_wrap "
                "changed=none changed_vertices=8 "
                "seam_p95=none seam_max=none "
                "accessory_confidence=0.932 "
                "runtime_preserved=True rig_ready=True "
                "skin_weights_ready=True morph_deformation_ready=True "
                "rebake_ready=True "
                f"path={Path(tmp)/'rigged-accessory.glb'}",
            )
            detail=job.composite_details[-1]
            self.assertEqual(
                detail["strategy"],
                "rigged_accessory_wrap",
            )
            self.assertEqual(detail["changed_vertices"],8)
            self.assertTrue(detail["runtime_preserved"])
            self.assertTrue(detail["rig_ready"])
            self.assertTrue(detail["skin_weights_ready"])
            self.assertTrue(detail["morph_deformation_ready"])
            self.assertTrue(detail["rebake_ready"])
            self.assertEqual(detail["accessory_confidence"],0.932)

    def test_inserted_accessory_production_proof_is_streamed(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=self.make_job(Path(tmp))
            parse_pipeline_line(
                job,
                "HAYUYA_COMPOSITE_DETAIL_READY "
                "label=composite_accessory_donor_medal "
                "base=base donor=donor region=local "
                "source=medal.png strategy=rigged_accessory_insert "
                "changed=none changed_vertices=none "
                "inserted_vertices=24 inserted_faces=12 "
                "inserted_primitives=3 material_groups=3 "
                "weight_transfer_vertices=24 weight_source_max=0.041 "
                "surface_transfer=hayuya-surface-transfer-bvh-barycentric-exact-v2 "
                "surface_fallback_vertices=0 "
                "surface_search_triangles=48 "
                "surface_bvh_nodes=17 "
                "surface_ambiguous_vertices=0 "
                "surface_skin_gap=none surface_skin_l1=0.0 "
                "morph_targets_transferred=2 "
                "geometry_ready=True legacy_preserved=True "
                "seam_p95=none seam_max=none "
                "accessory_confidence=none "
                "runtime_preserved=True rig_ready=True "
                "skin_weights_ready=True morph_deformation_ready=True "
                "animation_ready=True deformation_ready=True "
                "attachment_ready=True material_ready=True "
                "uv_ready=True uv_tangent_ready=True "
                "production_ready=True material_channels=baseColor,normal "
                "rebake_ready=none "
                f"path={Path(tmp)/'inserted-accessory.glb'}",
            )
            detail=job.composite_details[-1]
            self.assertEqual(detail["strategy"],"rigged_accessory_insert")
            self.assertEqual(detail["inserted_vertices"],24)
            self.assertEqual(detail["inserted_faces"],12)
            self.assertEqual(detail["inserted_primitives"],3)
            self.assertEqual(detail["material_groups"],3)
            self.assertEqual(detail["weight_transfer_vertices"],24)
            self.assertEqual(detail["weight_source_max"],0.041)
            self.assertEqual(
                detail["surface_transfer"],
                "hayuya-surface-transfer-bvh-barycentric-exact-v2",
            )
            self.assertEqual(detail["surface_fallback_vertices"],0)
            self.assertEqual(detail["surface_search_triangles"],48)
            self.assertEqual(detail["surface_bvh_nodes"],17)
            self.assertEqual(detail["surface_ambiguous_vertices"],0)
            self.assertIsNone(detail["surface_skin_gap"])
            self.assertEqual(detail["surface_skin_l1"],0.0)
            self.assertEqual(detail["morph_targets_transferred"],2)
            self.assertTrue(detail["geometry_ready"])
            self.assertTrue(detail["legacy_preserved"])
            self.assertTrue(detail["runtime_preserved"])
            self.assertTrue(detail["rig_ready"])
            self.assertTrue(detail["skin_weights_ready"])
            self.assertTrue(detail["morph_deformation_ready"])
            self.assertTrue(detail["animation_ready"])
            self.assertTrue(detail["deformation_ready"])
            self.assertTrue(detail["attachment_ready"])
            self.assertTrue(detail["material_ready"])
            self.assertTrue(detail["uv_ready"])
            self.assertTrue(detail["uv_tangent_ready"])
            self.assertTrue(detail["production_ready"])
            self.assertEqual(
                detail["material_channels"],
                ["baseColor","normal"],
            )

    def test_semantic_anatomy_report_is_streamed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            report=root/"semantic_anatomy.json"
            report.write_text(json.dumps({
                "required":True,
                "ready":False,
                "critical_targets":["eyes","hands"],
                "required_parts":[
                    "left_eye","right_eye",
                    "left_hand","right_hand",
                ],
                "detected_parts":[
                    "left_eye","right_eye","left_hand",
                ],
                "missing_parts":["right_hand"],
                "view_count":3,
                "parts":[
                    {
                        "part":"right_hand",
                        "required":True,
                        "detected_views":0,
                        "ready":False,
                    },
                ],
                "warnings":[],
                "errors":[],
            }),encoding="utf-8")
            job=self.make_job(root)
            parse_pipeline_line(
                job,
                "HAYUYA_SEMANTIC_ANATOMY_READY "
                "attempted=true ready=false "
                "targets=eyes,hands views=3 "
                f"report={report} "
                "error=semantic_anatomy_incomplete:right_hand",
            )
            self.assertIsNotNone(job.semantic_anatomy)
            self.assertFalse(job.semantic_anatomy["ready"])
            self.assertTrue(job.semantic_anatomy["attempted"])
            self.assertEqual(
                job.semantic_anatomy["critical_targets"],
                ["eyes","hands"],
            )
            self.assertEqual(
                job.semantic_anatomy["aggregate"]["missing_parts"],
                ["right_hand"],
            )
            self.assertEqual(
                job.events[-1]["kind"],
                "semantic_anatomy",
            )

    def test_portable_lod_parity_manifest_is_streamed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            manifest=root/"portable_manifest.json"
            manifest.write_text(json.dumps({
                "complete_lod_chain":True,
                "lod_parity_ready":True,
                "runtime_budget_ready":True,
                "tiers":[
                    {
                        "tier":"flagship",
                        "gameprep":{"lods":[{"name":"LOD0"},{"name":"LOD1"},{"name":"LOD2"},{"name":"LOD3"}]},
                        "lod_parity":{
                            "ready":True,
                            "lod_count":4,
                            "errors":[],
                            "items":[{
                                "name":"LOD1",
                                "ready":True,
                                "shape_p95_distance_ratio":0.021,
                                "faces":18000,
                                "rig_required":True,
                                "rig_ready":True,
                                "deformation_ready":True,
                                "errors":[],
                            }],
                        },
                        "runtime_budget":{
                            "ready":True,
                            "lod_count":4,
                            "errors":[],
                            "items":[{
                                "name":"LOD0",
                                "ready":True,
                                "faces":80000,
                                "face_budget_max":180000,
                                "material_count":2,
                                "material_slots_max":6,
                                "texture_max_edge":4096,
                                "texture_edge_max":4096,
                            }],
                        },
                    },
                    {
                        "tier":"high",
                        "gameprep":{"lods":[{"name":"LOD0"},{"name":"LOD1"},{"name":"LOD2"},{"name":"LOD3"}]},
                        "lod_parity":{
                            "ready":True,
                            "lod_count":4,
                            "errors":[],
                            "items":[],
                        },
                        "runtime_budget":{
                            "ready":True,
                            "lod_count":4,
                            "errors":[],
                            "items":[],
                        },
                    },
                ],
            }),encoding="utf-8")
            job=self.make_job(root)
            parse_pipeline_line(
                job,
                "HAYUYA_PORTABLE_PACK_READY "
                "tiers=2 complete_lods=True lod_parity_ready=True runtime_budget_ready=True "
                f"manifest={manifest}",
            )
            self.assertEqual(job.stage,"portable")
            self.assertIsNotNone(job.portable_pack)
            self.assertTrue(job.portable_pack["complete_lod_chain"])
            self.assertTrue(job.portable_pack["lod_parity_ready"])
            self.assertTrue(job.portable_pack["runtime_budget_ready"])
            self.assertEqual(len(job.portable_pack["tiers"]),2)
            self.assertTrue(
                job.portable_pack["tiers"][0]["lod_parity"]["ready"]
            )
            self.assertTrue(
                job.portable_pack["tiers"][0]["runtime_budget"]["ready"]
            )
            self.assertEqual(
                job.portable_pack["tiers"][0]["runtime_budget"]["items"][0]["face_budget_max"],
                180000,
            )
            self.assertEqual(
                job.events[-1]["kind"],
                "portable_pack",
            )

    def test_aaa_acceptance_report_is_streamed_to_studio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            report=root/"aaa_acceptance.json"
            report.write_text(json.dumps({
                "ready":False,
                "passed_required":10,
                "total_required":12,
                "blockers":[
                    "character has no validated animation clips",
                    "better regional donor evidence exists but Composite Champion fusion is not fully resolved",
                ],
                "gates":[
                    {
                        "id":"character.animation",
                        "category":"character",
                        "ready":False,
                        "required":True,
                        "evidence":"animations=0",
                        "blocker":"character has no validated animation clips",
                    }
                ],
            }),encoding="utf-8")
            job=self.make_job(root)
            parse_pipeline_line(
                job,
                "HAYUYA_AAA_READY "
                f"ready=false passed=10 total=12 "
                f"blockers=character.animation,composite.optimized "
                f"report={report}",
            )
            self.assertEqual(job.stage,"qa")
            self.assertIsNotNone(job.aaa_acceptance)
            self.assertFalse(job.aaa_acceptance["ready"])
            self.assertEqual(job.aaa_acceptance["passed_required"],10)
            self.assertEqual(job.aaa_acceptance["total_required"],12)
            self.assertEqual(job.events[-1]["kind"],"aaa_ready")
            self.assertEqual(
                job.events[-1]["aaa"]["gates"][0]["id"],
                "character.animation",
            )

    def test_texture_superres_event_stays_inside_refinement_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = self.make_job(Path(tmp))
            parse_pipeline_line(
                job,
                "HAYUYA_REFINEMENT_READY source=x preferred=y improvement=2",
            )
            refinement_progress = job.progress
            parse_pipeline_line(
                job,
                "HAYUYA_TEXTURE_SUPERRES_READY source=trellis2 "
                "candidate=trellis2_texture_sr basecolor=2048->4096 items=1",
            )
            self.assertEqual(job.stage, "refinement")
            self.assertEqual(job.progress, refinement_progress)

    def test_multipart_accepts_many_images_and_fields(self):
        boundary = "----hayuya-test"
        parts = []
        def field(name: str, value: str):
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        def file(name: str, filename: str, payload: bytes):
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: image/png\r\n\r\n"
            ).encode() + payload + b"\r\n"

        parts.append(field("profile", "ultra"))
        parts.append(field("mode", "character"))
        parts.append(file("images", "front.png", b"PNG-A"))
        parts.append(file("images", "back.png", b"PNG-B"))
        parts.append(file("face_images", "IMG_1234.jpg", b"FACE-C"))
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()

        fields, files = parse_multipart(
            body,
            f"multipart/form-data; boundary={boundary}",
        )
        self.assertEqual(fields["profile"], "ultra")
        self.assertEqual(fields["mode"], "character")
        self.assertEqual(len(files), 3)
        self.assertEqual(files[0][1], "front.png")
        self.assertEqual(files[1][2], b"PNG-B")
        self.assertEqual(files[2][0], "face_images")
        self.assertEqual(files[2][1], "IMG_1234.jpg")
        self.assertEqual(files[2][2], b"FACE-C")


if __name__ == "__main__":
    unittest.main()
