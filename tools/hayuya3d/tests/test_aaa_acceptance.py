from __future__ import annotations

import unittest

from tools.hayuya3d.aaa_acceptance import evaluate_aaa_acceptance


def base_manifest():
    return {
        "status":"success",
        "mode":"character",
        "profile":"monster",
        "champion":{"backend":"composite_material_b"},
        "judge_v4":{
            "passed":True,
            "hard_fail_reasons":[],
            "method":"fixture-pass",
        },
        "judge_v5":{
            "passed":True,
            "status":"APPROVED",
            "hard_fail_reasons":[],
            "method":"fixture-v5-pass",
        },
        "visual_approval":{
            "production_approved":True,
            "state":"APPROVED",
            "authoritative_judge":"HAYUYA_JUDGE_V5",
            "fail_closed":True,
        },
        "gameprep":{"lods":[{"name":"LOD0"},{"name":"LOD1"},{"name":"LOD2"},{"name":"LOD3"}]},
        "portable_pack":{
            "complete_lod_chain":True,
            "lod_parity_ready":True,
            "runtime_budget_ready":True,
            "tiers":[{"name":"flagship"},{"name":"high"},{"name":"balanced"},{"name":"compatibility"}],
        },
        "composite_champion":{
            "composite_required":False,
            "deferred_transfers":[],
            "executable_now":[],
        },
        "composite_execution":{"ready":True},
    }


def base_qa():
    return {
        "mode":"character",
        "profile":"monster",
        "production_ready":True,
        "geometry":{
            "ready":True,
            "head_density_score":99.0,
            "head_texel_density_score":98.0,
            "head_texture_detail_score":90.0,
        },
        "structure":{
            "valid":True,
            "finite_vertices":True,
            "duplicate_faces":0,
            "degenerate_faces":0,
            "nonmanifold_edges":0,
            "winding_consistent":True,
        },
        "component_crossing":{
            "applicable":True,
            "ready":True,
            "tested_pairs":2,
            "crossing_triangle_pairs":0,
        },
        "self_intersection":{
            "applicable":True,
            "ready":True,
            "audited_component_count":1,
            "crossing_triangle_pairs":0,
        },
        "composite_attachment":{
            "applicable":True,
            "ready":True,
            "component_count":6,
            "accessory_candidates":5,
            "anchored_accessories":5,
            "floating_components":0,
            "oversized_floating_components":0,
        },
        "source_coverage":{"expected":2,"judged":2},
        "turntable_qa":{"ready":True},
        "material":{
            "ready":True,
            "texture_resolution_ready":True,
            "rebake_ready":True,
            "channels":["baseColor","roughness","normal","occlusion"],
            "base_color_min_edge":4096,
            "target_texture_size":4096,
        },
        "uv_tangent":{
            "applicable":True,
            "ready":True,
            "missing_uv_primitives":0,
            "degenerate_uv_triangles":0,
            "invalid_tangent_primitives":0,
        },
        "shading_basis":{
            "applicable":True,
            "ready":True,
            "missing_normals":0,
            "missing_required_tangents":0,
            "invalid_handedness":0,
            "nonorthogonal_tangents":0,
        },
        "collision_qa":{
            "applicable":True,
            "ready":True,
            "faces":64,
            "watertight":True,
            "positive_volume":True,
            "volume":1.25,
            "convexity_ratio":1.0,
            "bbox_coverage_ready":True,
        },
        "face_evidence":{
            "required":True,
            "ready":True,
            "quality_evidence_ready":True,
            "evaluated":2,
            "expected":2,
            "min_score":90.0,
        },
        "rig":{
            "rig_ready":True,
            "animation_ready":True,
            "skins":1,
            "joint_count":65,
            "animations":3,
        },
        "skin_weights":{
            "applicable":True,
            "ready":True,
            "weighted_vertices":12000,
            "zero_weight_vertices":0,
            "non_normalized_vertices":0,
            "invalid_joint_references":0,
        },
        "animation_qa":{
            "applicable":True,
            "ready":True,
            "channel_count":12,
            "total_keyframes":240,
        },
        "deformation_qa":{
            "applicable":True,
            "ready":True,
            "sampled_frames":24,
            "max_displacement_ratio":0.85,
            "max_edge_stretch_ratio":1.35,
            "catastrophic_frames":0,
        },
        "warnings":[],
    }


