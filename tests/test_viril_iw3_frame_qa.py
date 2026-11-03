"""Prevent false-negative Android gameplay screenshot rejection.

No copyrighted game images are embedded in these tests.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from iw3_synthetic_frame_qa import audit


class ViewmodelScreenshotGateTests(unittest.TestCase):
    def test_dark_center_real_colorful_scene_is_valid(self):
        with tempfile.TemporaryDirectory() as d:
            pic = Image.new("RGB", (1280, 720), (21, 18, 16))
            # Dark central wall with a varied map and HUD along the edges.
            # 84+ quantized color bins ensure full-frame activity.
            for x in range(0, 1280, 10):
                for y in range(0, 80, 10):
                    pic.paste(((x//10*7)%256, (y//10*17)%256,
                               ((x+y)//10*9)%256), (x, y, x+10, y+10))
            path = Path(d) / "real_scene_like_synthetic.png"
            pic.save(path)
            a = audit(path)
            self.assertGreater(a["scene_palette_bins"], 50)
            self.assertLess(a["center_palette_bins"], 50)
            self.assertTrue(a["nonblank_gameplay"])

    def test_black_frame_remains_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "black.png"
            Image.new("RGB", (1280, 720)).save(path)
            self.assertFalse(audit(path)["nonblank_gameplay"])

    def test_pale_modal_remains_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "dialog.png"
            pic = Image.new("RGB", (1280, 720), (8, 8, 8))
            pic.paste((245, 245, 245), (220, 110, 950, 600))
            pic.save(path)
            self.assertFalse(audit(path)["android_launcher_anr_popup_rejected"])


if __name__ == "__main__":
    unittest.main()
