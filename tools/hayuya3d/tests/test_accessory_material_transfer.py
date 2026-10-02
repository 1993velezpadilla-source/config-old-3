from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import trimesh
from PIL import Image

from tools.hayuya3d.accessory_material_transfer import (
    accessory_material_transfer_supported,
    transfer_accessory_material,
)
from tools.hayuya3d.composite_champion import (
    build_composite_plan,
    execute_safe_accessory_challenger,
)
from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.rigged_accessory_insert import (
    insert_rigged_accessory,
    prepare_production_rigged_accessory_insert,
)
from tools.hayuya3d.rigged_accessory_split_insert import (
    insert_split_rigged_accessory,
)
from tools.hayuya3d.shading_basis_qa import audit_shading_basis
from tools.hayuya3d.uv_tangent_qa import audit_uv_tangents


def _align(blob: bytearray) -> int:
    while len(blob) % 4:
        blob.append(0)
    return len(blob)


def _append(blob: bytearray, payload: bytes) -> tuple[int, int]:
    offset = _align(blob)
    blob.extend(payload)
    return offset, len(payload)


def write_skinned_base_with_normals(
    path: Path,
    *,
    animated: bool = False,
) -> None:
    source = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    vertices = np.asarray(source.vertices, dtype=np.float32)
    normals = np.asarray(source.vertex_normals, dtype=np.float32)
    faces = np.asarray(source.faces, dtype=np.uint16)
    count = len(vertices)
    joints = np.zeros((count, 4), dtype=np.uint8)
    weights = np.zeros((count, 4), dtype=np.float32)
    upper = vertices[:, 1] >= 0.0
    joints[upper, 0] = 1
    weights[:, 0] = 1.0
    delta = np.zeros((count, 3), dtype=np.float32)
    delta[upper, 2] = 0.01

    blob = bytearray()
    payloads = [
        vertices.astype("<f4").tobytes(),
        normals.astype("<f4").tobytes(),
        joints.tobytes(),
        weights.astype("<f4").tobytes(),
        faces.astype("<u2").reshape(-1).tobytes(),
        delta.astype("<f4").tobytes(),
    ]
    chunks = [_append(blob, payload) for payload in payloads]
    views = [
        {"buffer": 0, "byteOffset": off, "byteLength": size}
        for off, size in chunks
    ]
    accessors = [
        {
            "bufferView": 0, "componentType": 5126,
            "count": count, "type": "VEC3",
            "min": vertices.min(axis=0).astype(float).tolist(),
            "max": vertices.max(axis=0).astype(float).tolist(),
        },
        {
            "bufferView": 1, "componentType": 5126,
            "count": count, "type": "VEC3",
            "min": normals.min(axis=0).astype(float).tolist(),
            "max": normals.max(axis=0).astype(float).tolist(),
        },
        {
            "bufferView": 2, "componentType": 5121,
            "count": count, "type": "VEC4",
        },
        {
            "bufferView": 3, "componentType": 5126,
            "count": count, "type": "VEC4",
        },
        {
            "bufferView": 4, "componentType": 5123,
            "count": int(faces.size), "type": "SCALAR",
        },
        {
            "bufferView": 5, "componentType": 5126,
            "count": count, "type": "VEC3",
            "min": delta.min(axis=0).astype(float).tolist(),
            "max": delta.max(axis=0).astype(float).tolist(),
        },
    ]

    animations = []
    if animated:
        times = np.asarray([0.0, 1.0], dtype=np.float32)
        translations = np.asarray([
            [0.0, 0.0, 0.0],
            [0.08, 0.0, 0.0],
        ], dtype=np.float32)

        time_offset = _align(blob)
        time_bytes = times.astype("<f4").tobytes()
        blob.extend(time_bytes)
        views.append({
            "buffer": 0,
            "byteOffset": time_offset,
            "byteLength": len(time_bytes),
        })
        time_accessor = len(accessors)
        accessors.append({
            "bufferView": len(views) - 1,
            "componentType": 5126,
            "count": len(times),
            "type": "SCALAR",
            "min": [0.0],
            "max": [1.0],
        })

        translation_offset = _align(blob)
        translation_bytes = translations.astype("<f4").tobytes()
        blob.extend(translation_bytes)
        views.append({
            "buffer": 0,
            "byteOffset": translation_offset,
            "byteLength": len(translation_bytes),
        })
        translation_accessor = len(accessors)
        accessors.append({
            "bufferView": len(views) - 1,
            "componentType": 5126,
            "count": len(translations),
            "type": "VEC3",
            "min": translations.min(axis=0).astype(float).tolist(),
            "max": translations.max(axis=0).astype(float).tolist(),
        })
        animations = [{
            "samplers": [{
                "input": time_accessor,
                "output": translation_accessor,
                "interpolation": "LINEAR",
            }],
            "channels": [
                {
                    "sampler": 0,
                    "target": {"node": 1, "path": "translation"},
                },
                {
                    "sampler": 0,
                    "target": {"node": 2, "path": "translation"},
                },
            ],
        }]

    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": views,
        "accessors": accessors,
        "meshes": [{
            "primitives": [{
                "attributes": {
                    "POSITION": 0,
                    "NORMAL": 1,
                    "JOINTS_0": 2,
                    "WEIGHTS_0": 3,
                },
                "indices": 4,
                "targets": [{"POSITION": 5}],
            }],
            "weights": [0.0],
        }],
        "nodes": [{"mesh": 0, "skin": 0}, {}, {}],
        "skins": [{"joints": [1, 2]}],
        "animations": animations,
        "scenes": [{"nodes": [0, 1, 2]}],
        "scene": 0,
    }
    write_glb(path, doc, bytes(blob))

