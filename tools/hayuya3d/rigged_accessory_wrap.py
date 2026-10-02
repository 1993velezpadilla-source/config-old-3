#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import struct
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RiggedAccessoryWrapResult:
    base_mesh: str
    donor_mesh: str
    output_glb: str
    attempted: bool
    ready: bool
    base_component_id: int | None
    donor_component_id: int | None
    confidence: float | None
    spatial_label: str | None
    changed_vertices: int
    clamped_vertices: int
    max_displacement_ratio: float | None
    mean_displacement_ratio: float | None
    bbox_drift_fraction: float | None
    runtime_payload_preserved: bool
    rig_ready: bool
    skin_weights_ready: bool
    morph_deformation_ready: bool | None
    component_crossing_ready: bool
    self_intersection_ready: bool
    attachment_ready: bool
    warnings: list[str]
    errors: list[str]
    rebake_ready: bool = False
    rebake_required: list[str] | None = None
    rebake_resolved: list[str] | None = None
    method: str = "hayuya-rig-preserving-accessory-wrap-v1"


def _deps():
    import numpy as np
    from scipy.spatial import cKDTree
    return np, cKDTree


def _read_indices(doc: dict, binary: bytes, accessor_index: int):
    np, _ = _deps()
    from gltf_position_patch import _accessor_layout

    accessor, _, component, dims, packed, stride, base = _accessor_layout(
        doc, accessor_index, "SCALAR"
    )
    if dims != 1:
        raise ValueError("index accessor must be SCALAR")
    formats = {
        5121: ("<B", np.uint8),
        5123: ("<H", np.uint16),
        5125: ("<I", np.uint32),
    }
    if component not in formats:
        raise ValueError(f"unsupported index component type {component}")
    fmt, dtype = formats[component]
    rows = []
    for row in range(int(accessor.get("count") or 0)):
        pos = base + row * stride
        if pos + packed > len(binary):
            raise ValueError("index accessor reads past BIN chunk")
        rows.append(struct.unpack_from(fmt, binary, pos)[0])
    return np.asarray(rows, dtype=dtype)


def _single_skinned_triangle_primitive(path: Path):
    np, _ = _deps()
    from gltf_position_patch import (
        _doc_and_bin,
        mesh_nodes_identity_for_accessors,
        read_position_accessor,
    )

    doc, binary, _ = _doc_and_bin(path)
    meshes = doc.get("meshes") or []
    nodes = doc.get("nodes") or []

    rows = []
    for node_index, node in enumerate(nodes):
        mesh_index = node.get("mesh")
        skin_index = node.get("skin")
        if not isinstance(mesh_index, int) or not isinstance(skin_index, int):
            continue
        if not (0 <= mesh_index < len(meshes)):
            continue
        primitives = meshes[mesh_index].get("primitives") or []
        for primitive_index, primitive in enumerate(primitives):
            attrs = primitive.get("attributes") or {}
            pos = attrs.get("POSITION")
            indices = primitive.get("indices")
            mode = int(primitive.get("mode", 4))
            if not isinstance(pos, int) or not isinstance(indices, int):
                continue
            if mode != 4:
                raise RuntimeError("rigged accessory wrap requires TRIANGLES primitive")
            rows.append((
                node_index,
                mesh_index,
                primitive_index,
                pos,
                indices,
            ))

    if len(rows) != 1:
        raise RuntimeError(
            "rigged accessory wrap currently requires exactly one indexed "
            f"skinned triangle primitive; found {len(rows)}"
        )

    _, _, _, position_accessor, index_accessor = rows[0]
    if not mesh_nodes_identity_for_accessors(doc, [position_accessor]):
        raise RuntimeError(
            "skinned mesh node transform is not identity; object-space "
            "accessory patch would be unsafe"
        )

    positions = np.asarray(
        read_position_accessor(path, position_accessor),
        dtype=np.float64,
    )
    indices = _read_indices(doc, binary, index_accessor).astype(np.int64)
    if len(indices) % 3:
        raise RuntimeError("triangle index count is not divisible by three")
    faces = indices.reshape((-1, 3))
    if len(positions) <= int(np.max(indices)):
        raise RuntimeError("index accessor references missing POSITION vertex")
    return doc, position_accessor, positions, faces


def _bbox(vertices):
    np, _ = _deps()
    vv = np.asarray(vertices, dtype=np.float64)
    lo = np.min(vv, axis=0)
    hi = np.max(vv, axis=0)
    return lo, hi, (lo + hi) * 0.5, hi - lo


def rigged_accessory_wrap_supported(path: Path) -> tuple[bool, str | None]:
    try:
        from gltf_audit import audit_glb
        from skin_weight_qa import audit_skin_weights

        rig = audit_glb(path)
        skin = audit_skin_weights(path)
        if rig.skin_count <= 0 or not rig.rig_ready:
            return False, "base is not a validated skinned GLB"
        if not skin.applicable or not skin.ready:
            return False, "base skin weights are not valid"
        _single_skinned_triangle_primitive(path)
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"


