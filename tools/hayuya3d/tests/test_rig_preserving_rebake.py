from __future__ import annotations

import io
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
HAYUYA_DIR=ROOT/"tools"/"hayuya3d"
sys.path.insert(0,str(HAYUYA_DIR))

import material_rebake

from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.gltf_audit import audit_glb
from tools.hayuya3d.gltf_position_patch import skin_payload_signature
from tools.hayuya3d.rig_preserving_rebake import (
    rebake_material_channels_preserve_rig,
)
from tools.hayuya3d.skin_weight_qa import audit_skin_weights
from tools.hayuya3d.texture_gate import embedded_images


def _append(blob:bytearray,payload:bytes)->tuple[int,int]:
    while len(blob)%4:
        blob.append(0)
    offset=len(blob)
    blob.extend(payload)
    return offset,len(payload)


def _png(color:tuple[int,int,int])->bytes:
    buf=io.BytesIO()
    Image.new("RGB",(8,8),color).save(buf,format="PNG")
    return buf.getvalue()


def build_skinned_normal_glb(
    path:Path,
    *,
    normal_color:tuple[int,int,int],
)->None:
    positions=(
        (-0.5,0.0,0.0),
        (0.5,0.0,0.0),
        (0.0,1.0,0.0),
    )
    joints=((0,1,0,0),(0,1,0,0),(1,0,0,0))
    weights=(
        (0.75,0.25,0.0,0.0),
        (0.50,0.50,0.0,0.0),
        (1.00,0.00,0.0,0.0),
    )
    indices=(0,1,2)
    normal=_png(normal_color)

    blob=bytearray()
    pos_off,pos_len=_append(
        blob,b"".join(struct.pack("<3f",*row) for row in positions)
    )
    joint_off,joint_len=_append(
        blob,b"".join(struct.pack("<4B",*row) for row in joints)
    )
    weight_off,weight_len=_append(
        blob,b"".join(struct.pack("<4f",*row) for row in weights)
    )
    index_off,index_len=_append(
        blob,b"".join(struct.pack("<H",value) for value in indices)
    )
    image_off,image_len=_append(blob,normal)

    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":[
            {"buffer":0,"byteOffset":pos_off,"byteLength":pos_len},
            {"buffer":0,"byteOffset":joint_off,"byteLength":joint_len},
            {"buffer":0,"byteOffset":weight_off,"byteLength":weight_len},
            {"buffer":0,"byteOffset":index_off,"byteLength":index_len},
            {"buffer":0,"byteOffset":image_off,"byteLength":image_len},
        ],
        "accessors":[
            {
                "bufferView":0,"componentType":5126,
                "count":3,"type":"VEC3",
                "min":[-0.5,0.0,0.0],
                "max":[0.5,1.0,0.0],
            },
            {
                "bufferView":1,"componentType":5121,
                "count":3,"type":"VEC4",
            },
            {
                "bufferView":2,"componentType":5126,
                "count":3,"type":"VEC4",
            },
            {
                "bufferView":3,"componentType":5123,
                "count":3,"type":"SCALAR",
            },
        ],
        "images":[{"bufferView":4,"mimeType":"image/png"}],
        "textures":[{"source":0}],
        "materials":[{
            "normalTexture":{"index":0},
            "pbrMetallicRoughness":{
                "baseColorFactor":[0.6,0.5,0.4,1.0],
                "roughnessFactor":0.7,
                "metallicFactor":0.0,
            },
        }],
        "meshes":[{
            "primitives":[{
                "attributes":{
                    "POSITION":0,
                    "JOINTS_0":1,
                    "WEIGHTS_0":2,
                },
                "indices":3,
                "material":0,
            }]
        }],
        "nodes":[{"mesh":0,"skin":0},{},{}],
        "skins":[{"joints":[1,2]}],
        "scenes":[{"nodes":[0,1,2]}],
        "scene":0,
    }
    write_glb(path,doc,bytes(blob))


def _normal_bytes(path:Path)->bytes:
    matches=[
        data
        for index,mime,data,roles in embedded_images(path)
        if "normal" in set(roles or [])
    ]
    if len(matches)!=1:
        raise AssertionError(f"expected one normal image, got {len(matches)}")
    return matches[0]


class RigPreservingRebakeTests(unittest.TestCase):
    def test_rebaked_normal_is_imported_without_touching_skin_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            target=root/"target.glb"
            baked=root/"baked.glb"
            output=root/"output.glb"
            build_skinned_normal_glb(
                target,
                normal_color=(128,128,255),
            )
            build_skinned_normal_glb(
                baked,
                normal_color=(150,110,245),
            )

            before_signature=skin_payload_signature(target)
            before_normal=_normal_bytes(target)
            baked_normal=_normal_bytes(baked)
            self.assertNotEqual(before_normal,baked_normal)
            self.assertTrue(audit_glb(target).rig_ready)
            self.assertTrue(audit_skin_weights(target).ready)

            def fake_rebake(
                source_mesh,
                target_mesh,
                output_glb,
                *,
                required,
                max_texture_size,
                blender=None,
            ):
                output_glb.write_bytes(baked.read_bytes())
                return SimpleNamespace(
                    resolved_channels=["normal"],
                    report=None,
                )

            with mock.patch.object(
                material_rebake,
                "rebake_material_channels",
                side_effect=fake_rebake,
            ):
                result=rebake_material_channels_preserve_rig(
                    target,
                    target,
                    output,
                    required=["normal"],
                    max_texture_size=256,
                )

            self.assertTrue(result.ready,result.error)
            self.assertTrue(result.skin_payload_preserved,result.error)
            self.assertTrue(result.rig_preserved,result.error)
            self.assertTrue(result.skin_weights_ready,result.error)
            self.assertEqual(result.remaining_channels,[])
            self.assertEqual(result.resolved_channels,["normal"])
            self.assertEqual(
                skin_payload_signature(output),
                before_signature,
            )
            self.assertEqual(_normal_bytes(output),baked_normal)
            self.assertTrue(audit_glb(output).rig_ready)
            self.assertTrue(audit_skin_weights(output).ready)

    def test_no_requested_channels_is_identity_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            target=root/"target.glb"
            output=root/"output.glb"
            build_skinned_normal_glb(
                target,
                normal_color=(128,128,255),
            )
            result=rebake_material_channels_preserve_rig(
                target,
                target,
                output,
                required=[],
                max_texture_size=256,
            )
            self.assertTrue(result.ready,result.error)
            self.assertEqual(output.read_bytes(),target.read_bytes())


if __name__=="__main__":
    unittest.main()
