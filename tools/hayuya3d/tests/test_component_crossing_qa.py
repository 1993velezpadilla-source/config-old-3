from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trimesh

from tools.hayuya3d.component_crossing_qa import (
    audit_component_crossings,
)


def write_scene(path:Path,meshes:list[trimesh.Trimesh])->None:
    scene=trimesh.Scene()
    for index,mesh in enumerate(meshes):
        scene.add_geometry(
            mesh,
            node_name=f"node{index}",
            geom_name=f"geom{index}",
        )
    path.write_bytes(trimesh.exchange.gltf.export_glb(scene))


class ComponentCrossingQATests(unittest.TestCase):
    def test_separated_large_components_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"separate.glb"
            a=trimesh.creation.box(extents=[1.0,1.0,1.0])
            b=trimesh.creation.box(extents=[1.0,1.0,1.0])
            b.apply_translation([2.0,0.0,0.0])
            write_scene(path,[a,b])

            report=audit_component_crossings(path)
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.crossing_triangle_pairs,0)

    def test_intersecting_large_components_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"cross.glb"
            a=trimesh.creation.box(extents=[1.0,1.0,1.0])
            b=trimesh.creation.box(extents=[1.0,1.0,1.0])
            b.apply_translation([0.35,0.20,0.10])
            write_scene(path,[a,b])

            report=audit_component_crossings(path)
            self.assertTrue(report.applicable)
            self.assertFalse(report.ready)
            self.assertGreater(report.crossing_triangle_pairs,0)
            self.assertTrue(
                any("surfaces cross" in item for item in report.errors),
                report.errors,
            )

    def test_fully_nested_closed_component_does_not_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"nested.glb"
            outer=trimesh.creation.box(extents=[2.0,2.0,2.0])
            inner=trimesh.creation.box(extents=[0.5,0.5,0.5])
            write_scene(path,[outer,inner])

            report=audit_component_crossings(
                path,
                min_face_fraction=0.0,
            )
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.crossing_triangle_pairs,0)

    def test_small_accessory_component_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"accessory.glb"
            body=trimesh.creation.icosphere(
                subdivisions=2,
                radius=1.0,
            )
            accessory=trimesh.creation.box(
                extents=[0.25,0.25,0.25]
            )
            accessory.apply_translation([0.92,0.0,0.0])
            write_scene(path,[body,accessory])

            report=audit_component_crossings(
                path,
                min_face_fraction=0.08,
            )
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(
                len(report.ignored_accessory_components),
                1,
            )
            self.assertEqual(report.large_component_count,1)
            self.assertEqual(report.component_count,2)


if __name__=="__main__":
    unittest.main()
