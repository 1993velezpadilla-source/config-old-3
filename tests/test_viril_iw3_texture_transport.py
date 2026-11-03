import struct
import sys
import tempfile
from pathlib import Path
import unittest

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_iwi_to_iwvt import first_color_iwi,iwvt_from_dds
from test_viril_iw3_material_probe import make_material_glb

class OriginalIW3RGBAInteropTest(unittest.TestCase):
    def test_gltf_original_color_uri_resolves_iwi(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"sample.glb"
            path.write_bytes(make_material_glb())
            self.assertEqual(first_color_iwi(path),"images/real_iw3_color.iwi")
    def test_synthetic_dds_to_escaped_rgba_native_iwvt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"synthetic.dds"
            picture=Image.new("RGBA",(2,3),(15,80,220,255))
            picture.save(path,format="DDS")
            binary=iwvt_from_dds(path)
            self.assertEqual(struct.unpack_from("<4sIII",binary),
                             (b"IWVT",1,2,3))
            self.assertEqual(len(binary),16+2*3*4)
            self.assertEqual(binary[16:20],bytes([15,80,220,255]))
if __name__=="__main__":
    unittest.main()
