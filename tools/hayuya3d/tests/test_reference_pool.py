from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from reference_pool import classify_reference, infer_detail_region_hint, split_reference_roles


class ReferencePoolTests(unittest.TestCase):
    def test_studio_face_detail_prefix_is_head_detail_evidence(self):
        face = Path("jobs/123/inputs/details/000-face_detail-IMG_1234.jpg")
        self.assertEqual(classify_reference(face), "detail")
        self.assertEqual(infer_detail_region_hint(face), "head")

    def test_detail_reference_never_replaces_geometry_pool_when_geometry_exists(self):
        front = Path("jobs/123/inputs/000-front.png")
        face = Path("jobs/123/inputs/details/000-face_detail-IMG_1234.jpg")
        roles = split_reference_roles([front, face])
        self.assertEqual(roles.geometry, [front])
        self.assertEqual(roles.detail, [face])


if __name__ == "__main__":
    unittest.main()
