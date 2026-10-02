from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from tools.hayuya3d.runtime_budget_qa import (
    audit_runtime_lod,
    audit_runtime_tier,
)


def plan(
    *,
    triangles:int=500,
    materials:int=2,
    texture_edge:int=64,
):
    return {
        "tier":"test",
        "runtime_target":{
            "lod0_triangles":[1,triangles],
            "lod1_triangles":[1,triangles],
            "lod2_triangles":[1,triangles],
            "lod3_triangles":[1,triangles],
            "material_slots_target":[1,materials],
            "exceptional_texture_edge_px":texture_edge,
        },
    }


def material(edge:int,color):
    return trimesh.visual.material.PBRMaterial(
        baseColorTexture=Image.fromarray(
            np.full((edge,edge,4),[*color,255],dtype=np.uint8),
            mode="RGBA",
        ),
        metallicFactor=0.0,
        roughnessFactor=0.7,
    )


def write_asset(
    path:Path,
    *,
    subdivisions:int=1,
    material_count:int=1,
    texture_edge:int=32,
):
    scene=trimesh.Scene()
    for index in range(material_count):
        mesh=trimesh.creation.icosphere(
            subdivisions=subdivisions,
            radius=0.35,
        )
        mesh.apply_translation([index*1.0,0.0,0.0])
        uv=np.zeros((len(mesh.vertices),2),dtype=np.float64)
        mesh.visual=trimesh.visual.TextureVisuals(
            uv=uv,
            material=material(
                texture_edge,
                (80+index*20,100,120),
            ),
        )
        scene.add_geometry(mesh,node_name=f"part_{index}")
    path.write_bytes(trimesh.exchange.gltf.export_glb(scene))


class RuntimeBudgetQATests(unittest.TestCase):
    def test_asset_inside_house_budget_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"lod0.glb"
            write_asset(path)
            item=audit_runtime_lod(
                path,
                name="LOD0",
                plan=plan(),
                mode="prop",
            )
            self.assertTrue(item.ready,item.errors)
            self.assertLessEqual(item.faces,item.face_budget_max)
            self.assertLessEqual(
                item.material_count,
                item.material_slots_max,
            )
            self.assertLessEqual(
                item.texture_max_edge,
                item.texture_edge_max,
            )
            self.assertGreater(item.estimated_rgba_bytes,0)

    def test_triangle_budget_overflow_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"lod0.glb"
            write_asset(path,subdivisions=2)
            item=audit_runtime_lod(
                path,
                name="LOD0",
                plan=plan(triangles=40),
                mode="prop",
            )
            self.assertFalse(item.ready)
            self.assertTrue(
                any("triangles" in x for x in item.errors),
                item.errors,
            )

    def test_material_slot_overflow_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"lod0.glb"
            write_asset(path,material_count=3)
            item=audit_runtime_lod(
                path,
                name="LOD0",
                plan=plan(materials=2,triangles=500),
                mode="prop",
            )
            self.assertFalse(item.ready)
            self.assertGreater(item.material_count,2)
            self.assertTrue(
                any("material slots" in x for x in item.errors),
                item.errors,
            )

    def test_texture_edge_overflow_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"lod0.glb"
            write_asset(path,texture_edge=128)
            item=audit_runtime_lod(
                path,
                name="LOD0",
                plan=plan(texture_edge=64),
                mode="prop",
            )
            self.assertFalse(item.ready)
            self.assertEqual(item.texture_max_edge,128)
            self.assertTrue(
                any("texture edge" in x for x in item.errors),
                item.errors,
            )

    def test_tier_report_collects_lod_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            lod0=root/"lod0.glb"
            lod1=root/"lod1.glb"
            write_asset(lod0,subdivisions=1)
            write_asset(lod1,subdivisions=1)
            report=audit_runtime_tier(
                [("LOD0",lod0),("LOD1",lod1)],
                plan=plan(),
                mode="prop",
            )
            self.assertTrue(report.ready,report.errors)
            self.assertEqual(report.lod_count,2)
            self.assertEqual(len(report.items),2)
            self.assertGreater(
                report.total_estimated_rgba_bytes,
                0,
            )


if __name__=="__main__":
    unittest.main()
