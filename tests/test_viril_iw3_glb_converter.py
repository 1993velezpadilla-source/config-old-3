#!/usr/bin/env python3
"""Synthetic CC0 triangle GLB coverage; absolutely no proprietary game models."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "iwvm", ROOT/"scripts/iw3_glb_to_iwvm.py")
iwvm=importlib.util.module_from_spec(spec)
spec.loader.exec_module(iwvm)


def example_glb():
    positions=struct.pack("<9f",0,0,0, 1,0,0, 0,1,0)
    uv=struct.pack("<6f",0,0, 1,0, 0,1)
    indices=struct.pack("<3H",0,1,2)+b"\0\0"
    blob=positions+uv+indices
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":[
            {"buffer":0,"byteOffset":0,"byteLength":len(positions)},
            {"buffer":0,"byteOffset":len(positions),"byteLength":len(uv)},
            {"buffer":0,"byteOffset":len(positions)+len(uv),"byteLength":len(indices)}
        ],
        "accessors":[
            {"bufferView":0,"componentType":5126,"count":3,"type":"VEC3"},
            {"bufferView":1,"componentType":5126,"count":3,"type":"VEC2"},
            {"bufferView":2,"componentType":5123,"count":3,"type":"SCALAR"}
        ],
        "meshes":[{"primitives":[{
            "attributes":{"POSITION":0,"TEXCOORD_0":1},
            "indices":2,"mode":4
        }]}],
        "nodes":[{"mesh":0,"translation":[2,0,0]}],
        "scenes":[{"nodes":[0]}],"scene":0
    }
    raw=json.dumps(doc,separators=(",",":")).encode()
    raw+=b" " * ((-len(raw))%4)
    total=12+8+len(raw)+8+len(blob)
    return (
        struct.pack("<4sII",b"glTF",2,total)
        +struct.pack("<I4s",len(raw),b"JSON")+raw
        +struct.pack("<I4s",len(blob),b"BIN\0")+blob
    )


class IWVMGLBTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.path=Path(self.t.name)/"triangle.glb"
        self.path.write_bytes(example_glb())

    def test_static_mesh_positions_scene_transform(self):
        out,info=iwvm.convert(self.path,scale=1.0,axis="original")
        self.assertEqual(struct.unpack_from("<4sIII",out), (b"IWVM",1,3,3))
        v1=struct.unpack_from("<5f",out,16)
        self.assertEqual(v1[:3],(2.0,0.0,0.0))
        self.assertEqual(struct.unpack_from("<3H",out,16+3*20),(0,1,2))
        self.assertEqual(info["triangles"],1)
        self.assertFalse(info["skeleton_animation_supported"])

    def test_quake_coordinate_conversion(self):
        out,_=iwvm.convert(self.path)
        v=struct.unpack_from("<5f",out,16+20)
        self.assertEqual(v[:3],(0.0,-3.0,0.0))

    def test_truncated_blob_rejected(self):
        self.path.write_bytes(example_glb()[:-1])
        with self.assertRaises(ValueError):
            iwvm.convert(self.path)

    def test_bad_scale_rejected(self):
        with self.assertRaises(ValueError):
            iwvm.convert(self.path,scale=float("nan"))


if __name__=="__main__":
    unittest.main()
