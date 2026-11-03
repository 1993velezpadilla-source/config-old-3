import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_glb_skin_probe import describe,census
from test_viril_iw3_glb_converter import example_glb

class OriginalSkinProbeTests(unittest.TestCase):
    def test_unskinned_original_model_does_not_claim_animation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"export"
            root.mkdir()
            p=root/"viewmodel_synthetic_lod0.glb"
            p.write_bytes(example_glb())
            data=describe(p)
            self.assertEqual(data["weighted_vertices"],0)
            self.assertFalse(data["readable_skin_data"])
            self.assertEqual(data["skin_count"],0)
            reports=census(root)
            self.assertEqual(reports["aggregate"]["usable_skin_models"],0)
            self.assertFalse(reports["animated_IW3_GLES_renderer_implemented"])

if __name__=="__main__":unittest.main()
