import sys
from pathlib import Path
import zipfile
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_iwd_texture_inventory import match,dds_links
from test_viril_iw3_material_probe import make_material_glb

class COD4IWDMaterialInventory(unittest.TestCase):
    def test_original_cod4_iwd_image_matches_glb_texture_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            glb=root/"viewmodel_test_lod0.glb"
            glb.write_bytes(make_material_glb())
            archive=root/"iw_00.iwd"
            with zipfile.ZipFile(archive,"w") as z:
                z.writestr("images/real_iw3_color.iwi",b"\xffIWI synthetic bytes")
            self.assertIn("images/real_iw3_color.iwi",dds_links(glb))
            r=match([glb],[archive])
            self.assertEqual(r["iwi_references_found"],1)
            self.assertEqual(r["iwi_references_missing"],0)
            self.assertFalse(r["iwi_payloads_copied"])

    def test_reports_missing_original_iwd_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            glb=root/"model.glb"
            glb.write_bytes(make_material_glb())
            archive=root/"iw_00.iwd"
            with zipfile.ZipFile(archive,"w") as z:
                z.writestr("images/unrelated.iwi",b"dummy")
            r=match([glb],[archive])
            self.assertEqual(r["iwi_references_found"],0)
            self.assertEqual(r["iwi_references_missing"],1)

if __name__=="__main__":
    unittest.main()
