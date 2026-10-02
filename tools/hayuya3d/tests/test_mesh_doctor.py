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

from mesh_doctor import audit_mesh, repair_candidate


def write_colored_glb(path: Path, mesh, color=(20, 180, 70, 255)) -> None:
    rgba = np.tile(
        np.asarray([color], dtype=np.uint8),
        (len(mesh.vertices), 1),
    )
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=rgba)
    path.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh)))


class MeshDoctorTests(unittest.TestCase):
    def test_audit_detects_duplicate_degenerate_and_unreferenced_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.glb"
            vertices = np.array([
                [-0.5, -0.5, 0.0],
                [ 0.5, -0.5, 0.0],
                [ 0.5,  0.5, 0.0],
                [-0.5,  0.5, 0.0],
                [ 9.0,  9.0, 9.0],  # deliberately unreferenced
            ], dtype=np.float64)
            faces = np.array([
                [0, 1, 2],
                [0, 2, 3],
                [0, 1, 2],  # duplicate
                [0, 0, 1],  # degenerate
            ], dtype=np.int64)
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            write_colored_glb(path, mesh)

            audit = audit_mesh(path)
            self.assertTrue(audit.valid)
            self.assertGreaterEqual(audit.duplicate_faces, 1)
            self.assertGreaterEqual(audit.degenerate_faces, 1)
            # GLB serialization may legally discard unreferenced vertices before
            # the file reaches Mesh Doctor, so the persistent defects we require
            # here are duplicate/degenerate topology.
            self.assertTrue(audit.repair_recommended)
            self.assertGreater(audit.defect_score, 0.0)

    def test_safe_repair_improves_structure_and_preserves_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "broken.glb"
            vertices = np.array([
                [-0.5, -0.5, 0.0],
                [ 0.5, -0.5, 0.0],
                [ 0.5,  0.5, 0.0],
                [-0.5,  0.5, 0.0],
                [ 9.0,  9.0, 9.0],
            ], dtype=np.float64)
            faces = np.array([
                [0, 1, 2],
                [0, 2, 3],
                [0, 1, 2],
                [0, 0, 1],
            ], dtype=np.int64)
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            write_colored_glb(source, mesh, color=(30, 160, 220, 255))

            result = repair_candidate(
                source,
                root / "doctor",
                mode="character",
                texture_size=256,
            )
            self.assertTrue(result.safe_for_arena, result.reasons)
            self.assertLess(result.after.defect_score, result.before.defect_score)
            self.assertEqual(result.after.duplicate_faces, 0)
            self.assertEqual(result.after.degenerate_faces, 0)
            self.assertEqual(result.after.unreferenced_vertices, 0)
            self.assertLessEqual(result.max_extent_relative_drift, 0.001)
            self.assertLessEqual(result.centroid_drift_normalized, 0.001)
            self.assertLessEqual(result.vertex_surface_drift_normalized, 0.001)
            self.assertTrue(Path(result.manifest).is_file())

            scene = trimesh.load(result.bridged_glb, force="scene", process=False)
            repaired = trimesh.util.concatenate(list(scene.geometry.values()))
            colors = np.asarray(repaired.visual.vertex_colors[:, :3], dtype=float)
            mean = colors.mean(axis=0)
            self.assertTrue(np.allclose(mean, [30, 160, 220], atol=3.0), mean)

    def test_prop_repair_can_close_small_triangle_hole(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "hole.glb"
            box = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
            box.update_faces(np.arange(len(box.faces)) != 0)
            box.remove_unreferenced_vertices()
            write_colored_glb(source, box)

            before = audit_mesh(source)
            self.assertFalse(before.watertight)

            result = repair_candidate(
                source,
                root / "doctor",
                mode="prop",
                texture_size=256,
            )
            geometry_audit = audit_mesh(Path(result.repaired_geometry))
            self.assertTrue(
                result.safe_for_arena,
                {
                    "reasons": result.reasons,
                    "before": result.before,
                    "geometry": geometry_audit,
                    "after": result.after,
                },
            )
            self.assertTrue(result.after.watertight)

    def test_tiny_component_is_audited_not_auto_marked_for_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accessory.glb"
            body = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
            tiny = trimesh.creation.icosphere(subdivisions=1, radius=0.005)
            tiny.apply_translation([0.7, 0.0, 0.0])
            combined = trimesh.util.concatenate([body, tiny])
            write_colored_glb(path, combined)

            audit = audit_mesh(path)
            self.assertGreaterEqual(audit.components, 2)
            self.assertGreaterEqual(audit.tiny_components, 1)
            self.assertFalse(audit.repair_recommended)


if __name__ == "__main__":
    unittest.main()
