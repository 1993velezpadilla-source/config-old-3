#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def _deps():
    import numpy as np
    return np


def split_rigged_accessory_insert_supported(
    base_mesh: Path,
    donor_mesh: Path,
    *,
    base_up_axis: str = "y",
    donor_up_axis: str | None = None,
) -> tuple[bool, str | None]:
    donor_up_axis = donor_up_axis or base_up_axis
    try:
        from gltf_audit import audit_glb
        from skin_weight_qa import audit_skin_weights
        from accessory_match import inspect_accessories
        from accessory_source_groups import audit_accessory_source_groups
        from rigged_accessory_insert import _base_primitive

        if donor_up_axis != base_up_axis:
            return False, "split insertion requires matching base/donor up axes"
        rig = audit_glb(base_mesh)
        skin = audit_skin_weights(base_mesh)
        if not rig.rig_ready:
            return False, "base rig is not valid"
        if not skin.applicable or not skin.ready:
            return False, "base skin weights are not valid"
        if inspect_accessories(
            base_mesh,
            mode="character",
            up_axis=base_up_axis,
        ):
            return (
                False,
                "base already has detached accessory candidates; use wrap",
            )
        _base_primitive(base_mesh)
        source = audit_accessory_source_groups(
            donor_mesh,
            mode="character",
            up_axis=donor_up_axis,
        )
        if not source.ready:
            return False, ";".join(source.errors or ["source-group audit failed"])
        if source.group_count <= 1:
            return False, "donor does not require split-preserving insertion"
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"


def _group_geometry(
    donor_doc: dict,
    donor_binary: bytes,
    group,
):
    np = _deps()
    from deformation_qa import _global_matrices
    from part_map import _component_ids
    from skin_weight_qa import _read_accessor

    meshes = donor_doc.get("meshes") or []
    if not (0 <= int(group.mesh_index) < len(meshes)):
        raise RuntimeError("source group mesh index is invalid")
    primitives = meshes[int(group.mesh_index)].get("primitives") or []
    if not (0 <= int(group.primitive_index) < len(primitives)):
        raise RuntimeError("source group primitive index is invalid")
    primitive = primitives[int(group.primitive_index)]
    attrs = primitive.get("attributes") or {}
    position_index = attrs.get("POSITION")
    index_index = primitive.get("indices")
    if not isinstance(position_index, int) or not isinstance(index_index, int):
        raise RuntimeError("source group primitive is not indexed")
    positions = np.asarray(
        _read_accessor(donor_doc, donor_binary, position_index),
        dtype=np.float64,
    )
    raw = np.asarray(
        _read_accessor(donor_doc, donor_binary, index_index),
        dtype=np.int64,
    ).reshape(-1)
    if len(raw) % 3:
        raise RuntimeError("source group index count is not divisible by three")
    faces = raw.reshape((-1, 3))
    component_ids = _component_ids(faces)
    wanted = np.asarray(group.primitive_component_ids, dtype=np.int64)
    selected_faces = faces[np.isin(component_ids, wanted)]
    if not len(selected_faces):
        raise RuntimeError("source group contains no selected faces")
    used = np.unique(selected_faces.reshape(-1))
    expected = np.asarray(group.used_vertex_ids, dtype=np.int64)
    if not np.array_equal(used, expected):
        raise RuntimeError(
            "source-group vertex mapping changed between audit and insertion"
        )
    remap = {int(old): new for new, old in enumerate(used.tolist())}
    local_faces = np.asarray([
        [remap[int(x)] for x in tri]
        for tri in selected_faces
    ], dtype=np.int64)

    globals_ = _global_matrices(donor_doc, {})
    matrix = np.asarray(
        globals_[int(group.node_index)],
        dtype=np.float64,
    )
    homogeneous = np.concatenate(
        [
            positions[used],
            np.ones((len(used), 1), dtype=np.float64),
        ],
        axis=1,
    )
    world = (matrix @ homogeneous.T).T[:, :3]
    return primitive, used, world, local_faces