def wrap_rigged_accessory(
    base_mesh: Path,
    donor_mesh: Path,
    output_glb: Path,
    *,
    mode: str = "character",
    base_up_axis: str = "y",
    donor_up_axis: str | None = None,
    max_displacement_fraction: float = 0.08,
    max_bbox_drift_fraction: float = 0.12,
    max_centroid_correction_ratio: float = 0.12,
) -> RiggedAccessoryWrapResult:
    np, cKDTree = _deps()
    warnings: list[str] = []
    errors: list[str] = []
    donor_up_axis = donor_up_axis or base_up_axis

    def failed(exc: Exception | str) -> RiggedAccessoryWrapResult:
        message = str(exc)
        if isinstance(exc, Exception):
            message = f"{type(exc).__name__}:{exc}"
        return RiggedAccessoryWrapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            attempted=True,
            ready=False,
            base_component_id=None,
            donor_component_id=None,
            confidence=None,
            spatial_label=None,
            changed_vertices=0,
            clamped_vertices=0,
            max_displacement_ratio=None,
            mean_displacement_ratio=None,
            bbox_drift_fraction=None,
            runtime_payload_preserved=False,
            rig_ready=False,
            skin_weights_ready=False,
            morph_deformation_ready=None,
            component_crossing_ready=False,
            self_intersection_ready=False,
            attachment_ready=False,
            warnings=warnings,
            errors=[message],
            rebake_ready=False,
            rebake_required=[],
            rebake_resolved=[],
        )

    try:
        if not math.isfinite(max_displacement_fraction) or max_displacement_fraction <= 0:
            raise ValueError("max_displacement_fraction must be finite and positive")

        from accessory_match import match_accessories
        from gltf_audit import audit_glb
        from gltf_position_patch import (
            patch_position_accessors,
            runtime_payload_signature,
        )
        from part_map import _component_ids, _load_mesh
        from skin_weight_qa import audit_skin_weights

        before_rig = audit_glb(base_mesh)
        before_skin = audit_skin_weights(base_mesh)
        if not before_rig.rig_ready:
            raise RuntimeError("base character rig is not valid")
        if not before_skin.applicable or not before_skin.ready:
            raise RuntimeError("base character skin weights are not valid")

        match_report = match_accessories(
            base_mesh,
            donor_mesh,
            mode=mode,
            base_up_axis=base_up_axis,
            donor_up_axis=donor_up_axis,
        )
        ready_matches = [item for item in match_report.matches if item.ready]
        if not ready_matches:
            raise RuntimeError(
                "no unambiguous detached accessory correspondence passed"
            )
        selected = max(ready_matches, key=lambda item: float(item.confidence))

        _, position_accessor, base_vertices, base_faces = (
            _single_skinned_triangle_primitive(base_mesh)
        )
        base_components = _component_ids(base_faces)
        unique_components = np.unique(base_components)
        if int(selected.base_component_id) not in set(
            int(x) for x in unique_components
        ):
            raise RuntimeError(
                "matched accessory component is not represented by the "
                "single skinned primitive"
            )

        component_faces = base_faces[
            base_components == int(selected.base_component_id)
        ]
        component_vertices = np.unique(component_faces.reshape(-1))
        if len(component_vertices) < 3:
            raise RuntimeError("matched base accessory component is too sparse")

        donor = _load_mesh(donor_mesh)
        donor_faces = np.asarray(donor.faces, dtype=np.int64)
        donor_components = _component_ids(donor_faces)
        donor_component_faces = donor_faces[
            donor_components == int(selected.donor_component_id)
        ]
        if not len(donor_component_faces):
            raise RuntimeError("matched donor accessory component is missing")
        donor_vertex_ids = np.unique(donor_component_faces.reshape(-1))
        donor_accessory = np.asarray(
            donor.vertices, dtype=np.float64
        )[donor_vertex_ids]
        if len(donor_accessory) < 3:
            raise RuntimeError("matched donor accessory component is too sparse")

        base_lo, base_hi, base_center, base_extent = _bbox(base_vertices)
        donor_all = np.asarray(donor.vertices, dtype=np.float64)
        _, _, donor_center, donor_extent = _bbox(donor_all)
        base_diag = max(float(np.linalg.norm(base_extent)), 1e-9)
        donor_diag = max(float(np.linalg.norm(donor_extent)), 1e-9)
        scale = base_diag / donor_diag

        aligned = (donor_accessory - donor_center) * scale + base_center
        base_accessory = base_vertices[component_vertices]
        base_acc_center = np.mean(base_accessory, axis=0)
        donor_acc_center = np.mean(aligned, axis=0)
        correction = base_acc_center - donor_acc_center
        correction_ratio = float(np.linalg.norm(correction)) / base_diag
        if correction_ratio > max_centroid_correction_ratio:
            raise RuntimeError(
                "rigged accessory centroid correction too large: "
                f"{correction_ratio:.6f}>{max_centroid_correction_ratio:.6f}"
            )
        aligned += correction

        tree = cKDTree(aligned)
        _, nearest = tree.query(base_accessory, k=1, workers=-1)
        targets = aligned[np.asarray(nearest, dtype=np.int64)]
        displacement = targets - base_accessory
        raw_norm = np.linalg.norm(displacement, axis=1)
        max_displacement = max_displacement_fraction * base_diag
        clamp_scale = np.ones_like(raw_norm)
        too_large = raw_norm > max_displacement
        clamp_scale[too_large] = max_displacement / np.maximum(
            raw_norm[too_large], 1e-12
        )
        displacement *= clamp_scale[:, None]

        wrapped = base_vertices.copy()
        wrapped[component_vertices] += displacement
        moved_norm = np.linalg.norm(displacement, axis=1) / base_diag
        changed_vertices = int(np.count_nonzero(moved_norm > 1e-10))
        if changed_vertices <= 0:
            raise RuntimeError("rigged accessory wrap made no geometry change")

        runtime_before = runtime_payload_signature(base_mesh)
        patch = patch_position_accessors(
            base_mesh,
            output_glb,
            {position_accessor: wrapped.tolist()},
        )
        if not patch.ready:
            raise RuntimeError(
                "POSITION patch failed: " + str(patch.error or "unknown")
            )
        runtime_after = runtime_payload_signature(output_glb)
        runtime_preserved = bool(
            runtime_before == runtime_after
            and patch.runtime_payload_preserved
        )
        if not runtime_preserved:
            errors.append(
                "skin/animation/morph runtime payload changed during "
                "topology-preserving accessory wrap"
            )

        after_rig = audit_glb(output_glb)
        after_skin = audit_skin_weights(output_glb)
        rig_ready = bool(after_rig.rig_ready)
        skin_ready = bool(after_skin.applicable and after_skin.ready)
        if not rig_ready:
            errors.append("rig became invalid after accessory wrap")
        if not skin_ready:
            errors.append("skin weights became invalid after accessory wrap")
        if (
            after_rig.skin_count != before_rig.skin_count
            or after_rig.joint_count != before_rig.joint_count
            or after_rig.animation_count != before_rig.animation_count
            or after_rig.morph_target_count != before_rig.morph_target_count
        ):
            errors.append(
                "runtime rig/morph cardinality changed during accessory wrap"
            )

        morph_deformation_ready = None
        if before_rig.morph_target_count > 0:
            from morph_deformation_qa import audit_morph_deformation
            morph = audit_morph_deformation(output_glb)
            morph_deformation_ready = bool(morph.applicable and morph.ready)
            warnings.extend(morph.warnings or [])
            if not morph_deformation_ready:
                errors.append("morph deformation QA failed after accessory wrap")
                errors.extend(morph.errors or [])

        from qa import inspect_mesh
        output_qa = inspect_mesh(
            output_glb,
            backend="rigged_accessory_wrap",
            mode=mode,
            target_faces=max(1, int(len(base_faces))),
        )
        if not output_qa.valid:
            errors.append("wrapped accessory output failed mesh QA")
        if int(output_qa.components) != int(len(unique_components)):
            errors.append(
                "topology-preserving accessory wrap changed component count: "
                f"{len(unique_components)}->{int(output_qa.components)}"
            )

        _, _, _, output_extent = _bbox(
            np.asarray(
                _single_skinned_triangle_primitive(output_glb)[2],
                dtype=np.float64,
            )
        )
        bbox_drift = float(np.max(
            np.abs(output_extent - base_extent)
            / np.maximum(base_extent, base_diag * 1e-6)
        ))
        if bbox_drift > max_bbox_drift_fraction:
            errors.append(
                "rigged accessory wrap bbox drift "
                f"{bbox_drift:.6f}>{max_bbox_drift_fraction:.6f}"
            )

        from component_crossing_qa import audit_component_crossings
        crossing = audit_component_crossings(output_glb)
        if not crossing.ready:
            errors.append(
                "rigged accessory wrap introduced major component crossings"
            )

        from self_intersection_qa import audit_self_intersections
        self_cross = audit_self_intersections(output_glb)
        if not self_cross.ready:
            errors.append(
                "rigged accessory wrap introduced self intersections"
            )

        from composite_attachment_qa import audit_composite_attachments
        attachment = audit_composite_attachments(output_glb, mode=mode)
        warnings.extend(attachment.warnings or [])
        if not attachment.ready:
            errors.append(
                "rigged accessory wrap introduced detached/floating topology"
            )
            errors.extend(attachment.errors or [])

        return RiggedAccessoryWrapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            attempted=True,
            ready=not errors,
            base_component_id=int(selected.base_component_id),
            donor_component_id=int(selected.donor_component_id),
            confidence=round(float(selected.confidence), 6),
            spatial_label=str(selected.spatial_label),
            changed_vertices=changed_vertices,
            clamped_vertices=int(np.count_nonzero(too_large)),
            max_displacement_ratio=round(
                float(np.max(moved_norm)) if len(moved_norm) else 0.0, 8
            ),
            mean_displacement_ratio=round(
                float(np.mean(moved_norm)) if len(moved_norm) else 0.0, 8
            ),
            bbox_drift_fraction=round(bbox_drift, 8),
            runtime_payload_preserved=runtime_preserved,
            rig_ready=rig_ready,
            skin_weights_ready=skin_ready,
            morph_deformation_ready=morph_deformation_ready,
            component_crossing_ready=bool(crossing.ready),
            self_intersection_ready=bool(self_cross.ready),
            attachment_ready=bool(attachment.ready),
            warnings=warnings,
            errors=errors,
            rebake_ready=False,
            rebake_required=[],
            rebake_resolved=[],
        )
    except Exception as exc:
        return failed(exc)


