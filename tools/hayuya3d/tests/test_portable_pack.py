from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

import numpy as np
import trimesh

from portable_pack import TIERS, build_portable_pack


class PortablePackTests(unittest.TestCase):
    def test_builds_all_runtime_tiers_from_exact_hero_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "hero.glb"

            mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
            rgba = np.tile(
                np.array([[90, 125, 170, 255]], dtype=np.uint8),
                (len(mesh.vertices), 1),
            )
            mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=rgba)
            source.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh)))
            source_bytes = source.read_bytes()

            result = build_portable_pack(
                source,
                root / "pack",
                mode="character",
                profile_name="ultra",
                material_samples=2500,
            )

            self.assertEqual(Path(result.hero_master).read_bytes(), source_bytes)
            self.assertEqual([x.tier for x in result.tiers], list(TIERS))
            self.assertTrue(Path(result.manifest).is_file())
            self.assertTrue(result.complete_lod_chain)
            self.assertTrue(result.lod_parity_ready)
            self.assertTrue(result.runtime_budget_ready)

            expected_max = {
                "flagship": 180000,
                "high": 100000,
                "balanced": 60000,
                "compatibility": 35000,
            }
            expected_texture = {
                "flagship": 4096,
                "high": 4096,
                "balanced": 2048,
                "compatibility": 2048,
            }

            for artifact in result.tiers:
                tier_dir = Path(artifact.directory)
                self.assertTrue((tier_dir / "tier_manifest.json").is_file())
                self.assertEqual(len(artifact.gameprep["lods"]), 4)
                self.assertTrue(
                    artifact.lod_parity["ready"],
                    artifact.lod_parity.get("errors"),
                )
                self.assertEqual(
                    artifact.lod_parity["lod_count"],
                    4,
                )
                self.assertTrue(
                    Path(artifact.lod_parity["report"]).is_file()
                )
                self.assertTrue(
                    artifact.runtime_budget["ready"],
                    artifact.runtime_budget.get("errors"),
                )
                self.assertEqual(
                    artifact.runtime_budget["lod_count"],
                    4,
                )
                self.assertTrue(
                    Path(artifact.runtime_budget["report"]).is_file()
                )
                self.assertLessEqual(
                    artifact.gameprep["target_lod0_faces"],
                    expected_max[artifact.tier],
                )
                self.assertEqual(
                    artifact.portability_plan["runtime_target"]["exceptional_texture_edge_px"],
                    expected_texture[artifact.tier],
                )
                for name in ("LOD0.glb", "LOD1.glb", "LOD2.glb", "LOD3.glb"):
                    p = tier_dir / name
                    self.assertTrue(p.is_file(), f"missing {p}")
                    self.assertEqual(p.read_bytes()[:4], b"glTF")

            manifest = json.loads(Path(result.manifest).read_text())
            self.assertEqual(manifest["asset_mode"], "character")
            self.assertEqual(len(manifest["tiers"]), 4)
            self.assertTrue(manifest["runtime_budget_ready"])


if __name__ == "__main__":
    unittest.main()