def write_textured_donor(path: Path) -> None:
    body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    body_v = np.asarray(body.vertices, dtype=np.float32)
    body_n = np.asarray(body.vertex_normals, dtype=np.float32)
    body_f = np.asarray(body.faces, dtype=np.uint16)

    center = np.asarray([0.0, 1.08, 0.0], dtype=np.float32)
    accessory_v = np.asarray([
        [-0.08, -0.07, -0.05],
        [ 0.08, -0.07, -0.05],
        [ 0.00,  0.09, -0.03],
        [ 0.00, -0.01,  0.08],
    ], dtype=np.float32) + center
    accessory_f = np.asarray([
        [0, 2, 1],
        [0, 1, 3],
        [1, 2, 3],
        [2, 0, 3],
    ], dtype=np.uint16)
    accessory_mesh = trimesh.Trimesh(
        vertices=accessory_v,
        faces=accessory_f,
        process=False,
    )
    accessory_n = np.asarray(
        accessory_mesh.vertex_normals,
        dtype=np.float32,
    )
    accessory_uv = np.asarray([
        [0.05, 0.05],
        [0.95, 0.05],
        [0.20, 0.95],
        [0.80, 0.85],
    ], dtype=np.float32)

    image = Image.new("RGBA", (16, 16), (190, 130, 40, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    png = stream.getvalue()

    blob = bytearray()
    payloads = [
        body_v.astype("<f4").tobytes(),
        body_n.astype("<f4").tobytes(),
        body_f.astype("<u2").reshape(-1).tobytes(),
        accessory_v.astype("<f4").tobytes(),
        accessory_n.astype("<f4").tobytes(),
        accessory_uv.astype("<f4").tobytes(),
        accessory_f.astype("<u2").reshape(-1).tobytes(),
        png,
    ]
    chunks = [_append(blob, payload) for payload in payloads]
    views = [
        {"buffer": 0, "byteOffset": off, "byteLength": size}
        for off, size in chunks
    ]
    accessors = [
        {
            "bufferView": 0, "componentType": 5126,
            "count": len(body_v), "type": "VEC3",
            "min": body_v.min(axis=0).astype(float).tolist(),
            "max": body_v.max(axis=0).astype(float).tolist(),
        },
        {
            "bufferView": 1, "componentType": 5126,
            "count": len(body_n), "type": "VEC3",
        },
        {
            "bufferView": 2, "componentType": 5123,
            "count": int(body_f.size), "type": "SCALAR",
        },
        {
            "bufferView": 3, "componentType": 5126,
            "count": len(accessory_v), "type": "VEC3",
            "min": accessory_v.min(axis=0).astype(float).tolist(),
            "max": accessory_v.max(axis=0).astype(float).tolist(),
        },
        {
            "bufferView": 4, "componentType": 5126,
            "count": len(accessory_n), "type": "VEC3",
        },
        {
            "bufferView": 5, "componentType": 5126,
            "count": len(accessory_uv), "type": "VEC2",
        },
        {
            "bufferView": 6, "componentType": 5123,
            "count": int(accessory_f.size), "type": "SCALAR",
        },
    ]
    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": views,
        "accessors": accessors,
        "images": [{
            "bufferView": 7,
            "mimeType": "image/png",
        }],
        "textures": [{"source": 0}],
        "materials": [{
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0},
                "metallicFactor": 0.0,
                "roughnessFactor": 0.55,
            }
        }],
        "meshes": [{
            "primitives": [
                {
                    "attributes": {
                        "POSITION": 0,
                        "NORMAL": 1,
                    },
                    "indices": 2,
                },
                {
                    "attributes": {
                        "POSITION": 3,
                        "NORMAL": 4,
                        "TEXCOORD_0": 5,
                    },
                    "indices": 6,
                    "material": 0,
                },
            ]
        }],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    write_glb(path, doc, bytes(blob))


