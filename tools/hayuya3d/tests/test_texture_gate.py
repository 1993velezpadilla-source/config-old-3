from __future__ import annotations

import io
import unittest

from PIL import Image

from tools.hayuya3d.texture_gate import (
    base_color_resolution_ok,
    material_image_roles,
    metric,
    texture_resolution_ok,
)


class TextureGateRoleTests(unittest.TestCase):
    def test_material_roles_follow_texture_sources(self):
        doc = {
            "textures": [
                {"source": 2},
                {"source": 0},
                {"source": 1},
            ],
            "materials": [
                {
                    "pbrMetallicRoughness": {
                        "baseColorTexture": {"index": 0},
                        "metallicRoughnessTexture": {"index": 2},
                    },
                    "normalTexture": {"index": 1},
                    "occlusionTexture": {"index": 2},
                }
            ],
        }
        roles = material_image_roles(doc)
        self.assertEqual(roles[2], {"baseColor"})
        self.assertEqual(roles[0], {"normal"})
        self.assertEqual(roles[1], {"metallicRoughness", "occlusion"})

    def test_metric_preserves_roles(self):
        image = Image.new("RGB", (64, 32), (120, 80, 40))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        result = metric(3, "image/png", buf.getvalue(), ["baseColor"])
        self.assertEqual(result.index, 3)
        self.assertEqual(result.width, 64)
        self.assertEqual(result.height, 32)
        self.assertEqual(result.roles, ["baseColor"])

    def test_all_bound_base_colors_must_meet_resolution_floor(self):
        self.assertTrue(base_color_resolution_ok([4096, 4096], 4096))
        self.assertFalse(base_color_resolution_ok([4096, 1024], 4096))
        self.assertFalse(base_color_resolution_ok([], 4096))

    def test_non_color_maps_cannot_fake_texture_quality(self):
        # A 4K normal/ORM map alone is not visible color fidelity.
        self.assertFalse(texture_resolution_ok([4096], [], 1024, 1024))
        self.assertTrue(texture_resolution_ok([4096, 2048], [2048], 1024, 2048))
        self.assertFalse(texture_resolution_ok([4096, 1024], [1024], 1024, 2048))


if __name__ == "__main__":
    unittest.main()