class AAAAcceptanceTests(unittest.TestCase):
    def test_complete_high_end_character_passes_internal_contract(self):
        report=evaluate_aaa_acceptance(base_manifest(),base_qa())
        self.assertTrue(report.ready,report.blockers)
        self.assertEqual(report.passed_required,report.total_required)

    def test_missing_visual_judge_v4_blocks_high_end_character(self):
        manifest=base_manifest()
        manifest.pop("judge_v4",None)
        report=evaluate_aaa_acceptance(manifest,base_qa())
        self.assertFalse(report.ready)
        self.assertTrue(
            any("Judge v4" in x for x in report.blockers),
            report.blockers,
        )

    def test_missing_visual_judge_v5_blocks_high_end_character(self):
        manifest=base_manifest()
        manifest.pop("judge_v5",None)
        manifest["visual_approval"]["production_approved"]=False
        report=evaluate_aaa_acceptance(manifest,base_qa())
        self.assertFalse(report.ready)
        self.assertTrue(
            any("Judge v5" in x for x in report.blockers),
            report.blockers,
        )

    def test_blocked_uncalibrated_v5_cannot_ship(self):
        manifest=base_manifest()
        manifest["judge_v5"]={
            "passed":False,
            "status":"BLOCKED_UNCALIBRATED",
            "hard_fail_reasons":[],
            "method":"fixture-v5-blocked",
        }
        manifest["visual_approval"]["production_approved"]=False
        report=evaluate_aaa_acceptance(manifest,base_qa())
        self.assertFalse(report.ready)
        self.assertTrue(
            any("Judge v5" in x for x in report.blockers),
            report.blockers,
        )

    def test_rejected_visual_judge_v4_blocks_high_end_character(self):
        manifest=base_manifest()
        manifest["judge_v4"]={
            "passed":False,
            "hard_fail_reasons":["face_anatomy"],
            "method":"fixture-reject",
        }
        report=evaluate_aaa_acceptance(manifest,base_qa())
        self.assertFalse(report.ready)
        self.assertTrue(
            any("Judge v4" in x for x in report.blockers),
            report.blockers,
        )

    def test_missing_face_texel_evidence_fails_closed(self):
        qa=base_qa()
        qa["geometry"]["head_texel_density_score"]=None
        qa["face_evidence"]["quality_evidence_ready"]=False
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("face-quality evidence" in x for x in report.blockers),
            report.blockers,
        )
        self.assertTrue(
            any("head_texel_density_score" in x for x in report.blockers),
            report.blockers,
        )

    def test_unresolved_better_regional_donor_blocks_aaa_claim(self):
        manifest=base_manifest()
        manifest["composite_champion"]["composite_required"]=True
        manifest["composite_champion"]["deferred_transfers"]=["face_identity"]
        report=evaluate_aaa_acceptance(manifest,base_qa())
        self.assertFalse(report.ready)
        self.assertTrue(
            any("Composite Champion" in x for x in report.blockers),
            report.blockers,
        )

    def test_non_composite_base_can_pass_when_no_region_is_better(self):
        manifest=base_manifest()
        manifest["champion"]={"backend":"trellis2"}
        manifest["composite_champion"]={
            "composite_required":False,
            "deferred_transfers":[],
        }
        manifest["composite_execution"]=None
        report=evaluate_aaa_acceptance(manifest,base_qa())
        self.assertTrue(report.ready,report.blockers)

    def test_major_surface_crossing_blocks_aaa(self):
        qa=base_qa()
        qa["component_crossing"]["ready"]=False
        qa["component_crossing"]["crossing_triangle_pairs"]=7
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any(
                "cross" in item.lower()
                or "interpenetrate" in item.lower()
                for item in report.blockers
            ),
            report.blockers,
        )

    def test_self_intersection_blocks_aaa(self):
        qa=base_qa()
        qa["self_intersection"]["ready"]=False
        qa["self_intersection"]["crossing_triangle_pairs"]=5
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any(
                "self-intersect" in item.lower()
                for item in report.blockers
            ),
            report.blockers,
        )

    def test_floating_composite_attachment_blocks_aaa(self):
        qa=base_qa()
        qa["composite_attachment"]["ready"]=False
        qa["composite_attachment"]["anchored_accessories"]=4
        qa["composite_attachment"]["floating_components"]=1
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any(
                "accessory" in item.lower()
                or "donor" in item.lower()
                for item in report.blockers
            ),
            report.blockers,
        )

    def test_invalid_runtime_collision_blocks_aaa(self):
        qa=base_qa()
        qa["collision_qa"]["ready"]=False
        qa["collision_qa"]["watertight"]=False
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any(
                "collision" in item.lower()
                for item in report.blockers
            ),
            report.blockers,
        )

    def test_runtime_lod_parity_failure_blocks_aaa(self):
        manifest=base_manifest()
        manifest["portable_pack"]["lod_parity_ready"]=False
        report=evaluate_aaa_acceptance(manifest,base_qa())
        self.assertFalse(report.ready)
        self.assertTrue(
            any("LOD" in x or "parity" in x.lower() for x in report.blockers),
            report.blockers,
        )

    def test_runtime_asset_budget_failure_blocks_aaa(self):
        manifest=base_manifest()
        manifest["portable_pack"]["runtime_budget_ready"]=False
        report=evaluate_aaa_acceptance(manifest,base_qa())
        self.assertFalse(report.ready)
        self.assertTrue(
            any(
                "budget" in item.lower()
                for item in report.blockers
            ),
            report.blockers,
        )

    def test_high_end_collapsed_uvs_block_aaa(self):
        qa=base_qa()
        qa["uv_tangent"]["ready"]=False
        qa["uv_tangent"]["degenerate_uv_triangles"]=12
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("UV" in item or "tangent" in item.lower() for item in report.blockers),
            report.blockers,
        )

    def test_high_end_invalid_shading_basis_blocks_aaa(self):
        qa=base_qa()
        qa["shading_basis"]["ready"]=False
        qa["shading_basis"]["missing_required_tangents"]=1
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any(
                "shading basis" in item.lower()
                or "normal/tangent" in item.lower()
                for item in report.blockers
            ),
            report.blockers,
        )

    def test_high_end_missing_normal_map_fails(self):
        qa=base_qa()
        qa["material"]["channels"]=["baseColor","roughness"]
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("PBR" in x for x in report.blockers),
            report.blockers,
        )

    def test_invalid_existing_morph_targets_fail(self):
        qa=base_qa()
        qa["rig"]["morph_target_count"]=4
        qa["rig"]["morph_mesh_count"]=1
        qa["rig"]["morph_primitive_count"]=1
        qa["rig"]["morph_ready"]=False
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any(
                "morph" in item.lower()
                or "blendshape" in item.lower()
                for item in report.blockers
            ),
            report.blockers,
        )

    def test_character_without_morph_targets_does_not_gain_fake_requirement(self):
        qa=base_qa()
        qa["rig"]["morph_target_count"]=0
        qa["rig"]["morph_ready"]=False
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertTrue(report.ready,report.blockers)

    def test_invalid_skin_weights_fail(self):
        qa=base_qa()
        qa["skin_weights"]["ready"]=False
        qa["skin_weights"]["non_normalized_vertices"]=12
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("skin weights" in x.lower() for x in report.blockers),
            report.blockers,
        )

    def test_invalid_animation_integrity_fails(self):
        qa=base_qa()
        qa["animation_qa"]["ready"]=False
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("integrity" in x.lower() for x in report.blockers),
            report.blockers,
        )

    def test_catastrophic_deformation_fails(self):
        qa=base_qa()
        qa["deformation_qa"]["ready"]=False
        qa["deformation_qa"]["catastrophic_frames"]=1
        qa["deformation_qa"]["max_displacement_ratio"]=30.0
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("deformation" in x.lower() for x in report.blockers),
            report.blockers,
        )

    def test_missing_explicit_critical_anatomy_reference_blocks_aaa(self):
        qa=base_qa()
        qa["critical_anatomy"]={
            "required":True,
            "ready":False,
            "expected":3,
            "evaluated":2,
            "missing":["/refs/teeth_detail.png"],
            "targets":[
                {"target":"eyes","ready":True},
                {"target":"hands","ready":True},
                {"target":"teeth","ready":False},
            ],
        }
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("critical anatomy" in x.lower() for x in report.blockers),
            report.blockers,
        )

    def test_major_surface_crossing_blocks_aaa(self):
        qa=base_qa()
        qa["component_crossing"]={
            "applicable":True,
            "ready":False,
            "large_component_count":2,
            "crossing_triangle_pairs":14,
        }
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("surface" in x.lower() for x in report.blockers),
            report.blockers,
        )

    def test_malformed_morph_payload_blocks_aaa_when_present(self):
        qa=base_qa()
        qa["rig"]["morph_target_count"]=3
        qa["rig"]["morph_mesh_count"]=1
        qa["rig"]["morph_primitive_count"]=1
        qa["rig"]["morph_ready"]=False
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("morph" in x.lower() or "blendshape" in x.lower() for x in report.blockers),
            report.blockers,
        )

    def test_final_semantic_anatomy_failure_blocks_high_end_aaa(self):
        manifest=base_manifest()
        manifest["semantic_anatomy"]={
            "required":True,
            "attempted":True,
            "ready":False,
            "critical_targets":["eyes","hands"],
            "rendered_views":["front.png","side.png","rear.png"],
            "aggregate":{
                "ready":False,
                "missing_parts":["right_hand"],
            },
            "error":"semantic_anatomy_incomplete:right_hand",
        }
        qa=base_qa()
        qa["critical_anatomy"]={
            "required":True,
            "ready":True,
            "expected":2,
            "evaluated":2,
            "missing":[],
            "targets":[
                {"target":"eyes","ready":True},
                {"target":"hands","ready":True},
            ],
        }
        report=evaluate_aaa_acceptance(manifest,qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("semantic" in item.lower() for item in report.blockers),
            report.blockers,
        )

    def test_character_without_animation_fails(self):
        qa=base_qa()
        qa["rig"]["animation_ready"]=False
        report=evaluate_aaa_acceptance(base_manifest(),qa)
        self.assertFalse(report.ready)
        self.assertTrue(
            any("animation" in x.lower() for x in report.blockers),
            report.blockers,
        )


if __name__=="__main__":
    unittest.main()
