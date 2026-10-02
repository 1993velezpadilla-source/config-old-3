from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.lod_parity import (
    audit_lod_chain,
    compare_lod,
)


def write_sphere(
    path:Path,
    subdivisions:int,
    *,
    scale:float=1.0,
    pbr:bool=False,
)->None:
    mesh=trimesh.creation.icosphere(
        subdivisions=subdivisions,
        radius=0.5*scale,
    )
    if pbr:
        mesh.visual=trimesh.visual.TextureVisuals(
            uv=np.zeros((len(mesh.vertices),2),dtype=np.float64),
            material=trimesh.visual.material.PBRMaterial(
                baseColorFactor=[160,110,80,255],
                metallicFactor=0.0,
                roughnessFactor=0.7,
            ),
        )
    else:
        rgba=np.tile(
            np.array([[160,110,80,255]],dtype=np.uint8),
            (len(mesh.vertices),1),
        )
        mesh.visual=trimesh.visual.ColorVisuals(
            mesh,vertex_colors=rgba
        )
    path.write_bytes(
        trimesh.exchange.gltf.export_glb(
            trimesh.Scene(mesh)
        )
    )


def _append(blob:bytearray,payload:bytes)->tuple[int,int]:
    while len(blob)%4:
        blob.append(0)
    offset=len(blob)
    blob.extend(payload)
    return offset,len(payload)


def write_triangle_with_optional_morph(
    path:Path,
    *,
    morph:bool,
)->None:
    positions=(
        (-0.5,0.0,0.0),
        (0.5,0.0,0.0),
        (0.0,1.0,0.0),
    )
    indices=(0,1,2)
    morph_delta=(
        (0.0,0.0,0.0),
        (0.0,0.0,0.0),
        (0.0,0.1,0.0),
    )
    blob=bytearray()
    pos_off,pos_len=_append(
        blob,b"".join(struct.pack("<3f",*row) for row in positions)
    )
    idx_off,idx_len=_append(
        blob,b"".join(struct.pack("<H",value) for value in indices)
    )
    views=[
        {"buffer":0,"byteOffset":pos_off,"byteLength":pos_len},
        {"buffer":0,"byteOffset":idx_off,"byteLength":idx_len},
    ]
    accessors=[
        {
            "bufferView":0,"componentType":5126,
            "count":3,"type":"VEC3",
            "min":[-0.5,0.0,0.0],
            "max":[0.5,1.0,0.0],
        },
        {
            "bufferView":1,"componentType":5123,
            "count":3,"type":"SCALAR",
        },
    ]
    primitive={
        "attributes":{"POSITION":0},
        "indices":1,
    }
    mesh={"primitives":[primitive]}
    if morph:
        morph_off,morph_len=_append(
            blob,
            b"".join(struct.pack("<3f",*row) for row in morph_delta),
        )
        views.append({
            "buffer":0,
            "byteOffset":morph_off,
            "byteLength":morph_len,
        })
        accessors.append({
            "bufferView":2,
            "componentType":5126,
            "count":3,
            "type":"VEC3",
        })
        primitive["targets"]=[{"POSITION":2}]
        mesh["weights"]=[0.0]
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":views,
        "accessors":accessors,
        "meshes":[mesh],
        "nodes":[{"mesh":0}],
        "scenes":[{"nodes":[0]}],
        "scene":0,
    }
    write_glb(path,doc,bytes(blob))