def prepare_rigged_accessory_challenger(
    base_mesh: Path,
    donor_mesh: Path,
    out_dir: Path,
    *,
    texture_size: int,
    base_up_axis: str = "y",
    donor_up_axis: str | None = None,
    blender: str | Path | None = None,
    require_rebake: bool = True,
) -> RiggedAccessoryWrapResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "rigged_accessory_wrap_raw.glb"
    result = wrap_rigged_accessory(
        base_mesh,
        donor_mesh,
        raw,
        mode="character",
        base_up_axis=base_up_axis,
        donor_up_axis=donor_up_axis,
    )
    if not result.ready:
        return result

    try:
        from gltf_audit import audit_glb
        audit = audit_glb(base_mesh)
        required = [
            channel
            for channel in ("normal", "occlusion")
            if channel in set(audit.material_channels or [])
        ]
    except Exception:
        required = ["normal", "occlusion"]

    result.rebake_required = list(required)
    if not required:
        result.rebake_ready = True
        result.rebake_resolved = []
        return result

    final = out_dir / "rigged_accessory_wrap_rebaked.glb"
    try:
        from gltf_position_patch import runtime_payload_signature
        from rig_preserving_rebake import (
            rebake_material_channels_preserve_rig,
        )

        before_runtime = runtime_payload_signature(raw)
        rebake = rebake_material_channels_preserve_rig(
            base_mesh,
            raw,
            final,
            required=required,
            max_texture_size=texture_size,
            blender=blender,
        )
        result.rebake_resolved = list(rebake.resolved_channels)
        result.rebake_ready = bool(
            rebake.ready and not rebake.remaining_channels
        )
        if result.rebake_ready:
            after_runtime = runtime_payload_signature(final)
            if before_runtime != after_runtime:
                result.errors.append(
                    "runtime payload changed during rig-preserving accessory rebake"
                )
                result.runtime_payload_preserved = False
                result.rebake_ready = False
            else:
                result.output_glb = str(final)
                result.rig_ready = bool(rebake.rig_preserved)
                result.skin_weights_ready = bool(rebake.skin_weights_ready)
        if require_rebake and not result.rebake_ready:
            result.errors.append(
                "rigged accessory material rebake incomplete: "
                + ",".join(rebake.remaining_channels or required)
            )
        result.ready = bool(
            result.ready
            and result.runtime_payload_preserved
            and result.rig_ready
            and result.skin_weights_ready
            and (result.rebake_ready or not require_rebake)
            and not result.errors
        )
        return result
    except Exception as exc:
        result.rebake_ready = False
        if require_rebake:
            result.ready = False
        result.errors.append(
            f"rigged_accessory_rebake_failed:{type(exc).__name__}:{exc}"
        )
        return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description=(
            "Topology-preserving detached accessory wrap for skinned HAYUYA "
            "characters. Existing accessory vertices are reshaped toward a "
            "matched donor while runtime skin/morph/animation payload remains "
            "byte-stable."
        )
    )
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-up-axis", choices=["x", "y", "z"], default="y")
    parser.add_argument("--donor-up-axis", choices=["x", "y", "z"])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = wrap_rigged_accessory(
        args.base,
        args.donor,
        args.output,
        mode="character",
        base_up_axis=args.base_up_axis,
        donor_up_axis=args.donor_up_axis,
    )
    payload = json.dumps(asdict(result), indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")
    return 0 if result.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
