from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.hayuya3d.skin_weight_qa import audit_skin_weights


JSON_CHUNK=0x4E4F534A
BIN_CHUNK=0x004E4942


def _pad4(data:bytes,pad:bytes)->bytes:
    while len(data)%4:
        data+=pad
    return data


def build_skin_glb(
    path:Path,
    *,
    joints:list[tuple[int,int,int,int]],
    weights:list[tuple[float,float,float,float]],
)->None:
    if len(joints)!=len(weights):
        raise ValueError("joint/weight rows must match")

    joint_blob=b"".join(struct.pack("<4B",*row) for row in joints)
    while len(joint_blob)%4:
        joint_blob+=b"\x00"
    weight_offset=len(joint_blob)
    weight_blob=b"".join(struct.pack("<4f",*row) for row in weights)
    binary=_pad4(joint_blob+weight_blob,b"\x00")

    count=len(joints)
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(binary)}],
        "bufferViews":[
            {
                "buffer":0,
                "byteOffset":0,
                "byteLength":len(joint_blob),
            },
            {
                "buffer":0,
                "byteOffset":weight_offset,
                "byteLength":len(weight_blob),
            },
        ],
        "accessors":[
            {
                "bufferView":0,
                "componentType":5121,
                "count":count,
                "type":"VEC4",
            },
            {
                "bufferView":1,
                "componentType":5126,
                "count":count,
                "type":"VEC4",
            },
        ],
        "meshes":[{
            "primitives":[{
                "attributes":{
                    "JOINTS_0":0,
                    "WEIGHTS_0":1,
                }
            }]
        }],
        "nodes":[
            {"mesh":0,"skin":0},
            {},
            {},
        ],
        "skins":[{
            "joints":[1,2],
        }],
        "scenes":[{"nodes":[0,1,2]}],
        "scene":0,
    }

    raw_json=json.dumps(doc,separators=(",",":")).encode("utf-8")
    json_chunk=_pad4(raw_json,b" ")
    total=12+8+len(json_chunk)+8+len(binary)
    blob=bytearray()
    blob.extend(b"glTF")
    blob.extend(struct.pack("<II",2,total))
    blob.extend(struct.pack("<II",len(json_chunk),JSON_CHUNK))
    blob.extend(json_chunk)
    blob.extend(struct.pack("<II",len(binary),BIN_CHUNK))
    blob.extend(binary)
    path.write_bytes(bytes(blob))


class SkinWeightQATests(unittest.TestCase):
    def test_valid_normalized_weights_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"valid.glb"
            build_skin_glb(
                path,
                joints=[
                    (0,1,0,0),
                    (1,0,0,0),
                    (0,1,0,0),
                ],
                weights=[
                    (0.70,0.30,0.0,0.0),
                    (1.00,0.00,0.0,0.0),
                    (0.25,0.75,0.0,0.0),
                ],
            )
            report=audit_skin_weights(path)
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.weighted_vertices,3)
            self.assertEqual(report.zero_weight_vertices,0)
            self.assertEqual(report.non_normalized_vertices,0)
            self.assertEqual(report.invalid_joint_references,0)
            self.assertEqual(report.max_influences,2)

    def test_non_normalized_weight_sum_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad-sum.glb"
            build_skin_glb(
                path,
                joints=[(0,1,0,0)],
                weights=[(0.40,0.20,0.0,0.0)],
            )
            report=audit_skin_weights(path)
            self.assertFalse(report.ready)
            self.assertEqual(report.non_normalized_vertices,1)

    def test_active_invalid_joint_reference_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad-joint.glb"
            build_skin_glb(
                path,
                joints=[(0,7,0,0)],
                weights=[(0.50,0.50,0.0,0.0)],
            )
            report=audit_skin_weights(path)
            self.assertFalse(report.ready)
            self.assertEqual(report.invalid_joint_references,1)

    def test_zero_weight_vertex_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"zero.glb"
            build_skin_glb(
                path,
                joints=[(0,1,0,0)],
                weights=[(0.0,0.0,0.0,0.0)],
            )
            report=audit_skin_weights(path)
            self.assertFalse(report.ready)
            self.assertEqual(report.zero_weight_vertices,1)

    def test_unskinned_glb_is_not_applicable_not_false_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"unskinned.glb"
            build_skin_glb(
                path,
                joints=[(0,1,0,0)],
                weights=[(1.0,0.0,0.0,0.0)],
            )
            blob=path.read_bytes()
            # Build a clean non-skinned fixture instead of mutating binary offsets.
            doc={
                "asset":{"version":"2.0"},
                "buffers":[{"byteLength":0}],
                "meshes":[{"primitives":[{"attributes":{}}]}],
                "nodes":[{"mesh":0}],
                "scenes":[{"nodes":[0]}],
                "scene":0,
            }
            raw=json.dumps(doc,separators=(",",":")).encode()
            json_chunk=_pad4(raw,b" ")
            binary=b""
            total=12+8+len(json_chunk)+8
            out=bytearray(b"glTF")
            out.extend(struct.pack("<II",2,total))
            out.extend(struct.pack("<II",len(json_chunk),JSON_CHUNK))
            out.extend(json_chunk)
            out.extend(struct.pack("<II",0,BIN_CHUNK))
            path.write_bytes(bytes(out))

            report=audit_skin_weights(path)
            self.assertFalse(report.applicable)
            self.assertFalse(report.ready)


if __name__=="__main__":
    unittest.main()
