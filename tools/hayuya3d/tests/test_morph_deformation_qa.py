from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.morph_deformation_qa import (
    audit_morph_deformation,
)


def _append(blob:bytearray,payload:bytes)->tuple[int,int]:
    while len(blob)%4:
        blob.append(0)
    offset=len(blob)
    blob.extend(payload)
    return offset,len(payload)


def build_morph_glb(
    path:Path,
    *,
    deltas:list[tuple[float,float,float]]|None=None,
    target_count:int=1,
    interpolation:str="LINEAR",
    weight_output:list[float]|None=None,
    include_animation:bool=True,
)->None:
    positions=[
        (-0.5,0.0,0.0),
        (0.5,0.0,0.0),
        (0.0,1.0,0.0),
    ]
    indices=[0,1,2]
    blob=bytearray()
    views=[]
    accessors=[]

    def add_accessor(rows,fmt,type_name,component_type):
        flat=[]
        for row in rows:
            if isinstance(row,(tuple,list)):
                flat.extend(row)
            else:
                flat.append(row)
        payload=b"".join(struct.pack(fmt,x) for x in flat)
        offset,length=_append(blob,payload)
        view_index=len(views)
        views.append({
            "buffer":0,
            "byteOffset":offset,
            "byteLength":length,
        })
        count=len(rows)
        accessor_index=len(accessors)
        accessors.append({
            "bufferView":view_index,
            "componentType":component_type,
            "count":count,
            "type":type_name,
        })
        return accessor_index

    position_accessor=add_accessor(
        positions,"<f","VEC3",5126
    )
    index_accessor=add_accessor(
        indices,"<H","SCALAR",5123
    )

    targets=[]
    for target_index in range(target_count):
        if deltas is None:
            target_deltas=[
                (0.0,0.0,0.0),
                (0.05*(target_index+1),0.0,0.0),
                (0.0,0.04*(target_index+1),0.0),
            ]
        else:
            target_deltas=list(deltas)
        delta_accessor=add_accessor(
            target_deltas,"<f","VEC3",5126
        )
        targets.append({"POSITION":delta_accessor})

    primitive={
        "attributes":{"POSITION":position_accessor},
        "indices":index_accessor,
        "targets":targets,
    }
    mesh={
        "primitives":[primitive],
        "weights":[0.0]*target_count,
    }
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":0}],
        "bufferViews":views,
        "accessors":accessors,
        "meshes":[mesh],
        "nodes":[{"mesh":0}],
        "scenes":[{"nodes":[0]}],
        "scene":0,
    }

    if include_animation:
        time_accessor=add_accessor(
            [0.0,1.0],"<f","SCALAR",5126
        )
        if weight_output is None:
            if interpolation=="CUBICSPLINE":
                # [in tangent, value, out tangent] for each key.
                values=[]
                for key in range(2):
                    values.extend(
                        [0.0]*target_count
                    )
                    values.extend(
                        ([0.0]*target_count if key==0 else [1.0]*target_count)
                    )
                    values.extend(
                        [0.0]*target_count
                    )
            else:
                values=[
                    0.0
                    for _ in range(target_count)
                ]+[
                    1.0
                    for _ in range(target_count)
                ]
        else:
            values=list(weight_output)
        weight_accessor=add_accessor(
            values,"<f","SCALAR",5126
        )
        doc["animations"]=[{
            "samplers":[{
                "input":time_accessor,
                "output":weight_accessor,
                "interpolation":interpolation,
            }],
            "channels":[{
                "sampler":0,
                "target":{"node":0,"path":"weights"},
            }],
        }]

    doc["buffers"][0]["byteLength"]=len(blob)
    write_glb(path,doc,bytes(blob))


def build_plain_glb(path:Path)->None:
    positions=[
        (-0.5,0.0,0.0),
        (0.5,0.0,0.0),
        (0.0,1.0,0.0),
    ]
    blob=bytearray()
    payload=b"".join(
        struct.pack("<3f",*row)
        for row in positions
    )
    off,length=_append(blob,payload)
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":[{
            "buffer":0,
            "byteOffset":off,
            "byteLength":length,
        }],
        "accessors":[{
            "bufferView":0,
            "componentType":5126,
            "count":3,
            "type":"VEC3",
        }],
        "meshes":[{
            "primitives":[{
                "attributes":{"POSITION":0},
                "mode":4,
            }],
        }],
        "nodes":[{"mesh":0}],
        "scenes":[{"nodes":[0]}],
        "scene":0,
    }
    write_glb(path,doc,bytes(blob))


class MorphDeformationQATests(unittest.TestCase):
    def test_valid_linear_morph_animation_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"valid.glb"
            build_morph_glb(path)
            report=audit_morph_deformation(path)
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.morph_targets,1)
            self.assertGreaterEqual(report.sampled_poses,4)
            self.assertEqual(report.catastrophic_poses,0)
            self.assertEqual(report.nonfinite_vertices,0)
            self.assertLess(report.max_displacement_ratio,1.0)

    def test_huge_target_delta_fails_even_without_animation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"huge.glb"
            build_morph_glb(
                path,
                deltas=[
                    (0.0,0.0,0.0),
                    (100.0,0.0,0.0),
                    (0.0,0.0,0.0),
                ],
                include_animation=False,
            )
            report=audit_morph_deformation(path)
            self.assertTrue(report.applicable)
            self.assertFalse(report.ready)
            self.assertTrue(
                any("delta explosion" in x for x in report.errors),
                report.errors,
            )
            self.assertGreater(report.max_displacement_ratio,5.0)

    def test_malformed_weight_output_count_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad-output.glb"
            build_morph_glb(
                path,
                target_count=2,
                weight_output=[0.0,1.0],
            )
            report=audit_morph_deformation(path)
            self.assertTrue(report.applicable)
            self.assertFalse(report.ready)
            self.assertTrue(
                any("scalar count mismatch" in x for x in report.errors),
                report.errors,
            )

    def test_cubic_tangent_overshoot_is_sampled_and_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"overshoot.glb"
            # 1 target, 2 keys:
            # key0: in=0, value=0, out=1000
            # key1: in=-1000, value=0, out=0
            build_morph_glb(
                path,
                interpolation="CUBICSPLINE",
                weight_output=[
                    0.0,0.0,1000.0,
                    -1000.0,0.0,0.0,
                ],
            )
            report=audit_morph_deformation(path)
            self.assertTrue(report.applicable)
            self.assertFalse(report.ready)
            self.assertTrue(
                any(
                    "displacement explosion" in x
                    for x in report.errors
                ),
                report.errors,
            )
            self.assertTrue(
                any(
                    "cubic" in pose.source and not pose.ready
                    for pose in report.poses
                ),
                [(pose.source,pose.errors) for pose in report.poses],
            )

    def test_no_morph_targets_is_clean_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"plain.glb"
            build_plain_glb(path)
            report=audit_morph_deformation(path)
            self.assertFalse(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.morph_targets,0)
            self.assertEqual(report.sampled_poses,0)


if __name__=="__main__":
    unittest.main()
