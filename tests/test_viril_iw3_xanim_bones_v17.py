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
            self.assertEqual(report["decoded_all_bones_and_root_delta"],1)
            self.assertEqual(report["rejected_due_to_schema"],0)

    def test_invalid_tail_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/"bad"
            f.write_bytes(self.fixture()+b"garbage")
            with self.assertRaises(BrokenXAnim):
                decode(f)

    def test_genuine_iw3_root_delta_quaternion2_and_position(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/"delta"
            # Flags=2 means original CoD4 delta: first quat2 track,
            # then root trans; both zero => constant/no displacement.
            f.write_bytes(HEADER.pack(17,20,0,2,0,30)
                +struct.pack("<HH",0,0)+b"\\x00")
            decoded=decode(f)
            self.assertEqual(decoded["root_delta"]["rotation"]["kind"],"identity")
            self.assertEqual(decoded["root_delta"]["position"]["kind"],"none")
            self.assertEqual(decoded["frames"],20)

if __name__=="__main__":
    unittest.main()