def write_shared_atlas_cluster_donor(path: Path) -> None:
    body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    body_v = np.asarray(body.vertices, dtype=np.float32)
    body_f = np.asarray(body.faces, dtype=np.int64)

    pieces = []
    for center in (
        (0.0, 1.06, 0.0),
        (0.0, 1.17, 0.0),
        (0.0, 1.28, 0.0),
    ):
        local = np.asarray([
            [-0.045, -0.040, -0.035],
            [ 0.045, -0.040, -0.035],
            [ 0.000,  0.050, -0.025],
            [ 0.000,  0.000,  0.050],
        ], dtype=np.float32)
        local += np.asarray(center, dtype=np.float32)
        faces = np.asarray([
            [0, 2, 1],
            [0, 1, 3],
            [1, 2, 3],
            [2, 0, 3],
        ], dtype=np.int64)
        pieces.append((local, faces))

    vertices = [body_v]
    faces = [body_f]
    cursor = len(body_v)
    for vv, ff in pieces:
        vertices.append(vv)
        faces.append(ff + cursor)
        cursor += len(vv)
    vertices = np.concatenate(vertices, axis=0).astype(np.float32)
    faces = np.concatenate(faces, axis=0).astype(np.uint16)

    combined = trimesh.Trimesh(
        vertices=vertices,
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    normals = np.asarray(combined.vertex_normals, dtype=np.float32)

    uvs = np.zeros((len(vertices), 2), dtype=np.float32)
    cursor = len(body_v)
    piece_uv = np.asarray([
        [0.05, 0.05],
        [0.35, 0.08],
        [0.14, 0.38],
        [0.38, 0.34],
    ], dtype=np.float32)
    offsets = (
        (0.00, 0.00),
        (0.48, 0.00),
        (0.22, 0.52),
    )
    for offset in offsets:
        uv = piece_uv + np.asarray(offset, dtype=np.float32)
        uvs[cursor:cursor + 4] = uv
        cursor += 4

    image = Image.new("RGBA", (32, 32), (176, 120, 42, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    png = stream.getvalue()

    blob = bytearray()
    payloads = [
        vertices.astype("<f4").tobytes(),
        normals.astype("<f4").tobytes(),
        uvs.astype("<f4").tobytes(),
        faces.astype("<u2").reshape(-1).tobytes(),
        png,
    ]
    chunks = [_append(blob, payload) for payload in payloads]
    views = [
        {"buffer": 0, "byteOffset": off, "byteLength": size}
        for off, size in chunks
    ]
    accessors = [
        {
            "bufferView": 0, "componentType": 5126,
            "count": len(vertices), "type": "VEC3",
            "min": vertices.min(axis=0).astype(float).tolist(),
            "max": vertices.max(axis=0).astype(float).tolist(),
        },
        {
            "bufferView": 1, "componentType": 5126,
            "count": len(normals), "type": "VEC3",
        },
        {
            "bufferView": 2, "componentType": 5126,
            "count": len(uvs), "type": "VEC2",
        },
        {
            "bufferView": 3, "componentType": 5123,
            "count": int(faces.size), "type": "SCALAR",
        },
    ]
    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": views,
        "accessors": accessors,
        "images": [{"bufferView": 4, "mimeType": "image/png"}],
        "textures": [{"source": 0}],
        "materials": [{
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0},
                "metallicFactor": 0.1,
                "roughnessFactor": 0.48,
            }
        }],
        "meshes": [{
            "primitives": [{
                "attributes": {
                    "POSITION": 0,
                    "NORMAL": 1,
                    "TEXCOORD_0": 2,
                },
                "indices": 3,
                "material": 0,
            }]
        }],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    write_glb(path, doc, bytes(blob))


def write_split_material_cluster_donor(
    path: Path,
    *,
    normal_maps: bool = False,
) -> None:
    def piece(center, color):
        vertices = np.asarray([
            [-0.045, -0.040, -0.035],
            [ 0.045, -0.040, -0.035],
            [ 0.000,  0.050, -0.025],
            [ 0.000,  0.000,  0.050],
        ], dtype=np.float64)
        vertices += np.asarray(center, dtype=np.float64)
        faces = np.asarray([
            [0, 2, 1],
            [0, 1, 3],
            [1, 2, 3],
            [2, 0, 3],
        ], dtype=np.int64)
        mesh = trimesh.Trimesh(
            vertices=vertices,
            faces=faces,
            process=False,
        )
        uv = np.asarray([
            [0.05, 0.05],
            [0.95, 0.05],
            [0.10, 0.90],
            [0.90, 0.85],
        ], dtype=np.float64)
        base = np.zeros((16, 16, 4), dtype=np.uint8)
        base[:, :, :3] = np.asarray(color, dtype=np.uint8)
        base[:, :, 3] = 255

        normal_texture = None
        if normal_maps:
            normal_pixels = np.zeros((16, 16, 3), dtype=np.uint8)
            normal_pixels[:, :, 0] = 128
            normal_pixels[:, :, 1] = 128
            normal_pixels[:, :, 2] = 255
            normal_texture = Image.fromarray(normal_pixels, "RGB")

        material = trimesh.visual.material.PBRMaterial(
            baseColorTexture=Image.fromarray(base, "RGBA"),
            normalTexture=normal_texture,
            metallicFactor=0.15,
            roughnessFactor=0.5,
        )
        mesh.visual = trimesh.visual.TextureVisuals(
            uv=uv,
            material=material,
        )
        return mesh

    scene = trimesh.Scene()
    scene.add_geometry(
        trimesh.creation.icosphere(subdivisions=2, radius=1.0),
        node_name="body",
    )
    for index, (center, color) in enumerate((
        ((0.0, 1.06, 0.0), (180, 120, 35)),
        ((0.0, 1.17, 0.0), (150, 85, 30)),
        ((0.0, 1.28, 0.0), (205, 155, 60)),
    )):
        scene.add_geometry(
            piece(center, color),
            node_name=f"accessory_{index}",
        )
    path.write_bytes(trimesh.exchange.gltf.export_glb(scene))

def _candidate(
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


class AccessoryMaterialTransferTests(unittest.TestCase):
    def test_textured_donor_material_becomes_valid_inserted_primitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "donor.glb"
            raw = root / "raw-insert.glb"
            final = root / "material-insert.glb"
            write_skinned_base_with_normals(base)
            write_textured_donor(donor)

            supported, blocker = accessory_material_transfer_supported(
                donor,
                up_axis="y",
            )
            self.assertTrue(supported, blocker)

            inserted = insert_rigged_accessory(
                base,
                donor,
                raw,
            )
            self.assertTrue(inserted.geometry_ready, inserted.errors)
            self.assertFalse(inserted.production_ready)

            transfer = transfer_accessory_material(
                donor,
                raw,
                final,
                donor_up_axis="y",
            )
            self.assertTrue(transfer.ready, transfer.errors)
            self.assertEqual(transfer.uv_vertices, inserted.inserted_vertices)
            self.assertEqual(transfer.copied_images, 1)
            self.assertEqual(transfer.copied_textures, 1)
            self.assertIn("baseColor", transfer.copied_channels)
            self.assertTrue(transfer.uv_tangent_ready)
            self.assertTrue(transfer.shading_basis_ready)
            self.assertFalse(transfer.tangent_generated)
            self.assertTrue(audit_uv_tangents(final).ready)
            self.assertTrue(audit_shading_basis(final).ready)

    def test_shared_atlas_multi_piece_cluster_transfers_as_one_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "cluster.glb"
            raw = root / "cluster-raw.glb"
            final = root / "cluster-final.glb"
            write_skinned_base_with_normals(base)
            write_shared_atlas_cluster_donor(donor)

            supported, blocker = accessory_material_transfer_supported(
                donor,
                up_axis="y",
            )
            self.assertTrue(supported, blocker)

            inserted = insert_rigged_accessory(
                base,
                donor,
                raw,
            )
            self.assertTrue(inserted.geometry_ready, inserted.errors)
            self.assertEqual(inserted.spatial_label, "cluster")
            self.assertFalse(inserted.production_ready)

            transfer = transfer_accessory_material(
                donor,
                raw,
                final,
                donor_up_axis="y",
            )
            self.assertTrue(transfer.ready, transfer.errors)
            self.assertEqual(len(transfer.donor_component_ids), 3)
            self.assertEqual(
                transfer.uv_vertices,
                inserted.inserted_vertices,
            )
            self.assertEqual(transfer.copied_images, 1)
            self.assertEqual(transfer.copied_textures, 1)
            self.assertIn("baseColor", transfer.copied_channels)
            self.assertTrue(transfer.uv_tangent_ready)
            self.assertTrue(transfer.shading_basis_ready)
            self.assertTrue(audit_uv_tangents(final).ready)
            self.assertTrue(audit_shading_basis(final).ready)

    def test_shared_atlas_cluster_is_production_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "cluster.glb"
            write_skinned_base_with_normals(base)
            write_shared_atlas_cluster_donor(donor)

            result = prepare_production_rigged_accessory_insert(
                base,
                donor,
                root / "production",
            )
            self.assertTrue(result.ready, result.errors)
            self.assertTrue(result.production_ready, result.material_blockers)
            self.assertTrue(result.geometry_ready)
            self.assertTrue(result.material_ready)
            self.assertTrue(result.uv_ready)
            self.assertTrue(result.uv_tangent_ready)
            self.assertTrue(result.legacy_payload_preserved)
            self.assertTrue(result.rig_ready)
            self.assertTrue(result.skin_weights_ready)
            self.assertTrue(result.morph_deformation_ready)
            self.assertTrue(result.attachment_ready)
            self.assertIn("baseColor", result.material_channels)

    def test_composite_executes_shared_atlas_cluster_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "base.glb"
            donor_path = root / "cluster.glb"
            source = "/refs/rosary_cluster.png"
            write_skinned_base_with_normals(base_path)
            write_shared_atlas_cluster_donor(donor_path)

            base = _candidate(
                "base",
                base_path,
                96.0,
                detail_source=source,
                detail_score=70.0,
            )
            donor = _candidate(
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
                item for item in plan.detail_donors
                if item.source == source
            )
            token = "detail:" + source
            self.assertEqual(
                detail.strategy,
                "new_rigged_accessory_insert_weight_morph_transfer",
            )
            self.assertTrue(
                detail.accessory_match["rigged_insert_supported"],
                detail.accessory_match,
            )
            self.assertTrue(
                detail.accessory_match["rigged_insert_material_ready"],
                detail.accessory_match,
            )
            self.assertIn(token, plan.executable_now)
            self.assertNotIn(token, plan.deferred_transfers)

            result = execute_safe_accessory_challenger(
                plan,
                root / "composite",
                detail_source=source,
                texture_size=256,
            )
            self.assertTrue(result.attempted)
            self.assertTrue(result.ready, result.error)
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
            self.assertIn("baseColor", result.fusion["material_channels"])

    def test_split_material_cluster_preserves_piece_materials_and_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "split-cluster.glb"
            raw = root / "split-raw.glb"
            final = root / "split-final.glb"
            write_skinned_base_with_normals(base)
            write_split_material_cluster_donor(donor)

            supported, blocker = accessory_material_transfer_supported(
                donor,
                up_axis="y",
            )
            self.assertTrue(supported, blocker)

            inserted = insert_split_rigged_accessory(
                base,
                donor,
                raw,
            )
            self.assertTrue(inserted.geometry_ready, inserted.errors)
            self.assertEqual(inserted.spatial_label, "cluster")
            self.assertFalse(inserted.production_ready)
            self.assertTrue(
                any(
                    warning == "split_accessory_groups=3"
                    for warning in inserted.warnings
                ),
                inserted.warnings,
            )

            transfer = transfer_accessory_material(
                donor,
                raw,
                final,
                donor_up_axis="y",
            )
            self.assertTrue(transfer.ready, transfer.errors)
            self.assertEqual(len(transfer.donor_component_ids), 3)
            self.assertEqual(
                transfer.uv_vertices,
                inserted.inserted_vertices,
            )
            self.assertGreaterEqual(transfer.copied_images, 3)
            self.assertGreaterEqual(transfer.copied_textures, 3)
            self.assertIn("baseColor", transfer.copied_channels)
            self.assertTrue(transfer.uv_tangent_ready)
            self.assertTrue(transfer.shading_basis_ready)
            self.assertTrue(audit_uv_tangents(final).ready)
            self.assertTrue(audit_shading_basis(final).ready)

            production = prepare_production_rigged_accessory_insert(
                base,
                donor,
                root / "split-production",
            )
            self.assertTrue(production.ready, production.errors)
            self.assertTrue(
                production.production_ready,
                production.material_blockers,
            )
            self.assertTrue(production.legacy_payload_preserved)
            self.assertTrue(production.rig_ready)
            self.assertTrue(production.skin_weights_ready)
            self.assertTrue(production.morph_deformation_ready)
            self.assertTrue(production.attachment_ready)

    def test_split_insert_builds_surface_bvh_once_for_all_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "split-cluster.glb"
            raw = root / "split-raw.glb"
            write_skinned_base_with_normals(base)
            write_split_material_cluster_donor(donor)

            import importlib
            surface_transfer = importlib.import_module("surface_transfer")
            original = surface_transfer.build_surface_transfer_index
            calls = []

            def counted(*args, **kwargs):
                calls.append(1)
                return original(*args, **kwargs)

            from unittest.mock import patch
            with patch.object(
                surface_transfer,
                "build_surface_transfer_index",
                side_effect=counted,
            ):
                inserted = insert_split_rigged_accessory(
                    base,
                    donor,
                    raw,
                )

            self.assertTrue(inserted.geometry_ready, inserted.errors)
            self.assertEqual(len(calls), 1)
            self.assertTrue(
                any(
                    warning == "split_accessory_groups=3"
                    for warning in inserted.warnings
                ),
                inserted.warnings,
            )

    def test_split_material_normal_maps_survive_skeletal_animation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "animated-base.glb"
            donor = root / "normal-split-cluster.glb"
            write_skinned_base_with_normals(
                base,
                animated=True,
            )
            write_split_material_cluster_donor(
                donor,
                normal_maps=True,
            )

            production = prepare_production_rigged_accessory_insert(
                base,
                donor,
                root / "animated-production",
            )
            self.assertTrue(production.ready, production.errors)
            self.assertTrue(
                production.production_ready,
                production.material_blockers,
            )
            self.assertTrue(production.animation_ready, production.errors)
            self.assertTrue(production.deformation_ready, production.errors)
            self.assertTrue(production.skin_weights_ready, production.errors)
            self.assertTrue(
                production.morph_deformation_ready,
                production.errors,
            )
            self.assertTrue(production.uv_tangent_ready)
            self.assertIn("baseColor", production.material_channels)
            self.assertIn("normal", production.material_channels)

            from tools.hayuya3d.glb_images import read_glb
            final_doc, _ = read_glb(Path(production.output_glb))
            skinned_node = next(
                node
                for node in final_doc.get("nodes") or []
                if isinstance(node.get("mesh"), int)
                and isinstance(node.get("skin"), int)
            )
            primitives = final_doc["meshes"][int(skinned_node["mesh"])][
                "primitives"
            ]
            split_primitives = [
                primitive
                for primitive in primitives
                if (primitive.get("extras") or {}).get(
                    "hayuyaAccessorySplit"
                )
            ]
            self.assertEqual(len(split_primitives), 3)
            self.assertTrue(all(
                "TANGENT" in (primitive.get("attributes") or {})
                for primitive in split_primitives
            ))
            self.assertTrue(
                audit_uv_tangents(Path(production.output_glb)).ready
            )
            self.assertTrue(
                audit_shading_basis(Path(production.output_glb)).ready
            )

    def test_composite_executes_split_material_cluster_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "base.glb"
            donor_path = root / "split-cluster.glb"
            source = "/refs/rosary_split_material.png"
            write_skinned_base_with_normals(base_path)
            write_split_material_cluster_donor(donor_path)

            base = _candidate(
                "base",
                base_path,
                96.0,
                detail_source=source,
                detail_score=70.0,
            )
            donor = _candidate(
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
                item for item in plan.detail_donors
                if item.source == source
            )
            token = "detail:" + source
            self.assertEqual(
                detail.strategy,
                "new_rigged_accessory_insert_weight_morph_transfer",
            )
            self.assertTrue(
                detail.accessory_match["rigged_insert_supported"],
                detail.accessory_match,
            )
            self.assertTrue(
                detail.accessory_match["rigged_insert_material_ready"],
                detail.accessory_match,
            )
            self.assertIn(token, plan.executable_now)
            self.assertNotIn(token, plan.deferred_transfers)

            result = execute_safe_accessory_challenger(
                plan,
                root / "composite",
                detail_source=source,
                texture_size=256,
            )
            self.assertTrue(result.attempted)
            self.assertTrue(result.ready, result.error)
            self.assertTrue(Path(result.candidate_path or "").is_file())
            self.assertTrue(result.fusion)
            self.assertTrue(result.fusion["production_ready"])
            self.assertTrue(result.fusion["material_ready"])
            self.assertTrue(result.fusion["uv_ready"])
            self.assertTrue(result.fusion["uv_tangent_ready"])
            self.assertTrue(result.fusion["legacy_payload_preserved"])
            self.assertTrue(result.fusion["rig_ready"])
            self.assertTrue(result.fusion["skin_weights_ready"])
            self.assertTrue(result.fusion["morph_deformation_ready"])
            self.assertTrue(result.fusion["attachment_ready"])
            self.assertIn("baseColor", result.fusion["material_channels"])

            from tools.hayuya3d.glb_images import read_glb
            final_doc, _ = read_glb(Path(result.candidate_path))
            skinned_node = next(
                node
                for node in final_doc.get("nodes") or []
                if isinstance(node.get("mesh"), int)
                and isinstance(node.get("skin"), int)
            )
            mesh = final_doc["meshes"][int(skinned_node["mesh"])]
            primitives = mesh.get("primitives") or []
            self.assertEqual(len(primitives), 4)
            accessory_primitives = primitives[1:]
            self.assertTrue(all(
                isinstance(item.get("material"), int)
                for item in accessory_primitives
            ))
            self.assertEqual(
                len({
                    int(item["material"])
                    for item in accessory_primitives
                }),
                3,
            )

    def test_untextured_donor_material_support_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            donor = Path(tmp) / "donor.glb"
            body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
            charm = trimesh.creation.box(
                extents=[0.12, 0.12, 0.10]
            )
            charm.apply_translation([0.0, 1.08, 0.0])
            scene = trimesh.Scene()
            scene.add_geometry(body)
            scene.add_geometry(charm)
            donor.write_bytes(trimesh.exchange.gltf.export_glb(scene))

            supported, blocker = accessory_material_transfer_supported(donor)
            self.assertFalse(supported)
            self.assertIsNotNone(blocker)


if __name__ == "__main__":
    unittest.main()
