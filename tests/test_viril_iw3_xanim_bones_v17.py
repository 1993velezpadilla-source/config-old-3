import sys
from pathlib import Path
import struct
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from iw3_xanim_bones_v17 import decode,census,BrokenXAnim
from iw3_xanim_header_probe import HEADER

class FullBoneDecoderTests(unittest.TestCase):
    @staticmethod
    def fixture():
        # Real v17 schema: header, flip mask, half mask, bone name,
        # one fixed quaternion (x,y,z) and one fixed translation,
        # one notify with a frame number.
        return (HEADER.pack(17,20,1,0,0,30) +
                b"\0" + b"\0" +
                b"tag_weapon\0" +
                struct.pack("<Hhhh",1,0,0,0) +
                struct.pack("<Hfff",1,1.0,2.0,3.0) +
                b"\x01fire\0" + struct.pack("<H",10))

    def test_real_file_layout_no_delta(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/"xanim"
            root.mkdir()
            file=root/"viewmodel_fire"
            file.write_bytes(self.fixture())
            result=decode(file)
            self.assertEqual(result["frames"],20)
            self.assertEqual(result["fps"],30)
            self.assertEqual(result["bones"][0]["name"],"tag_weapon")
            self.assertEqual(result["bones"][0]["position"]["xyz"][0],[1.,2.,3.])
            self.assertEqual(result["notifications"],[{"name":"fire","frame":10}])
            report=census(root)
            self.assertEqual(report["decoded_full_bones_without_rootdelta"],1)
            self.assertEqual(report["rejected_due_to_schema"],0)

    def test_invalid_tail_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/"bad"
            f.write_bytes(self.fixture()+b"garbage")
            with self.assertRaises(BrokenXAnim):
                decode(f)

    def test_delta_is_rejected_not_invented(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/"delta"
            f.write_bytes(HEADER.pack(17,20,1,2,0,30)+b"padding")
            with self.assertRaisesRegex(BrokenXAnim,"root-delta"):
                decode(f)

if __name__=="__main__":
    unittest.main()
