from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import trimesh
from PIL import Image

from tools.hayuya3d.composite_champion import (
    build_composite_plan,
    execute_safe_accessory_challenger,
)
from tools.hayuya3d.glb_images import read_glb, write_glb
from tools.hayuya3d.gltf_audit import audit_glb
from tools.hayuya3d.morph_deformation_qa import audit_morph_deformation
from tools.hayuya3d.rigged_accessory_insert import (
    _blend_skin_weights,
    _require_exact_surface_relation,
    _surface_skin_ambiguity,
    insert_rigged_accessory,
    prepare_production_rigged_accessory_insert,
    rigged_accessory_insert_supported,
)
from tools.hayuya3d.skin_weight_qa import audit_skin_weights


def _align(blob: bytearray) -> int:
    while len(blob) % 4:
        blob.append(0)
    return len(blob)


def write_skinned_base(
    path: Path,
    *,
    morph: bool = True,
    animated: bool = False,
    morph_gradient: bool = False,
) -> None:
    source = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    vertices = np.asarray(source.vertices, dtype=np.float32)
    normals = np.asarray(source.vertex_normals, dtype=np.float32)
    faces = np.asarray(source.faces, dtype=np.uint16)
    count = len(vertices)

    # Two-bone field: upper half follows joint 1, lower half joint 0.
    joints = np.zeros((count, 4), dtype=np.uint8)
    weights = np.zeros((count, 4), dtype=np.float32)
    upper = vertices[:, 1] >= 0.0
    joints[upper, 0] = 1
    weights[:, 0] = 1.0

    blob = bytearray()
    pos_offset = _align(blob)
    pos_bytes = vertices.astype("<f4").tobytes()
    blob.extend(pos_bytes)
    normal_offset = _align(blob)
    normal_bytes = normals.astype("<f4").tobytes()
    blob.extend(normal_bytes)
    joint_offset = _align(blob)
    joint_bytes = joints.tobytes()
    blob.extend(joint_bytes)
    weight_offset = _align(blob)
    weight_bytes = weights.astype("<f4").tobytes()
    blob.extend(weight_bytes)
    index_offset = _align(blob)
    index_bytes = faces.astype("<u2").reshape(-1).tobytes()
    blob.extend(index_bytes)

    views = [
        {"buffer": 0, "byteOffset": pos_offset, "byteLength": len(pos_bytes)},
        {"buffer": 0, "byteOffset": normal_offset, "byteLength": len(normal_bytes)},
        {"buffer": 0, "byteOffset": joint_offset, "byteLength": len(joint_bytes)},
        {"buffer": 0, "byteOffset": weight_offset, "byteLength": len(weight_bytes)},
        {"buffer": 0, "byteOffset": index_offset, "byteLength": len(index_bytes)},
    ]
    accessors = [
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": count,
            "type": "VEC3",
            "min": vertices.min(axis=0).astype(float).tolist(),
            "max": vertices.max(axis=0).astype(float).tolist(),
        },
        {
            "bufferView": 1,
            "componentType": 5126,
            "count": count,
            "type": "VEC3",
            "min": normals.min(axis=0).astype(float).tolist(),
            "max": normals.max(axis=0).astype(float).tolist(),
        },
        {
            "bufferView": 2,
            "componentType": 5121,
            "count": count,
            "type": "VEC4",
        },
        {
            "bufferView": 3,
            "componentType": 5126,
            "count": count,
            "type": "VEC4",
        },
        {
            "bufferView": 4,
            "componentType": 5123,
            "count": int(faces.size),
            "type": "SCALAR",
        },
    ]
    primitive = {
        "attributes": {
            "POSITION": 0,
            "NORMAL": 1,
            "JOINTS_0": 2,
            "WEIGHTS_0": 3,
        },
        "indices": 4,
    }
    mesh = {"primitives": [primitive]}

    if morph:
        delta = np.zeros((count, 3), dtype=np.float32)
        if morph_gradient:
            # Linear field makes barycentric interpolation analytically
            # distinguishable from nearest-vertex copying.
            delta[:, 2] = 0.01 * (vertices[:, 0] + 1.0)
        else:
            # Upper-body breathing/shape target. New accessory vertices should
            # inherit nearby canonical deltas instead of receiving invented zeros.
            delta[upper, 2] = 0.015
        morph_offset = _align(blob)
        morph_bytes = delta.astype("<f4").tobytes()
        blob.extend(morph_bytes)
        views.append({
            "buffer": 0,
            "byteOffset": morph_offset,
            "byteLength": len(morph_bytes),
        })
        accessors.append({
            "bufferView": len(views) - 1,
            "componentType": 5126,
            "count": count,
            "type": "VEC3",
            "min": delta.min(axis=0).astype(float).tolist(),
            "max": delta.max(axis=0).astype(float).tolist(),
        })
        primitive["targets"] = [{"POSITION": len(accessors) - 1}]
        mesh["weights"] = [0.0]

    animations=[]
    if animated:
        times=np.asarray([0.0,1.0],dtype=np.float32)
        translations=np.asarray([
            [0.0,0.0,0.0],
            [0.08,0.0,0.0],
        ],dtype=np.float32)
        time_offset=_align(blob)
        time_bytes=times.astype("<f4").tobytes()
        blob.extend(time_bytes)
        views.append({
            "buffer":0,
            "byteOffset":time_offset,
            "byteLength":len(time_bytes),
        })
        time_accessor=len(accessors)
        accessors.append({
            "bufferView":len(views)-1,
            "componentType":5126,
            "count":len(times),
            "type":"SCALAR",
            "min":[0.0],
            "max":[1.0],
        })

        translation_offset=_align(blob)
        translation_bytes=translations.astype("<f4").tobytes()
        blob.extend(translation_bytes)
        views.append({
            "buffer":0,
            "byteOffset":translation_offset,
            "byteLength":len(translation_bytes),
        })
        translation_accessor=len(accessors)
        accessors.append({
            "bufferView":len(views)-1,
            "componentType":5126,
            "count":len(translations),
            "type":"VEC3",
            "min":translations.min(axis=0).astype(float).tolist(),
            "max":translations.max(axis=0).astype(float).tolist(),
        })
        animations=[{
            "samplers":[{
                "input":time_accessor,
                "output":translation_accessor,
                "interpolation":"LINEAR",
            }],
            "channels":[
                {
                    "sampler":0,
                    "target":{"node":1,"path":"translation"},
                },
                {
                    "sampler":0,
                    "target":{"node":2,"path":"translation"},
                },
            ],
        }]

    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": views,
        "accessors": accessors,
        "meshes": [mesh],
        "nodes": [
            {"mesh": 0, "skin": 0},
            {},
            {},
        ],
        "skins": [{"joints": [1, 2]}],
        "animations":animations,
        "scenes": [{"nodes": [0, 1, 2]}],
        "scene": 0,
    }
    write_glb(path, doc, bytes(blob))


