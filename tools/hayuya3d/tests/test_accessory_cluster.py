from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trimesh

from tools.hayuya3d.accessory_cluster import inspect_accessory_clusters


def _write_scene(path: Path, pieces) -> None:
    scene = trimesh.Scene()
    body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    scene.add_geometry(body, node_name="body")
    for index, piece in enumerate(pieces):
        scene.add_geometry(piece, node_name=f"piece_{index}")
    path.write_bytes(trimesh.exchange.gltf.export_glb(scene))


def _box(center, extents=(0.10, 0.10, 0.08)):
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(center)
    return mesh


class AccessoryClusterTests(unittest.TestCase):
    def test_chain_and_medal_form_one_anchored_logical_accessory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rosary.glb"
            # First link is close to the body. The second is close to the first
            # but intentionally farther from the body so reachability must flow
            # through the accessory-accessory proximity edge.
            _write_scene(path, [
                _box((0.0, 1.06, 0.0), (0.10, 0.10, 0.08)),
                _box((0.0, 1.17, 0.0), (0.09, 0.10, 0.07)),
                _box((0.0, 1.28, 0.0), (0.08, 0.10, 0.06)),
            ])

            report = inspect_accessory_clusters(path)
            self.assertTrue(report.ready, report.errors)
            self.assertEqual(report.accessory_components, 3)
            self.assertEqual(report.cluster_count, 1)
            self.assertEqual(len(report.selected_component_ids), 3)
            cluster = report.clusters[0]
            self.assertTrue(cluster.anchored_to_main)
            self.assertEqual(len(cluster.component_ids), 3)
            self.assertGreaterEqual(len(cluster.direct_main_anchors), 1)
            self.assertLess(
                len(cluster.direct_main_anchors),
                len(cluster.component_ids),
            )
            self.assertLessEqual(
                cluster.max_internal_link_gap_ratio,
                0.06,
            )
            self.assertTrue(
                any(member.linked_accessory_ids for member in cluster.members)
            )

    def test_two_independent_body_anchored_accessories_are_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ambiguous.glb"
            _write_scene(path, [
                _box((0.0, 1.06, 0.0), (0.10, 0.10, 0.08)),
                _box((0.0, -1.06, 0.0), (0.10, 0.10, 0.08)),
            ])

            report = inspect_accessory_clusters(path)
            self.assertFalse(report.ready)
            self.assertEqual(report.accessory_components, 2)
            self.assertEqual(report.cluster_count, 2)
            self.assertEqual(report.selected_component_ids, [])
            self.assertTrue(
                any(
                    "multiple independent accessory clusters" in error
                    for error in report.errors
                ),
                report.errors,
            )

    def test_floating_cluster_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "floating.glb"
            _write_scene(path, [
                _box((0.0, 1.06, 0.0), (0.10, 0.10, 0.08)),
                _box((3.0, 3.0, 3.0), (0.08, 0.08, 0.08)),
            ])

            report = inspect_accessory_clusters(path)
            self.assertFalse(report.ready)
            self.assertEqual(report.cluster_count, 2)
            self.assertTrue(
                any(
                    "floating accessory clusters" in error
                    for error in report.errors
                ),
                report.errors,
            )


if __name__ == "__main__":
    unittest.main()
