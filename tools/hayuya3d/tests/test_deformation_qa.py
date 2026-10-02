from __future__ import annotations

import math
import struct
import tempfile
import unittest
from pathlib import Path

from tools.hayuya3d.deformation_qa import audit_deformation
from tools.hayuya3d.glb_images import write_glb


def _append(blob:bytearray,payload:bytes)->tuple[int,int]:
    while len(blob)%4:
        blob.append(0)
    offset=len(blob)
    blob.extend(payload)
    return offset,len(payload)


def build_skinned_animation_glb(
    path:Path,
    *,
    end_translation:tuple[float,float,float]=(0.5,0.0,0.0),
)->None:
    positions=(
        (-0.5,0.0,0.0),
        (0.5,0.0,0.0),
        (0.0,1.0,0.0),
    )
    indices=(0,1,2)
    joints=((0,0,0,0),)*3
    weights=((1.0,0.0,0.0,0.0),)*3
    times=(0.0,1.0)
    translations=((0.0,0.0,0.0),end_translation)

    blob=bytearray()
    pos_off,pos_len=_append(
        blob,b"".join(struct.pack("<3f",*row) for row in positions)
    )
    idx_off,idx_len=_append(
        blob,b"".join(struct.pack("<H",x) for x in indices)
    )
    joint_off,joint_len=_append(
        blob,b"".join(struct.pack("<4B",*row) for row in joints)
    )
    weight_off,weight_len=_append(
        blob,b"".join(struct.pack("<4f",*row) for row in weights)
    )
    time_off,time_len=_append(
        blob,b"".join(struct.pack("<f",x) for x in times)
    )
    trans_off,trans_len=_append(
        blob,b"".join(struct.pack("<3f",*row) for row in translations)
    )

    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":[
            {"buffer":0,"byteOffset":pos_off,"byteLength":pos_len},
            {"buffer":0,"byteOffset":idx_off,"byteLength":idx_len},
            {"buffer":0,"byteOffset":joint_off,"byteLength":joint_len},
            {"buffer":0,"byteOffset":weight_off,"byteLength":weight_len},
            {"buffer":0,"byteOffset":time_off,"byteLength":time_len},
            {"buffer":0,"byteOffset":trans_off,"byteLength":trans_len},
        ],
        "accessors":[
            {
                "bufferView":0,"componentType":5126,
                "count":3,"type":"VEC3",
                "min":[-0.5,0.0,0.0],
                "max":[0.5,1.0,0.0],
            },
            {
                "bufferView":1,"componentType":5123,
                "count":3,"type":"SCALAR",
            },
            {
                "bufferView":2,"componentType":5121,
                "count":3,"type":"VEC4",
            },
            {
                "bufferView":3,"componentType":5126,
                "count":3,"type":"VEC4",
            },
            {
                "bufferView":4,"componentType":5126,
                "count":2,"type":"SCALAR",
            },
            {
                "bufferView":5,"componentType":5126,
                "count":2,"type":"VEC3",
            },
        ],
        "meshes":[{
            "primitives":[{
                "attributes":{
                    "POSITION":0,
                    "JOINTS_0":2,
                    "WEIGHTS_0":3,
                },
                "indices":1,
            }]
        }],
        "nodes":[
            {"mesh":0,"skin":0},
            {"name":"root_joint"},
        ],
        "skins":[{"joints":[1]}],
        "animations":[{
            "samplers":[{
                "input":4,
                "output":5,
                "interpolation":"LINEAR",
            }],
            "channels":[{
                "sampler":0,
                "target":{"node":1,"path":"translation"},
            }],
        }],
        "scenes":[{"nodes":[0,1]}],
        "scene":0,
    }
    write_glb(path,doc,bytes(blob))


class DeformationQATests(unittest.TestCase):
    def test_valid_rigid_bone_motion_preserves_mesh_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"valid.glb"
            build_skinned_animation_glb(
                path,
                end_translation=(0.5,0.0,0.0),
            )
            report=audit_deformation(path)
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.animation_count,1)
            self.assertGreaterEqual(report.sampled_frames,2)
            self.assertEqual(report.nonfinite_vertices,0)
            self.assertLess(report.max_displacement_ratio,1.0)
            self.assertAlmostEqual(
                report.max_edge_stretch_ratio,
                1.0,
                places=5,
            )
            self.assertAlmostEqual(
                report.min_edge_stretch_ratio,
                1.0,
                places=5,
            )

    def test_catastrophic_bone_translation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"exploded.glb"
            build_skinned_animation_glb(
                path,
                end_translation=(100.0,0.0,0.0),
            )
            report=audit_deformation(path)
            self.assertFalse(report.ready)
            self.assertGreater(report.catastrophic_frames,0)
            self.assertGreater(report.max_displacement_ratio,25.0)
            self.assertTrue(
                any("displacement explosion" in item for item in report.errors),
                report.errors,
            )

    def test_nonfinite_animated_transform_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"nan.glb"
            build_skinned_animation_glb(
                path,
                end_translation=(float("nan"),0.0,0.0),
            )
            report=audit_deformation(path)
            self.assertFalse(report.ready)
            self.assertGreater(report.catastrophic_frames,0)
            self.assertTrue(report.errors)

    def test_asset_without_skin_or_animation_is_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"plain.glb"
            # Reuse the fixture then strip applicability by building no animation
            # would require binary surgery; use an empty valid GLB instead.
            write_glb(
                path,
                {
                    "asset":{"version":"2.0"},
                    "buffers":[{"byteLength":0}],
                    "nodes":[],
                    "meshes":[],
                    "scenes":[{"nodes":[]}],
                    "scene":0,
                },
                b"",
            )
            report=audit_deformation(path)
            self.assertFalse(report.applicable)
            self.assertFalse(report.ready)


if __name__=="__main__":
    unittest.main()
