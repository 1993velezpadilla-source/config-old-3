from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import trimesh
from PIL import Image

from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.hayuya import (
    _strict_metric_improvement,
    accessory_composite_regressions,
    local_detail_composite_regressions,
)

from tools.hayuya3d.composite_champion import (
    build_composite_plan,
    execute_safe_accessory_challenger,
    execute_safe_head_wrap_challenger,
    execute_safe_local_detail_challenger,
    execute_safe_material_challenger,
)


def candidate(
    backend: str,
    score: float,
    *,
    face_min=None,
    face_mesh=None,
    face_tex=None,
    face_detail=None,
    visual=None,
    appearance=None,
    material=None,
    texture=None,
    appearance_details=None,
    up_axis=None,
):
    return SimpleNamespace(
        backend=backend,
        path=f"/tmp/{backend}.glb",
        score=score,
        valid=True,
        production_score=score,
        visual_score=visual,
        appearance_score=appearance,
        appearance_face_detail_score=face_min,
        appearance_face_detail_min_score=face_min,
        head_density_score=face_mesh,
        head_texel_density_score=face_tex,
        head_texture_detail_score=face_detail,
        material_score=material,
        texture_resolution_score=texture,
        appearance_details=appearance_details or [],
        visual_views=(
            [{"best_up_axis":up_axis}]
            if up_axis in {"x","y","z"} else []
        ),
    )


def _append_blob(blob:bytearray,payload:bytes)->tuple[int,int]:
    while len(blob)%4:
        blob.append(0)
    offset=len(blob)
    blob.extend(payload)
    return offset,len(payload)


def write_runtime_guard_mesh(path:Path, *, skinned:bool)->None:
    positions=(
        (-0.5,0.0,0.0),
        (0.5,0.0,0.0),
        (0.0,1.0,0.0),
    )
    indices=(0,1,2)
    blob=bytearray()
    pos_off,pos_len=_append_blob(
        blob,b"".join(struct.pack("<3f",*row) for row in positions)
    )
    idx_off,idx_len=_append_blob(
        blob,b"".join(struct.pack("<H",value) for value in indices)
    )
    views=[
        {"buffer":0,"byteOffset":pos_off,"byteLength":pos_len},
        {"buffer":0,"byteOffset":idx_off,"byteLength":idx_len},
    ]
    accessors=[
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
    ]
    attrs={"POSITION":0}
    nodes=[{"mesh":0}]
    skins=[]
    if skinned:
        joints=((0,0,0,0),)*3
        weights=((1.0,0.0,0.0,0.0),)*3
        joint_off,joint_len=_append_blob(
            blob,b"".join(struct.pack("<4B",*row) for row in joints)
        )
        weight_off,weight_len=_append_blob(
            blob,b"".join(struct.pack("<4f",*row) for row in weights)
        )
        views.extend([
            {"buffer":0,"byteOffset":joint_off,"byteLength":joint_len},
            {"buffer":0,"byteOffset":weight_off,"byteLength":weight_len},
        ])
        accessors.extend([
            {
                "bufferView":2,"componentType":5121,
                "count":3,"type":"VEC4",
            },
            {
                "bufferView":3,"componentType":5126,
                "count":3,"type":"VEC4",
            },
        ])
        attrs.update({"JOINTS_0":2,"WEIGHTS_0":3})
        nodes=[
            {"mesh":0,"skin":0},
            {"name":"root_joint"},
        ]
        skins=[{"joints":[1]}]
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(blob)}],
        "bufferViews":views,
        "accessors":accessors,
        "meshes":[{"primitives":[{
            "attributes":attrs,
            "indices":1,
        }]}],
        "nodes":nodes,
        "skins":skins,
        "scenes":[{"nodes":list(range(len(nodes)))}],
        "scene":0,
    }
    write_glb(path,doc,bytes(blob))


