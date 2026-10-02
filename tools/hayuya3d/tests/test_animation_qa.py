from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from tools.hayuya3d.animation_qa import audit_animation
from tools.hayuya3d.glb_images import write_glb


def _append(blob:bytearray,payload:bytes)->tuple[int,int]:
    while len(blob)%4:
        blob.append(0)
    offset=len(blob)
    blob.extend(payload)
    return offset,len(payload)


def build_animation_glb(
    path:Path,
    *,
    times:tuple[float,...]=(0.0,1.0),
    rotations:tuple[tuple[float,float,float,float],...]=(
        (0.0,0.0,0.0,1.0),
        (0.0,0.7071068,0.0,0.7071068),
    ),
    interpolation:str="LINEAR",
    duplicate_channel:bool=False,
)->None:
    positions=(
        (-0.5,0.0,0.0),
        (0.5,0.0,0.0),
        (0.0,1.0,0.0),
    )
    blob=bytearray()
    pos_off,pos_len=_append(
        blob,
        b"".join(struct.pack("<3f",*row) for row in positions),
    )
    time_off,time_len=_append(
        blob,
        b"".join(struct.pack("<f",x) for x in times),
    )
    rot_off,rot_len=_append(
        blob,
        b"".join(struct.pack("<4f",*row) for row in rotations),
    )

    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":[
            {"buffer":0,"byteOffset":pos_off,"byteLength":pos_len},
            {"buffer":0,"byteOffset":time_off,"byteLength":time_len},
            {"buffer":0,"byteOffset":rot_off,"byteLength":rot_len},
        ],
        "accessors":[
            {
                "bufferView":0,
                "componentType":5126,
                "count":len(positions),
                "type":"VEC3",
                "min":[-0.5,0.0,0.0],
                "max":[0.5,1.0,0.0],
            },
            {
                "bufferView":1,
                "componentType":5126,
                "count":len(times),
                "type":"SCALAR",
            },
            {
                "bufferView":2,
                "componentType":5126,
                "count":len(rotations),
                "type":"VEC4",
            },
        ],
        "meshes":[{
            "primitives":[{
                "attributes":{"POSITION":0},
                "mode":4,
            }]
        }],
        "nodes":[{"mesh":0}],
        "animations":[{
            "samplers":[{
                "input":1,
                "output":2,
                "interpolation":interpolation,
            }],
            "channels":[
                {
                    "sampler":0,
                    "target":{"node":0,"path":"rotation"},
                },
                *(
                    [{
                        "sampler":0,
                        "target":{"node":0,"path":"rotation"},
                    }]
                    if duplicate_channel else []
                ),
            ],
        }],
        "scenes":[{"nodes":[0]}],
        "scene":0,
    }
    write_glb(path,doc,bytes(blob))


class AnimationQATests(unittest.TestCase):
    def test_valid_rotation_clip_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"valid.glb"
            build_animation_glb(path)
            report=audit_animation(path)
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.animation_count,1)
            self.assertEqual(report.channel_count,1)
            self.assertEqual(report.total_keyframes,2)
            self.assertEqual(report.rotation_channels,1)

    def test_non_monotonic_timestamps_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad-time.glb"
            build_animation_glb(
                path,
                times=(0.0,0.0),
            )
            report=audit_animation(path)
            self.assertFalse(report.ready)
            self.assertTrue(
                any("strictly increasing" in item for item in report.errors),
                report.errors,
            )

    def test_non_normalized_rotation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad-quat.glb"
            build_animation_glb(
                path,
                rotations=(
                    (0.0,0.0,0.0,1.0),
                    (0.0,2.0,0.0,0.0),
                ),
            )
            report=audit_animation(path)
            self.assertFalse(report.ready)
            self.assertTrue(
                any("not normalized" in item for item in report.errors),
                report.errors,
            )

    def test_duplicate_target_channel_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"duplicate.glb"
            build_animation_glb(
                path,
                duplicate_channel=True,
            )
            report=audit_animation(path)
            self.assertFalse(report.ready)
            self.assertTrue(
                any("duplicate target" in item for item in report.errors),
                report.errors,
            )

    def test_cubic_rotation_checks_values_not_tangents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"cubic.glb"
            rotations=(
                (9.0,0.0,0.0,0.0),
                (0.0,0.0,0.0,1.0),
                (7.0,0.0,0.0,0.0),
                (5.0,0.0,0.0,0.0),
                (0.0,0.7071068,0.0,0.7071068),
                (4.0,0.0,0.0,0.0),
            )
            build_animation_glb(
                path,
                rotations=rotations,
                interpolation="CUBICSPLINE",
            )
            report=audit_animation(path)
            self.assertTrue(report.ready,report.errors)


if __name__=="__main__":
    unittest.main()
