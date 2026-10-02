from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trimesh

from tools.hayuya3d.collision_qa import audit_collision


def write_mesh(path:Path,mesh)->None:
    path.write_bytes(
        trimesh.exchange.gltf.export_glb(
            trimesh.Scene(mesh)
        )
    )


class CollisionQATests(unittest.TestCase):
    def test_convex_hull_collision_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master.glb"
            collision=root/"collision.glb"

            mesh=trimesh.creation.icosphere(
                subdivisions=2,
                radius=1.0,
            )
            # Introduce a small concavity in the Hero Master; its convex hull
            # remains a valid collision proxy.
            mesh.vertices[0]*=0.75
            write_mesh(master,mesh)
            write_mesh(collision,mesh.convex_hull)

            report=audit_collision(
                master,
                collision,
            )
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertTrue(report.watertight)
            self.assertTrue(report.positive_volume)
            self.assertTrue(report.bbox_coverage_ready)
            self.assertIsNotNone(report.convexity_ratio)
            self.assertGreaterEqual(
                float(report.convexity_ratio),
                0.98,
            )

    def test_missing_collision_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master.glb"
            write_mesh(
                master,
                trimesh.creation.box(
                    extents=[1.0,2.0,1.0],
                ),
            )
            report=audit_collision(
                master,
                root/"missing.glb",
            )
            self.assertFalse(report.ready)
            self.assertTrue(report.errors)

    def test_open_collision_surface_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master.glb"
            collision=root/"open.glb"
            write_mesh(
                master,
                trimesh.creation.box(
                    extents=[1.0,1.0,1.0],
                ),
            )
            box=trimesh.creation.box(
                extents=[1.0,1.0,1.0],
            )
            open_mesh=trimesh.Trimesh(
                vertices=box.vertices.copy(),
                faces=box.faces[:-2].copy(),
                process=False,
            )
            write_mesh(collision,open_mesh)

            report=audit_collision(
                master,
                collision,
            )
            self.assertFalse(report.ready)
            self.assertFalse(report.watertight)
            self.assertTrue(
                any(
                    "watertight" in item
                    for item in report.errors
                ),
                report.errors,
            )

    def test_proxy_that_does_not_cover_master_bounds_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master.glb"
            collision=root/"small.glb"
            write_mesh(
                master,
                trimesh.creation.box(
                    extents=[2.0,2.0,2.0],
                ),
            )
            write_mesh(
                collision,
                trimesh.creation.box(
                    extents=[1.0,1.0,1.0],
                ),
            )

            report=audit_collision(
                master,
                collision,
            )
            self.assertFalse(report.ready)
            self.assertFalse(
                report.bbox_coverage_ready
            )
            self.assertTrue(
                any(
                    "does not cover" in item
                    for item in report.errors
                ),
                report.errors,
            )


if __name__=="__main__":
    unittest.main()
