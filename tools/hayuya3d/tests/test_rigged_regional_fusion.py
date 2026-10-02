from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.gltf_audit import audit_glb
from tools.hayuya3d.gltf_position_patch import skin_payload_signature
from tools.hayuya3d.regional_fusion import (
    build_rig_preserving_head_wrap_geometry,
    prepare_head_wrap_challenger,
)
from tools.hayuya3d.skin_weight_qa import audit_skin_weights


def _align(blob:bytearray)->int:
    while len(blob)%4:
        blob.append(0)
    return len(blob)


def build_skinned_character(path:Path, *, head_scale:float=1.0)->None:
    source=trimesh.creation.icosphere(subdivisions=3,radius=1.0)
    vertices=np.asarray(source.vertices,dtype=np.float32).copy()
    vertices[:,1]*=2.0
    lo=float(vertices[:,1].min())
    hi=float(vertices[:,1].max())
    norm=(vertices[:,1]-lo)/max(hi-lo,1e-9)
    head=norm>=0.78
    vertices[head,0]*=head_scale
    vertices[head,2]*=head_scale

    faces=np.asarray(source.faces,dtype=np.uint16)
    count=len(vertices)
    joints=np.zeros((count,4),dtype=np.uint8)
    weights=np.zeros((count,4),dtype=np.float32)
    weights[:,0]=1.0

    blob=bytearray()
    pos_offset=_align(blob)
    pos_bytes=vertices.astype("<f4").tobytes()
    blob.extend(pos_bytes)
    joint_offset=_align(blob)
    joint_bytes=joints.tobytes()
    blob.extend(joint_bytes)
    weight_offset=_align(blob)
    weight_bytes=weights.astype("<f4").tobytes()
    blob.extend(weight_bytes)
    index_offset=_align(blob)
    index_bytes=faces.astype("<u2").reshape(-1).tobytes()
    blob.extend(index_bytes)

    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":[
            {"buffer":0,"byteOffset":pos_offset,"byteLength":len(pos_bytes)},
            {"buffer":0,"byteOffset":joint_offset,"byteLength":len(joint_bytes)},
            {"buffer":0,"byteOffset":weight_offset,"byteLength":len(weight_bytes)},
            {"buffer":0,"byteOffset":index_offset,"byteLength":len(index_bytes)},
        ],
        "accessors":[
            {
                "bufferView":0,"componentType":5126,
                "count":count,"type":"VEC3",
                "min":vertices.min(axis=0).astype(float).tolist(),
                "max":vertices.max(axis=0).astype(float).tolist(),
            },
            {
                "bufferView":1,"componentType":5121,
                "count":count,"type":"VEC4",
            },
            {
                "bufferView":2,"componentType":5126,
                "count":count,"type":"VEC4",
            },
            {
                "bufferView":3,"componentType":5123,
                "count":int(faces.size),"type":"SCALAR",
            },
        ],
        "meshes":[{
            "primitives":[{
                "attributes":{
                    "POSITION":0,
                    "JOINTS_0":1,
                    "WEIGHTS_0":2,
                },
                "indices":3,
            }]
        }],
        "nodes":[
            {"mesh":0,"skin":0},
            {},
            {},
        ],
        "skins":[{"joints":[1,2]}],
        "scenes":[{"nodes":[0,1,2]}],
        "scene":0,
    }
    write_glb(path,doc,bytes(blob))


class RiggedRegionalFusionTests(unittest.TestCase):
    def test_rigged_head_wrap_preserves_skin_payload_and_weight_validity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            wrapped=root/"wrapped.glb"
            build_skinned_character(base,head_scale=1.0)
            build_skinned_character(donor,head_scale=1.16)

            before=skin_payload_signature(base)
            self.assertTrue(audit_glb(base).rig_ready)
            self.assertTrue(audit_skin_weights(base).ready)

            result=build_rig_preserving_head_wrap_geometry(
                base,
                donor,
                wrapped,
                up_axis="y",
            )
            self.assertTrue(result.geometry_ready,result.error)
            self.assertTrue(result.rig_preserved,result.error)
            self.assertTrue(result.skin_weights_ready,result.error)
            self.assertTrue(result.skin_payload_preserved,result.error)
            self.assertGreater(result.changed_vertices,0)
            self.assertEqual(before,skin_payload_signature(wrapped))
            self.assertTrue(audit_glb(wrapped).rig_ready)
            self.assertTrue(audit_skin_weights(wrapped).ready)

    def test_prepare_rigged_untextured_head_wrap_is_judge_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            build_skinned_character(base,head_scale=1.0)
            build_skinned_character(donor,head_scale=1.10)

            result=prepare_head_wrap_challenger(
                base,
                donor,
                root/"fusion",
                texture_size=256,
                up_axis="y",
            )
            self.assertTrue(result.geometry_ready,result.error)
            self.assertTrue(result.rebake_ready,result.error)
            self.assertTrue(result.ready_for_judge,result.error)
            self.assertTrue(result.rig_preserved,result.error)
            self.assertTrue(result.skin_weights_ready,result.error)
            self.assertEqual(result.rebake_required,[])


if __name__=="__main__":
    unittest.main()
