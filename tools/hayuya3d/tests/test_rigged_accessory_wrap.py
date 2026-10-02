from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import trimesh

from tools.hayuya3d.composite_champion import (
    build_composite_plan,
    execute_safe_accessory_challenger,
)
from tools.hayuya3d.glb_images import write_glb
from tools.hayuya3d.gltf_audit import audit_glb
from tools.hayuya3d.gltf_position_patch import runtime_payload_signature
from tools.hayuya3d.morph_deformation_qa import audit_morph_deformation
from tools.hayuya3d.rigged_accessory_wrap import wrap_rigged_accessory
from tools.hayuya3d.skin_weight_qa import audit_skin_weights


def _align(blob: bytearray) -> int:
    while len(blob) % 4:
        blob.append(0)
    return len(blob)


def _combined_body_accessory(
    *,
    accessory_extent=(0.16, 0.16, 0.16),
    accessory_center=(0.0, 1.14, 0.0),
):
    body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    accessory = trimesh.creation.box(extents=accessory_extent)
    accessory.apply_translation(accessory_center)
    return trimesh.util.concatenate([body, accessory])


def write_skinned_accessory_character(
    path: Path,
    *,
    accessory_extent=(0.16, 0.16, 0.16),
    morph: bool = True,
) -> None:
    mesh = _combined_body_accessory(accessory_extent=accessory_extent)
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.uint16)
    count = len(vertices)

    joints = np.zeros((count, 4), dtype=np.uint8)
    weights = np.zeros((count, 4), dtype=np.float32)
    weights[:, 0] = 1.0

    blob = bytearray()
    pos_offset = _align(blob)
    pos_bytes = vertices.astype("<f4").tobytes()
    blob.extend(pos_bytes)

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
            "componentType": 5121,
            "count": count,
            "type": "VEC4",
        },
        {
            "bufferView": 2,
            "componentType": 5126,
            "count": count,
            "type": "VEC4",
        },
        {
            "bufferView": 3,
            "componentType": 5123,
            "count": int(faces.size),
            "type": "SCALAR",
        },
    ]
    primitive = {
        "attributes": {
            "POSITION": 0,
            "JOINTS_0": 1,
            "WEIGHTS_0": 2,
        },
        "indices": 3,
    }
    mesh_doc = {"primitives": [primitive]}

    if morph:
        delta = np.zeros((count, 3), dtype=np.float32)
        # Small benign deformation so this is a real morph payload, not merely
        # an empty target. The topology-preserving accessory wrap must not
        # alter these bytes.
        delta[:, 1] = 0.002
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
        mesh_doc["weights"] = [0.0]

    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": views,
        "accessors": accessors,
        "meshes": [mesh_doc],
        "nodes": [
            {"mesh": 0, "skin": 0},
            {},
            {},
        ],
        "skins": [{"joints": [1, 2]}],
        "scenes": [{"nodes": [0, 1, 2]}],
        "scene": 0,
    }
    write_glb(path, doc, bytes(blob))


def write_unskinned_donor(
    path: Path,
    *,
    accessory_extent=(0.26, 0.12, 0.20),
) -> None:
    mesh = _combined_body_accessory(accessory_extent=accessory_extent)
    path.write_bytes(
        trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
    )


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


