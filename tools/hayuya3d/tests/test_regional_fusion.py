from __future__ import annotations

import json
import math
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import trimesh
from PIL import Image

from tools.hayuya3d.gltf_position_patch import skin_payload_signature
from tools.hayuya3d.regional_fusion import (
    build_head_wrap_geometry,
    prepare_head_wrap_challenger,
)
from tools.hayuya3d.skin_weight_qa import audit_skin_weights
from tools.hayuya3d.gltf_audit import audit_glb


def make_character(
    path:Path,
    *,
    head_scale:float=1.0,
    textured:bool=False,
    up_axis:str="y",
):
    mesh=trimesh.creation.icosphere(subdivisions=3,radius=1.0)
    vertices=np.asarray(mesh.vertices,dtype=np.float64).copy()
    # Make Y the character height axis.
    vertices[:,1]*=2.0
    low=float(vertices[:,1].min())
    high=float(vertices[:,1].max())
    norm=(vertices[:,1]-low)/max(high-low,1e-9)
    head=norm>=0.78
    vertices[head,0]*=head_scale
    vertices[head,2]*=head_scale
    if str(up_axis).lower()=="z":
        vertices=vertices[:,[0,2,1]]
    elif str(up_axis).lower()!="y":
        raise ValueError(f"unsupported fixture up_axis: {up_axis}")

    out=trimesh.Trimesh(
        vertices=vertices,
        faces=np.asarray(mesh.faces).copy(),
        process=False,
    )
    if textured:
        u=(vertices[:,0]-vertices[:,0].min())/max(
            float(vertices[:,0].max()-vertices[:,0].min()),
            1e-9,
        )
        v=(vertices[:,1]-vertices[:,1].min())/max(
            float(vertices[:,1].max()-vertices[:,1].min()),
            1e-9,
        )
        uv=np.stack([u,v],axis=1)
        image=Image.new("RGBA",(8,8),(40,80,120,255))
        material=trimesh.visual.texture.SimpleMaterial(image=image)
        out.visual=trimesh.visual.texture.TextureVisuals(
            uv=uv,
            material=material,
        )
    path.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(out)))



def _pad4(data:bytes,pad:bytes)->bytes:
    while len(data)%4:
        data+=pad
    return data


def make_skinned_character(
    path:Path,
    *,
    weight_pair:tuple[float,float]=(0.65,0.35),
)->None:
    positions=[]
    for i in range(40):
        y=-2.0+4.0*(i/39.0)
        radius=0.55 if y<0.8 else 0.38
        angle=(i%10)*(math.tau/10.0)
        positions.append((
            radius*math.cos(angle),
            y,
            radius*math.sin(angle),
        ))
    joints=[(0,1,0,0) for _ in positions]
    weights=[
        (float(weight_pair[0]),float(weight_pair[1]),0.0,0.0)
        for _ in positions
    ]

    pos_blob=b"".join(struct.pack("<3f",*row) for row in positions)
    pos_blob=_pad4(pos_blob,b"\x00")
    joints_offset=len(pos_blob)
    joint_blob=b"".join(struct.pack("<4B",*row) for row in joints)
    joint_blob=_pad4(joint_blob,b"\x00")
    weights_offset=joints_offset+len(joint_blob)
    weight_blob=b"".join(struct.pack("<4f",*row) for row in weights)
    binary=_pad4(pos_blob+joint_blob+weight_blob,b"\x00")

    count=len(positions)
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(binary)}],
        "bufferViews":[
            {"buffer":0,"byteOffset":0,"byteLength":len(pos_blob)},
            {
                "buffer":0,
                "byteOffset":joints_offset,
                "byteLength":len(joint_blob),
            },
            {
                "buffer":0,
                "byteOffset":weights_offset,
                "byteLength":len(weight_blob),
            },
        ],
        "accessors":[
            {
                "bufferView":0,
                "componentType":5126,
                "count":count,
                "type":"VEC3",
                "min":[min(x[i] for x in positions) for i in range(3)],
                "max":[max(x[i] for x in positions) for i in range(3)],
            },
            {
                "bufferView":1,
                "componentType":5121,
                "count":count,
                "type":"VEC4",
            },
            {
                "bufferView":2,
                "componentType":5126,
                "count":count,
                "type":"VEC4",
            },
        ],
        "meshes":[{
            "primitives":[{
                "attributes":{
                    "POSITION":0,
                    "JOINTS_0":1,
                    "WEIGHTS_0":2,
                },
                "mode":0,
            }]
        }],
        "nodes":[
            {"mesh":0,"skin":0},
            {"name":"root_joint"},
            {"name":"head_joint"},
        ],
        "skins":[{"joints":[1,2]}],
        "scenes":[{"nodes":[0,1,2]}],
        "scene":0,
    }
    raw_json=_pad4(
        json.dumps(doc,separators=(",",":")).encode("utf-8"),
        b" ",
    )
    total=12+8+len(raw_json)+8+len(binary)
    blob=bytearray(b"glTF")
    blob.extend(struct.pack("<II",2,total))
    blob.extend(struct.pack("<II",len(raw_json),0x4E4F534A))
    blob.extend(raw_json)
    blob.extend(struct.pack("<II",len(binary),0x004E4942))
    blob.extend(binary)
    path.write_bytes(bytes(blob))