def _textured(mesh, uv, color):
    base=np.zeros((16,16,4),dtype=np.uint8)
    base[:,:,:3]=np.asarray(color,dtype=np.uint8)
    base[:,:,3]=255
    normal=np.zeros((16,16,3),dtype=np.uint8)
    normal[:,:,0]=128
    normal[:,:,1]=128
    normal[:,:,2]=255
    material=trimesh.visual.material.PBRMaterial(
        baseColorTexture=Image.fromarray(base,"RGBA"),
        normalTexture=Image.fromarray(normal,"RGB"),
        metallicFactor=0.15,
        roughnessFactor=0.55,
    )
    mesh.visual=trimesh.visual.TextureVisuals(
        uv=np.asarray(uv,dtype=np.float64),
        material=material,
    )
    return mesh


def write_donor(
    path: Path,
    *,
    ambiguous: bool = False,
    textured: bool = False,
) -> None:
    body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    if textured:
        bv=np.asarray(body.vertices,dtype=np.float64)
        blo=bv.min(axis=0)
        bext=np.maximum(bv.max(axis=0)-blo,1e-9)
        body_uv=np.stack([
            (bv[:,0]-blo[0])/bext[0],
            (bv[:,2]-blo[2])/bext[2],
        ],axis=1)
        body=_textured(body,body_uv,[120,110,100])

        vertices=np.asarray([
            [-0.08,1.02,-0.06],
            [ 0.08,1.02,-0.06],
            [ 0.00,1.20,-0.06],
            [ 0.00,1.10, 0.08],
        ],dtype=np.float64)
        faces=np.asarray([
            [0,2,1],
            [0,1,3],
            [1,2,3],
            [2,0,3],
        ],dtype=np.int64)
        charm=trimesh.Trimesh(
            vertices=vertices,
            faces=faces,
            process=False,
        )
        charm=_textured(
            charm,
            [
                [0.0,0.0],
                [1.0,0.0],
                [0.5,1.0],
                [0.5,0.4],
            ],
            [180,40,45],
        )
    else:
        charm = trimesh.creation.box(extents=[0.16, 0.18, 0.10])
        charm.apply_translation([0.0, 1.10, 0.0])

    scene = trimesh.Scene()
    scene.add_geometry(body, node_name="body")
    scene.add_geometry(charm, node_name="charm")
    if ambiguous:
        second = trimesh.creation.box(extents=[0.14, 0.16, 0.10])
        second.apply_translation([0.25, 1.08, 0.0])
        scene.add_geometry(second, node_name="second_charm")
    path.write_bytes(trimesh.exchange.gltf.export_glb(scene))