class LODParityTests(unittest.TestCase):
    def test_lower_density_sphere_preserves_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master.glb"
            lod=root/"lod1.glb"
            write_sphere(master,3)
            write_sphere(lod,2)

            item=compare_lod(
                master,lod,
                name="LOD1",
                mode="prop",
                samples=4000,
            )
            self.assertTrue(item.ready,item.errors)
            self.assertLess(item.shape_p95_distance_ratio,0.075)
            self.assertGreater(item.bbox_extent_ratio_min,0.9)
            self.assertLess(item.bbox_extent_ratio_max,1.1)

    def test_collapsed_lod_fails_shape_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master.glb"
            bad=root/"lod1.glb"
            write_sphere(master,3)
            write_sphere(bad,2,scale=0.2)

            item=compare_lod(
                master,bad,
                name="LOD1",
                mode="prop",
                samples=3000,
            )
            self.assertFalse(item.ready)
            self.assertLess(item.bbox_extent_ratio_min,0.70)
            self.assertTrue(
                any("bbox extent collapse" in x for x in item.errors),
                item.errors,
            )

    def test_chain_requires_monotonic_face_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master.glb"
            lod0=root/"lod0.glb"
            lod1=root/"lod1.glb"
            write_sphere(master,3)
            write_sphere(lod0,1)
            write_sphere(lod1,2)

            report=audit_lod_chain(
                master,
                [("LOD0",lod0),("LOD1",lod1)],
                mode="prop",
                samples=2500,
            )
            self.assertFalse(report.ready)
            self.assertFalse(report.face_chain_monotonic)
            self.assertTrue(
                any("monotonically" in x for x in report.errors),
                report.errors,
            )

    def test_morph_targets_cannot_disappear_from_lod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master-morph.glb"
            lod=root/"lod-no-morph.glb"
            write_triangle_with_optional_morph(master,morph=True)
            write_triangle_with_optional_morph(lod,morph=False)

            item=compare_lod(
                master,lod,
                name="LOD1",
                mode="prop",
                samples=1200,
            )
            self.assertTrue(item.morph_required)
            self.assertFalse(item.morph_ready)
            self.assertEqual(item.morph_target_count,0)
            self.assertFalse(item.ready)
            self.assertTrue(
                any("morph" in error.lower() for error in item.errors),
                item.errors,
            )

    def test_floating_accessory_blocks_runtime_lod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master_accessory.glb"
            lod=root/"lod_accessory.glb"

            def write_asset(path:Path, accessory_x:float):
                body=trimesh.creation.icosphere(
                    subdivisions=2,
                    radius=1.0,
                )
                charm=trimesh.creation.box(
                    extents=[0.08,0.08,0.08]
                )
                charm.apply_translation(
                    [accessory_x,0.0,0.0]
                )
                scene=trimesh.Scene()
                scene.add_geometry(body)
                scene.add_geometry(charm)
                path.write_bytes(
                    trimesh.exchange.gltf.export_glb(scene)
                )

            write_asset(master,1.08)
            write_asset(lod,1.35)
            item=compare_lod(
                master,
                lod,
                name="LOD1",
                mode="prop",
                samples=600,
            )
            self.assertFalse(item.ready)
            self.assertFalse(item.attachment_ready)
            self.assertEqual(
                item.attachment_floating_components,
                1,
            )
            self.assertTrue(
                any(
                    "attachment" in error.lower()
                    for error in item.errors
                ),
                item.errors,
            )

    def test_lod0_cannot_drop_hero_accessory_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master_accessory.glb"
            lod=root/"lod0_missing_accessory.glb"

            body=trimesh.creation.icosphere(
                subdivisions=2,
                radius=1.0,
            )
            charm=trimesh.creation.box(
                extents=[0.08,0.08,0.08]
            )
            charm.apply_translation([1.08,0.0,0.0])
            scene=trimesh.Scene()
            scene.add_geometry(body)
            scene.add_geometry(charm)
            master.write_bytes(
                trimesh.exchange.gltf.export_glb(scene)
            )
            lod.write_bytes(
                trimesh.exchange.gltf.export_glb(
                    trimesh.Scene(body.copy())
                )
            )

            item=compare_lod(
                master,
                lod,
                name="LOD0",
                mode="prop",
                samples=600,
            )
            self.assertFalse(item.ready)
            self.assertTrue(item.attachment_ready)
            self.assertFalse(
                item.attachment_accessory_retention_ready
            )
            self.assertTrue(
                any(
                    "lost detached accessory" in error.lower()
                    for error in item.errors
                ),
                item.errors,
            )

    def test_material_channel_loss_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            master=root/"master.glb"
            lod=root/"lod.glb"
            write_sphere(master,2,pbr=True)
            write_sphere(lod,2,pbr=False)

            item=compare_lod(
                master,lod,
                name="LOD1",
                mode="prop",
                samples=2000,
            )
            self.assertFalse(item.ready)
            self.assertTrue(item.missing_material_channels)
            self.assertTrue(
                any("material channels lost" in x for x in item.errors),
                item.errors,
            )


if __name__=="__main__":
    unittest.main()
