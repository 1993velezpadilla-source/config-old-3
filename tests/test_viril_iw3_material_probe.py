import json
import struct
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_gltf_material_probe import probe
from test_viril_iw3_glb_converter import example_glb


def make_material_glb(uri="../images/real_iw3_color.dds"):
    original=example_glb()
    original_json_length=struct.unpack_from("<I",original,12)[0]
    d=json.loads(original[20:20+original_json_length])
    d["materials"]=[{"name":"original_weapon_material",
        "pbrMetallicRoughness":{"baseColorTexture":{"index":0}}}]
    d["textures"]=[{"source":0}]
    d["images"]=[{"uri":uri}]
    offset=20+original_json_length
    binary=original[offset:]
    descriptor=json.dumps(d,separators=(",",":")).encode()
    descriptor+=b" " * ((-len(descriptor))%4)
    total=12+8+len(descriptor)+len(binary)
    return struct.pack("<4sII",b"glTF",2,total)+struct.pack("<I4s",len(descriptor),b"JSON")+descriptor+binary


class MaterialProbeTest(unittest.TestCase):
    def test_real_oat_style_dds_reference_resolves(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/"model").mkdir()
            (root/"images").mkdir()
            (root/"images/real_iw3_color.dds").write_bytes(b"synthetic dummy DDS")
            p=root/"model/viewmodel_test_lod0.glb"
            p.write_bytes(make_material_glb())
            r=probe(p,root)
            self.assertTrue(r["all_references_resolved"])
            self.assertEqual(r["statistics"]["original_texture_file_present"],1)
    def test_original_dds_missing_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/"model").mkdir()
            p=root/"model/viewmodel_test_lod0.glb"
            p.write_bytes(make_material_glb())
            r=probe(p,root)
            self.assertFalse(r["all_references_resolved"])
            self.assertEqual(r["statistics"]["texture_file_missing"],1)
    def test_reject_texture_escape(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/"model").mkdir()
            p=root/"model/test.glb"
            p.write_bytes(make_material_glb("../../../outside.dds"))
            r=probe(p,root)
            self.assertEqual(r["statistics"]["image_outside_original_extraction"],1)
if __name__=="__main__":
    unittest.main()