def insert_split_rigged_accessory(
    base_mesh: Path,
    donor_mesh: Path,
    output_glb: Path,
    *,
    base_up_axis: str = "y",
    donor_up_axis: str | None = None,
    max_weight_source_distance_ratio: float = 0.12,
    max_bbox_drift_fraction: float = 0.18,
):
    np = _deps()
    donor_up_axis = donor_up_axis or base_up_axis
    warnings: list[str] = []
    errors: list[str] = []

    from rigged_accessory_insert import (
        RiggedAccessoryInsertResult,
        _append_accessor,
        _base_primitive,
        _bbox,
        _legacy_payload_preserved,
        _surface_skin_transfer,
        _require_exact_surface_relation,
        _pack_joints,
        _read_target_deltas,
    )

    def fail(message: str):
        return RiggedAccessoryInsertResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            attempted=True,
            ready=False,
            geometry_ready=False,
            material_ready=False,
            uv_ready=False,
            uv_tangent_ready=False,
            material_channels=[],
            production_ready=False,
            legacy_payload_preserved=False,
            material_blockers=[],
            donor_component_id=None,
            spatial_label=None,
            inserted_vertices=0,
            inserted_faces=0,
            transferred_weight_vertices=0,
            weight_source_max_distance_ratio=None,
            weight_source_mean_distance_ratio=None,
            morph_targets_transferred=0,
            morph_semantics_transferred=[],
            rig_ready=False,
            skin_weights_ready=False,
            morph_ready=False,
            morph_deformation_ready=None,
            animation_ready=None,
            deformation_ready=None,
            attachment_ready=False,
            component_crossing_ready=False,
            self_intersection_ready=False,
            bbox_drift_fraction=None,
            warnings=warnings,
            errors=[message],
        )

    try:
        from accessory_match import inspect_accessories
        from accessory_source_groups import audit_accessory_source_groups
        from gltf_audit import audit_glb
        from gltf_position_patch import _doc_and_bin
        from skin_weight_qa import audit_skin_weights
        from part_map import _component_ids, _load_mesh

        before_rig = audit_glb(base_mesh)
        before_skin = audit_skin_weights(base_mesh)
        if not before_rig.rig_ready:
            raise RuntimeError("base rig is not valid")
        if not before_skin.applicable or not before_skin.ready:
            raise RuntimeError("base skin weights are not valid")
        if donor_up_axis != base_up_axis:
            raise RuntimeError(
                "split insertion requires matching base/donor up axes"
            )
        if inspect_accessories(
            base_mesh,
            mode="character",
            up_axis=base_up_axis,
        ):
            raise RuntimeError(
                "base already has detached accessory candidates; use wrap"
            )

        source = audit_accessory_source_groups(
            donor_mesh,
            mode="character",
            up_axis=donor_up_axis,
        )
        if not source.ready:
            raise RuntimeError(
                "donor source groups are not ready: "
                + ";".join(source.errors or [])
            )
        if source.group_count <= 1:
            raise RuntimeError(
                "split insertion requires more than one source primitive group"
            )

        base = _base_primitive(base_mesh)
        base_vertices = np.asarray(base["positions"], dtype=np.float64)
        from surface_transfer import build_surface_transfer_index
        surface_index = build_surface_transfer_index(
            base_vertices,
            base["faces"],
        )
        _, _, base_center, base_extent = _bbox(base_vertices)
        base_diag = max(float(np.linalg.norm(base_extent)), 1e-9)

        # Alignment authority remains the donor main body, not any accessory
        # piece, so all split primitives retain their relative layout.
        flat = _load_mesh(donor_mesh)
        donor_vertices_flat = np.asarray(flat.vertices, dtype=np.float64)
        donor_faces_flat = np.asarray(flat.faces, dtype=np.int64)
        flat_ids = _component_ids(donor_faces_flat)
        ids, counts = np.unique(flat_ids, return_counts=True)
        main_id = int(ids[int(np.argmax(counts))])
        main_faces = donor_faces_flat[flat_ids == main_id]
        main_used = np.unique(main_faces.reshape(-1))
        donor_main = donor_vertices_flat[main_used]
        _, _, donor_center, donor_extent = _bbox(donor_main)
        donor_diag = max(float(np.linalg.norm(donor_extent)), 1e-9)
        scale = base_diag / donor_diag

        donor_doc, donor_binary, _ = _doc_and_bin(donor_mesh)
        before_doc = json.loads(json.dumps(base["doc"]))
        before_binary = bytes(base["binary"])
        doc = json.loads(json.dumps(base["doc"]))
        blob = bytearray(base["binary"])

        base_targets = base["primitive"].get("targets") or []
        semantics = sorted({
            semantic
            for target in base_targets
            for semantic in (target or {}).keys()
            if semantic in {"POSITION", "NORMAL", "TANGENT"}
        })
        target_deltas = {
            semantic: _read_target_deltas(base, semantic)
            for semantic in semantics
        }

        mesh = (doc.get("meshes") or [])[int(base["mesh_index"])]
        inserted_vertices = 0
        inserted_faces = 0
        all_source_ratios = []
        transferred_semantics = set()
        surface_fallback_vertices = 0
        surface_transfer_method = "hayuya-surface-transfer-bvh-barycentric-exact-v2"
        surface_max_examined_triangles = 0
        surface_max_visited_bvh_nodes = 0
        surface_ambiguous_vertices = 0
        surface_min_gap_ratio = None
        surface_max_skin_l1 = 0.0

        for group_index, group in enumerate(source.groups):
            primitive, donor_used, donor_world, donor_faces = _group_geometry(
                donor_doc,
                donor_binary,
                group,
            )
            aligned = (
                (donor_world - donor_center) * scale
                + base_center
            )

            (
                joints,
                weights,
                surface_relation,
            ) = _surface_skin_transfer(
                base_vertices,
                base["faces"],
                base["joints"],
                base["weights"],
                aligned,
                surface_index=surface_index,
            )
            source_distance = np.asarray(
                surface_relation.surface_distance,
                dtype=np.float64,
            )
            nearest = np.asarray(
                surface_relation.nearest_vertex_ids,
                dtype=np.int64,
            )
            surface_fallback_vertices += int(
                surface_relation.fallback_vertices
            )
            surface_transfer_method = str(surface_relation.method)
            surface_max_examined_triangles = max(
                surface_max_examined_triangles,
                int(surface_relation.max_examined_triangles),
            )
            surface_max_visited_bvh_nodes = max(
                surface_max_visited_bvh_nodes,
                int(surface_relation.max_visited_bvh_nodes),
            )
            surface_ambiguous_vertices += int(
                surface_relation.ambiguous_skin_vertices
            )
            if surface_relation.surface_skin_min_gap_ratio is not None:
                value = float(
                    surface_relation.surface_skin_min_gap_ratio
                )
                surface_min_gap_ratio = (
                    value
                    if surface_min_gap_ratio is None
                    else min(surface_min_gap_ratio, value)
                )
            surface_max_skin_l1 = max(
                surface_max_skin_l1,
                float(surface_relation.surface_skin_max_l1),
            )
            _require_exact_surface_relation(surface_relation)
            source_ratio = source_distance / base_diag
            all_source_ratios.extend(source_ratio.tolist())
            if len(source_ratio) and float(np.max(source_ratio)) > (
                max_weight_source_distance_ratio
            ):
                raise RuntimeError(
                    "split accessory group is too far from canonical body "
                    f"for weight transfer: {float(np.max(source_ratio)):.6f}>"
                    f"{max_weight_source_distance_ratio:.6f}"
                )
            sums = np.sum(weights, axis=1)
            if np.any(~np.isfinite(weights)) or np.any(sums <= 1e-8):
                raise RuntimeError("split accessory skin weights are invalid")
            weights = weights / sums[:, None]

            import trimesh
            temp = trimesh.Trimesh(
                vertices=np.asarray(aligned, dtype=np.float64),
                faces=np.asarray(donor_faces, dtype=np.int64),
                process=False,
            )
            normals = np.asarray(temp.vertex_normals, dtype=np.float64)

            position_accessor = _append_accessor(
                doc,
                blob,
                np.asarray(aligned, dtype="<f4").tobytes(),
                component_type=5126,
                count=len(aligned),
                accessor_type="VEC3",
                minimum=np.min(aligned, axis=0),
                maximum=np.max(aligned, axis=0),
                target=34962,
            )
            normal_accessor = _append_accessor(
                doc,
                blob,
                np.asarray(normals, dtype="<f4").tobytes(),
                component_type=5126,
                count=len(normals),
                accessor_type="VEC3",
                minimum=np.min(normals, axis=0),
                maximum=np.max(normals, axis=0),
                target=34962,
            )
            joint_accessor = _append_accessor(
                doc,
                blob,
                _pack_joints(joints, int(base["joint_component"])),
                component_type=int(base["joint_component"]),
                count=len(joints),
                accessor_type="VEC4",
            )
            weight_accessor = _append_accessor(
                doc,
                blob,
                np.asarray(weights, dtype="<f4").tobytes(),
                component_type=5126,
                count=len(weights),
                accessor_type="VEC4",
            )

            max_index = int(np.max(donor_faces))
            if max_index <= 65535:
                index_component = 5123
                index_bytes = np.asarray(
                    donor_faces,
                    dtype="<u2",
                ).reshape(-1).tobytes()
            else:
                index_component = 5125
                index_bytes = np.asarray(
                    donor_faces,
                    dtype="<u4",
                ).reshape(-1).tobytes()
            index_accessor = _append_accessor(
                doc,
                blob,
                index_bytes,
                component_type=index_component,
                count=int(donor_faces.size),
                accessor_type="SCALAR",
                minimum=[0],
                maximum=[max_index],
                target=34963,
            )

            new_targets = []
            for target_index in range(len(base_targets)):
                target_out = {}
                for semantic in semantics:
                    from surface_transfer import interpolate_vertex_values
                    source_delta = interpolate_vertex_values(
                        target_deltas[semantic][target_index],
                        surface_relation,
                    )
                    accessor = _append_accessor(
                        doc,
                        blob,
                        np.asarray(source_delta, dtype="<f4").tobytes(),
                        component_type=5126,
                        count=len(source_delta),
                        accessor_type="VEC3",
                        minimum=np.min(source_delta, axis=0),
                        maximum=np.max(source_delta, axis=0),
                    )
                    target_out[semantic] = accessor
                    transferred_semantics.add(semantic)
                new_targets.append(target_out)

            new_primitive = {
                "attributes": {
                    "POSITION": position_accessor,
                    "NORMAL": normal_accessor,
                    "JOINTS_0": joint_accessor,
                    "WEIGHTS_0": weight_accessor,
                },
                "indices": index_accessor,
                "mode": 4,
                "extras": {
                    "hayuyaAccessorySplit": True,
                    "hayuyaSourceNode": int(group.node_index),
                    "hayuyaSourceMesh": int(group.mesh_index),
                    "hayuyaSourcePrimitive": int(group.primitive_index),
                    "hayuyaSourceComponents": [
                        int(x) for x in group.primitive_component_ids
                    ],
                    "hayuyaCandidateComponents": [
                        int(x) for x in group.candidate_component_ids
                    ],
                },
            }
            if new_targets:
                new_primitive["targets"] = new_targets
            mesh.setdefault("primitives", []).append(new_primitive)
            inserted_vertices += int(len(aligned))
            inserted_faces += int(len(donor_faces))

        from glb_images import read_glb, write_glb
        write_glb(output_glb, doc, bytes(blob))
        after_doc, after_binary = read_glb(output_glb)
        legacy_preserved = _legacy_payload_preserved(
            before_doc,
            before_binary,
            after_doc,
            after_binary,
        )
        if not legacy_preserved:
            errors.append(
                "pre-existing GLB payload changed during split accessory insertion"
            )

        after_rig = audit_glb(output_glb)
        after_skin = audit_skin_weights(output_glb)
        rig_ready = bool(after_rig.rig_ready)
        skin_ready = bool(after_skin.applicable and after_skin.ready)
        morph_ready = bool(
            after_rig.morph_ready
            and after_rig.morph_target_count == before_rig.morph_target_count
        )
        if not rig_ready:
            errors.append("rig audit failed after split accessory insertion")
            errors.extend(after_rig.errors or [])
        if not skin_ready:
            errors.append("skin-weight QA failed after split accessory insertion")
            errors.extend(after_skin.errors or [])
        if not morph_ready:
            errors.append("morph structure failed after split accessory insertion")

        morph_deformation_ready = None
        if before_rig.morph_target_count > 0:
            from morph_deformation_qa import audit_morph_deformation
            morph = audit_morph_deformation(output_glb)
            morph_deformation_ready = bool(morph.applicable and morph.ready)
            warnings.extend(morph.warnings or [])
            if not morph_deformation_ready:
                errors.append(
                    "morph deformation QA failed after split accessory insertion"
                )
                errors.extend(morph.errors or [])

        animation_ready = None
        deformation_ready = None
        if before_rig.animation_count > 0:
            from animation_qa import audit_animation
            from deformation_qa import audit_deformation
            animation = audit_animation(output_glb)
            deformation = audit_deformation(
                output_glb,
                max_frames_per_animation=6,
            )
            animation_ready = bool(animation.applicable and animation.ready)
            deformation_ready = bool(deformation.applicable and deformation.ready)
            warnings.extend(animation.warnings or [])
            warnings.extend(deformation.warnings or [])
            if not animation_ready:
                errors.append("animation QA failed after split insertion")
                errors.extend(animation.errors or [])
            if not deformation_ready:
                errors.append("deformation QA failed after split insertion")
                errors.extend(deformation.errors or [])

        from composite_attachment_qa import audit_composite_attachments
        attachment = audit_composite_attachments(
            output_glb,
            mode="character",
        )
        attachment_ready = bool(attachment.applicable and attachment.ready)
        warnings.extend(attachment.warnings or [])
        if not attachment_ready:
            errors.append("split accessory attachment QA failed")
            errors.extend(attachment.errors or [])

        from component_crossing_qa import audit_component_crossings
        from self_intersection_qa import audit_self_intersections
        crossing = audit_component_crossings(output_glb)
        self_cross = audit_self_intersections(output_glb)
        if not crossing.ready:
            errors.append("split accessory component crossing QA failed")
        if not self_cross.ready:
            errors.append("split accessory self-intersection QA failed")

        output_mesh = _load_mesh(output_glb)
        _, _, _, output_extent = _bbox(output_mesh.vertices)
        bbox_drift = float(np.max(
            np.abs(output_extent - base_extent)
            / np.maximum(base_extent, base_diag * 1e-6)
        ))
        if bbox_drift > max_bbox_drift_fraction:
            errors.append(
                "split accessory bbox drift "
                f"{bbox_drift:.6f}>{max_bbox_drift_fraction:.6f}"
            )

        warnings.append(
            f"split_accessory_groups={source.group_count}"
        )
        ratios = np.asarray(all_source_ratios, dtype=np.float64)
        selected_ids = source.selected_component_ids
        geometry_ready = not errors
        return RiggedAccessoryInsertResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            attempted=True,
            ready=geometry_ready,
            geometry_ready=geometry_ready,
            material_ready=False,
            uv_ready=False,
            uv_tangent_ready=False,
            material_channels=[],
            production_ready=False,
            legacy_payload_preserved=legacy_preserved,
            material_blockers=[
                "split accessory material transfer not applied"
            ],
            donor_component_id=(
                int(selected_ids[0]) if selected_ids else None
            ),
            spatial_label="cluster",
            inserted_vertices=inserted_vertices,
            inserted_faces=inserted_faces,
            transferred_weight_vertices=inserted_vertices,
            weight_source_max_distance_ratio=(
                round(float(np.max(ratios)), 8)
                if len(ratios) else 0.0
            ),
            weight_source_mean_distance_ratio=(
                round(float(np.mean(ratios)), 8)
                if len(ratios) else 0.0
            ),
            morph_targets_transferred=int(len(base_targets) * source.group_count),
            morph_semantics_transferred=sorted(transferred_semantics),
            rig_ready=rig_ready,
            skin_weights_ready=skin_ready,
            morph_ready=morph_ready,
            morph_deformation_ready=morph_deformation_ready,
            animation_ready=animation_ready,
            deformation_ready=deformation_ready,
            attachment_ready=attachment_ready,
            component_crossing_ready=bool(crossing.ready),
            self_intersection_ready=bool(self_cross.ready),
            bbox_drift_fraction=round(bbox_drift, 8),
            warnings=warnings,
            errors=errors,
            surface_transfer_method=surface_transfer_method,
            surface_transfer_fallback_vertices=int(
                surface_fallback_vertices
            ),
            surface_transfer_max_examined_triangles=int(
                surface_max_examined_triangles
            ),
            surface_transfer_max_visited_bvh_nodes=int(
                surface_max_visited_bvh_nodes
            ),
            surface_skin_ambiguous_vertices=int(
                surface_ambiguous_vertices
            ),
            surface_skin_min_gap_ratio=(
                None
                if surface_min_gap_ratio is None
                else round(float(surface_min_gap_ratio), 8)
            ),
            surface_skin_max_l1=round(
                float(surface_max_skin_l1),
                8,
            ),
        )
    except Exception as exc:
        return fail(f"{type(exc).__name__}:{exc}")
