"""Android fullscreen confirmation must not be mistaken for 3D gameplay."""
from PIL import Image,ImageDraw
import sys
from pathlib import Path
from unittest.mock import patch
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import iw3_capture_live_viewmodel as capture


class IW3OverlayCaptureTests(unittest.TestCase):
    def test_dismiss_detected_actual_android_dialog_colors(self):
        canvas=Image.new("RGB",(1200,700),(10,10,10))
        draw=ImageDraw.Draw(canvas)
        draw.rectangle((250,0,900,350),fill=(238,237,244))
        draw.rectangle((800,250,900,360),fill=(71,93,146))
        calls=[]
        with patch.object(capture,"adb",side_effect=lambda *a,**k:calls.append(a)),patch.object(capture.time,"sleep"):
            handled=capture.dismiss_os_fullscreen_dialog(canvas)
        self.assertTrue(handled)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0][0:3],("shell","input","tap"))

    def test_never_tap_actual_3d_frame(self):
        canvas=Image.new("RGB",(1200,700),(15,9,7))
        calls=[]
        with patch.object(capture,"adb",side_effect=lambda *a,**k:calls.append(a)):
            handled=capture.dismiss_os_fullscreen_dialog(canvas)
        self.assertFalse(handled)
        self.assertEqual(calls,[])

if __name__=="__main__":unittest.main()
