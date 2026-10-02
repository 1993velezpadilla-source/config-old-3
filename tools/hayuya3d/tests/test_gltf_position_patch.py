from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.hayuya3d.gltf_position_patch import (
    _doc_and_bin,
    mesh_nodes_identity_for_accessors,
    mesh_position_accessors,
    patch_position_accessors,
    read_position_accessor,
    runtime_payload_signature,
    skin_payload_signature,
)
from tools.hayuya3d.skin_weight_qa import audit_skin_weights


JSON_CHUNK=0x4E4F534A
BIN_CHUNK=0x004E4942


def pad4(data:bytes,pad:bytes)->bytes:
    while len(data)%4:
        data+=pad
    return data


def build_skinned_position_glb(path:Path, *, translated:bool=False)->None:
    positions=[
        (-0.5,0.0,0.0),
        (0.5,0.0,0.0),
        (0.0,1.0,0.0),
    ]
    joints=[
        (0,1,0,0),
        (0,1,0,0),
        (1,0,0,0),
    ]
    weights=[
        (0.75,0.25,0.0,0.0),
        (0.50,0.50,0.0,0.0),
        (1.00,0.00,0.0,0.0),
    ]

    pos_blob=b"".join(struct.pack("<3f",*row) for row in positions)
    joint_offset=len(pos_blob)
    joint_blob=b"".join(struct.pack("<4B",*row) for row in joints)
    weight_offset=joint_offset+len(joint_blob)
    weight_blob=b"".join(struct.pack("<4f",*row) for row in weights)
    binary=pad4(pos_blob+joint_blob+weight_blob,b"\x00")

    node={"mesh":0,"skin":0}
    if translated:
        node["translation"]=[1.0,0.0,0.0]

    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(binary)}],
        "bufferViews":[
            {"buffer":0,"byteOffset":0,"byteLength":len(pos_blob)},
            {"buffer":0,"byteOffset":joint_offset,"byteLength":len(joint_blob)},
            {"buffer":0,"byteOffset":weight_offset,"byteLength":len(weight_blob)},
        ],
        "accessors":[
            {
                "bufferView":0,
                "componentType":5126,
                "count":3,
                "type":"VEC3",
                "min":[-0.5,0.0,0.0],
                "max":[0.5,1.0,0.0],
            },
            {
                "bufferView":1,
                "componentType":5121,
                "count":3,
                "type":"VEC4",
            },
            {
                "bufferView":2,
                "componentType":5126,
                "count":3,
                "type":"VEC4",
            },
        ],
        "meshes":[{
            "primitives":[{
                "attributes":{
                    "POSITION":0,
                    "JOINTS_0":1,
                    "WEIGHTS_0":2,
                }
            }]
        }],
        "nodes":[node,{},{}],
        "skins":[{"joints":[1,2]}],
        "scenes":[{"nodes":[0,1,2]}],
        "scene":0,
    }
    raw_json=pad4(
        json.dumps(doc,separators=(",",":")).encode(),
        b" ",
    )
    total=12+8+len(raw_json)+8+len(binary)
    blob=bytearray(b"glTF")
    blob.extend(struct.pack("<II",2,total))
    blob.extend(struct.pack("<II",len(raw_json),JSON_CHUNK))
    blob.extend(raw_json)
    blob.extend(struct.pack("<II",len(binary),BIN_CHUNK))
    blob.extend(binary)
    path.write_bytes(bytes(blob))


class GLTFPositionPatchTests(unittest.TestCase):
    def test_position_patch_preserves_skin_payload_bit_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"source.glb"
            output=root/"patched.glb"
            build_skinned_position_glb(source)

            before=skin_payload_signature(source)
            runtime_before=runtime_payload_signature(source)
            positions=read_position_accessor(source,0)
            moved=[
                (x*1.1,y,z)
                for x,y,z in positions
            ]
            result=patch_position_accessors(
                source,
                output,
                {0:moved},
            )

            self.assertTrue(result.ready,result.error)
            self.assertTrue(result.skin_payload_preserved)
            self.assertEqual(result.skin_signature_before,before)
            self.assertEqual(result.skin_signature_after,before)
            self.assertEqual(
                runtime_payload_signature(output),
                runtime_before,
            )
            patched=read_position_accessor(output,0)
            self.assertEqual(len(patched),len(moved))
            for actual,expected in zip(patched,moved):
                for a,b in zip(actual,expected):
                    self.assertAlmostEqual(a,b,places=6)
            self.assertTrue(audit_skin_weights(output).ready)

            doc,_,_=_doc_and_bin(output)
            self.assertEqual(doc["accessors"][0]["min"],[-0.55,0.0,0.0])
            self.assertEqual(doc["accessors"][0]["max"],[0.55,1.0,0.0])

    def test_skinned_position_accessors_are_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"skin.glb"
            build_skinned_position_glb(path)
            doc,_,_=_doc_and_bin(path)
            self.assertEqual(
                mesh_position_accessors(doc,skinned_only=True),
                [0],
            )
            self.assertTrue(
                mesh_nodes_identity_for_accessors(doc,[0])
            )

    def test_non_identity_mesh_node_is_detected_for_safe_fusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"translated.glb"
            build_skinned_position_glb(path,translated=True)
            doc,_,_=_doc_and_bin(path)
            self.assertFalse(
                mesh_nodes_identity_for_accessors(doc,[0])
            )


if __name__=="__main__":
    unittest.main()
