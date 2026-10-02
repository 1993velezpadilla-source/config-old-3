from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from tools.hayuya3d.local_detail_fusion import (
    _seam_added_delta,
    fuse_local_basecolor,
)
from tools.hayuya3d.texture_gate import embedded_images


def write_textured_grid(
    path:Path,
    color:tuple[int,int,int],
)->None:
    vertices=np.asarray([
        [-0.5,-1.0,0.0],
        [ 0.5,-1.0,0.0],
        [-0.5, 0.0,0.0],
        [ 0.5, 0.0,0.0],
        [-0.5, 1.0,0.0],
        [ 0.5, 1.0,0.0],
    ],dtype=np.float64)
    faces=np.asarray([
        [0,1,3],[0,3,2],
        [2,3,5],[2,5,4],
    ],dtype=np.int64)
    uv=np.asarray([
        [0.0,0.0],
        [1.0,0.0],
        [0.0,0.5],
        [1.0,0.5],
        [0.0,1.0],
        [1.0,1.0],
    ],dtype=np.float64)
    image=Image.new("RGB",(64,64),color)
    material=trimesh.visual.material.PBRMaterial(
        baseColorTexture=image,
        metallicFactor=0.0,
        roughnessFactor=0.7,
    )
    mesh=trimesh.Trimesh(
        vertices=vertices,
        faces=faces,
        process=False,
        visual=trimesh.visual.TextureVisuals(
            uv=uv,
            material=material,
        ),
    )
    path.write_bytes(
        trimesh.exchange.gltf.export_glb(
            trimesh.Scene(mesh)
        )
    )


def basecolor_rgb(path:Path)->np.ndarray:
    matches=[
        data
        for index,mime,data,roles in embedded_images(path)
        if "baseColor" in set(roles or [])
    ]
    if len(matches)!=1:
        raise AssertionError(
            f"expected one baseColor image, got {len(matches)}"
        )
    with Image.open(io.BytesIO(matches[0])) as image:
        return np.asarray(image.convert("RGB"),dtype=np.uint8)


class LocalDetailFusionTests(unittest.TestCase):
    def test_head_region_changes_only_upper_texture_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            output=root/"fused.glb"
            write_textured_grid(base,(90,90,90))
            write_textured_grid(donor,(220,45,35))

            before=basecolor_rgb(base)
            result=fuse_local_basecolor(
                base,
                donor,
                output,
                region="head",
                up_axis="y",
                donor_samples=5000,
            )
            self.assertTrue(result.ready,result.error)
            self.assertTrue(result.geometry_preserved)
            self.assertTrue(result.skin_payload_preserved)
            self.assertTrue(result.seam_ready,result.error)
            self.assertGreater(result.seam_boundary_pairs,0)
            self.assertIsNotNone(result.seam_added_delta_p95)
            self.assertLessEqual(
                float(result.seam_added_delta_p95),
                12.0,
            )
            self.assertGreater(result.changed_pixels,0)
            self.assertGreater(result.unchanged_pixels,0)
            self.assertGreater(result.changed_fraction,0.05)
            self.assertLess(result.changed_fraction,0.60)

            after=basecolor_rgb(output)
            self.assertEqual(after.shape,before.shape)
            # Top of the atlas corresponds to the upper body/head UVs.
            self.assertGreater(
                float(np.mean(np.abs(
                    after[:16].astype(np.int16)
                    -before[:16].astype(np.int16)
                ))),
                10.0,
            )
            # Lower atlas remains byte-equivalent in RGB pixel values.
            self.assertTrue(
                np.array_equal(after[40:],before[40:])
            )

    def test_middle_region_leaves_top_and_bottom_edges_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            output=root/"fused.glb"
            write_textured_grid(base,(80,100,120))
            write_textured_grid(donor,(40,210,80))
            before=basecolor_rgb(base)

            result=fuse_local_basecolor(
                base,
                donor,
                output,
                region="middle",
                up_axis="y",
                donor_samples=5000,
            )
            self.assertTrue(result.ready,result.error)
            after=basecolor_rgb(output)
            self.assertTrue(np.array_equal(after[:4],before[:4]))
            self.assertTrue(np.array_equal(after[-4:],before[-4:]))
            self.assertFalse(np.array_equal(after[24:40],before[24:40]))

    def test_seam_metric_detects_hard_texture_cut(self):
        before=np.full((32,32,3),100,dtype=np.uint8)
        after=before.copy()
        after[:16,:,:]=220
        changed=np.zeros((32,32),dtype=bool)
        changed[:16,:]=True

        pairs,p95,maximum=_seam_added_delta(
            before,
            after,
            changed,
        )
        self.assertGreater(pairs,0)
        self.assertGreater(p95,12.0)
        self.assertGreaterEqual(maximum,p95)

    def test_unsupported_unlocalized_detail_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            output=root/"fused.glb"
            write_textured_grid(base,(90,90,90))
            write_textured_grid(donor,(200,40,40))

            result=fuse_local_basecolor(
                base,
                donor,
                output,
                region="local",
                up_axis="y",
                donor_samples=2000,
            )
            self.assertFalse(result.ready)
            self.assertIn("not executable",result.error or "")
            self.assertFalse(output.exists())


if __name__=="__main__":
    unittest.main()
