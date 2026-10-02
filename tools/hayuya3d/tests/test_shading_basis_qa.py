from __future__ import annotations

import io
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.shading_basis_qa import audit_shading_basis


def _append(blob:bytearray,payload:bytes)->tuple[int,int]:
    while len(blob)%4:
        blob.append(0)
    offset=len(blob)
    blob.extend(payload)
    return offset,len(payload)


def _png()->bytes:
    buf=io.BytesIO()
    Image.new("RGB",(4,4),(128,128,255)).save(buf,format="PNG")
    return buf.getvalue()


def build_glb(
    path:Path,
    *,
    normal=(0.0,0.0,1.0),
    tangent=(1.0,0.0,0.0,1.0),
    include_tangent:bool=True,
    normal_map:bool=True,
)->None:
    positions=(
        (-0.5,0.0,0.0),
        (0.5,0.0,0.0),
        (0.0,1.0,0.0),
    )
    normals=(normal,normal,normal)
    tangents=(tangent,tangent,tangent)
    indices=(0,1,2)

    blob=bytearray()
    pos_off,pos_len=_append(
        blob,b"".join(struct.pack("<3f",*row) for row in positions)
    )
    normal_off,normal_len=_append(
        blob,b"".join(struct.pack("<3f",*row) for row in normals)
    )
    tangent_off=tangent_len=None
    if include_tangent:
        tangent_off,tangent_len=_append(
            blob,b"".join(struct.pack("<4f",*row) for row in tangents)
        )
    index_off,index_len=_append(
        blob,b"".join(struct.pack("<H",x) for x in indices)
    )
    image_off=image_len=None
    if normal_map:
        image_off,image_len=_append(blob,_png())

    views=[
        {"buffer":0,"byteOffset":pos_off,"byteLength":pos_len},
        {"buffer":0,"byteOffset":normal_off,"byteLength":normal_len},
    ]
    accessors=[
        {
            "bufferView":0,"componentType":5126,
            "count":3,"type":"VEC3",
            "min":[-0.5,0.0,0.0],
            "max":[0.5,1.0,0.0],
        },
        {
            "bufferView":1,"componentType":5126,
            "count":3,"type":"VEC3",
        },
    ]
    attrs={"POSITION":0,"NORMAL":1}

    if include_tangent:
        views.append({
            "buffer":0,
            "byteOffset":tangent_off,
            "byteLength":tangent_len,
        })
        attrs["TANGENT"]=len(accessors)
        accessors.append({
            "bufferView":len(views)-1,
            "componentType":5126,
            "count":3,
            "type":"VEC4",
        })

    views.append({
        "buffer":0,
        "byteOffset":index_off,
        "byteLength":index_len,
    })
    index_accessor=len(accessors)
    accessors.append({
        "bufferView":len(views)-1,
        "componentType":5123,
        "count":3,
        "type":"SCALAR",
    })

    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":views,
        "accessors":accessors,
        "meshes":[{
            "primitives":[{
                "attributes":attrs,
                "indices":index_accessor,
                "material":0,
            }]
        }],
        "nodes":[{"mesh":0}],
        "scenes":[{"nodes":[0]}],
        "scene":0,
    }

    if normal_map:
        views.append({
            "buffer":0,
            "byteOffset":image_off,
            "byteLength":image_len,
        })
        doc["images"]=[{
            "bufferView":len(views)-1,
            "mimeType":"image/png",
        }]
        doc["textures"]=[{"source":0}]
        doc["materials"]=[{
            "normalTexture":{"index":0},
            "pbrMetallicRoughness":{
                "baseColorFactor":[1,1,1,1],
                "metallicFactor":0.0,
                "roughnessFactor":0.7,
            },
        }]
    else:
        doc["materials"]=[{
            "pbrMetallicRoughness":{
                "baseColorFactor":[1,1,1,1],
                "metallicFactor":0.0,
                "roughnessFactor":0.7,
            },
        }]

    # write_glb uses the supplied bufferViews by reference, so append the image
    # view before serialization and keep byteLength synchronized.
    doc["buffers"][0]["byteLength"]=len(blob)
    write_glb(path,doc,bytes(blob))


class ShadingBasisQATests(unittest.TestCase):
    def test_valid_normal_mapped_basis_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"valid.glb"
            build_glb(path)
            report=audit_shading_basis(path)
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.normal_mapped_primitives,1)
            self.assertEqual(report.explicit_tangent_primitives,1)
            self.assertEqual(report.invalid_handedness,0)
            self.assertEqual(report.nonorthogonal_tangents,0)

    def test_normal_map_without_explicit_tangent_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"missing-tangent.glb"
            build_glb(path,include_tangent=False)
            report=audit_shading_basis(path)
            self.assertFalse(report.ready)
            self.assertEqual(report.missing_required_tangents,1)
            self.assertTrue(
                any("TANGENT" in item for item in report.errors),
                report.errors,
            )

    def test_nonunit_normal_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad-normal.glb"
            build_glb(path,normal=(0.0,0.0,2.0))
            report=audit_shading_basis(path)
            self.assertFalse(report.ready)
            self.assertGreater(report.nonunit_vectors,0)

    def test_parallel_tangent_and_normal_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad-ortho.glb"
            build_glb(
                path,
                tangent=(0.0,0.0,1.0,1.0),
            )
            report=audit_shading_basis(path)
            self.assertFalse(report.ready)
            self.assertGreater(report.nonorthogonal_tangents,0)

    def test_invalid_tangent_handedness_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad-hand.glb"
            build_glb(
                path,
                tangent=(1.0,0.0,0.0,0.0),
            )
            report=audit_shading_basis(path)
            self.assertFalse(report.ready)
            self.assertGreater(report.invalid_handedness,0)

    def test_non_normal_mapped_asset_does_not_require_tangents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"plain.glb"
            build_glb(
                path,
                include_tangent=False,
                normal_map=False,
            )
            report=audit_shading_basis(path)
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.missing_required_tangents,0)


if __name__=="__main__":
    unittest.main()
