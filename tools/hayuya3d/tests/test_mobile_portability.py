from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from mobile_portability import build_portability_plan, resolve_tier


class MobilePortabilityTests(unittest.TestCase):
    def test_profile_auto_tiers(self):
        self.assertEqual(resolve_tier("auto", "mobile"), "compatibility")
        self.assertEqual(resolve_tier("auto", "game"), "balanced")
        self.assertEqual(resolve_tier("auto", "monster"), "high")
        self.assertEqual(resolve_tier("auto", "ultra"), "flagship")

    def test_character_flagship_keeps_hero_separate(self):
        p = build_portability_plan(
            mode="character",
            tier="flagship",
            profile_name="ultra",
        )
        self.assertEqual(p["runtime_target"]["lod0_triangles"], [80000, 180000])
        self.assertEqual(p["runtime_target"]["default_texture_edge_px"], 2048)
        self.assertEqual(p["runtime_target"]["exceptional_texture_edge_px"], 4096)
        self.assertTrue(p["hero_master"]["preserve"])
        self.assertEqual(p["hero_master"]["source_texture_edge_px"], 8192)
        self.assertLess(
            p["runtime_target"]["lod3_triangles"][1],
            p["runtime_target"]["lod0_triangles"][1],
        )

    def test_architecture_balanced_budget(self):
        p = build_portability_plan(
            mode="architecture",
            tier="balanced",
            profile_name="game",
        )
        self.assertEqual(p["runtime_target"]["lod0_triangles"], [10000, 40000])
        self.assertTrue(p["portable_contract"]["mipmaps_required"])


if __name__ == "__main__":
    unittest.main()