class RiggedAccessoryWrapTests(unittest.TestCase):
    def test_wrap_preserves_skin_and_morph_runtime_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "donor.glb"
            output = root / "wrapped.glb"
            write_skinned_accessory_character(base, morph=True)
            write_unskinned_donor(donor)

            before_signature = runtime_payload_signature(base)
            before_rig = audit_glb(base)
            self.assertTrue(before_rig.rig_ready)
            self.assertGreater(before_rig.morph_target_count, 0)
            self.assertTrue(audit_skin_weights(base).ready)
            self.assertTrue(audit_morph_deformation(base).ready)

            result = wrap_rigged_accessory(
                base,
                donor,
                output,
                mode="character",
                base_up_axis="y",
            )

            self.assertTrue(result.ready, result.errors)
            self.assertTrue(output.is_file())
            self.assertGreater(result.changed_vertices, 0)
            self.assertTrue(result.runtime_payload_preserved)
            self.assertTrue(result.rig_ready)
            self.assertTrue(result.skin_weights_ready)
            self.assertTrue(result.morph_deformation_ready)
            self.assertTrue(result.component_crossing_ready)
            self.assertTrue(result.self_intersection_ready)
            self.assertTrue(result.attachment_ready)
            self.assertEqual(
                before_signature,
                runtime_payload_signature(output),
            )
            self.assertTrue(audit_glb(output).rig_ready)
            self.assertTrue(audit_skin_weights(output).ready)
            self.assertTrue(audit_morph_deformation(output).ready)

    def test_composite_champion_executes_rigged_accessory_wrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "base.glb"
            donor_path = root / "donor.glb"
            source = "/refs/rosary_detail.png"
            write_skinned_accessory_character(base_path, morph=True)
            write_unskinned_donor(
                donor_path,
                accessory_extent=(0.24, 0.12, 0.20),
            )

            base = candidate(
                "base",
                base_path,
                96.0,
                detail_source=source,
                detail_score=72.0,
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
                "matched_rig_preserving_accessory_wrap_then_rebake",
            )
            self.assertTrue(
                detail.accessory_match["rigged_wrap_supported"]
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
            self.assertTrue(result.fusion["runtime_payload_preserved"])
            self.assertTrue(result.fusion["rig_ready"])
            self.assertTrue(result.fusion["skin_weights_ready"])
            self.assertTrue(result.fusion["morph_deformation_ready"])
            self.assertTrue(result.fusion["attachment_ready"])
            self.assertTrue(result.fusion["rebake_ready"])

    def test_missing_base_accessory_fails_closed_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.glb"
            donor = root / "donor.glb"
            output = root / "blocked.glb"

            # A single connected skinned sphere has no detached accessory
            # candidate, so HAYUYA must not invent one from the donor.
            source = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
            vertices = np.asarray(source.vertices, dtype=np.float32)
            faces = np.asarray(source.faces, dtype=np.uint16)
            count = len(vertices)
            joints = np.zeros((count, 4), dtype=np.uint8)
            weights = np.zeros((count, 4), dtype=np.float32)
            weights[:, 0] = 1.0

            blob = bytearray()
            chunks = []
            for payload in (
                vertices.astype("<f4").tobytes(),
                joints.tobytes(),
                weights.astype("<f4").tobytes(),
                faces.astype("<u2").reshape(-1).tobytes(),
            ):
                offset = _align(blob)
                blob.extend(payload)
                chunks.append((offset, len(payload)))
            doc = {
                "asset": {"version": "2.0"},
                "buffers": [{"byteLength": len(blob)}],
                "bufferViews": [
                    {"buffer": 0, "byteOffset": o, "byteLength": n}
                    for o, n in chunks
                ],
                "accessors": [
                    {
                        "bufferView": 0, "componentType": 5126,
                        "count": count, "type": "VEC3",
                        "min": vertices.min(axis=0).astype(float).tolist(),
                        "max": vertices.max(axis=0).astype(float).tolist(),
                    },
                    {
                        "bufferView": 1, "componentType": 5121,
                        "count": count, "type": "VEC4",
                    },
                    {
                        "bufferView": 2, "componentType": 5126,
                        "count": count, "type": "VEC4",
                    },
                    {
                        "bufferView": 3, "componentType": 5123,
                        "count": int(faces.size), "type": "SCALAR",
                    },
                ],
                "meshes": [{
                    "primitives": [{
                        "attributes": {
                            "POSITION": 0,
                            "JOINTS_0": 1,
                            "WEIGHTS_0": 2,
                        },
                        "indices": 3,
                    }]
                }],
                "nodes": [{"mesh": 0, "skin": 0}, {}, {}],
                "skins": [{"joints": [1, 2]}],
                "scenes": [{"nodes": [0, 1, 2]}],
                "scene": 0,
            }
            write_glb(base, doc, bytes(blob))
            write_unskinned_donor(donor)

            result = wrap_rigged_accessory(base, donor, output)
            self.assertFalse(result.ready)
            self.assertFalse(output.exists())
            self.assertTrue(
                any(
                    "accessory correspondence" in error
                    for error in result.errors
                ),
                result.errors,
            )


if __name__ == "__main__":
    unittest.main()
