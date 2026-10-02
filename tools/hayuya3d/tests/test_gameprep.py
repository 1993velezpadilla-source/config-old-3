from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

import numpy as np
import trimesh

from gameprep import build_gameprep
from visual_judge import SourceViewScore


class GamePrepTests(unittest.TestCase):
    def test_builds_lods_collision_and_turntable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master = root / "input.glb"

            mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
            rgba = np.tile(
                np.array([[35, 170, 220, 255]], dtype=np.uint8),
                (len(mesh.vertices), 1),
            )
            mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=rgba)
            master.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
            )

            anchor = SourceViewScore(
                source="test",
                best_score=100.0,
                best_azimuth=30.0,
                best_elevation=0.0,
                best_up_axis="y",
                silhouette_iou=1.0,
                boundary_f1=1.0,
            )

            result = build_gameprep(
                master,
                root / "gameprep",
                target_faces=400,
                anchor_view=anchor,
                material_samples=3000,
            )

            self.assertEqual(len(result.lods), 4)
            self.assertEqual(result.rig_audit["skin_count"], 0)
            self.assertFalse(result.rig_audit["rig_ready"])
            self.assertIn("unrigged source", result.lod_policy)
            self.assertTrue(Path(result.rig_audit_path).is_file())
            self.assertEqual(len(result.turntable_frames), 24)
            self.assertTrue(Path(result.master).is_file())
            self.assertTrue(result.collision and Path(result.collision).is_file())
            self.assertTrue(Path(result.manifest).is_file())

            faces = [lod.actual_faces for lod in result.lods]
            self.assertTrue(all(a >= b for a, b in zip(faces, faces[1:])))
            self.assertLessEqual(faces[0], result.source_faces)

            for lod in result.lods:
                path = Path(lod.path)
                self.assertTrue(path.is_file())
                self.assertEqual(path.read_bytes()[:4], b"glTF")
                self.assertIsInstance(lod.dropped_channels, list)
                self.assertIsInstance(lod.rebake_required, list)
                self.assertIsInstance(lod.rebaked_channels, list)
                self.assertIn(lod.rebake_method, (None, "blender_unavailable", "nothing_supported_requested"))

            for frame in result.turntable_frames:
                self.assertTrue(Path(frame).is_file())


if __name__ == "__main__":
    unittest.main()
