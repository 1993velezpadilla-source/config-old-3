from __future__ import annotations

import io
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.uv_tangent_qa import audit_uv_tangents


def _append(blob:bytearray,payload:bytes)->tuple[int,int]:
    while len(blob)%4:
        blob.append(0)
    offset=len(blob)
    blob.extend(payload)
    return offset,len(payload)


def _png()->bytes:
    out=io.BytesIO()
    Image.new("RGB",(4,4),(128,128,255)).save(out,format="PNG")
    return out.getvalue()


def build_uv_glb(
    path:Path,
    *,
    textured:bool=True,
    normal_mapped:bool=False,
    include_uv:bool=True,
    degenerate_uv:bool=False,
    tangents:tuple[tuple[float,float,float,float],...]|None=None,
)->None:
    positions=(
        (-0.5,-0.5,0.0),
        ( 0.5,-0.5,0.0),
        ( 0.5, 0.5,0.0),
        (-0.5, 0.5,0.0),
    )
    indices=(0,1,2,0,2,3)
    uvs=(
        ((0.0,0.0),(0.0,0.0),(0.0,0.0),(0.0,0.0))
        if degenerate_uv
        else ((0.0,0.0),(1.0,0.0),(1.0,1.0),(0.0,1.0))
    )

    blob=bytearray()
    views=[]
    accessors=[]

    def add_accessor(payload,component,count,kind):
        offset,length=_append(blob,payload)
        view_index=len(views)
        views.append({
            "buffer":0,
            "byteOffset":offset,
            "byteLength":length,
        })
        accessor_index=len(accessors)
        accessors.append({
            "bufferView":view_index,
            "componentType":component,
            "count":count,
            "type":kind,
        })
        return accessor_index

    pos=add_accessor(
        b"".join(struct.pack("<3f",*row) for row in positions),
        5126,4,"VEC3",
    )
    idx=add_accessor(
        b"".join(struct.pack("<H",value) for value in indices),
        5123,6,"SCALAR",
    )
    attrs={"POSITION":pos}
    if include_uv:
        uv=add_accessor(
            b"".join(struct.pack("<2f",*row) for row in uvs),
            5126,4,"VEC2",
        )
        attrs["TEXCOORD_0"]=uv
    if tangents is not None:
        tangent=add_accessor(
            b"".join(struct.pack("<4f",*row) for row in tangents),
            5126,len(tangents),"VEC4",
        )
        attrs["TANGENT"]=tangent

    primitive={
        "attributes":attrs,
        "indices":idx,
    }
    materials=[]
    textures=[]
    images=[]
    if textured:
        image_payload=_png()
        image_offset,image_length=_append(blob,image_payload)
        image_view=len(views)
        views.append({
            "buffer":0,
            "byteOffset":image_offset,
            "byteLength":image_length,
        })
        images=[{
            "bufferView":image_view,
            "mimeType":"image/png",
        }]
        textures=[{"source":0}]
        material=(
            {"normalTexture":{"index":0}}
            if normal_mapped
            else {
                "pbrMetallicRoughness":{
                    "baseColorTexture":{"index":0}
                }
            }
        )
        materials=[material]
        primitive["material"]=0

    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":views,
        "accessors":accessors,
        "meshes":[{"primitives":[primitive]}],
        "nodes":[{"mesh":0}],
        "scenes":[{"nodes":[0]}],
        "scene":0,
    }
    if materials:
        doc["materials"]=materials
        doc["textures"]=textures
        doc["images"]=images
    write_glb(path,doc,bytes(blob))


class UVTangentQATests(unittest.TestCase):
    def test_normal_map_without_explicit_tangent_passes_when_derivable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"derived.glb"
            build_uv_glb(
                path,
                normal_mapped=True,
            )
            report=audit_uv_tangents(path)
            self.assertTrue(report.applicable)
            self.assertTrue(report.ready,report.errors)
            item=report.primitives[0]
            self.assertTrue(item.normal_mapped)
            self.assertFalse(item.tangent_present)
            self.assertTrue(item.tangent_derivable)
            self.assertEqual(item.degenerate_uv_triangles,0)

    def test_textured_primitive_missing_required_uv_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"missing-uv.glb"
            build_uv_glb(
                path,
                textured=True,
                include_uv=False,
            )
            report=audit_uv_tangents(path)
            self.assertFalse(report.ready)
            self.assertEqual(report.missing_uv_primitives,1)
            self.assertTrue(
                any("missing required UV" in item for item in report.errors),
                report.errors,
            )

    def test_normal_map_with_collapsed_uvs_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"collapsed-uv.glb"
            build_uv_glb(
                path,
                normal_mapped=True,
                degenerate_uv=True,
            )
            report=audit_uv_tangents(path)
            self.assertFalse(report.ready)
            self.assertGreater(report.degenerate_uv_triangles,0)
            self.assertTrue(
                any("degenerate UV" in item for item in report.errors),
                report.errors,
            )
            self.assertFalse(report.primitives[0].tangent_derivable)

    def test_explicit_zero_length_tangents_fail_even_if_uvs_are_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad-tangent.glb"
            build_uv_glb(
                path,
                normal_mapped=True,
                tangents=(
                    (0.0,0.0,0.0,1.0),
                    (0.0,0.0,0.0,1.0),
                    (0.0,0.0,0.0,1.0),
                    (0.0,0.0,0.0,1.0),
                ),
            )
            report=audit_uv_tangents(path)
            self.assertFalse(report.ready)
            self.assertEqual(report.invalid_tangent_primitives,1)
            self.assertTrue(
                any("TANGENT accessor" in item for item in report.errors),
                report.errors,
            )

    def test_untextured_mesh_has_no_fake_uv_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"plain.glb"
            build_uv_glb(
                path,
                textured=False,
                include_uv=False,
            )
            report=audit_uv_tangents(path)
            self.assertFalse(report.applicable)
            self.assertTrue(report.ready,report.errors)


if __name__=="__main__":
    unittest.main()
