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

from part_map import build_part_map


class PartMapTests(unittest.TestCase):
    def test_character_regions_cover_full_mesh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "character.glb"

            body = trimesh.creation.box(extents=[0.8, 2.0, 0.5])
            body.apply_translation([0.0, 0.0, 0.0])
            path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(body))
            )

            result = build_part_map(path, mode="character", up_axis="y")
            labels = set(result.face_labels)
            self.assertTrue(any(label.startswith("head") for label in labels))
            self.assertTrue(any("upper_body" in label for label in labels))
            self.assertTrue(any("legs_feet" in label for label in labels))
            self.assertEqual(sum(region.face_count for region in result.regions), result.face_count)

    def test_small_disconnected_component_is_accessory_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "with_accessory.glb"

            body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
            accessory = trimesh.creation.box(extents=[0.08, 0.08, 0.08])
            accessory.apply_translation([1.25, 0.3, 0.0])

            scene = trimesh.Scene()
            scene.add_geometry(body)
            scene.add_geometry(accessory)
            path.write_bytes(trimesh.exchange.gltf.export_glb(scene))

            result = build_part_map(
                path,
                mode="character",
                up_axis="y",
                accessory_face_fraction=0.10,
            )
            self.assertGreaterEqual(result.component_count, 2)
            self.assertGreaterEqual(len(result.accessory_component_ids), 1)
            accessory_components = [
                component
                for component in result.components
                if component.accessory_candidate
            ]
            self.assertTrue(accessory_components)
            self.assertTrue(all(not c.main_component for c in accessory_components))

    def test_architecture_uses_base_wall_roof_regions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "tower.glb"

            mesh = trimesh.creation.box(extents=[1.0, 4.0, 1.0])
            path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
            )

            result = build_part_map(path, mode="architecture", up_axis="y")
            labels = set(result.face_labels)
            self.assertIn("foundation_base", labels)
            self.assertIn("wall_body", labels)
            self.assertIn("roof_upper", labels)

    def test_up_axis_x_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "xup.glb"

            mesh = trimesh.creation.box(extents=[3.0, 1.0, 1.0])
            path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
            )

            result = build_part_map(path, mode="prop", up_axis="x")
            self.assertEqual(result.up_axis, "x")
            self.assertEqual(len(result.face_labels), result.face_count)

    def test_up_axis_z_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "zup.glb"

            mesh = trimesh.creation.box(extents=[1.0, 1.0, 3.0])
            path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
            )

            result = build_part_map(path, mode="prop", up_axis="z")
            self.assertEqual(result.up_axis, "z")
            self.assertEqual(len(result.face_labels), result.face_count)


if __name__ == "__main__":
    unittest.main()
