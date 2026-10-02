from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from viewforge import WONDER3D_VIEWS, collect_wonder3d_outputs


class ViewForgeTests(unittest.TestCase):
    def test_collects_stable_rgb_and_normal_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw" / "cropsize-224-cfg1.0" / "source"
            masked = raw / "masked_colors"
            normals_raw = raw / "normals"
            masked.mkdir(parents=True)
            normals_raw.mkdir(parents=True)

            from PIL import Image
            source = root / "source_real.jpg"
            Image.new("RGB", (32, 48), (120, 80, 40)).save(source, format="JPEG")

            for view in WONDER3D_VIEWS:
                (masked / f"rgb_000_{view}.png").write_bytes(f"rgb-{view}".encode())
                (raw / f"normals_000_{view}.png").write_bytes(f"normal-{view}".encode())
                (normals_raw / f"normals_000_{view}.png").write_bytes(b"raw-normal")

            result = collect_wonder3d_outputs(root / "raw", root / "stable", source)

            self.assertEqual(len(result.rgb_views), 6)
            self.assertEqual(len(result.normal_views), 6)
            self.assertEqual(len(result.synthetic_reconstruction_views), 5)
            self.assertNotIn(result.rgb_views["front"], result.synthetic_reconstruction_views)
            self.assertTrue(Path(result.manifest_path).is_file())
            anchor = root / "stable" / "anchors" / "source_real.png"
            self.assertTrue(anchor.is_file())
            self.assertEqual(anchor.read_bytes()[:8], bytes([137, 80, 78, 71, 13, 10, 26, 10]))
            for path in result.synthetic_reconstruction_views:
                self.assertTrue(Path(path).is_file())


if __name__ == "__main__":
    unittest.main()
