from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

from tools.hayuya3d.self_intersection_qa import (
    audit_self_intersections,
)


def write_mesh(path:Path,vertices,faces)->None:
    mesh=trimesh.Trimesh(
        vertices=np.asarray(vertices,dtype=np.float64),
        faces=np.asarray(faces,dtype=np.int64),
        process=False,
    )
    path.write_bytes(
        trimesh.exchange.gltf.export_glb(
            trimesh.Scene(mesh)
        )
    )


class SelfIntersectionQATests(unittest.TestCase):
    def test_closed_box_has_no_self_crossings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"box.glb"
            box=trimesh.creation.box(extents=[1.0,1.0,1.0])
            path.write_bytes(
                trimesh.exchange.gltf.export_glb(
                    trimesh.Scene(box)
                )
            )
            report=audit_self_intersections(path)
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.crossing_triangle_pairs,0)

    def test_adjacent_faces_are_not_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"quad.glb"
            write_mesh(
                path,
                [
                    (-1.0,-1.0,0.0),
                    ( 1.0,-1.0,0.0),
                    ( 1.0, 1.0,0.0),
                    (-1.0, 1.0,0.0),
                ],
                [
                    (0,1,2),
                    (0,2,3),
                ],
            )
            report=audit_self_intersections(
                path,
                min_face_fraction=0.0,
            )
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.crossing_triangle_pairs,0)

    def test_connected_component_with_nonadjacent_crossing_faces_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"crossed.glb"
            vertices=[
                # Triangle A: horizontal.
                (-1.0,0.0,0.0), # 0
                ( 1.0,0.0,0.0), # 1
                ( 0.0,1.0,0.0), # 2
                # Triangle B: vertical. Edge 3->4 crosses z=0 at
                # (0,0.30,0), strictly inside triangle A.
                (0.0, 0.30,-1.0), # 3
                (0.0, 0.30, 1.0), # 4
                (0.0,-0.60, 0.2), # 5
                # Connector placed away from the central crossing.
                (1.8,1.8,1.8),   # 6
                (2.1,1.8,1.8),   # 7
            ]
            faces=[
                (0,1,2),   # target A
                (3,4,5),   # target B
                # Connectivity path joins the two triangle vertex sets into
                # one topological component without sharing A/B vertices.
                (2,6,7),
                (6,3,7),
            ]
            write_mesh(path,vertices,faces)
            report=audit_self_intersections(
                path,
                min_face_fraction=0.0,
            )
            self.assertTrue(report.applicable)
            self.assertFalse(report.ready)
            self.assertGreater(report.crossing_triangle_pairs,0)
            self.assertTrue(
                any(
                    "self-intersects" in item
                    for item in report.errors
                ),
                report.errors,
            )

    def test_small_component_can_be_excluded_from_expensive_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"mixed.glb"
            body=trimesh.creation.icosphere(
                subdivisions=2,
                radius=1.0,
            )
            tiny=trimesh.creation.box(
                extents=[0.1,0.1,0.1]
            )
            tiny.apply_translation([2.0,0.0,0.0])
            scene=trimesh.Scene()
            scene.add_geometry(body,geom_name="body")
            scene.add_geometry(tiny,geom_name="tiny")
            path.write_bytes(
                trimesh.exchange.gltf.export_glb(scene)
            )
            report=audit_self_intersections(
                path,
                min_face_fraction=0.08,
            )
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(len(report.ignored_small_components),1)
            self.assertEqual(report.audited_component_count,1)


if __name__=="__main__":
    unittest.main()
