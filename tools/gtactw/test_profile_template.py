#!/usr/bin/env python3
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile_template


class ProfileTemplateTests(unittest.TestCase):
    def make_report(self):
        p = "Java_com_rockstargames_oswrapper_GameNative_"
        return {
            "file_size": 123456,
            "sha256": "a" * 64,
            "elf": {
                "machine": "AArch64",
                "build_id": "0123456789abcdef",
            },
            "text": {"sha256": "b" * 64},
            "symbols": {
                "known_jni_details": {
                    p + "implOnDrawFrame": {
                        "present": True,
                        "value": 0x1000,
                        "size": 16,
                    },
                    p + "implOnInitialSetup": {
                        "present": True,
                        "value": 0x2000,
                        "size": 16,
                    },
                    p + "implOnGamepadAxesChanged": {
                        "present": True,
                        "value": 0x3000,
                        "size": 16,
                    },
                },
                "known_4243_engine_symbols": {
                    "_Z17OS_ScreenGetWidthv": {
                        "present": True,
                        "value": 0x3500,
                        "size": 12,
                    },
                    "_Z18OS_ScreenGetHeightv": {
                        "present": False,
                        "value": None,
                        "size": None,
                    },
                },
                "candidate_groups": {
                    "camera": [
                        {
                            "source": "symbol",
                            "name": "CameraUpdate",
                            "value": 0x4000,
                            "size": 64,
                        }
                    ],
                    "streaming": [],
                    "lod_culling": [],
                    "player_render": [],
                },
            },
        }

    def test_profile_uses_jni_rvas_and_empty_patch_targets(self):
        profile = profile_template.make_profile(self.make_report())
        self.assertEqual(
            profile["fingerprint"]["jni_rvas"]["implOnDrawFrame"],
            0x1000,
        )
        self.assertEqual(
            profile["candidate_symbols"]["camera"][0]["name"],
            "CameraUpdate",
        )
        self.assertTrue(
            all(v is None for v in profile["patch_targets_rva"].values())
        )
        self.assertEqual(
            profile["status"],
            "template_needs_verified_internal_rvas",
        )
        self.assertEqual(
            profile["public_4243_engine_anchors"]["present_count"],
            1,
        )
        self.assertEqual(
            profile["public_4243_engine_anchors"]["total_count"],
            2,
        )
        self.assertEqual(
            profile["public_4243_engine_anchors"]["present"][0]["rva"],
            0x3500,
        )
        self.assertEqual(
            set(profile["abi_verification"]),
            set(profile_template.TARGET_KEYS),
        )
        self.assertTrue(
            all(
                item["status"] == "pending"
                for item in profile["abi_verification"].values()
            )
        )

    def test_profile_ranks_xref_evidence_without_filling_targets(self):
        xrefs = {
            "groups": {
                "camera": [
                    {
                        "function": "CameraUpdate",
                        "function_rva": 0x4000,
                        "pc_rva": 0x4010,
                        "string": "CameraFarClipDistance",
                    },
                    {
                        "function": "CameraUpdate",
                        "function_rva": 0x4000,
                        "pc_rva": 0x4020,
                        "string": "CameraFov",
                    },
                ],
                "streaming": [],
                "lod_culling": [],
                "player_render": [],
            }
        }
        profile = profile_template.make_profile(self.make_report(), xrefs)
        ranked = profile["candidate_xref_functions"]["camera"]
        self.assertEqual(ranked[0]["function"], "CameraUpdate")
        self.assertEqual(ranked[0]["rva"], 0x4000)
        self.assertEqual(ranked[0]["hits"], 2)
        self.assertEqual(
            ranked[0]["call_sites"],
            [0x4010, 0x4020],
        )
        self.assertTrue(
            all(v is None for v in profile["patch_targets_rva"].values())
        )


    def test_target_evidence_separates_camera_and_projection(self):
        report = self.make_report()
        report["symbols"]["candidate_groups"]["camera"] = [
            {
                "source": "symbol",
                "name": "CameraUpdate",
                "value": 0x4000,
                "size": 64,
            },
            {
                "source": "symbol",
                "name": "ProjectionSetup",
                "value": 0x5000,
                "size": 64,
            },
        ]
        xrefs = {
            "groups": {
                "camera": [
                    {
                        "function": "CameraUpdate",
                        "function_rva": 0x4000,
                        "pc_rva": 0x4010,
                        "string": "CameraViewLook",
                    },
                    {
                        "function": "ProjectionSetup",
                        "function_rva": 0x5000,
                        "pc_rva": 0x5010,
                        "string": "CameraFarClipDistance",
                    },
                    {
                        "function": "ProjectionSetup",
                        "function_rva": 0x5000,
                        "pc_rva": 0x5020,
                        "string": "CameraFov",
                    },
                ],
                "streaming": [],
                "lod_culling": [],
                "player_render": [],
            },
            "candidate_function_fingerprints": {
                "0x4000": {
                    "function": "CameraUpdate",
                    "rva": 0x4000,
                    "size": 64,
                    "sha256": "c" * 64,
                    "prefix_hex": "aa" * 16,
                },
                "0x5000": {
                    "function": "ProjectionSetup",
                    "rva": 0x5000,
                    "size": 64,
                    "sha256": "d" * 64,
                    "prefix_hex": "bb" * 16,
                },
            },
            "candidate_call_neighborhoods": {
                "0x4000": {
                    "incoming": [{"caller": "FrameUpdate", "caller_rva": 0x3500}],
                    "outgoing": [],
                },
                "0x5000": {
                    "incoming": [{"caller": "CameraUpdate", "caller_rva": 0x4000}],
                    "outgoing": [],
                },
            },
        }

        profile = profile_template.make_profile(report, xrefs)
        camera = profile["target_evidence_rankings"]["camera_update"]
        projection = profile["target_evidence_rankings"]["projection_setup"]

        self.assertEqual(camera[0]["rva"], 0x4000)
        self.assertEqual(projection[0]["rva"], 0x5000)
        self.assertTrue(
            all(v is None for v in profile["patch_targets_rva"].values())
        )
        self.assertIn(
            "symbol + xref cross-signal",
            projection[0]["reasons"],
        )
        self.assertEqual(
            camera[0]["function_fingerprint"]["sha256"],
            "c" * 64,
        )
        self.assertEqual(
            projection[0]["call_neighborhood"]["incoming"][0]["caller"],
            "CameraUpdate",
        )


    def test_projection_ranking_uses_gl_matrix_plt_call(self):
        report = self.make_report()
        xrefs = {
            "groups": {
                "camera": [],
                "streaming": [],
                "lod_culling": [],
                "player_render": [],
            }
        }
        plt = {
            "groups": {
                "projection": [
                    {
                        "caller": "UploadProjection",
                        "caller_rva": 0x5500,
                        "call_site_rva": 0x5510,
                        "import_symbol": "glUniformMatrix4fv",
                        "draw_frame_reachable": True,
                        "draw_frame_hops": 1,
                        "draw_frame_path_rvas": [0x1000, 0x5500],
                        "draw_frame_path_functions": [
                            profile_template.DRAW,
                            "UploadProjection",
                        ],
                    }
                ],
                "render": [],
                "visibility": [],
            }
        }
        profile = profile_template.make_profile(report, xrefs, plt)
        ranked = profile["target_evidence_rankings"]["projection_setup"]
        self.assertEqual(ranked[0]["rva"], 0x5500)
        self.assertIn("glUniformMatrix4fv", ranked[0]["plt_imports"])
        self.assertIn(
            "calls glUniformMatrix4fv through verified PLT mapping",
            ranked[0]["reasons"],
        )
        self.assertEqual(ranked[0]["draw_frame_hops"], 1)
        self.assertIn(
            "reachable from implOnDrawFrame in 1 symbol hop(s)",
            ranked[0]["reasons"],
        )
        self.assertIsNone(profile["patch_targets_rva"]["projection_setup"])


    def test_projection_prefers_drawframe_reachable_matrix_uploader(self):
        report = self.make_report()
        xrefs = {
            "groups": {
                "camera": [],
                "streaming": [],
                "lod_culling": [],
                "player_render": [],
            }
        }
        plt = {
            "groups": {
                "projection": [
                    {
                        "caller": "InitMatrices",
                        "caller_rva": 0x6100,
                        "call_site_rva": 0x6110,
                        "import_symbol": "glUniformMatrix4fv",
                        "draw_frame_reachable": False,
                        "draw_frame_hops": None,
                    },
                    {
                        "caller": "FrameProjection",
                        "caller_rva": 0x6200,
                        "call_site_rva": 0x6210,
                        "import_symbol": "glUniformMatrix4fv",
                        "draw_frame_reachable": True,
                        "draw_frame_hops": 1,
                        "draw_frame_path_rvas": [0x1000, 0x6200],
                        "draw_frame_path_functions": [
                            profile_template.DRAW,
                            "FrameProjection",
                        ],
                    },
                ],
                "render": [],
                "visibility": [],
            }
        }

        profile = profile_template.make_profile(report, xrefs, plt)
        ranked = profile["target_evidence_rankings"]["projection_setup"]
        self.assertEqual(ranked[0]["rva"], 0x6200)
        self.assertEqual(ranked[0]["draw_frame_hops"], 1)
        self.assertEqual(ranked[1]["rva"], 0x6100)


    def test_visibility_and_player_gl_calls_are_cross_signals_only(self):
        report = self.make_report()
        xrefs = {
            "groups": {
                "camera": [],
                "streaming": [
                    {
                        "function": "SectorCull",
                        "function_rva": 0x7000,
                        "pc_rva": 0x7010,
                        "string": "SectorVisibility",
                    }
                ],
                "lod_culling": [
                    {
                        "function": "SectorCull",
                        "function_rva": 0x7000,
                        "pc_rva": 0x7014,
                        "string": "FrustumCull",
                    }
                ],
                "player_render": [
                    {
                        "function": "PlayerRender",
                        "function_rva": 0x8000,
                        "pc_rva": 0x8010,
                        "string": "PlayerSkeletonRender",
                    }
                ],
            }
        }
        plt = {
            "groups": {
                "projection": [],
                "visibility": [
                    {
                        "caller": "SectorCull",
                        "caller_rva": 0x7000,
                        "call_site_rva": 0x7020,
                        "import_symbol": "glScissor",
                        "draw_frame_hops": 2,
                        "draw_frame_path_rvas": [0x1000, 0x6800, 0x7000],
                        "draw_frame_path_functions": [
                            profile_template.DRAW,
                            "WorldRender",
                            "SectorCull",
                        ],
                    },
                    {
                        "caller": "UnrelatedScissor",
                        "caller_rva": 0x9000,
                        "call_site_rva": 0x9010,
                        "import_symbol": "glScissor",
                        "draw_frame_hops": 1,
                    },
                ],
                "render": [
                    {
                        "caller": "PlayerRender",
                        "caller_rva": 0x8000,
                        "call_site_rva": 0x8020,
                        "import_symbol": "glDrawElements",
                        "draw_frame_hops": 2,
                        "draw_frame_path_rvas": [0x1000, 0x7800, 0x8000],
                        "draw_frame_path_functions": [
                            profile_template.DRAW,
                            "WorldRender",
                            "PlayerRender",
                        ],
                    },
                    {
                        "caller": "UnrelatedDraw",
                        "caller_rva": 0xA000,
                        "call_site_rva": 0xA010,
                        "import_symbol": "glDrawElements",
                        "draw_frame_hops": 1,
                    },
                ],
            }
        }

        profile = profile_template.make_profile(report, xrefs, plt)
        visibility = profile["target_evidence_rankings"]["sector_visibility"]
        player = profile["target_evidence_rankings"]["player_render"]

        self.assertEqual(visibility[0]["rva"], 0x7000)
        self.assertIn("glScissor", visibility[0]["plt_imports"])
        self.assertIn(
            "visibility candidate also calls glScissor",
            visibility[0]["reasons"],
        )
        self.assertNotIn(0x9000, [x["rva"] for x in visibility])

        self.assertEqual(player[0]["rva"], 0x8000)
        self.assertIn("glDrawElements", player[0]["plt_imports"])
        self.assertIn(
            "player-render candidate also calls glDrawElements",
            player[0]["reasons"],
        )
        self.assertNotIn(0xA000, [x["rva"] for x in player])


    def test_projection_scores_depthrange_and_viewport_as_secondary_evidence(self):
        report = self.make_report()
        xrefs = {
            "groups": {
                "camera": [],
                "streaming": [],
                "lod_culling": [],
                "player_render": [],
            }
        }
        plt = {
            "groups": {
                "projection": [
                    {
                        "caller": "ProjectionState",
                        "caller_rva": 0x6600,
                        "call_site_rva": 0x6610,
                        "import_symbol": "glDepthRangef",
                        "draw_frame_reachable": True,
                        "draw_frame_hops": 2,
                        "draw_frame_path_rvas": [0x1000, 0x6500, 0x6600],
                        "draw_frame_path_functions": [
                            profile_template.DRAW,
                            "WorldRender",
                            "ProjectionState",
                        ],
                    },
                    {
                        "caller": "ProjectionState",
                        "caller_rva": 0x6600,
                        "call_site_rva": 0x6614,
                        "import_symbol": "glViewport",
                        "draw_frame_reachable": True,
                        "draw_frame_hops": 2,
                        "draw_frame_path_rvas": [0x1000, 0x6500, 0x6600],
                        "draw_frame_path_functions": [
                            profile_template.DRAW,
                            "WorldRender",
                            "ProjectionState",
                        ],
                    },
                ],
                "render": [],
                "visibility": [],
            }
        }

        profile = profile_template.make_profile(report, xrefs, plt)
        ranked = profile["target_evidence_rankings"]["projection_setup"]
        self.assertEqual(ranked[0]["rva"], 0x6600)
        self.assertIn("glDepthRangef", ranked[0]["plt_imports"])
        self.assertIn("glViewport", ranked[0]["plt_imports"])
        self.assertIn(
            "calls glDepthRangef through PLT mapping",
            ranked[0]["reasons"],
        )
        self.assertIn(
            "calls glViewport through PLT mapping",
            ranked[0]["reasons"],
        )

    def test_rejects_missing_required_jni(self):
        report = self.make_report()
        p = "Java_com_rockstargames_oswrapper_GameNative_"
        report["symbols"]["known_jni_details"][
            p + "implOnDrawFrame"
        ]["present"] = False
        with self.assertRaises(ValueError):
            profile_template.make_profile(report)


if __name__ == "__main__":
    unittest.main()