def write_cluster_donor(path: Path) -> None:
    body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    pieces = []
    for y, extents in (
        (1.06, [0.10, 0.10, 0.08]),
        (1.17, [0.09, 0.10, 0.07]),
        (1.28, [0.08, 0.10, 0.06]),
    ):
        piece = trimesh.creation.box(extents=extents)
        piece.apply_translation([0.0, y, 0.0])
        pieces.append(piece)
    scene = trimesh.Scene()
    scene.add_geometry(body, node_name="body")
    for index, piece in enumerate(pieces):
        scene.add_geometry(piece, node_name=f"rosary_{index}")
    path.write_bytes(trimesh.exchange.gltf.export_glb(scene))


def candidate(
    backend: str,
    path: Path,
    score: float,
    *,
    detail_source: str,
    detail_score: float,
):
    return SimpleNamespace(
        backend=backend,
        path=str(path),
        score=score,
        valid=True,
        production_score=score,
        visual_score=score,
        appearance_score=score,
        appearance_face_detail_score=92.0,
        appearance_face_detail_min_score=90.0,
        head_density_score=98.0,
        head_texel_density_score=98.0,
        head_texture_detail_score=92.0,
        material_score=95.0,
        texture_resolution_score=100.0,
        base_color_min_edge=0,
        pbr_channels=[],
        appearance_details=[{
            "source": detail_source,
            "score": detail_score,
            "region_hint": "local",
        }],
        visual_views=[{"best_up_axis": "y"}],
        up_axis="y",
    )


