from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

import numpy as np
import trimesh
from PIL import Image

from portable_textures import detect_toolchain, inspect_basisu_glb, transcode_glb_to_ktx2


def make_textured_fixture(path: Path) -> None:
    vertices = np.array([
        [-0.5, -0.5, 0.0],
        [ 0.5, -0.5, 0.0],
        [ 0.5,  0.5, 0.0],
        [-0.5,  0.5, 0.0],
    ], dtype=np.float64)
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    uvs = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [0.0, 1.0],
    ], dtype=np.float64)

    base = Image.fromarray(np.full((32, 32, 4), [180, 70, 30, 255], dtype=np.uint8), mode="RGBA")
    mr = Image.fromarray(np.full((32, 32, 3), [0, 90, 210], dtype=np.uint8), mode="RGB")
    normal = Image.fromarray(np.full((32, 32, 3), [128, 128, 255], dtype=np.uint8), mode="RGB")

    material = trimesh.visual.material.PBRMaterial(
        name="hayuya_ktx2_fixture",
        baseColorTexture=base,
        metallicRoughnessTexture=mr,
        normalTexture=normal,
        metallicFactor=0.8,
        roughnessFactor=0.6,
    )
    mesh = trimesh.Trimesh(
        vertices=vertices,
        faces=faces,
        process=False,
        visual=trimesh.visual.TextureVisuals(uv=uvs, material=material),
    )
    path.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh)))


@unittest.skipUnless(
    os.environ.get("HAYUYA_KTX2_E2E") == "1",
    "physical KTX2 toolchain test only runs in dedicated CI",
)
class PortableTextureE2ETests(unittest.TestCase):
    def test_physically_embeds_basisu_ktx2_in_glb(self):
        tools = detect_toolchain()
        self.assertTrue(tools.ready, tools.reasons)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.glb"
            output = root / "runtime.ktx2.glb"
            make_textured_fixture(source)

            result = transcode_glb_to_ktx2(
                source,
                output,
                max_texture_size=64,
                toolchain=tools,
            )
            self.assertTrue(output.is_file())
            self.assertEqual(output.read_bytes()[:4], b"glTF")
            self.assertGreater(result.texture_count, 0)
            self.assertEqual(result.texture_count, result.ktx2_image_count)
            self.assertTrue(result.all_textures_basisu)
            self.assertTrue(result.all_images_ktx2)

            audit = inspect_basisu_glb(output)
            self.assertTrue(audit["uses_khr_texture_basisu"])
            self.assertTrue(audit["requires_khr_texture_basisu"])
            self.assertTrue(audit["all_textures_basisu"])
            self.assertTrue(audit["all_images_ktx2"])


if __name__ == "__main__":
    unittest.main()
