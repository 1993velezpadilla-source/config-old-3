from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from reference_pool import classify_reference, split_reference_roles

spec = importlib.util.spec_from_file_location("hayuya_main", HAYUYA_DIR / "hayuya.py")
hayuya = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = hayuya
spec.loader.exec_module(hayuya)


class HayuyaPlannerTests(unittest.TestCase):
    def test_profiles_have_monster_path(self):
        p = hayuya.PROFILES["monster"]
        self.assertGreaterEqual(p.faces, 200_000)
        self.assertGreaterEqual(p.hero_faces, 1_000_000)
        self.assertGreater(p.hero_faces, p.faces)
        self.assertGreaterEqual(p.texture_size, 4096)
        self.assertIn("trellis2", p.backends)
        self.assertIn("triposg", p.backends)
        self.assertIn("trellis", p.backends)

    def test_monster_plan_separates_hero_master_from_runtime_budget(self):
        refs = [Path("/tmp/zombie_front.png")]
        plan = hayuya.make_job_plan(
            refs,
            profile_name="monster",
            mode="character",
            seed=1993,
            selected_backends=["trellis2"],
            model_root=Path("/tmp/models"),
        )
        self.assertEqual(plan["targets"]["runtime_faces"], 250_000)
        self.assertEqual(plan["targets"]["hero_faces"], 1_500_000)
        self.assertTrue(plan["hero_master"]["enabled"])
        self.assertIn("before retopology", plan["hero_master"]["policy"])

    def test_multi_photo_plan_has_no_logical_limit(self):
        refs = [Path(f"/tmp/view-{i}.png") for i in range(9)]
        plan = hayuya.make_job_plan(
            refs,
            profile_name="monster",
            mode="character",
            seed=1993,
            selected_backends=["trellis2", "triposg", "trellis"],
            model_root=Path("/tmp/models"),
        )
        self.assertEqual(plan["input_count"], 9)
        self.assertIsNone(plan["reference_pool"]["logical_limit"])
        self.assertTrue(plan["multi_reference"]["enabled"])
        self.assertTrue(plan["multi_reference"]["all_geometry_sources_always_used_by_judge"])
        self.assertIn("reference-pool fusion", plan["viewforge"]["strategy"])

    def test_reference_groups_cover_every_source(self):
        refs = [Path(f"/tmp/view-{i}.png") for i in range(14)]
        groups = hayuya.make_reference_groups(refs, 6)
        self.assertGreater(len(groups), 1)
        self.assertTrue(all(group[0] == refs[0] for group in groups))
        covered = {p for group in groups for p in group}
        self.assertEqual(covered, set(refs))
        self.assertTrue(all(len(group) <= 6 for group in groups))

    def test_multiview_groups_prioritize_angle_diversity(self):
        refs = [
            Path("/tmp/zombie_front.png"),
            Path("/tmp/zombie_front_45_left.png"),
            Path("/tmp/zombie_back_45_left.png"),
            Path("/tmp/zombie_left_side.png"),
            Path("/tmp/zombie_back.png"),
            Path("/tmp/zombie_right_side.png"),
            Path("/tmp/zombie_front_45_right.png"),
            Path("/tmp/zombie_back_45_right.png"),
        ]
        groups = hayuya.make_reference_groups(refs, 4)
        self.assertEqual(groups[0][0], refs[0])
        self.assertEqual(
            {p.name for p in groups[0][1:]},
            {"zombie_right_side.png", "zombie_back.png", "zombie_left_side.png"},
        )

    def test_anchor_budget_zero_means_all_sources(self):
        refs = [Path(f"/tmp/view-{i}.png") for i in range(11)]
        self.assertEqual(hayuya.limit_anchor_refs(refs, 0), refs)
        limited = hayuya.limit_anchor_refs(refs, 4)
        self.assertEqual(len(limited), 4)
        self.assertEqual(limited[0], refs[0])
        self.assertEqual(limited[-1], refs[-1])

    def test_detail_references_are_preserved_but_not_geometry_judged(self):
        refs = [
            Path("/tmp/zombie_front.png"),
            Path("/tmp/zombie_back.png"),
            Path("/tmp/zombie_face_closeup.png"),
            Path("/tmp/zombie_hand_detail.png"),
        ]
        roles = split_reference_roles(refs)
        self.assertEqual(roles.geometry, refs[:2])
        self.assertEqual(roles.detail, refs[2:])

        plan = hayuya.make_job_plan(
            refs,
            profile_name="monster",
            mode="character",
            seed=1993,
            selected_backends=["trellis", "triposg"],
            model_root=Path("/tmp/models"),
        )
        self.assertEqual(plan["reference_pool"]["geometry_source_count"], 2)
        self.assertEqual(plan["reference_pool"]["detail_source_count"], 2)
        self.assertEqual(plan["multi_reference"]["group_count"], 1)

    def test_unnamed_large_face_is_reclassified_as_real_head_detail(self):
        full=Path("/tmp/IMG_0001.png").resolve()
        close=Path("/tmp/IMG_1234.png").resolve()
        report=SimpleNamespace(
            sources=[
                SimpleNamespace(
                    source=str(full),
                    direct_face_detected=True,
                    semantic_face_or_head_confirmed=True,
                    face_box_fraction=0.012,
                    face_detail="/tmp/source_autofix/details/000-face_detail-auto.png",
                ),
                SimpleNamespace(
                    source=str(close),
                    direct_face_detected=True,
                    semantic_face_or_head_confirmed=True,
                    face_box_fraction=0.24,
                    face_detail="/tmp/source_autofix/details/001-face_detail-auto.png",
                ),
            ]
        )

        geometry,details,semantic=hayuya.reclassify_semantic_face_closeups(
            [full,close],
            [],
            report,
        )

        self.assertEqual(geometry,[full])
        self.assertEqual(details,[close])
        self.assertEqual(semantic,[close])
        self.assertEqual(
            hayuya.face_seed_hypothesis_count(
                "monster",
                details,
                semantic_head_inputs=semantic,
            ),
            2,
        )
        self.assertTrue(
            hayuya.is_head_detail_evidence(
                close,
                semantic_head_inputs=semantic,
            )
        )

    def test_semantic_closeup_reclassification_never_removes_all_geometry(self):
        a=Path("/tmp/IMG_A.png").resolve()
        b=Path("/tmp/IMG_B.png").resolve()
        report=SimpleNamespace(
            sources=[
                SimpleNamespace(
                    source=str(a),
                    direct_face_detected=True,
                    semantic_face_or_head_confirmed=True,
                    face_box_fraction=0.31,
                ),
                SimpleNamespace(
                    source=str(b),
                    direct_face_detected=True,
                    semantic_face_or_head_confirmed=True,
                    face_box_fraction=0.29,
                ),
            ]
        )
        geometry,details,semantic=hayuya.reclassify_semantic_face_closeups(
            [a,b],
            [],
            report,
        )
        self.assertEqual(len(geometry),1)
        self.assertEqual(len(details),1)
        self.assertEqual(len(semantic),1)
        self.assertNotEqual(geometry[0],details[0])

    def test_reclassified_detail_face_cannot_force_character_mode_by_itself(self):
        prop=Path("/tmp/altar_front.png").resolve()
        close=Path("/tmp/IMG_face.png").resolve()
        report=SimpleNamespace(
            character_hint=True,
            sources=[
                SimpleNamespace(
                    source=str(prop),
                    semantic_face_or_head_confirmed=False,
                ),
                SimpleNamespace(
                    source=str(close),
                    semantic_face_or_head_confirmed=True,
                ),
            ],
        )
        self.assertFalse(
            hayuya.semantic_character_hint_for_geometry(
                report,
                [prop],
            )
        )
        self.assertTrue(
            hayuya.semantic_character_hint_for_geometry(
                report,
                [prop,close],
            )
        )

    def test_job_plan_accepts_content_routed_reference_roles(self):
        full=Path("/tmp/IMG_full.png")
        close=Path("/tmp/IMG_close.png")
        plan=hayuya.make_job_plan(
            [full,close],
            profile_name="monster",
            mode="character",
            seed=1993,
            selected_backends=["triposg"],
            model_root=Path("/tmp/models"),
            geometry_inputs_override=[full],
            real_detail_inputs_override=[close],
            semantic_head_detail_inputs=[close],
        )
        pool=plan["reference_pool"]
        self.assertEqual(pool["geometry_sources"],[str(full)])
        self.assertEqual(pool["real_detail_sources"],[str(close)])
        self.assertEqual(
            pool["semantic_head_detail_sources"],
            [str(close)],
        )
        self.assertTrue(plan["face_seed_tournament"]["enabled"])

    def test_face_seed_tournament_is_bounded_and_face_conditioned(self):
        face = Path("/tmp/refs/details/face_detail.png")
        hand = Path("/tmp/refs/details/hand_detail.png")
        self.assertEqual(hayuya.face_seed_hypothesis_count("monster", [face]), 2)
        self.assertEqual(hayuya.face_seed_hypothesis_count("ultra", [face]), 3)
        self.assertEqual(hayuya.face_seed_hypothesis_count("game", [face]), 1)
        self.assertEqual(hayuya.face_seed_hypothesis_count("monster", [hand]), 1)
        self.assertEqual(hayuya.face_seed_hypothesis_count("monster", []), 1)

        refs = [Path("/tmp/zombie_front.png"), face]
        plan = hayuya.make_job_plan(
            refs,
            profile_name="monster",
            mode="character",
            seed=1993,
            selected_backends=["trellis2"],
            model_root=Path("/tmp/models"),
        )
        self.assertTrue(plan["face_seed_tournament"]["enabled"])
        self.assertEqual(plan["face_seed_tournament"]["trellis2_seed_count"], 2)

    def test_reference_role_inference_is_conservative(self):
        self.assertEqual(classify_reference(Path("zombie_front.png")), "geometry")
        self.assertEqual(classify_reference(Path("zombie_face_closeup.png")), "detail")
        self.assertEqual(classify_reference(Path("zombie_texture_detail.png")), "detail")
        self.assertEqual(classify_reference(Path("refs/details/01.png")), "detail")
        self.assertEqual(classify_reference(Path("refs/textures/albedo.png")), "detail")
        self.assertEqual(classify_reference(Path("refs/individual/zombie_back.png")), "geometry")
        self.assertEqual(classify_reference(Path("unknown_phone_photo.png")), "geometry")

    def test_default_stack_is_permissive(self):
        lock = hayuya.load_lock()
        for item in lock["backends"]:
            if item["enabled_by_default"]:
                self.assertIn(item["license"], {"MIT", "Apache-2.0"})

    def test_vram_budget_filters_expensive_models(self):
        lock = hayuya.load_lock()
        selected = hayuya.choose_backends(
            lock,
            hayuya.PROFILES["monster"],
            None,
            gpu_vram=8,
            allow_restricted=False,
        )
        self.assertIn("triposg", selected)
        self.assertIn("triposr", selected)
        self.assertNotIn("trellis2", selected)
        self.assertNotIn("trellis", selected)
        self.assertNotIn("instantmesh", selected)

    def test_asset_mode_detects_llorona_character_path(self):
        self.assertEqual(
            hayuya.infer_asset_mode(
                Path("/tmp/assets/characters/llorona/v2/hayuya/individual/llorona_front.png")
            ),
            "character",
        )
        self.assertEqual(
            hayuya.infer_asset_mode(Path("/tmp/assets/architecture/church/front.png")),
            "architecture",
        )
        self.assertEqual(
            hayuya.infer_asset_mode(Path("/tmp/assets/props/chair/front.png")),
            "prop",
        )

    def test_pshuman_is_not_permissive_default(self):
        lock = hayuya.load_lock()
        meta = hayuya.backend_meta(lock)
        self.assertFalse(meta["pshuman"]["enabled_by_default"])
        self.assertNotIn(meta["pshuman"]["license"], {"MIT", "Apache-2.0"})

    def test_instant_meshes_retopo_is_optional_permissive_cpu_tool(self):
        lock = hayuya.load_lock()
        meta = hayuya.backend_meta(lock)
        tool = meta["instant_meshes_retopo"]
        self.assertFalse(tool["enabled_by_default"])
        self.assertEqual(tool["license"], "BSD-3-Clause")
        self.assertEqual(tool["min_vram_gb"], 0)
        self.assertTrue(tool["submodules"])

    def test_job_plan_records_retopology_as_challenger(self):
        refs = [Path("/tmp/zombie_front.png")]
        plan = hayuya.make_job_plan(
            refs,
            profile_name="monster",
            mode="character",
            seed=1993,
            selected_backends=["triposg"],
            model_root=Path("/tmp/models"),
            retopo_mode="auto",
        )
        self.assertEqual(plan["retopology"]["mode"], "auto")
        self.assertIn("Judge", plan["retopology"]["policy"])
        self.assertIn("skip", plan["retopology"]["rig_policy"])

    def test_native_conform_blocks_nonstatic_gltf_features(self):
        static = SimpleNamespace(
            valid_glb=True,
            errors=[],
            skin_count=0,
            animation_count=0,
            morph_target_count=0,
        )
        self.assertEqual(hayuya.native_conform_mutation_blockers(static), [])

        animated = SimpleNamespace(
            valid_glb=True,
            errors=[],
            skin_count=1,
            animation_count=4,
            morph_target_count=7,
        )
        blockers = hayuya.native_conform_mutation_blockers(animated)
        self.assertIn("skins=1", blockers)
        self.assertIn("animations=4", blockers)
        self.assertIn("morph_targets=7", blockers)

        invalid = SimpleNamespace(
            valid_glb=False,
            errors=["bad accessor"],
            skin_count=0,
            animation_count=0,
            morph_target_count=0,
        )
        blockers = hayuya.native_conform_mutation_blockers(invalid)
        self.assertIn("invalid_glb", blockers)
        self.assertIn("gltf_audit_errors=1", blockers)


    def test_job_plan_native_conform_is_generic_native_challenger(self):
        refs = [Path("/tmp/another_character_front.png")]
        plan = hayuya.make_job_plan(
            refs,
            profile_name="monster",
            mode="character",
            seed=1993,
            selected_backends=["triposg"],
            model_root=Path("/tmp/models"),
            native_silhouette_conform_mode="auto",
        )
        policy = plan["native_silhouette_conform"]
        self.assertEqual(policy["mode"], "auto")
        self.assertFalse(policy["asset_specific_coordinates"])
        self.assertIn("native", policy["input_geometry"])
        self.assertIn("challenger", policy["promotion_policy"])
        self.assertNotIn("monja", json.dumps(policy).lower())
        self.assertNotIn("source_visible_front", policy["input_geometry"])

    def test_job_plan_native_face_repair_is_current_source_generic(self):
        refs = [
            Path("/tmp/another_character_front.png"),
            Path("/tmp/details/another_character_face_detail.png"),
        ]
        plan = hayuya.make_job_plan(
            refs,
            profile_name="monster",
            mode="character",
            seed=1993,
            selected_backends=["trellis2", "triposg"],
            model_root=Path("/tmp/models"),
            native_face_repair_mode="auto",
        )
        policy = plan["native_face_repair"]
        self.assertEqual(policy["mode"], "auto")
        self.assertFalse(policy["asset_specific_coordinates"])
        self.assertFalse(policy["projection_proxy_created"])
        self.assertIn("current source", policy["source_target"])
        self.assertIn("native 3D head donor", policy["donor_policy"])
        self.assertIn("challenger", policy["promotion_policy"])
        self.assertNotIn("monja", json.dumps(policy).lower())
        self.assertNotIn("source_visible_front", json.dumps(policy).lower())

    def test_native_face_repair_plan_is_character_only_for_props(self):
        plan = hayuya.make_job_plan(
            [Path("/tmp/props/church_altar/front.png")],
            profile_name="game",
            mode="prop",
            seed=1993,
            selected_backends=["triposg"],
            model_root=Path("/tmp/models"),
            native_face_repair_mode="auto",
        )
        policy = plan["native_face_repair"]
        self.assertEqual(policy["asset_scope"], "character-only")
        self.assertIn("props", policy["activation"])
        self.assertIn("architecture", policy["activation"])

    def test_hunyuan_is_not_default(self):
        lock = hayuya.load_lock()
        meta = hayuya.backend_meta(lock)
        self.assertFalse(meta["hunyuan3d_2_1"]["enabled_by_default"])

    def test_universal_asset_profile_inference(self):
        self.assertEqual(hayuya.infer_asset_profile(Path("/tmp/weapons/pump_shotgun/front.png")), "weapon.firearm")
        self.assertEqual(hayuya.infer_asset_profile(Path("/tmp/foliage/grass/front.png")), "foliage.grass")
        self.assertEqual(hayuya.infer_asset_profile(Path("/tmp/vehicles/truck/front.png")), "vehicle")
        self.assertEqual(hayuya.infer_asset_profile(Path("/tmp/zombies/candy/front.png")), "character.humanoid")

    def test_weapon_plan_uses_mechanical_pipeline(self):
        refs=[Path("/tmp/weapons/pump_shotgun_front.png")]
        plan=hayuya.make_job_plan(
            refs,
            profile_name="game",
            mode="prop",
            seed=1993,
            selected_backends=["triposg"],
            model_root=Path("/tmp/models"),
            asset_profile="weapon.firearm",
            animation_requested=True,
        )
        self.assertEqual(plan["asset_profile"], "weapon.firearm")
        self.assertIn("mechanical_skeleton", plan["asset_pipeline"]["animation_systems"])
        self.assertIn("weapon_compatibility_gate", plan["asset_pipeline"]["preferred_pipeline"])

    def test_grass_plan_uses_vertex_wind_not_humanoid_rig(self):
        refs=[Path("/tmp/foliage/grass_front.png")]
        plan=hayuya.make_job_plan(
            refs,
            profile_name="game",
            mode="prop",
            seed=1993,
            selected_backends=["triposg"],
            model_root=Path("/tmp/models"),
            asset_profile="foliage.grass",
            animation_requested=True,
        )
        self.assertIn("vertex_wind", plan["asset_pipeline"]["animation_systems"])
        self.assertNotIn("humanoid_autorig", plan["asset_pipeline"]["preferred_pipeline"])


if __name__ == "__main__":
    unittest.main()
