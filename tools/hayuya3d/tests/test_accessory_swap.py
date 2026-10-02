from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import trimesh
from PIL import Image

from tools.hayuya3d.accessory_swap import (
    swap_detached_accessory,
)


def _material(color):
    return trimesh.visual.material.PBRMaterial(
        baseColorTexture=Image.fromarray(
            np.full(
                (16,16,4),
                [*color,255],
                dtype=np.uint8,
            ),
            mode="RGBA",
        ),
        metallicFactor=0.0,
        roughnessFactor=0.7,
    )


def _with_uv(mesh,material):
    mesh=mesh.copy()
    vertices=np.asarray(
        mesh.vertices,
        dtype=np.float64,
    )
    lo=vertices.min(axis=0)
    hi=vertices.max(axis=0)
    extent=np.maximum(hi-lo,1e-9)
    uv=np.stack([
        (vertices[:,0]-lo[0])/extent[0],
        (vertices[:,2]-lo[2])/extent[2],
    ],axis=1)
    mesh.visual=trimesh.visual.TextureVisuals(
        uv=uv,
        material=material,
    )
    return mesh


def write_character_like(
    path:Path,
    *,
    accessory_kind:str,
    accessory_y:float=1.20,
)->None:
    body=_with_uv(
        trimesh.creation.icosphere(
            subdivisions=2,
            radius=1.0,
        ),
        _material((100,100,110)),
    )

    if accessory_kind=="sphere":
        accessory=trimesh.creation.icosphere(
            subdivisions=0,
            radius=0.14,
        )
    elif accessory_kind=="box":
        accessory=trimesh.creation.box(
            extents=[0.24,0.24,0.24],
        )
    else:
        raise ValueError(accessory_kind)

    accessory.apply_translation(
        [0.0,accessory_y,0.0]
    )
    accessory=_with_uv(
        accessory,
        _material(
            (50,90,220)
            if accessory_kind=="sphere"
            else (220,70,50)
        ),
    )

    scene=trimesh.Scene()
    scene.add_geometry(
        body,
        node_name="body",
    )
    scene.add_geometry(
        accessory,
        node_name="accessory",
    )
    path.write_bytes(
        trimesh.exchange.gltf.export_glb(scene)
    )


class AccessorySwapTests(unittest.TestCase):
    def test_unskinned_corresponding_accessory_swaps_and_passes_geometry_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            output=root/"swapped.glb"
            write_character_like(
                base,
                accessory_kind="sphere",
            )
            write_character_like(
                donor,
                accessory_kind="box",
            )

            result=swap_detached_accessory(
                base,
                donor,
                output,
                mode="character",
                base_up_axis="y",
            )
            self.assertTrue(result.ready,result.errors)
            self.assertTrue(output.is_file())
            self.assertEqual(
                output.read_bytes()[:4],
                b"glTF",
            )
            self.assertIsNotNone(
                result.base_component_id
            )
            self.assertIsNotNone(
                result.donor_component_id
            )
            self.assertGreater(
                result.confidence or 0.0,
                0.55,
            )
            self.assertTrue(
                result.component_crossing_ready
            )
            self.assertTrue(
                result.self_intersection_ready
            )
            self.assertTrue(
                result.attachment_ready
            )
            self.assertEqual(
                result.attachment_floating_components,
                0,
            )
            self.assertEqual(
                result.attachment_oversized_floating_components,
                0,
            )
            self.assertEqual(
                result.output_components,
                2,
            )
            self.assertLessEqual(
                result.bbox_drift_fraction or 1.0,
                0.15,
            )

    def test_runtime_payload_blocks_swap_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            output=root/"blocked.glb"
            write_character_like(
                base,
                accessory_kind="sphere",
            )
            write_character_like(
                donor,
                accessory_kind="box",
            )

            with mock.patch(
                "tools.hayuya3d.accessory_swap._runtime_payload_blocks_swap",
                side_effect=[
                    ["skin","animation"],
                    [],
                ],
            ):
                result=swap_detached_accessory(
                    base,
                    donor,
                    output,
                    mode="character",
                )
            self.assertFalse(result.ready)
            self.assertFalse(output.exists())
            self.assertTrue(
                any(
                    "runtime-payload-free"
                    in item
                    for item in result.errors
                ),
                result.errors,
            )

    def test_large_alignment_correction_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            output=root/"blocked.glb"
            write_character_like(
                base,
                accessory_kind="sphere",
                accessory_y=1.20,
            )
            write_character_like(
                donor,
                accessory_kind="box",
                accessory_y=0.0,
            )
            result=swap_detached_accessory(
                base,
                donor,
                output,
                mode="character",
            )
            self.assertFalse(result.ready)


if __name__=="__main__":
    unittest.main()
