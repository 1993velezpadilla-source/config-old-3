import sys
from pathlib import Path
import struct
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_xanim_header_probe import HEADER,header,census

class XAnimHeaderTest(unittest.TestCase):
    def test_real_iw3_v17_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"xanim"
            root.mkdir()
            data=HEADER.pack(17,60,27,3,0,30)
            (root/"viewmodel_reload").write_bytes(data+b"\x00"*20)
            value=header(root/"viewmodel_reload")
            self.assertEqual(value["frames"],60)
            self.assertEqual(value["bones"],27)
            self.assertTrue(value["root_delta"])
            self.assertTrue(value["loop"])
            report=census(root)
            self.assertEqual(report["totals"]["valid_compiled_iw3_v17"],1)
            self.assertEqual(report["name_categories"]["reload"],1)
            self.assertFalse(report["played_by_vril"])
    def test_reject_other_iw_engine_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad"
            path.write_bytes(HEADER.pack(18,20,12,0,1,30))
            with self.assertRaises(ValueError):
                header(path)
    def test_reject_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad"
            path.write_bytes(b"\x11\x00\x20")
            with self.assertRaises(ValueError):
                header(path)
    def test_reject_invalid_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad"
            path.write_bytes(HEADER.pack(17,20,12,0x80,1,30))
            with self.assertRaises(ValueError):
                header(path)

if __name__=="__main__":
    unittest.main()