class CompositeChampionPlannerTests(unittest.TestCase):
    def test_high_global_base_can_borrow_better_face(self):
        base=candidate(
            "global99",99.0,
            face_min=70.0,
            face_mesh=97.0,
            face_tex=96.0,
            face_detail=82.0,
            visual=99.0,
            appearance=98.0,
            material=98.0,
            texture=100.0,
        )
        face=candidate(
            "face80",80.0,
            face_min=98.0,
            face_mesh=100.0,
            face_tex=100.0,
            face_detail=99.0,
            visual=80.0,
            appearance=90.0,
            material=85.0,
            texture=100.0,
        )
        plan=build_composite_plan(
            [base,face],
            mode="character",
            inspect_parts=False,
        )
        self.assertEqual(plan.base_backend,"global99")
        identity=next(x for x in plan.donors if x.region=="face_identity")
        self.assertEqual(identity.donor_backend,"face80")
        self.assertEqual(identity.base_score,70.0)
        self.assertEqual(identity.donor_score,98.0)
        self.assertTrue(plan.composite_required)
        self.assertIn("face_identity",plan.executable_now)
        self.assertNotIn("face_identity",plan.deferred_transfers)

    def test_material_and_face_can_come_from_different_finalists(self):
        base=candidate(
            "base",95.0,
            face_min=85.0,face_mesh=95.0,face_tex=90.0,face_detail=88.0,
            visual=96.0,appearance=93.0,material=80.0,texture=90.0,
        )
        face=candidate(
            "face",84.0,
            face_min=99.0,face_mesh=100.0,face_tex=100.0,face_detail=100.0,
            visual=82.0,appearance=90.0,material=75.0,texture=90.0,
        )
        material=candidate(
            "material",83.0,
            face_min=80.0,face_mesh=92.0,face_tex=95.0,face_detail=94.0,
            visual=81.0,appearance=91.0,material=100.0,texture=100.0,
        )
        plan=build_composite_plan(
            [base,face,material],
            mode="character",
            inspect_parts=False,
        )
        donors={x.region:x.donor_backend for x in plan.donors}
        self.assertEqual(donors["face_identity"],"face")
        self.assertEqual(donors["face_geometry"],"face")
        self.assertEqual(donors["material_response"],"material")
        self.assertEqual(donors["texture_resolution"],"material")

    def test_single_finalist_stays_non_composite(self):
        only=candidate(
            "only",91.0,
            face_min=90.0,face_mesh=100.0,face_tex=100.0,face_detail=90.0,
            visual=91.0,appearance=91.0,material=91.0,texture=100.0,
        )
        plan=build_composite_plan(
            [only],
            mode="character",
            inspect_parts=False,
        )
        self.assertFalse(plan.composite_required)
        self.assertEqual(plan.deferred_transfers,[])
        self.assertEqual(plan.executable_now,[])

    def test_small_metric_noise_does_not_request_composite(self):
        base=candidate(
            "base",95.0,
            face_min=90.0,face_mesh=99.0,face_tex=99.0,face_detail=90.0,
            visual=95.0,appearance=95.0,material=95.0,texture=100.0,
        )
        tiny=candidate(
            "tiny",90.0,
            face_min=90.2,face_mesh=99.2,face_tex=99.2,face_detail=90.2,
            visual=94.0,appearance=94.0,material=95.2,texture=100.0,
        )
        plan=build_composite_plan(
            [base,tiny],
            mode="character",
            minimum_regional_gain=0.5,
            inspect_parts=False,
        )
        self.assertFalse(plan.composite_required)

    def test_local_detail_donor_becomes_executable_challenger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base_path=root/"base_local.glb"
            donor_path=root/"donor_local.glb"

            vertices=np.asarray([
                [-0.5,-1.0,0.0],
                [ 0.5,-1.0,0.0],
                [-0.5, 0.0,0.0],
                [ 0.5, 0.0,0.0],
                [-0.5, 1.0,0.0],
                [ 0.5, 1.0,0.0],
            ],dtype=np.float64)
            faces=np.asarray([
                [0,1,3],[0,3,2],
                [2,3,5],[2,5,4],
            ],dtype=np.int64)
            uv=np.asarray([
                [0.0,0.0],[1.0,0.0],
                [0.0,0.5],[1.0,0.5],
                [0.0,1.0],[1.0,1.0],
            ],dtype=np.float64)

            def write_mesh(path,color):
                material=trimesh.visual.material.PBRMaterial(
                    baseColorTexture=Image.fromarray(
                        np.full((64,64,4),[*color,255],dtype=np.uint8),
                        mode="RGBA",
                    ),
                    metallicFactor=0.0,
                    roughnessFactor=0.7,
                )
                mesh=trimesh.Trimesh(
                    vertices=vertices,
                    faces=faces,
                    process=False,
                    visual=trimesh.visual.TextureVisuals(
                        uv=uv,
                        material=material,
                    ),
                )
                path.write_bytes(
                    trimesh.exchange.gltf.export_glb(
                        trimesh.Scene(mesh)
                    )
                )

            write_mesh(base_path,(90,90,90))
            write_mesh(donor_path,(210,50,40))

            source="/refs/face-scar-closeup.png"
            base=candidate(
                "base",99.0,
                face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
                visual=99.0,appearance=96.0,material=90.0,texture=100.0,
                appearance_details=[{
                    "source":source,
                    "score":72.0,
                    "region_hint":"head",
                }],
                up_axis="y",
            )
            donor=candidate(
                "detail",82.0,
                face_min=94.0,face_mesh=98.0,face_tex=98.0,face_detail=96.0,
                visual=82.0,appearance=92.0,material=86.0,texture=100.0,
                appearance_details=[{
                    "source":source,
                    "score":98.0,
                    "region_hint":"head",
                }],
                up_axis="y",
            )
            base.path=str(base_path)
            donor.path=str(donor_path)
            plan=build_composite_plan(
                [base,donor],
                mode="character",
                inspect_parts=False,
            )
            token="detail:"+source
            self.assertIn(token,plan.executable_now)
            self.assertNotIn(token,plan.deferred_transfers)
            detail=next(
                item for item in plan.detail_donors
                if item.source==source
            )
            self.assertEqual(detail.donor_backend,"detail")
            self.assertEqual(detail.region_hint,"head")

            result=execute_safe_local_detail_challenger(
                plan,
                root/"detail-composite",
                detail_source=source,
                donor_samples=5000,
            )
            self.assertTrue(result.attempted)
            self.assertTrue(result.ready,result.error)
            self.assertEqual(result.donor_backend,"detail")
            self.assertEqual(result.source,source)
            self.assertEqual(result.region_hint,"head")
            self.assertTrue(Path(result.candidate_path or "").is_file())
            self.assertTrue(
                result.fusion and result.fusion["geometry_preserved"]
            )
            self.assertTrue(
                result.fusion and result.fusion["skin_payload_preserved"]
            )

    def test_more_small_components_alone_do_not_create_accessory_donor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)

            def write_asset(path,centers):
                body=trimesh.creation.icosphere(subdivisions=2,radius=1.0)
                scene=trimesh.Scene()
                scene.add_geometry(body)
                for center in centers:
                    accessory=trimesh.creation.box(
                        extents=[0.14,0.18,0.12]
                    )
                    accessory.apply_translation(center)
                    scene.add_geometry(accessory)
                path.write_bytes(
                    trimesh.exchange.gltf.export_glb(scene)
                )

            base_path=root/"base.glb"
            noisy_path=root/"noisy.glb"
            write_asset(base_path,[(1.12,0.18,0.0)])
            write_asset(
                noisy_path,
                [
                    (1.12,0.18,0.0),
                    (-1.12,0.18,0.0),
                ],
            )
            base=candidate(
                "base",95.0,
                face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
                visual=95.0,appearance=95.0,material=95.0,texture=100.0,
                up_axis="y",
            )
            noisy=candidate(
                "noisy",90.0,
                face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
                visual=90.0,appearance=90.0,material=90.0,texture=100.0,
                up_axis="y",
            )
            base.path=str(base_path)
            noisy.path=str(noisy_path)
            plan=build_composite_plan(
                [base,noisy],
                mode="prop",
                inspect_parts=True,
            )
            self.assertFalse(
                any(
                    donor.region=="detached_accessories"
                    for donor in plan.donors
                ),
                plan.donors,
            )
            self.assertFalse(plan.composite_required)

    def test_local_accessory_reference_records_safe_correspondence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)

            def write_asset(path,center):
                body=trimesh.creation.icosphere(subdivisions=2,radius=1.0)
                accessory=trimesh.creation.box(
                    extents=[0.14,0.18,0.12]
                )
                accessory.apply_translation(center)
                scene=trimesh.Scene()
                scene.add_geometry(body)
                scene.add_geometry(accessory)
                path.write_bytes(
                    trimesh.exchange.gltf.export_glb(scene)
                )

            base_path=root/"base.glb"
            donor_path=root/"donor.glb"
            write_asset(base_path,(1.12,0.18,0.0))
            write_asset(donor_path,(1.15,0.20,0.01))
            source="/refs/rosary_detail.png"
            base=candidate(
                "base",96.0,
                face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
                visual=96.0,appearance=96.0,material=95.0,texture=100.0,
                appearance_details=[{
                    "source":source,
                    "score":72.0,
                    "region_hint":"local",
                }],
                up_axis="y",
            )
            donor=candidate(
                "donor",84.0,
                face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
                visual=84.0,appearance=92.0,material=90.0,texture=100.0,
                appearance_details=[{
                    "source":source,
                    "score":98.0,
                    "region_hint":"local",
                }],
                up_axis="y",
            )
            base.path=str(base_path)
            donor.path=str(donor_path)
            plan=build_composite_plan(
                [base,donor],
                mode="prop",
                inspect_parts=True,
            )
            detail=next(
                item for item in plan.detail_donors
                if item.source==source
            )
            self.assertEqual(
                detail.strategy,
                "matched_detached_accessory_swap_then_mesh_doctor",
            )
            self.assertIsNotNone(detail.accessory_match)
            self.assertTrue(detail.accessory_match["ready"])
            token="detail:"+source
            self.assertIn(token,plan.executable_now)
            self.assertNotIn(token,plan.deferred_transfers)
            self.assertTrue(plan.composite_required)

            result=execute_safe_accessory_challenger(
                plan,
                root/"accessory-composite",
                detail_source=source,
            )
            self.assertTrue(result.attempted)
            self.assertTrue(result.ready,result.error)
            self.assertEqual(result.region_hint,"local")
            self.assertTrue(Path(result.candidate_path or "").is_file())
            self.assertTrue(result.fusion)
            self.assertTrue(result.fusion["component_crossing_ready"])
            self.assertTrue(result.fusion["self_intersection_ready"])
            self.assertTrue(result.fusion["attachment_ready"])
            self.assertEqual(result.fusion["attachment_floating_components"],0)
            self.assertEqual(
                result.fusion["attachment_oversized_floating_components"],
                0,
            )

    def test_character_accessory_geometry_remains_deferred_even_with_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)

            def write_asset(path,center):
                body=trimesh.creation.icosphere(subdivisions=2,radius=1.0)
                accessory=trimesh.creation.box(
                    extents=[0.14,0.18,0.12]
                )
                accessory.apply_translation(center)
                scene=trimesh.Scene()
                scene.add_geometry(body)
                scene.add_geometry(accessory)
                path.write_bytes(
                    trimesh.exchange.gltf.export_glb(scene)
                )

            base_path=root/"base.glb"
            donor_path=root/"donor.glb"
            write_asset(base_path,(1.12,0.18,0.0))
            write_asset(donor_path,(1.15,0.20,0.01))
            source="/refs/rosary_detail.png"
            base=candidate(
                "base",96.0,
                face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
                visual=96.0,appearance=96.0,material=95.0,texture=100.0,
                appearance_details=[{
                    "source":source,
                    "score":72.0,
                    "region_hint":"local",
                }],
                up_axis="y",
            )
            donor=candidate(
                "donor",84.0,
                face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
                visual=84.0,appearance=92.0,material=90.0,texture=100.0,
                appearance_details=[{
                    "source":source,
                    "score":98.0,
                    "region_hint":"local",
                }],
                up_axis="y",
            )
            base.path=str(base_path)
            donor.path=str(donor_path)
            plan=build_composite_plan(
                [base,donor],
                mode="character",
                inspect_parts=True,
            )
            token="detail:"+source
            detail=next(
                item for item in plan.detail_donors
                if item.source==source
            )
            self.assertTrue(detail.accessory_match["ready"])
            self.assertIn(token,plan.deferred_transfers)
            self.assertNotIn(token,plan.executable_now)

            result=execute_safe_accessory_challenger(
                plan,
                root/"blocked",
                detail_source=source,
            )
            self.assertFalse(result.attempted)
            self.assertFalse(result.ready)
            self.assertIn(
                "skin-weight",
                result.error or "",
            )

    def test_unlocalized_detail_remains_deferred(self):
        source="/refs/tiny-symbol.png"
        base=candidate(
            "base",95.0,
            face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
            visual=95.0,appearance=95.0,material=95.0,texture=100.0,
            appearance_details=[{
                "source":source,
                "score":70.0,
                "region_hint":"local",
            }],
        )
        donor=candidate(
            "donor",80.0,
            face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
            visual=80.0,appearance=90.0,material=90.0,texture=100.0,
            appearance_details=[{
                "source":source,
                "score":99.0,
                "region_hint":"local",
            }],
        )
        plan=build_composite_plan(
            [base,donor],
            mode="character",
            inspect_parts=False,
        )
        token="detail:"+source
        self.assertNotIn(token,plan.executable_now)
        self.assertIn(token,plan.deferred_transfers)

    def test_face_donor_executes_as_head_wrap_challenger_when_unskinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base_path=root/"base_face.glb"
            donor_path=root/"donor_face.glb"

            sphere=trimesh.creation.icosphere(subdivisions=3,radius=1.0)
            base_vertices=np.asarray(sphere.vertices,dtype=np.float64).copy()
            base_vertices[:,1]*=2.0
            lo=float(base_vertices[:,1].min())
            hi=float(base_vertices[:,1].max())
            normalized=(base_vertices[:,1]-lo)/max(hi-lo,1e-9)
            donor_vertices=base_vertices.copy()
            head=normalized>=0.78
            donor_vertices[head,0]*=1.12
            donor_vertices[head,2]*=1.12

            base_mesh=trimesh.Trimesh(
                vertices=base_vertices,
                faces=np.asarray(sphere.faces).copy(),
                process=False,
            )
            donor_mesh=trimesh.Trimesh(
                vertices=donor_vertices,
                faces=np.asarray(sphere.faces).copy(),
                process=False,
            )
            base_path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(base_mesh))
            )
            donor_path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(donor_mesh))
            )

            base=candidate(
                "base",99.0,
                face_min=70.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
                visual=99.0,appearance=96.0,material=90.0,texture=100.0,
            )
            donor=candidate(
                "face",80.0,
                face_min=98.0,face_mesh=100.0,face_tex=98.0,face_detail=96.0,
                visual=80.0,appearance=92.0,material=85.0,texture=100.0,
            )
            base.path=str(base_path)
            donor.path=str(donor_path)
            plan=build_composite_plan(
                [base,donor],
                mode="character",
                inspect_parts=False,
            )
            self.assertIn("face_identity",plan.executable_now)

            result=execute_safe_head_wrap_challenger(
                plan,
                root/"head-composite",
                texture_size=256,
            )
            self.assertTrue(result.attempted)
            self.assertTrue(result.ready,result.error)
            self.assertEqual(result.donor_backend,"face")
            self.assertTrue(Path(result.candidate_path or "").is_file())
            self.assertTrue(result.fusion and result.fusion["geometry_ready"])

    def test_material_challenger_rejects_runtime_payload_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base_path=root/"runtime-base.glb"
            stripped_path=root/"runtime-stripped.glb"
            donor_path=root/"runtime-donor.glb"
            write_runtime_guard_mesh(base_path,skinned=True)
            write_runtime_guard_mesh(stripped_path,skinned=False)
            write_runtime_guard_mesh(donor_path,skinned=False)

            base=candidate(
                "base_runtime",95.0,
                face_min=90.0,face_mesh=98.0,face_tex=98.0,face_detail=90.0,
                visual=95.0,appearance=95.0,material=60.0,texture=100.0,
            )
            donor=candidate(
                "donor_runtime",80.0,
                face_min=85.0,face_mesh=95.0,face_tex=95.0,face_detail=85.0,
                visual=80.0,appearance=88.0,material=99.0,texture=100.0,
            )
            base.path=str(base_path)
            donor.path=str(donor_path)
            plan=build_composite_plan(
                [base,donor],
                mode="character",
                inspect_parts=False,
            )
            self.assertIn("material_response",plan.executable_now)

            def fake_transfer(source,target,output,**kwargs):
                output.write_bytes(stripped_path.read_bytes())
                return SimpleNamespace(rebake_required=[])

            with mock.patch(
                "material_bridge.transfer_best_material",
                side_effect=fake_transfer,
            ):
                result=execute_safe_material_challenger(
                    plan,
                    root/"runtime-composite",
                    texture_size=256,
                    total_samples=1000,
                )

            self.assertTrue(result.attempted)
            self.assertFalse(result.ready)
            self.assertFalse(result.runtime_payload_preserved)
            self.assertIn(
                "protected runtime payload",
                result.error or "",
            )

    def test_material_donor_executes_as_geometry_preserving_challenger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base_path=root/"base.glb"
            donor_path=root/"donor.glb"

            vertices=np.array([
                [-0.5,-0.5,0.0],
                [ 0.5,-0.5,0.0],
                [ 0.5, 0.5,0.0],
                [-0.5, 0.5,0.0],
            ],dtype=np.float64)
            faces=np.array([[0,1,2],[0,2,3]],dtype=np.int64)
            uv=np.array([
                [0.0,0.0],
                [1.0,0.0],
                [1.0,1.0],
                [0.0,1.0],
            ],dtype=np.float64)

            base_material=trimesh.visual.material.PBRMaterial(
                baseColorTexture=Image.fromarray(
                    np.full((8,8,4),[90,90,90,255],dtype=np.uint8),
                    mode="RGBA",
                ),
                roughnessFactor=0.9,
                metallicFactor=0.0,
            )
            donor_material=trimesh.visual.material.PBRMaterial(
                baseColorTexture=Image.fromarray(
                    np.full((8,8,4),[190,60,45,255],dtype=np.uint8),
                    mode="RGBA",
                ),
                metallicRoughnessTexture=Image.fromarray(
                    np.full((8,8,3),[0,80,180],dtype=np.uint8),
                    mode="RGB",
                ),
                roughnessFactor=0.55,
                metallicFactor=0.25,
            )
            base_mesh=trimesh.Trimesh(
                vertices=vertices,
                faces=faces,
                process=False,
                visual=trimesh.visual.TextureVisuals(
                    uv=uv,
                    material=base_material,
                ),
            )
            donor_mesh=trimesh.Trimesh(
                vertices=vertices,
                faces=faces,
                process=False,
                visual=trimesh.visual.TextureVisuals(
                    uv=uv,
                    material=donor_material,
                ),
            )
            base_path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(base_mesh))
            )
            donor_path.write_bytes(
                trimesh.exchange.gltf.export_glb(trimesh.Scene(donor_mesh))
            )

            base=candidate(
                "base",95.0,
                face_min=90.0,face_mesh=100.0,face_tex=100.0,face_detail=90.0,
                visual=95.0,appearance=95.0,material=60.0,texture=100.0,
            )
            donor=candidate(
                "material",80.0,
                face_min=80.0,face_mesh=95.0,face_tex=95.0,face_detail=85.0,
                visual=80.0,appearance=88.0,material=95.0,texture=100.0,
            )
            base.path=str(base_path)
            donor.path=str(donor_path)
            plan=build_composite_plan(
                [base,donor],
                mode="character",
                inspect_parts=False,
            )
            self.assertIn("material_response",plan.executable_now)

            result=execute_safe_material_challenger(
                plan,
                root/"composite",
                texture_size=64,
                total_samples=4000,
            )
            self.assertTrue(result.attempted)
            self.assertTrue(result.ready,result.error)
            self.assertTrue(result.geometry_preserved)
            self.assertEqual(result.donor_backend,"material")
            self.assertTrue(Path(result.candidate_path or "").is_file())
            self.assertEqual(
                Path(result.candidate_path or "").read_bytes()[:4],
                b"glTF",
            )

    def test_local_detail_guard_requires_target_reference_improvement(self):
        source="/refs/scar-closeup.png"
        base=SimpleNamespace(
            score=99.0,
            production_score=98.0,
            vertices=100,
            faces=180,
            components=1,
            bbox=[1.0,2.0,1.0],
            pbr_channels=["baseColor","roughness","normal"],
            head_texture_detail_score=90.0,
            head_texel_density_score=98.0,
            visual_score=99.0,
            appearance_score=96.0,
            appearance_face_detail_score=94.0,
            appearance_face_detail_min_score=91.0,
            base_color_min_edge=4096,
            appearance_details=[{
                "source":source,
                "score":80.0,
                "region_hint":"head",
            }],
        )
        flat=SimpleNamespace(
            **{
                **base.__dict__,
                "appearance_details":[{
                    "source":source,
                    "score":80.0,
                    "region_hint":"head",
                }],
            }
        )
        improved=SimpleNamespace(
            **{
                **base.__dict__,
                "appearance_details":[{
                    "source":source,
                    "score":88.0,
                    "region_hint":"head",
                }],
            }
        )

        flat_reasons=local_detail_composite_regressions(
            base,flat,source
        )
        self.assertTrue(
            any("target_detail_not_improved" in item for item in flat_reasons),
            flat_reasons,
        )
        self.assertEqual(
            local_detail_composite_regressions(
                base,improved,source
            ),
            [],
        )

    def test_accessory_guard_allows_geometry_change_but_not_global_regression(self):
        source="/refs/rosary_detail.png"
        base=SimpleNamespace(
            score=96.0,
            production_score=95.0,
            visual_score=96.0,
            appearance_score=95.0,
            material_score=94.0,
            texture_resolution_score=100.0,
            head_texture_detail_score=None,
            head_texel_density_score=None,
            appearance_face_detail_score=None,
            appearance_face_detail_min_score=None,
            pbr_channels=["baseColor","roughness","normal"],
            base_color_min_edge=2048,
            vertices=1000,
            faces=1800,
            components=2,
            appearance_details=[{
                "source":source,
                "score":70.0,
                "region_hint":"local",
            }],
        )
        winner=SimpleNamespace(
            **{
                **base.__dict__,
                "vertices":1040,
                "faces":1880,
                "appearance_details":[{
                    "source":source,
                    "score":92.0,
                    "region_hint":"local",
                }],
            }
        )
        self.assertEqual(
            accessory_composite_regressions(
                base,winner,source
            ),
            [],
        )

        regressed=SimpleNamespace(
            **{
                **winner.__dict__,
                "score":95.0,
            }
        )
        reasons=accessory_composite_regressions(
            base,regressed,source
        )
        self.assertTrue(
            any("regressed:score" in item for item in reasons),
            reasons,
        )

    def test_target_metric_must_strictly_improve(self):
        base=SimpleNamespace(material_score=90.0)
        same=SimpleNamespace(material_score=90.0)
        better=SimpleNamespace(material_score=91.0)
        self.assertTrue(
            _strict_metric_improvement(
                base,same,"material_score"
            )
        )
        self.assertEqual(
            _strict_metric_improvement(
                base,better,"material_score"
            ),
            [],
        )

    def test_promotion_contract_requires_rejudge_and_atomic_fallback(self):
        base=candidate(
            "base",95.0,
            face_min=80.0,face_mesh=90.0,face_tex=90.0,face_detail=80.0,
            visual=95.0,appearance=95.0,material=95.0,texture=100.0,
        )
        donor=candidate(
            "donor",85.0,
            face_min=98.0,face_mesh=100.0,face_tex=100.0,face_detail=98.0,
            visual=85.0,appearance=90.0,material=90.0,texture=100.0,
        )
        plan=build_composite_plan(
            [base,donor],
            mode="character",
            inspect_parts=False,
        )
        text=" ".join(plan.promotion_contract+plan.notes).lower()
        self.assertIn("re-enter",text)
        self.assertIn("weakest face",text)
        self.assertIn("atomic",text)
        self.assertIn("rig",text)


if __name__=="__main__":
    unittest.main()
