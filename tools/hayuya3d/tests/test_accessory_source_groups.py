from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from tools.hayuya3d.accessory_source_groups import (
    audit_accessory_source_groups,
)
from tools.hayuya3d.gltf_audit import audit_glb
from tools.hayuya3d.rigged_accessory_split_insert import (
    insert_split_rigged_accessory,
    split_rigged_accessory_insert_supported,
)
from tools.hayuya3d.skin_weight_qa import audit_skin_weights
from tools.hayuya3d.morph_deformation_qa import audit_morph_deformation
from tools.hayuya3d.glb_images import read_glb
from tools.hayuya3d.tests.test_accessory_material_transfer import (
    write_skinned_base_with_normals,
)


def _textured_tetra(center, color):
    vertices = np.asarray([
        [-0.045, -0.040, -0.035],
        [ 0.045, -0.040, -0.035],
        [ 0.000,  0.050, -0.025],
        [ 0.000,  0.000,  0.050],
    ], dtype=np.float64)
    vertices += np.asarray(center, dtype=np.float64)
    faces = np.asarray([
        [0, 2, 1],
        [0, 1, 3],
        [1, 2, 3],
        [2, 0, 3],
    ], dtype=np.int64)
    uv = np.asarray([
        [0.05, 0.05],
        [0.95, 0.05],
        [0.15, 0.85],
        [0.82, 0.73],
    ], dtype=np.float64)
    image = Image.new("RGBA", (16, 16), tuple(color) + (255,))
    material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=image,
        metallicFactor=0.1,
        roughnessFactor=0.5,
    )
    mesh = trimesh.Trimesh(
        vertices=vertices,
        faces=faces,
        process=False,
        visual=trimesh.visual.TextureVisuals(
            uv=uv,
            material=material,
        ),
    )
    return mesh


def write_multi_primitive_cluster(path: Path) -> None:
    scene = trimesh.Scene()
    scene.add_geometry(
        trimesh.creation.icosphere(subdivisions=2, radius=1.0),
        node_name="body",
    )
    for index, (center, color) in enumerate((
        ((0.0, 1.06, 0.0), (150, 100, 40)),
        ((0.0, 1.17, 0.0), (180, 130, 45)),
        ((0.0, 1.28, 0.0), (205, 170, 60)),
    )):
        scene.add_geometry(
            _textured_tetra(center, color),
            node_name=f"rosary_piece_{index}",
        )
    path.write_bytes(trimesh.exchange.gltf.export_glb(scene))


def write_ambiguous_accessories(path: Path) -> None:
    scene = trimesh.Scene()
    scene.add_geometry(
        trimesh.creation.icosphere(subdivisions=2, radius=1.0),
        node_name="body",
    )
    scene.add_geometry(
        _textured_tetra((0.0, 1.06, 0.0), (180, 130, 45)),
        node_name="upper_accessory",
    )
    scene.add_geometry(
        _textured_tetra((0.0, -1.06, 0.0), (90, 130, 190)),
        node_name="lower_accessory",
    )
    path.write_bytes(trimesh.exchange.gltf.export_glb(scene))


class AccessorySourceGroupTests(unittest.TestCase):
    def test_multi_material_cluster_maps_every_piece_to_its_primitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "multi-material.glb"
            write_multi_primitive_cluster(path)

            report = audit_accessory_source_groups(path)
            self.assertTrue(report.ready, report.errors)
            self.assertEqual(report.piece_count, 3)
            self.assertEqual(report.group_count, 3)
            self.assertEqual(len(report.selected_component_ids), 3)
            self.assertTrue(all(piece.ready for piece in report.pieces))
            self.assertTrue(all(group.ready for group in report.groups))
            self.assertEqual(
                sorted(
                    component_id
                    for group in report.groups
                    for component_id in group.candidate_component_ids
                ),
                sorted(report.selected_component_ids),
            )
            self.assertTrue(
                all(group.material_index is not None for group in report.groups)
            )
            self.assertTrue(
                all(group.texcoord0_accessor is not None for group in report.groups)
            )
            self.assertTrue(
                all(group.basecolor_texture for group in report.groups)
            )
            self.assertTrue(
                any(
                    "split-preserving insertion" in warning
                    for warning in report.warnings
                ),
                report.warnings,
            )

    def test_split_insert_adds_one_skinned_primitive_per_source_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "multi-material.glb"
            output = root / "split-insert.glb"
            write_skinned_base_with_normals(base)
            write_multi_primitive_cluster(donor)

            supported, blocker = split_rigged_accessory_insert_supported(
                base,
                donor,
            )
            self.assertTrue(supported, blocker)

            result = insert_split_rigged_accessory(
                base,
                donor,
                output,
            )
            self.assertTrue(result.ready, result.errors)
            self.assertTrue(result.geometry_ready)
            self.assertFalse(result.production_ready)
            self.assertTrue(result.legacy_payload_preserved)
            self.assertTrue(result.rig_ready)
            self.assertTrue(result.skin_weights_ready)
            self.assertTrue(result.morph_ready)
            self.assertTrue(result.morph_deformation_ready)
            self.assertTrue(result.attachment_ready)
            self.assertTrue(result.component_crossing_ready)
            self.assertTrue(result.self_intersection_ready)
            self.assertGreater(result.inserted_vertices, 0)
            self.assertGreater(result.inserted_faces, 0)
            self.assertEqual(
                result.transferred_weight_vertices,
                result.inserted_vertices,
            )
            self.assertTrue(
                any(
                    warning == "split_accessory_groups=3"
                    for warning in result.warnings
                ),
                result.warnings,
            )

            rig = audit_glb(output)
            self.assertTrue(rig.rig_ready, rig.errors)
            self.assertTrue(rig.morph_ready, rig.errors)
            self.assertEqual(rig.morph_primitive_count, 4)
            self.assertTrue(audit_skin_weights(output).ready)
            self.assertTrue(audit_morph_deformation(output).ready)

            doc, _ = read_glb(output)
            primitives = doc["meshes"][0]["primitives"]
            self.assertEqual(len(primitives), 4)
            inserted = primitives[1:]
            self.assertTrue(all("material" not in item for item in inserted))
            self.assertTrue(all(
                (item.get("extras") or {}).get("hayuyaAccessorySplit")
                for item in inserted
            ))
            self.assertEqual(
                sorted(
                    int((item.get("extras") or {})["hayuyaSourcePrimitive"])
                    for item in inserted
                ),
                [0, 0, 0],
            )

    def test_independent_accessories_never_become_one_source_group_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ambiguous.glb"
            write_ambiguous_accessories(path)

            report = audit_accessory_source_groups(path)
            self.assertFalse(report.ready)
            self.assertEqual(report.group_count, 0)
            self.assertTrue(
                any(
                    "not one proven logical cluster" in error
                    for error in report.errors
                ),
                report.errors,
            )


if __name__ == "__main__":
    unittest.main()
