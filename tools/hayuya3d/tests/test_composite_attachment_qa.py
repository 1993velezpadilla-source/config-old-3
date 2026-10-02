from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trimesh

from tools.hayuya3d.composite_attachment_qa import audit_composite_attachments


def write_scene(path: Path, meshes) -> None:
    scene = trimesh.Scene()
    for index, mesh in enumerate(meshes):
        scene.add_geometry(mesh, node_name=f"part_{index}", geom_name=f"part_{index}")
    path.write_bytes(trimesh.exchange.gltf.export_glb(scene))


class CompositeAttachmentQATests(unittest.TestCase):
    def test_single_component_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "single.glb"
            write_scene(path, [trimesh.creation.icosphere(subdivisions=2, radius=1.0)])
            report = audit_composite_attachments(path, mode="character")
            self.assertTrue(report.ready, report.errors)
            self.assertEqual(report.component_count, 1)
            self.assertEqual(report.floating_components, 0)

    def test_accessory_chain_can_anchor_through_neighbor_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.glb"
            body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
            beads = []
            for x in (1.12, 1.34, 1.56):
                bead = trimesh.creation.icosphere(subdivisions=0, radius=0.10)
                bead.apply_translation([x, 0.0, 0.0])
                beads.append(bead)
            write_scene(path, [body, *beads])

            report = audit_composite_attachments(path, mode="character")
            self.assertTrue(report.ready, report.errors)
            self.assertEqual(report.accessory_candidates, 3)
            self.assertEqual(report.anchored_accessories, 3)
            self.assertEqual(report.floating_components, 0)
            self.assertTrue(all(
                row.reachable_from_main
                for row in report.components
            ))

    def test_character_local_accessory_gap_matches_calibrated_tolerance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibrated_gap.glb"
            body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
            charm = trimesh.creation.box(extents=[0.08, 0.08, 0.08])
            # Surface gap is ~0.19 on a body diagonal of ~3.46 => ~0.055x.
            # This represents the measured stand-off seen after a valid matched
            # accessory normalization, while destructive fixtures remain far
            # outside the 0.06x character allowance.
            charm.apply_translation([1.23, 0.0, 0.0])
            write_scene(path, [body, charm])

            report = audit_composite_attachments(path, mode="character")
            self.assertTrue(report.ready, report.errors)
            self.assertEqual(report.accessory_candidates, 1)
            self.assertEqual(report.anchored_accessories, 1)
            self.assertEqual(report.floating_components, 0)

    def test_floating_small_accessory_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "floating_accessory.glb"
            body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
            charm = trimesh.creation.icosphere(subdivisions=0, radius=0.08)
            charm.apply_translation([4.0, 0.0, 0.0])
            write_scene(path, [body, charm])

            report = audit_composite_attachments(path, mode="character")
            self.assertFalse(report.ready)
            self.assertEqual(report.floating_components, 1)
            self.assertEqual(report.oversized_floating_components, 0)
            self.assertTrue(any(
                "floating accessory" in item
                for item in report.errors
            ), report.errors)

    def test_floating_large_donor_component_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "floating_donor.glb"
            body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
            donor = trimesh.creation.icosphere(subdivisions=1, radius=0.8)
            donor.apply_translation([5.0, 0.0, 0.0])
            write_scene(path, [body, donor])

            report = audit_composite_attachments(path, mode="character")
            self.assertFalse(report.ready)
            self.assertEqual(report.floating_components, 1)
            self.assertEqual(report.oversized_floating_components, 1)
            self.assertTrue(any(
                "detached donor/component" in item
                for item in report.errors
            ), report.errors)


if __name__ == "__main__":
    unittest.main()