class RiggedAccessoryInsertTests(unittest.TestCase):
    def test_new_accessory_gets_skin_weights_and_morph_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "donor.glb"
            output = root / "inserted.glb"
            write_skinned_base(base, morph=True)
            write_donor(donor)

            before = audit_glb(base)
            self.assertTrue(before.rig_ready)
            self.assertEqual(before.morph_target_count, 1)

            result = insert_rigged_accessory(
                base,
                donor,
                output,
            )

            self.assertTrue(result.ready, result.errors)
            self.assertTrue(result.geometry_ready)
            self.assertFalse(result.material_ready)
            self.assertFalse(result.uv_ready)
            self.assertFalse(result.production_ready)
            self.assertTrue(result.material_blockers)
            self.assertTrue(
                any(
                    "no valid material binding" in blocker
                    for blocker in result.material_blockers
                ),
                result.material_blockers,
            )
            self.assertTrue(
                any(
                    "UV/material evidence is incomplete" in warning
                    for warning in result.warnings
                ),
                result.warnings,
            )
            self.assertTrue(output.is_file())
            self.assertGreater(result.inserted_vertices, 0)
            self.assertGreater(result.inserted_faces, 0)
            self.assertEqual(
                result.transferred_weight_vertices,
                result.inserted_vertices,
            )
            self.assertTrue(result.legacy_payload_preserved)
            self.assertTrue(result.rig_ready)
            self.assertTrue(result.skin_weights_ready)
            self.assertTrue(result.morph_ready)
            self.assertTrue(result.morph_deformation_ready)
            self.assertEqual(result.morph_targets_transferred, 1)
            self.assertIn("POSITION", result.morph_semantics_transferred)
            self.assertTrue(result.attachment_ready)
            self.assertTrue(result.component_crossing_ready)
            self.assertTrue(result.self_intersection_ready)

            after = audit_glb(output)
            self.assertTrue(after.rig_ready, after.errors)
            self.assertTrue(after.morph_ready, after.errors)
            self.assertEqual(after.morph_target_count, 1)
            self.assertEqual(after.morph_primitive_count, 2)
            self.assertTrue(audit_skin_weights(output).ready)
            self.assertTrue(audit_morph_deformation(output).ready)

    def test_textured_donor_transplants_pbr_uv_and_tangent_basis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"textured_donor.glb"
            output=root/"inserted_textured.glb"
            write_skinned_base(base,morph=True)
            write_donor(donor,textured=True)

            supported,reason=rigged_accessory_insert_supported(
                base,donor,
            )
            self.assertTrue(supported,reason)

            raw=insert_rigged_accessory(
                base,donor,output,
            )
            self.assertTrue(raw.ready,raw.errors)
            self.assertTrue(raw.geometry_ready)
            self.assertFalse(raw.material_ready)
            self.assertFalse(raw.production_ready)

            result=prepare_production_rigged_accessory_insert(
                base,
                donor,
                root/"production",
            )
            self.assertTrue(result.ready,result.errors)
            self.assertTrue(result.geometry_ready)
            self.assertTrue(result.material_ready,result.material_blockers)
            self.assertTrue(result.uv_ready,result.material_blockers)
            self.assertTrue(result.uv_tangent_ready,result.material_blockers)
            self.assertTrue(result.production_ready,result.material_blockers)
            self.assertTrue(result.legacy_payload_preserved)
            self.assertIn("baseColor",result.material_channels)
            self.assertIn("normal",result.material_channels)

    def test_production_insert_survives_real_skeletal_animation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"animated_base.glb"
            donor=root/"textured_donor.glb"
            write_skinned_base(
                base,
                morph=True,
                animated=True,
            )
            write_donor(donor,textured=True)

            result=prepare_production_rigged_accessory_insert(
                base,
                donor,
                root/"production",
            )
            self.assertTrue(result.ready,result.errors)
            self.assertTrue(result.production_ready,result.material_blockers)
            self.assertTrue(result.animation_ready,result.errors)
            self.assertTrue(result.deformation_ready,result.errors)
            self.assertTrue(result.skin_weights_ready,result.errors)
            self.assertTrue(result.morph_deformation_ready,result.errors)
            self.assertTrue(result.attachment_ready,result.errors)

            from tools.hayuya3d.animation_qa import audit_animation
            from tools.hayuya3d.deformation_qa import audit_deformation
            animation=audit_animation(Path(result.output_glb))
            deformation=audit_deformation(Path(result.output_glb))
            self.assertTrue(animation.ready,animation.errors)
            self.assertEqual(animation.animation_count,1)
            self.assertTrue(deformation.ready,deformation.errors)
            self.assertGreaterEqual(deformation.sampled_frames,2)

    def test_multi_piece_cluster_gets_one_skin_morph_insertion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base.glb"
            donor=root/"rosary_cluster.glb"
            output=root/"cluster_insert.glb"
            write_skinned_base(base,morph=True)
            write_cluster_donor(donor)

            supported,reason=rigged_accessory_insert_supported(
                base,
                donor,
            )
            self.assertTrue(supported,reason)

            result=insert_rigged_accessory(
                base,
                donor,
                output,
            )
            self.assertTrue(result.ready,result.errors)
            self.assertTrue(result.geometry_ready,result.errors)
            self.assertFalse(result.production_ready)
            self.assertEqual(result.spatial_label,"cluster")
            self.assertGreater(result.inserted_vertices,8)
            self.assertGreater(result.inserted_faces,12)
            self.assertEqual(
                result.transferred_weight_vertices,
                result.inserted_vertices,
            )
            self.assertTrue(result.skin_weights_ready,result.errors)
            self.assertTrue(result.morph_ready,result.errors)
            self.assertTrue(result.morph_deformation_ready,result.errors)
            self.assertTrue(result.attachment_ready,result.errors)
            self.assertTrue(result.component_crossing_ready,result.errors)
            self.assertTrue(result.self_intersection_ready,result.errors)
            self.assertTrue(
                any(
                    warning.startswith("multi_piece_accessory_cluster=")
                    for warning in result.warnings
                ),
                result.warnings,
            )

    def test_planner_recognizes_multi_piece_cluster_but_defers_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base_path=root/"base.glb"
            donor_path=root/"rosary_cluster.glb"
            source="/refs/rosary_detail.png"
            write_skinned_base(base_path,morph=True)
            write_cluster_donor(donor_path)

            base=candidate(
                "base",
                base_path,
                96.0,
                detail_source=source,
                detail_score=70.0,
            )
            donor=candidate(
                "donor",
                donor_path,
                84.0,
                detail_source=source,
                detail_score=98.0,
            )
            plan=build_composite_plan(
                [base,donor],
                mode="character",
                inspect_parts=True,
            )
            detail=next(
                item for item in plan.detail_donors
                if item.source==source
            )
            token="detail:"+source
            self.assertEqual(
                detail.strategy,
                "new_rigged_accessory_insert_weight_morph_transfer",
            )
            self.assertTrue(
                detail.accessory_match["rigged_insert_supported"],
                detail.accessory_match,
            )
            self.assertFalse(
                detail.accessory_match["rigged_insert_material_ready"],
                detail.accessory_match,
            )
            self.assertNotIn(token,plan.executable_now)
            self.assertIn(token,plan.deferred_transfers)

    def test_inserted_morph_payload_matches_barycentric_surface_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"gradient-base.glb"
            donor=root/"donor.glb"
            output=root/"barycentric-insert.glb"
            write_skinned_base(
                base,
                morph=True,
                morph_gradient=True,
            )
            write_donor(donor)

            result=insert_rigged_accessory(
                base,
                donor,
                output,
            )
            self.assertTrue(result.geometry_ready,result.errors)
            self.assertEqual(
                result.surface_transfer_method,
                "hayuya-surface-transfer-bvh-barycentric-exact-v2",
            )
            self.assertEqual(result.surface_transfer_fallback_vertices,0)

            from tools.hayuya3d.skin_weight_qa import _read_accessor
            from tools.hayuya3d.surface_transfer import (
                build_surface_transfer_relation,
                interpolate_vertex_values,
            )

            base_doc,base_binary=read_glb(base)
            out_doc,out_binary=read_glb(output)
            base_primitive=base_doc["meshes"][0]["primitives"][0]
            out_primitives=out_doc["meshes"][0]["primitives"]
            inserted=out_primitives[-1]

            base_positions=np.asarray(
                _read_accessor(
                    base_doc,
                    base_binary,
                    int(base_primitive["attributes"]["POSITION"]),
                ),
                dtype=np.float64,
            )
            base_faces=np.asarray(
                _read_accessor(
                    base_doc,
                    base_binary,
                    int(base_primitive["indices"]),
                ),
                dtype=np.int64,
            ).reshape((-1,3))
            base_delta=np.asarray(
                _read_accessor(
                    base_doc,
                    base_binary,
                    int(base_primitive["targets"][0]["POSITION"]),
                ),
                dtype=np.float64,
            )
            inserted_positions=np.asarray(
                _read_accessor(
                    out_doc,
                    out_binary,
                    int(inserted["attributes"]["POSITION"]),
                ),
                dtype=np.float64,
            )
            actual_delta=np.asarray(
                _read_accessor(
                    out_doc,
                    out_binary,
                    int(inserted["targets"][0]["POSITION"]),
                ),
                dtype=np.float64,
            )

            relation=build_surface_transfer_relation(
                base_positions,
                base_faces,
                inserted_positions,
            )
            expected=interpolate_vertex_values(
                base_delta,
                relation,
            )
            self.assertTrue(
                np.allclose(actual_delta,expected,atol=2e-6),
                (actual_delta-expected),
            )

            nearest_copy=base_delta[
                np.asarray(relation.nearest_vertex_ids,dtype=np.int64)
            ]
            self.assertGreater(
                float(np.max(np.abs(expected-nearest_copy))),
                1e-5,
            )

    def test_thin_parallel_surfaces_with_different_skin_are_ambiguous(self):
        from tools.hayuya3d.surface_transfer import (
            build_surface_transfer_index,
            query_surface_transfer,
        )

        vertices=np.asarray([
            [-1.0,-1.0,0.0],
            [ 1.0,-1.0,0.0],
            [ 1.0, 1.0,0.0],
            [-1.0, 1.0,0.0],
            [-1.0,-1.0,0.006],
            [ 1.0,-1.0,0.006],
            [ 1.0, 1.0,0.006],
            [-1.0, 1.0,0.006],
        ],dtype=np.float64)
        faces=np.asarray([
            [0,1,2],[0,2,3],
            [4,6,5],[4,7,6],
        ],dtype=np.int64)
        joints=np.zeros((len(vertices),4),dtype=np.int64)
        joints[4:,0]=1
        weights=np.zeros((len(vertices),4),dtype=np.float64)
        weights[:,0]=1.0
        targets=np.asarray([[0.25,0.10,0.003]],dtype=np.float64)

        index=build_surface_transfer_index(vertices,faces)
        relation=query_surface_transfer(index,targets)
        report=_surface_skin_ambiguity(
            vertices,
            joints,
            weights,
            targets,
            index,
            relation,
        )
        self.assertEqual(report.ambiguous_vertices,1)
        self.assertAlmostEqual(report.max_skin_l1,2.0,places=6)
        self.assertAlmostEqual(
            report.min_distance_gap_ratio or 0.0,
            0.0,
            places=8,
        )

    def test_distant_competing_surface_is_not_skin_ambiguous(self):
        from tools.hayuya3d.surface_transfer import (
            build_surface_transfer_index,
            query_surface_transfer,
        )

        vertices=np.asarray([
            [-1.0,-1.0,0.0],
            [ 1.0,-1.0,0.0],
            [ 1.0, 1.0,0.0],
            [-1.0, 1.0,0.0],
            [-1.0,-1.0,0.05],
            [ 1.0,-1.0,0.05],
            [ 1.0, 1.0,0.05],
            [-1.0, 1.0,0.05],
        ],dtype=np.float64)
        faces=np.asarray([
            [0,1,2],[0,2,3],
            [4,6,5],[4,7,6],
        ],dtype=np.int64)
        joints=np.zeros((len(vertices),4),dtype=np.int64)
        joints[4:,0]=1
        weights=np.zeros((len(vertices),4),dtype=np.float64)
        weights[:,0]=1.0
        targets=np.asarray([[0.25,0.10,0.001]],dtype=np.float64)

        index=build_surface_transfer_index(vertices,faces)
        relation=query_surface_transfer(index,targets)
        report=_surface_skin_ambiguity(
            vertices,
            joints,
            weights,
            targets,
            index,
            relation,
        )
        self.assertEqual(report.ambiguous_vertices,0)
        self.assertIsNone(report.min_distance_gap_ratio)
        self.assertAlmostEqual(report.max_skin_l1,0.0,places=8)

    def test_equivalent_skin_patch_does_not_trigger_ambiguity(self):
        from tools.hayuya3d.surface_transfer import (
            build_surface_transfer_index,
            query_surface_transfer,
        )

        vertices=np.asarray([
            [-1.0,-1.0,0.0],
            [ 1.0,-1.0,0.0],
            [ 1.0, 1.0,0.0],
            [-1.0, 1.0,0.0],
            [-0.2,-0.2,0.002],
            [ 0.2,-0.2,0.002],
            [ 0.0, 0.2,0.002],
        ],dtype=np.float64)
        faces=np.asarray([
            [0,1,2],[0,2,3],
            [4,5,6],
        ],dtype=np.int64)
        joints=np.zeros((len(vertices),4),dtype=np.int64)
        weights=np.zeros((len(vertices),4),dtype=np.float64)
        weights[:,0]=1.0
        targets=np.asarray([[0.0,0.0,0.001]],dtype=np.float64)

        index=build_surface_transfer_index(vertices,faces)
        relation=query_surface_transfer(index,targets)
        report=_surface_skin_ambiguity(
            vertices,
            joints,
            weights,
            targets,
            index,
            relation,
        )
        self.assertEqual(report.ambiguous_vertices,0)
        self.assertAlmostEqual(report.max_skin_l1,0.0,places=8)

    def test_degenerate_surface_fallback_is_not_production_safe(self):
        relation=SimpleNamespace(fallback_vertices=1)
        with self.assertRaisesRegex(
            RuntimeError,
            "degenerate base topology",
        ):
            _require_exact_surface_relation(relation)

        _require_exact_surface_relation(
            SimpleNamespace(fallback_vertices=0)
        )

    def test_thin_surface_skin_ambiguity_is_not_production_safe(self):
        relation=SimpleNamespace(
            fallback_vertices=0,
            ambiguous_skin_vertices=1,
            surface_skin_min_gap_ratio=0.0004,
            surface_skin_max_l1=1.75,
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "ambiguous across thin/folded geometry",
        ):
            _require_exact_surface_relation(relation)

    def test_weight_transfer_blends_neighbor_joint_influences(self):
        source_positions=np.asarray([
            [-1.0,0.0,0.0],
            [1.0,0.0,0.0],
        ],dtype=np.float64)
        source_joints=np.asarray([
            [0,0,0,0],
            [1,0,0,0],
        ],dtype=np.int64)
        source_weights=np.asarray([
            [1.0,0.0,0.0,0.0],
            [1.0,0.0,0.0,0.0],
        ],dtype=np.float64)
        target=np.asarray([[0.0,0.0,0.0]],dtype=np.float64)

        joints,weights,distances,nearest=_blend_skin_weights(
            source_positions,
            source_joints,
            source_weights,
            target,
            k=2,
        )
        active={
            int(joint):float(weight)
            for joint,weight in zip(joints[0],weights[0])
            if float(weight)>1e-6
        }
        self.assertEqual(set(active),{0,1})
        self.assertAlmostEqual(active[0],0.5,places=5)
        self.assertAlmostEqual(active[1],0.5,places=5)
        self.assertAlmostEqual(float(distances[0]),1.0,places=5)
        self.assertIn(int(nearest[0]),{0,1})

    def test_existing_base_accessory_cannot_be_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"base_with_accessory.glb"
            donor=root/"donor.glb"
            output=root/"blocked.glb"

            # The insert path is exclusively for an actually missing accessory.
            # A base that already owns a detached component must use wrap.
            body=trimesh.creation.icosphere(subdivisions=2,radius=1.0)
            charm=trimesh.creation.box(extents=[0.12,0.12,0.10])
            charm.apply_translation([0.0,1.08,0.0])
            combined=trimesh.util.concatenate([body,charm])
            vertices=np.asarray(combined.vertices,dtype=np.float32)
            faces=np.asarray(combined.faces,dtype=np.uint16)
            count=len(vertices)
            joints=np.zeros((count,4),dtype=np.uint8)
            weights=np.zeros((count,4),dtype=np.float32)
            weights[:,0]=1.0

            blob=bytearray()
            chunks=[]
            for payload in (
                vertices.astype("<f4").tobytes(),
                joints.tobytes(),
                weights.astype("<f4").tobytes(),
                faces.astype("<u2").reshape(-1).tobytes(),
            ):
                offset=_align(blob)
                blob.extend(payload)
                chunks.append((offset,len(payload)))
            doc={
                "asset":{"version":"2.0"},
                "buffers":[{"byteLength":len(blob)}],
                "bufferViews":[
                    {"buffer":0,"byteOffset":o,"byteLength":n}
                    for o,n in chunks
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
                "nodes":[{"mesh":0,"skin":0},{},{}],
                "skins":[{"joints":[1,2]}],
                "scenes":[{"nodes":[0,1,2]}],
                "scene":0,
            }
            write_glb(base,doc,bytes(blob))
            write_donor(donor)

            supported,reason=rigged_accessory_insert_supported(
                base,donor,
            )
            self.assertFalse(supported)
            self.assertIn("already has detached accessory",reason or "")

            result=insert_rigged_accessory(base,donor,output)
            self.assertFalse(result.ready)
            self.assertFalse(output.exists())
            self.assertTrue(any(
                "already has detached accessory" in error
                for error in result.errors
            ),result.errors)

    def test_composite_planner_defers_new_accessory_until_material_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "base.glb"
            donor_path = root / "donor.glb"
            source = "/refs/medal_detail.png"
            write_skinned_base(base_path, morph=True)
            write_donor(donor_path)

            base = candidate(
                "base",
                base_path,
                96.0,
                detail_source=source,
                detail_score=70.0,
            )
            donor = candidate(
                "donor",
                donor_path,
                84.0,
                detail_source=source,
                detail_score=98.0,
            )
            plan = build_composite_plan(
                [base, donor],
                mode="character",
                inspect_parts=True,
            )
            detail = next(
                item
                for item in plan.detail_donors
                if item.source == source
            )
            token = "detail:" + source
            self.assertEqual(
                detail.strategy,
                "new_rigged_accessory_insert_weight_morph_transfer",
            )
            self.assertTrue(
                detail.accessory_match["rigged_insert_supported"]
            )
            self.assertFalse(
                detail.accessory_match["rigged_insert_material_ready"]
            )
            self.assertNotIn(token, plan.executable_now)
            self.assertIn(token, plan.deferred_transfers)

            result = execute_safe_accessory_challenger(
                plan,
                root / "composite",
                detail_source=source,
                texture_size=256,
            )
            self.assertFalse(result.attempted)
            self.assertFalse(result.ready)
            self.assertIn(
                "UV/material transfer",
                result.error or "",
            )

    def test_composite_executes_textured_new_accessory_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base_path=root/"base.glb"
            donor_path=root/"textured_donor.glb"
            source="/refs/medal_detail.png"
            write_skinned_base(base_path,morph=True)
            write_donor(donor_path,textured=True)

            base=candidate(
                "base",
                base_path,
                96.0,
                detail_source=source,
                detail_score=70.0,
            )
            donor=candidate(
                "donor",
                donor_path,
                84.0,
                detail_source=source,
                detail_score=98.0,
            )
            plan=build_composite_plan(
                [base,donor],
                mode="character",
                inspect_parts=True,
            )
            detail=next(
                item for item in plan.detail_donors
                if item.source==source
            )
            token="detail:"+source
            self.assertEqual(
                detail.strategy,
                "new_rigged_accessory_insert_weight_morph_transfer",
            )
            self.assertTrue(
                detail.accessory_match["rigged_insert_supported"]
            )
            self.assertTrue(
                detail.accessory_match["rigged_insert_material_ready"],
                detail.accessory_match,
            )
            self.assertIn(token,plan.executable_now)
            self.assertNotIn(token,plan.deferred_transfers)

            result=execute_safe_accessory_challenger(
                plan,
                root/"composite",
                detail_source=source,
                texture_size=256,
            )
            self.assertTrue(result.attempted)
            self.assertTrue(result.ready,result.error)
            self.assertTrue(Path(result.candidate_path or "").is_file())
            self.assertTrue(result.fusion)
            self.assertTrue(result.fusion["production_ready"])
            self.assertTrue(result.fusion["material_ready"])
            self.assertTrue(result.fusion["uv_ready"])
            self.assertTrue(result.fusion["uv_tangent_ready"])
            self.assertTrue(result.fusion["rig_ready"])
            self.assertTrue(result.fusion["skin_weights_ready"])
            self.assertTrue(result.fusion["morph_deformation_ready"])
            self.assertTrue(result.fusion["attachment_ready"])
            self.assertIn("baseColor",result.fusion["material_channels"])
            self.assertIn("normal",result.fusion["material_channels"])

    def test_ambiguous_multiple_donor_accessories_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "ambiguous.glb"
            output = root / "blocked.glb"
            write_skinned_base(base, morph=True)
            write_donor(donor, ambiguous=True)

            result = insert_rigged_accessory(
                base,
                donor,
                output,
            )
            self.assertFalse(result.ready)
            self.assertFalse(output.exists())
            self.assertTrue(
                any(
                    "automatic grouping would be ambiguous" in error
                    or "not one proven anchored logical cluster" in error
                    for error in result.errors
                ),
                result.errors,
            )


if __name__ == "__main__":
    unittest.main()