class RegionalFusionTests(unittest.TestCase):
    def test_head_wrap_changes_head_with_soft_neck_and_bounded_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            output=root/"wrapped.glb"
            make_character(base,head_scale=1.0)
            make_character(donor,head_scale=1.18)

            result=build_head_wrap_geometry(
                base,
                donor,
                output,
            )
            self.assertTrue(result.attempted)
            self.assertTrue(result.geometry_ready,result.error)
            self.assertGreater(result.head_vertices,16)
            self.assertGreater(result.changed_vertices,0)
            self.assertTrue(output.is_file())
            self.assertEqual(output.read_bytes()[:4],b"glTF")
            self.assertIsNotNone(result.seam_max_displacement_normalized)
            self.assertIsNotNone(result.seam_max_displacement_normalized)
            self.assertLessEqual(
                float(result.seam_max_displacement_normalized),
                0.012,
            )
            self.assertIsNotNone(result.max_displacement_normalized)
            self.assertLessEqual(
                float(result.max_displacement_normalized),
                0.055001,
            )
            self.assertIsNotNone(result.bbox_drift_fraction)
            self.assertLessEqual(
                float(result.bbox_drift_fraction),
                0.08,
            )

    def test_head_wrap_remaps_z_up_donor_onto_y_up_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base-y-up.glb"
            donor=root/"donor-z-up.glb"
            output=root/"wrapped-axis-normalized.glb"
            make_character(base,head_scale=1.0,up_axis="y")
            make_character(donor,head_scale=1.14,up_axis="z")

            result=build_head_wrap_geometry(
                base,
                donor,
                output,
                up_axis="y",
            )
            self.assertTrue(result.geometry_ready,result.error)
            self.assertEqual(result.up_axis,1)
            self.assertEqual(result.donor_up_axis,2)
            self.assertTrue(result.donor_axis_remapped)
            self.assertGreater(
                float(result.donor_up_axis_confidence or 0.0),
                1.08,
            )
            self.assertGreater(result.changed_vertices,0)

    def test_textured_head_wrap_preserves_topology_and_uv_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base-textured.glb"
            donor=root/"donor.glb"
            output=root/"wrapped-textured.glb"
            make_character(base,head_scale=1.0,textured=True)
            make_character(donor,head_scale=1.12)

            result=build_head_wrap_geometry(
                base,
                donor,
                output,
            )
            self.assertTrue(result.geometry_ready,result.error)
            self.assertTrue(result.topology_preserved,result.error)
            self.assertTrue(result.uv_preserved,result.error)
            self.assertTrue(output.is_file())

    def test_untextured_fixture_needs_no_material_rebake(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            make_character(base,head_scale=1.0)
            make_character(donor,head_scale=1.10)

            result=prepare_head_wrap_challenger(
                base,
                donor,
                root/"fusion",
                texture_size=256,
            )
            self.assertTrue(result.geometry_ready,result.error)
            self.assertTrue(result.rebake_ready,result.error)
            self.assertTrue(result.ready_for_judge,result.error)
            self.assertEqual(result.rebake_required,[])
            self.assertTrue(Path(result.output_glb or "").is_file())

    def test_invalid_skin_weights_fail_closed_before_head_wrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"bad-skin.glb"
            donor=root/"donor.glb"
            output=root/"blocked.glb"
            make_skinned_character(
                base,
                weight_pair=(0.40,0.20),
            )
            make_character(donor,head_scale=1.1)

            before=audit_skin_weights(base)
            self.assertTrue(before.applicable)
            self.assertFalse(before.ready)

            result=build_head_wrap_geometry(
                base,
                donor,
                output,
                up_axis="y",
            )
            self.assertTrue(result.attempted)
            self.assertFalse(result.geometry_ready)
            self.assertFalse(result.ready_for_judge)
            self.assertIn("skin weights",result.error or "")
            self.assertFalse(output.exists())


    def test_skinned_head_wrap_preserves_joint_weight_payload_and_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"skinned.glb"
            donor=root/"donor.glb"
            output=root/"skinned-wrapped.glb"
            make_skinned_character(base)
            make_character(donor,head_scale=1.15)

            before_signature=skin_payload_signature(base)
            before_skin=audit_skin_weights(base)
            before_rig=audit_glb(base)
            self.assertTrue(before_skin.ready,before_skin.errors)
            self.assertTrue(before_rig.rig_ready,before_rig.errors)

            result=build_head_wrap_geometry(
                base,
                donor,
                output,
                up_axis="y",
            )
            self.assertTrue(result.attempted)
            self.assertTrue(result.geometry_ready,result.error)
            self.assertTrue(result.skin_payload_preserved,result.error)
            self.assertTrue(result.skin_runtime_ready,result.error)
            self.assertTrue(output.is_file())
            self.assertEqual(
                skin_payload_signature(output),
                before_signature,
            )

            after_skin=audit_skin_weights(output)
            after_rig=audit_glb(output)
            self.assertTrue(after_skin.ready,after_skin.errors)
            self.assertTrue(after_rig.rig_ready,after_rig.errors)
            self.assertEqual(
                after_skin.non_normalized_vertices,
                0,
            )
            self.assertEqual(after_skin.invalid_joint_references,0)
            self.assertEqual(after_rig.skin_count,before_rig.skin_count)
            self.assertEqual(after_rig.joint_count,before_rig.joint_count)

    def test_extreme_donor_is_clamped_not_allowed_to_explode_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"donor.glb"
            make_character(base,head_scale=1.0)
            make_character(donor,head_scale=3.0)

            result=build_head_wrap_geometry(
                base,
                donor,
                root/"wrapped.glb",
            )
            self.assertTrue(result.attempted)
            self.assertGreater(result.clamped_vertices,0)
            self.assertIsNotNone(result.max_displacement_normalized)
            self.assertLessEqual(
                float(result.max_displacement_normalized),
                0.055001,
            )
            # Clamp alone is not enough: an extreme donor can still fold
            # or collapse the head while staying inside displacement/bbox limits.
            # The deformation-quality gate must now fail closed.
            self.assertFalse(result.geometry_ready)
            self.assertFalse(result.ready_for_judge)
            self.assertTrue(
                any(
                    token in (result.error or "")
                    for token in (
                        "head_face_collapse_fraction",
                        "head_edge_stretch_fraction",
                        "head_face_flip_fraction",
                    )
                ),
                result.error,
            )
            self.assertIsNotNone(result.collapsed_face_fraction)
            self.assertIsNotNone(result.stretched_edge_fraction)
            self.assertIsNotNone(result.flipped_face_fraction)


if __name__=="__main__":
    unittest.main()
