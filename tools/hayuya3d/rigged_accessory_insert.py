#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import struct
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RiggedAccessoryInsertResult:
    base_mesh: str
    donor_mesh: str
    output_glb: str
    attempted: bool
    ready: bool
    geometry_ready: bool
    material_ready: bool
    uv_ready: bool
    uv_tangent_ready: bool
    material_channels: list[str]
    production_ready: bool
    legacy_payload_preserved: bool
    material_blockers: list[str]
    donor_component_id: int | None
    spatial_label: str | None
    inserted_vertices: int
    inserted_faces: int
    transferred_weight_vertices: int
    weight_source_max_distance_ratio: float | None
    weight_source_mean_distance_ratio: float | None
    morph_targets_transferred: int
    morph_semantics_transferred: list[str]
    rig_ready: bool
    skin_weights_ready: bool
    morph_ready: bool
    morph_deformation_ready: bool | None
    animation_ready: bool | None
    deformation_ready: bool | None
    attachment_ready: bool
    component_crossing_ready: bool
    self_intersection_ready: bool
    bbox_drift_fraction: float | None
    warnings: list[str]
    errors: list[str]
    inserted_primitives: int = 1
    material_groups: int = 0
    surface_transfer_method: str = "nearest-vertex-knn-v1"
    surface_transfer_fallback_vertices: int = 0
    surface_transfer_max_examined_triangles: int = 0
    surface_transfer_max_visited_bvh_nodes: int = 0
    surface_skin_ambiguous_vertices: int = 0
    surface_skin_min_gap_ratio: float | None = None
    surface_skin_max_l1: float = 0.0
    method: str = "hayuya-rigged-accessory-insert-v1"


@dataclass
class SurfaceSkinAmbiguityReport:
    ambiguous_vertices: int
    min_distance_gap_ratio: float | None
    max_skin_l1: float
    checked_vertices: int
    margin_ratio: float
    skin_l1_threshold: float
    method: str = "hayuya-surface-skin-ambiguity-v1"


def _deps():
    import numpy as np
    from scipy.spatial import cKDTree
    return np, cKDTree


def _fail(
    base_mesh: Path,
    donor_mesh: Path,
    output_glb: Path,
    message: str,
    *,
    warnings: list[str] | None = None,
) -> RiggedAccessoryInsertResult:
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
        warnings=list(warnings or []),
        errors=[message],
    )


def _bbox(vertices):
    np, _ = _deps()
    vv = np.asarray(vertices, dtype=np.float64)
    lo = np.min(vv, axis=0)
    hi = np.max(vv, axis=0)
    return lo, hi, (lo + hi) * 0.5, hi - lo


def _blend_skin_weights(
    source_positions,
    source_joints,
    source_weights,
    target_positions,
    *,
    k: int = 4,
):
    np, cKDTree = _deps()
    source_positions = np.asarray(source_positions, dtype=np.float64)
    source_joints = np.asarray(source_joints, dtype=np.int64)
    source_weights = np.asarray(source_weights, dtype=np.float64)
    target_positions = np.asarray(target_positions, dtype=np.float64)
    if not len(source_positions):
        raise ValueError("skin-weight source surface is empty")

    kk = max(1, min(int(k), len(source_positions)))
    tree = cKDTree(source_positions)
    distances, neighbors = tree.query(
        target_positions,
        k=kk,
        workers=-1,
    )
    distances = np.asarray(distances, dtype=np.float64)
    neighbors = np.asarray(neighbors, dtype=np.int64)
    if kk == 1:
        distances = distances[:, None]
        neighbors = neighbors[:, None]

    out_joints = np.zeros((len(target_positions), 4), dtype=np.int64)
    out_weights = np.zeros((len(target_positions), 4), dtype=np.float64)

    for row in range(len(target_positions)):
        d = distances[row]
        ids = neighbors[row]
        spatial = 1.0 / np.maximum(d, 1e-6)
        spatial /= max(float(np.sum(spatial)), 1e-12)
        accumulated: dict[int, float] = {}
        for local_weight, source_index in zip(spatial, ids):
            for joint, skin_weight in zip(
                source_joints[int(source_index)],
                source_weights[int(source_index)],
            ):
                contribution = float(local_weight) * float(skin_weight)
                if contribution <= 1e-12:
                    continue
                accumulated[int(joint)] = (
                    accumulated.get(int(joint), 0.0) + contribution
                )
        strongest = sorted(
            accumulated.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:4]
        total = sum(weight for _, weight in strongest)
        if total <= 1e-12:
            raise RuntimeError(
                f"target accessory vertex {row} received no skin influence"
            )
        for slot, (joint, weight) in enumerate(strongest):
            out_joints[row, slot] = int(joint)
            out_weights[row, slot] = float(weight / total)

    return (
        out_joints,
        out_weights,
        distances[:, 0],
        neighbors[:, 0],
    )


def _surface_skin_transfer(
    source_positions,
    source_faces,
    source_joints,
    source_weights,
    target_positions,
    *,
    surface_index=None,
):
    from surface_transfer import (
        blend_joint_weights_from_relation,
        build_surface_transfer_index,
        query_surface_transfer,
    )

    if surface_index is None:
        surface_index = build_surface_transfer_index(
            source_positions,
            source_faces,
        )
    relation = query_surface_transfer(
        surface_index,
        target_positions,
    )
    ambiguity = _surface_skin_ambiguity(
        source_positions,
        source_joints,
        source_weights,
        target_positions,
        surface_index,
        relation,
    )
    relation.ambiguous_skin_vertices = int(
        ambiguity.ambiguous_vertices
    )
    relation.surface_skin_min_gap_ratio = (
        ambiguity.min_distance_gap_ratio
    )
    relation.surface_skin_max_l1 = float(
        ambiguity.max_skin_l1
    )
    joints, weights = blend_joint_weights_from_relation(
        source_joints,
        source_weights,
        relation,
    )
    return joints, weights, relation


def _joint_signature(
    source_joints,
    source_weights,
    triangle_vertex_ids,
    barycentric,
):
    np, _ = _deps()
    joints = np.asarray(source_joints, dtype=np.int64)
    weights = np.asarray(source_weights, dtype=np.float64)
    tri = np.asarray(triangle_vertex_ids, dtype=np.int64)
    bary = np.asarray(barycentric, dtype=np.float64)
    accumulated: dict[int, float] = {}
    for vertex_id, spatial in zip(tri, bary):
        for joint, skin_weight in zip(
            joints[int(vertex_id)],
            weights[int(vertex_id)],
        ):
            value = float(spatial) * float(skin_weight)
            if value <= 1e-12:
                continue
            accumulated[int(joint)] = (
                accumulated.get(int(joint), 0.0) + value
            )
    total = sum(accumulated.values())
    if total <= 1e-12:
        return {}
    return {
        joint: float(value / total)
        for joint, value in accumulated.items()
    }


def _surface_skin_ambiguity(
    source_positions,
    source_joints,
    source_weights,
    target_positions,
    surface_index,
    relation,
    *,
    margin_ratio: float = 0.002,
    skin_l1_threshold: float = 0.75,
) -> SurfaceSkinAmbiguityReport:
    np, _ = _deps()
    from surface_transfer import surface_candidates_within_distance

    vertices = np.asarray(source_positions, dtype=np.float64)
    targets = np.asarray(target_positions, dtype=np.float64)
    _, _, _, extent = _bbox(vertices)
    diagonal = max(float(np.linalg.norm(extent)), 1e-9)
    margin = diagonal * float(margin_ratio)

    ambiguous = 0
    min_gap_ratio = None
    max_skin_l1 = 0.0

    for row, point in enumerate(targets):
        best_tri = np.asarray(
            relation.triangle_vertex_ids[row],
            dtype=np.int64,
        )
        best_bary = np.asarray(
            relation.barycentric[row],
            dtype=np.float64,
        )
        best_distance = float(relation.surface_distance[row])
        best_signature = _joint_signature(
            source_joints,
            source_weights,
            best_tri,
            best_bary,
        )
        if not best_signature:
            continue

        candidates = surface_candidates_within_distance(
            surface_index,
            point,
            best_distance + margin,
        )
        risky = False
        row_best_gap_ratio = None
        row_max_l1 = 0.0

        for candidate in candidates:
            candidate_tri = np.asarray(
                candidate.triangle_vertex_ids,
                dtype=np.int64,
            )
            if np.array_equal(candidate_tri, best_tri):
                continue
            if set(int(x) for x in candidate_tri).intersection(
                int(x) for x in best_tri
            ):
                # Neighboring triangles on the same local patch are not
                # competing surfaces; their interpolation is expected to vary.
                continue

            distance_gap = max(
                0.0,
                float(candidate.distance) - best_distance,
            )
            if distance_gap > margin + 1e-12:
                continue

            candidate_signature = _joint_signature(
                source_joints,
                source_weights,
                candidate_tri,
                candidate.barycentric,
            )
            joints = set(best_signature) | set(candidate_signature)
            l1 = sum(
                abs(
                    float(best_signature.get(joint, 0.0))
                    - float(candidate_signature.get(joint, 0.0))
                )
                for joint in joints
            )
            row_max_l1 = max(row_max_l1, float(l1))
            if l1 < float(skin_l1_threshold):
                continue

            risky = True
            gap_ratio = float(distance_gap / diagonal)
            row_best_gap_ratio = (
                gap_ratio
                if row_best_gap_ratio is None
                else min(row_best_gap_ratio, gap_ratio)
            )

        if risky:
            ambiguous += 1
            max_skin_l1 = max(max_skin_l1, row_max_l1)
            if row_best_gap_ratio is not None:
                min_gap_ratio = (
                    row_best_gap_ratio
                    if min_gap_ratio is None
                    else min(min_gap_ratio, row_best_gap_ratio)
                )

    return SurfaceSkinAmbiguityReport(
        ambiguous_vertices=int(ambiguous),
        min_distance_gap_ratio=(
            None
            if min_gap_ratio is None
            else round(float(min_gap_ratio), 8)
        ),
        max_skin_l1=round(float(max_skin_l1), 8),
        checked_vertices=int(len(targets)),
        margin_ratio=float(margin_ratio),
        skin_l1_threshold=float(skin_l1_threshold),
    )


def _require_exact_surface_relation(relation) -> None:
    fallback = int(getattr(relation, "fallback_vertices", 0) or 0)
    if fallback > 0:
        raise RuntimeError(
            "barycentric surface transfer required nearest-vertex "
            "fallback on degenerate base topology for "
            f"{fallback} accessory vertices"
        )
    ambiguous = int(
        getattr(relation, "ambiguous_skin_vertices", 0) or 0
    )
    if ambiguous > 0:
        gap = getattr(
            relation,
            "surface_skin_min_gap_ratio",
            None,
        )
        l1 = float(
            getattr(relation, "surface_skin_max_l1", 0.0) or 0.0
        )
        raise RuntimeError(
            "closest-surface skin transfer is ambiguous across thin/folded "
            f"geometry for {ambiguous} accessory vertices "
            f"(min_gap_ratio={gap}, max_skin_l1={l1:.6f})"
        )


def _legacy_payload_preserved(
    before_doc: dict,
    before_binary: bytes,
    after_doc: dict,
    after_binary: bytes,
) -> bool:
    if bytes(after_binary[:len(before_binary)]) != bytes(before_binary):
        return False

    for key in (
        "bufferViews",
        "accessors",
        "skins",
        "animations",
        "materials",
        "textures",
        "images",
        "samplers",
    ):
        old = before_doc.get(key) or []
        new = after_doc.get(key) or []
        if new[:len(old)] != old:
            return False

    old_nodes = before_doc.get("nodes") or []
    new_nodes = after_doc.get("nodes") or []
    if new_nodes[:len(old_nodes)] != old_nodes:
        return False

    old_meshes = before_doc.get("meshes") or []
    new_meshes = after_doc.get("meshes") or []
    if len(new_meshes) < len(old_meshes):
        return False
    for index, old_mesh in enumerate(old_meshes):
        new_mesh = new_meshes[index]
        old_primitives = old_mesh.get("primitives") or []
        new_primitives = new_mesh.get("primitives") or []
        if new_primitives[:len(old_primitives)] != old_primitives:
            return False
        old_rest = {
            key: value for key, value in old_mesh.items()
            if key != "primitives"
        }
        new_rest = {
            key: value for key, value in new_mesh.items()
            if key != "primitives"
        }
        if old_rest != new_rest:
            return False
    return True


def _inserted_primitive_material_evidence(
    doc: dict,
    primitive: dict,
) -> tuple[bool, bool, list[str]]:
    blockers: list[str] = []
    materials = doc.get("materials") or []
    textures = doc.get("textures") or []
    images = doc.get("images") or []
    attrs = primitive.get("attributes") or []

    material_index = primitive.get("material")
    if not isinstance(material_index, int) or not (
        0 <= material_index < len(materials)
    ):
        return (
            False,
            False,
            ["inserted primitive has no valid material binding"],
        )

    material = materials[material_index] or {}
    pbr = material.get("pbrMetallicRoughness") or {}
    base_color = pbr.get("baseColorTexture")
    base_factor = pbr.get("baseColorFactor")
    if base_color is None and base_factor is None:
        blockers.append(
            "inserted primitive material has no explicit base-color evidence"
        )

    texture_infos = []
    for info in (
        base_color,
        pbr.get("metallicRoughnessTexture"),
        material.get("normalTexture"),
        material.get("occlusionTexture"),
        material.get("emissiveTexture"),
    ):
        if isinstance(info, dict):
            texture_infos.append(info)

    uv_ready = True
    for info in texture_infos:
        texture_index = info.get("index")
        if not isinstance(texture_index, int) or not (
            0 <= texture_index < len(textures)
        ):
            blockers.append(
                "inserted primitive material references invalid texture"
            )
            uv_ready = False
            continue
        source = (textures[texture_index] or {}).get("source")
        if not isinstance(source, int) or not (0 <= source < len(images)):
            blockers.append(
                "inserted primitive texture has no valid image source"
            )
            uv_ready = False
        texcoord = int(info.get("texCoord", 0) or 0)
        semantic = f"TEXCOORD_{texcoord}"
        if semantic not in attrs:
            blockers.append(
                f"inserted primitive texture requires missing {semantic}"
            )
            uv_ready = False

    material_ready = bool(not blockers and uv_ready)
    return material_ready, uv_ready, blockers


def _base_primitive(path: Path):
    np, _ = _deps()
    from gltf_position_patch import (
        _doc_and_bin,
        mesh_nodes_identity_for_accessors,
    )
    from skin_weight_qa import _read_accessor

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
        for primitive_index, primitive in enumerate(
            meshes[mesh_index].get("primitives") or []
        ):
            attrs = primitive.get("attributes") or {}
            if (
                isinstance(attrs.get("POSITION"), int)
                and isinstance(attrs.get("JOINTS_0"), int)
                and isinstance(attrs.get("WEIGHTS_0"), int)
                and isinstance(primitive.get("indices"), int)
            ):
                rows.append((
                    node_index,
                    mesh_index,
                    primitive_index,
                    skin_index,
                    primitive,
                ))

    if len(rows) != 1:
        raise RuntimeError(
            "new-vertex accessory insertion currently requires exactly one "
            f"indexed skinned primitive; found {len(rows)}"
        )

    node_index, mesh_index, primitive_index, skin_index, primitive = rows[0]
    attrs = primitive.get("attributes") or {}
    if any(
        key.startswith("JOINTS_") and key != "JOINTS_0"
        for key in attrs
    ) or any(
        key.startswith("WEIGHTS_") and key != "WEIGHTS_0"
        for key in attrs
    ):
        raise RuntimeError(
            "new-vertex insertion v1 supports one JOINTS_0/WEIGHTS_0 set only"
        )

    position_accessor = int(attrs["POSITION"])
    if not mesh_nodes_identity_for_accessors(doc, [position_accessor]):
        raise RuntimeError(
            "skinned mesh node transform is not identity; object-space "
            "new-vertex insertion is unsafe"
        )

    positions = np.asarray(
        _read_accessor(doc, binary, position_accessor),
        dtype=np.float64,
    )
    joints = np.asarray(
        _read_accessor(doc, binary, int(attrs["JOINTS_0"])),
        dtype=np.int64,
    )
    weights = np.asarray(
        _read_accessor(doc, binary, int(attrs["WEIGHTS_0"])),
        dtype=np.float64,
    )
    if int(primitive.get("mode", 4)) != 4:
        raise RuntimeError(
            "new-vertex insertion requires TRIANGLES base primitive"
        )
    raw_indices = np.asarray(
        _read_accessor(doc, binary, int(primitive["indices"])),
        dtype=np.int64,
    ).reshape(-1)
    if len(raw_indices) % 3:
        raise RuntimeError(
            "base primitive index count is not divisible by three"
        )
    faces = raw_indices.reshape((-1, 3))
    if len(faces) and (
        int(np.min(faces)) < 0
        or int(np.max(faces)) >= len(positions)
    ):
        raise RuntimeError(
            "base primitive indices reference missing vertices"
        )
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise RuntimeError("base POSITION accessor is not VEC3")
    if joints.shape != (len(positions), 4):
        raise RuntimeError("base JOINTS_0 accessor is not VEC4")
    if weights.shape != (len(positions), 4):
        raise RuntimeError("base WEIGHTS_0 accessor is not VEC4")

    accessors = doc.get("accessors") or []
    joint_meta = accessors[int(attrs["JOINTS_0"])]
    weight_meta = accessors[int(attrs["WEIGHTS_0"])]
    joint_component = int(joint_meta.get("componentType") or 0)
    weight_component = int(weight_meta.get("componentType") or 0)
    if joint_component not in {5121, 5123}:
        raise RuntimeError(
            "new-vertex insertion v1 requires unsigned byte/short JOINTS_0"
        )
    if weight_component != 5126 or bool(weight_meta.get("normalized")):
        raise RuntimeError(
            "new-vertex insertion v1 requires FLOAT WEIGHTS_0"
        )

    return {
        "doc": doc,
        "binary": binary,
        "node_index": node_index,
        "mesh_index": mesh_index,
        "primitive_index": primitive_index,
        "skin_index": skin_index,
        "primitive": primitive,
        "positions": positions,
        "faces": faces,
        "joints": joints,
        "weights": weights,
        "joint_component": joint_component,
    }


def _donor_accessory(path: Path, *, mode: str, up_axis: str):
    np, _ = _deps()
    from accessory_match import inspect_accessories
    from part_map import _component_ids, _load_mesh

    candidates = inspect_accessories(
        path,
        mode=mode,
        up_axis=up_axis,
    )
    if not candidates:
        raise RuntimeError(
            "new-vertex insertion requires donor accessory evidence"
        )

    selected_ids: list[int]
    if len(candidates) == 1:
        selected_ids = [int(candidates[0].component_id)]
    else:
        from accessory_cluster import inspect_accessory_clusters
        cluster = inspect_accessory_clusters(
            path,
            mode=mode,
            up_axis=up_axis,
        )
        if not cluster.ready or not cluster.selected_component_ids:
            detail = ";".join(cluster.errors or [])
            raise RuntimeError(
                "multiple donor accessory candidates are not one proven "
                "anchored logical cluster"
                + (f": {detail}" if detail else "")
            )
        selected_ids = [
            int(x) for x in cluster.selected_component_ids
        ]
        if set(selected_ids) != {
            int(item.component_id) for item in candidates
        }:
            raise RuntimeError(
                "accessory cluster proof did not account for every donor "
                "accessory candidate"
            )

    by_id = {
        int(item.component_id): item
        for item in candidates
    }
    selected_candidates = [by_id[x] for x in selected_ids]
    selected = selected_candidates[0]
    if len(selected_candidates) == 1 and (
        float(selected.attachment_distance_ratio) > 0.18
    ):
        raise RuntimeError(
            "donor accessory is too detached from its source body for "
            "automatic insertion"
        )

    mesh = _load_mesh(path)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    component_ids = _component_ids(faces)
    chosen_faces = faces[
        np.isin(component_ids, np.asarray(selected_ids, dtype=np.int64))
    ]
    if not len(chosen_faces):
        raise RuntimeError("donor accessory component has no faces")
    used = np.unique(chosen_faces.reshape(-1))
    remap = {int(old): new for new, old in enumerate(used.tolist())}
    local_faces = np.asarray([
        [remap[int(x)] for x in tri]
        for tri in chosen_faces
    ], dtype=np.int64)
    local_vertices = vertices[used]
    if len(local_vertices) < 3 or len(local_faces) < 1:
        raise RuntimeError("donor accessory component is too sparse")

    unique_components, counts = np.unique(component_ids, return_counts=True)
    main_component = int(
        unique_components[int(np.argmax(counts))]
    )
    main_faces = faces[component_ids == main_component]
    main_used = np.unique(main_faces.reshape(-1))
    main_vertices = vertices[main_used]
    if not len(main_vertices):
        raise RuntimeError("donor main body component is empty")

    visual=getattr(mesh,"visual",None)
    uv=getattr(visual,"uv",None) if visual is not None else None
    material=getattr(visual,"material",None) if visual is not None else None
    local_uv=None
    if uv is not None and len(uv)==len(vertices):
        uv_arr=np.asarray(uv,dtype=np.float64)
        candidate_uv=uv_arr[used]
        if (
            candidate_uv.shape==(len(local_vertices),2)
            and np.isfinite(candidate_uv).all()
        ):
            local_uv=candidate_uv

    return (
        selected,
        mesh,
        local_vertices,
        local_faces,
        main_vertices,
        local_uv,
        material,
        selected_ids,
    )


def _append_bytes(blob: bytearray, payload: bytes) -> tuple[int, int]:
    while len(blob) % 4:
        blob.append(0)
    offset = len(blob)
    blob.extend(payload)
    return offset, len(payload)


def _append_accessor(
    doc: dict,
    blob: bytearray,
    payload: bytes,
    *,
    component_type: int,
    count: int,
    accessor_type: str,
    minimum=None,
    maximum=None,
    normalized: bool = False,
    target: int | None = None,
) -> int:
    offset, length = _append_bytes(blob, payload)
    view = {
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": length,
    }
    if target is not None:
        view["target"] = int(target)
    views = doc.setdefault("bufferViews", [])
    view_index = len(views)
    views.append(view)

    accessor = {
        "bufferView": view_index,
        "componentType": int(component_type),
        "count": int(count),
        "type": str(accessor_type),
    }
    if normalized:
        accessor["normalized"] = True
    if minimum is not None:
        accessor["min"] = [float(x) for x in minimum]
    if maximum is not None:
        accessor["max"] = [float(x) for x in maximum]
    accessors = doc.setdefault("accessors", [])
    accessor_index = len(accessors)
    accessors.append(accessor)
    return accessor_index


def _parse_glb_bytes(payload: bytes) -> tuple[dict, bytes]:
    if len(payload)<20 or payload[:4]!=b"glTF":
        raise ValueError("material export is not a GLB")
    _,version,total=struct.unpack_from("<4sII",payload,0)
    if version!=2 or total!=len(payload):
        raise ValueError("invalid material GLB header")
    offset=12
    doc=None
    binary=b""
    while offset+8<=total:
        length,kind=struct.unpack_from("<II",payload,offset)
        offset+=8
        chunk=payload[offset:offset+length]
        offset+=length
        if kind==0x4E4F534A:
            doc=json.loads(chunk.decode("utf-8").rstrip("\x00 \t\r\n"))
        elif kind==0x004E4942:
            binary=chunk
    if doc is None:
        raise ValueError("material GLB JSON chunk missing")
    return doc,binary


def _export_material_glb(material):
    np,_=_deps()
    import trimesh

    vertices=np.asarray([
        [0.0,0.0,0.0],
        [1.0,0.0,0.0],
        [0.0,1.0,0.0],
    ],dtype=np.float64)
    faces=np.asarray([[0,1,2]],dtype=np.int64)
    uv=np.asarray([
        [0.0,0.0],
        [1.0,0.0],
        [0.0,1.0],
    ],dtype=np.float64)
    mesh=trimesh.Trimesh(
        vertices=vertices,
        faces=faces,
        process=False,
        visual=trimesh.visual.TextureVisuals(
            uv=uv,
            material=material.copy() if hasattr(material,"copy") else material,
        ),
    )
    raw=trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
    doc,binary=_parse_glb_bytes(raw)
    material_index=None
    for mesh_doc in doc.get("meshes") or []:
        for primitive in mesh_doc.get("primitives") or []:
            if isinstance(primitive.get("material"),int):
                material_index=int(primitive["material"])
                break
        if material_index is not None:
            break
    if material_index is None:
        raise RuntimeError("donor material export produced no material binding")
    return doc,binary,material_index


def _append_material_from_trimesh(
    doc: dict,
    blob: bytearray,
    material,
) -> int:
    source_doc,source_binary,source_material_index=(
        _export_material_glb(material)
    )
    source_materials=source_doc.get("materials") or []
    if not (
        0<=source_material_index<len(source_materials)
    ):
        raise RuntimeError("exported donor material index is invalid")
    source_material=json.loads(json.dumps(
        source_materials[source_material_index]
    ))
    if source_material.get("extensions"):
        raise RuntimeError(
            "new accessory material extensions are not yet proven safe"
        )

    image_map={}
    sampler_map={}
    texture_map={}

    def copy_sampler(index):
        if index is None:
            return None
        index=int(index)
        if index in sampler_map:
            return sampler_map[index]
        source=source_doc.get("samplers") or []
        if not (0<=index<len(source)):
            raise RuntimeError("donor material sampler index is invalid")
        target=doc.setdefault("samplers",[])
        new_index=len(target)
        target.append(json.loads(json.dumps(source[index])))
        sampler_map[index]=new_index
        return new_index

    def copy_image(index):
        index=int(index)
        if index in image_map:
            return image_map[index]
        images=source_doc.get("images") or []
        views=source_doc.get("bufferViews") or []
        if not (0<=index<len(images)):
            raise RuntimeError("donor material image index is invalid")
        image=json.loads(json.dumps(images[index]))
        view_index=image.get("bufferView")
        if not isinstance(view_index,int) or not (0<=view_index<len(views)):
            raise RuntimeError(
                "donor material image must be embedded in GLB bufferView"
            )
        view=views[view_index]
        if int(view.get("buffer",0) or 0)!=0:
            raise RuntimeError("donor material image uses unsupported buffer")
        start=int(view.get("byteOffset",0) or 0)
        length=int(view.get("byteLength",0) or 0)
        payload=source_binary[start:start+length]
        if len(payload)!=length or not payload:
            raise RuntimeError("donor material image payload is invalid")
        offset,new_length=_append_bytes(blob,payload)
        dest_views=doc.setdefault("bufferViews",[])
        new_view=len(dest_views)
        dest_views.append({
            "buffer":0,
            "byteOffset":offset,
            "byteLength":new_length,
        })
        image["bufferView"]=new_view
        image.pop("uri",None)
        dest_images=doc.setdefault("images",[])
        new_image=len(dest_images)
        dest_images.append(image)
        image_map[index]=new_image
        return new_image

    def copy_texture(index):
        index=int(index)
        if index in texture_map:
            return texture_map[index]
        textures=source_doc.get("textures") or []
        if not (0<=index<len(textures)):
            raise RuntimeError("donor material texture index is invalid")
        texture=json.loads(json.dumps(textures[index]))
        if texture.get("extensions"):
            raise RuntimeError(
                "new accessory texture extensions are not yet proven safe"
            )
        source_index=texture.get("source")
        if not isinstance(source_index,int):
            raise RuntimeError("donor texture has no image source")
        texture["source"]=copy_image(source_index)
        sampler=texture.get("sampler")
        if isinstance(sampler,int):
            texture["sampler"]=copy_sampler(sampler)
        dest_textures=doc.setdefault("textures",[])
        new_texture=len(dest_textures)
        dest_textures.append(texture)
        texture_map[index]=new_texture
        return new_texture

    pbr=source_material.get("pbrMetallicRoughness") or {}
    texture_infos=[
        pbr.get("baseColorTexture"),
        pbr.get("metallicRoughnessTexture"),
        source_material.get("normalTexture"),
        source_material.get("occlusionTexture"),
        source_material.get("emissiveTexture"),
    ]
    for info in texture_infos:
        if not isinstance(info,dict):
            continue
        source_index=info.get("index")
        if not isinstance(source_index,int):
            raise RuntimeError("donor material texture info has invalid index")
        info["index"]=copy_texture(source_index)

    materials=doc.setdefault("materials",[])
    new_material=len(materials)
    materials.append(source_material)
    return new_material


def _compute_tangents(vertices, normals, uvs, faces):
    np,_=_deps()
    vertices=np.asarray(vertices,dtype=np.float64)
    normals=np.asarray(normals,dtype=np.float64)
    uvs=np.asarray(uvs,dtype=np.float64)
    faces=np.asarray(faces,dtype=np.int64)
    tan=np.zeros((len(vertices),3),dtype=np.float64)
    bitan=np.zeros((len(vertices),3),dtype=np.float64)

    for tri in faces:
        i0,i1,i2=(int(x) for x in tri)
        p0,p1,p2=vertices[[i0,i1,i2]]
        uv0,uv1,uv2=uvs[[i0,i1,i2]]
        e1=p1-p0
        e2=p2-p0
        d1=uv1-uv0
        d2=uv2-uv0
        denom=float(d1[0]*d2[1]-d1[1]*d2[0])
        if not math.isfinite(denom) or abs(denom)<=1e-12:
            raise RuntimeError(
                "donor accessory has degenerate UV triangle; tangent basis unavailable"
            )
        r=1.0/denom
        t=(e1*d2[1]-e2*d1[1])*r
        b=(e2*d1[0]-e1*d2[0])*r
        for index in (i0,i1,i2):
            tan[index]+=t
            bitan[index]+=b

    output=np.zeros((len(vertices),4),dtype=np.float64)
    for index in range(len(vertices)):
        n=normals[index]
        n_norm=float(np.linalg.norm(n))
        if not math.isfinite(n_norm) or n_norm<=1e-12:
            raise RuntimeError("donor accessory normal is invalid")
        n=n/n_norm
        t=tan[index]-n*float(np.dot(n,tan[index]))
        t_norm=float(np.linalg.norm(t))
        if not math.isfinite(t_norm) or t_norm<=1e-12:
            raise RuntimeError("donor accessory tangent is invalid")
        t=t/t_norm
        handedness=(
            -1.0
            if float(np.dot(np.cross(n,t),bitan[index]))<0.0
            else 1.0
        )
        output[index,:3]=t
        output[index,3]=handedness
    return output


def _pack_joints(values, component_type: int) -> bytes:
    np, _ = _deps()
    arr = np.asarray(values)
    if component_type == 5121:
        if np.any(arr < 0) or np.any(arr > 255):
            raise ValueError("JOINTS_0 exceeds UNSIGNED_BYTE range")
        return arr.astype(np.uint8).tobytes()
    if component_type == 5123:
        if np.any(arr < 0) or np.any(arr > 65535):
            raise ValueError("JOINTS_0 exceeds UNSIGNED_SHORT range")
        return arr.astype("<u2").tobytes()
    raise ValueError(f"unsupported JOINTS_0 component type {component_type}")


def _read_target_deltas(base, semantic: str):
    np, _ = _deps()
    from skin_weight_qa import _read_accessor

    doc = base["doc"]
    binary = base["binary"]
    primitive = base["primitive"]
    count = len(base["positions"])
    output = []
    for target in primitive.get("targets") or []:
        accessor = (target or {}).get(semantic)
        if accessor is None:
            output.append(np.zeros((count, 3), dtype=np.float64))
            continue
        rows = np.asarray(
            _read_accessor(doc, binary, int(accessor)),
            dtype=np.float64,
        )
        if rows.shape != (count, 3):
            raise RuntimeError(
                f"base morph {semantic} accessor shape {rows.shape} "
                f"!= {(count, 3)}"
            )
        if not np.isfinite(rows).all():
            raise RuntimeError(f"base morph {semantic} contains non-finite values")
        output.append(rows)
    return output


def rigged_accessory_insert_supported(
    base_mesh: Path,
    donor_mesh: Path,
    *,
    base_up_axis: str = "y",
    donor_up_axis: str | None = None,
) -> tuple[bool, str | None]:
    try:
        from gltf_audit import audit_glb
        from skin_weight_qa import audit_skin_weights

        rig = audit_glb(base_mesh)
        skin = audit_skin_weights(base_mesh)
        if not rig.rig_ready:
            return False, "base rig is not valid"
        if not skin.applicable or not skin.ready:
            return False, "base skin weights are not valid"
        from accessory_match import inspect_accessories
        base_accessories = inspect_accessories(
            base_mesh,
            mode="character",
            up_axis=base_up_axis,
        )
        if base_accessories:
            return (
                False,
                "base already has detached accessory candidates; "
                "use rig-preserving accessory wrap instead",
            )
        if (donor_up_axis or base_up_axis) != base_up_axis:
            return (
                False,
                "new-vertex insertion v1 requires matching base/donor up axes",
            )
        _base_primitive(base_mesh)
        _donor_accessory(
            donor_mesh,
            mode="character",
            up_axis=donor_up_axis or base_up_axis,
        )
        # Geometry/runtime support is intentionally independent from material
        # support. Composite planning records both proofs separately so an
        # untextured donor can be diagnosed as material-blocked rather than
        # misclassified as an unrelated local-detail transfer.
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"


def insert_rigged_accessory(
    base_mesh: Path,
    donor_mesh: Path,
    output_glb: Path,
    *,
    base_up_axis: str = "y",
    donor_up_axis: str | None = None,
    max_weight_source_distance_ratio: float = 0.12,
    max_bbox_drift_fraction: float = 0.18,
) -> RiggedAccessoryInsertResult:
    np, cKDTree = _deps()
    warnings: list[str] = []
    errors: list[str] = []
    donor_up_axis = donor_up_axis or base_up_axis

    try:
        from gltf_audit import audit_glb
        from skin_weight_qa import audit_skin_weights

        before_rig = audit_glb(base_mesh)
        before_skin = audit_skin_weights(base_mesh)
        if not before_rig.rig_ready:
            raise RuntimeError("base rig is not valid")
        if not before_skin.applicable or not before_skin.ready:
            raise RuntimeError("base skin weights are not valid")

        from accessory_match import inspect_accessories
        base_accessories = inspect_accessories(
            base_mesh,
            mode="character",
            up_axis=base_up_axis,
        )
        if base_accessories:
            raise RuntimeError(
                "base already has detached accessory candidates; use the "
                "topology-preserving rigged accessory wrap path instead"
            )
        if donor_up_axis != base_up_axis:
            raise RuntimeError(
                "new-vertex insertion v1 requires matching base/donor up axes"
            )

        base = _base_primitive(base_mesh)
        (
            selected,
            donor_mesh_flat,
            donor_vertices,
            donor_faces,
            donor_main_vertices,
            donor_uv,
            donor_material,
            donor_component_ids,
        ) = _donor_accessory(
            donor_mesh,
            mode="character",
            up_axis=donor_up_axis,
        )

        base_vertices = base["positions"]
        _, _, base_center, base_extent = _bbox(base_vertices)
        _, _, donor_center, donor_extent = _bbox(donor_main_vertices)
        base_diag = max(float(np.linalg.norm(base_extent)), 1e-9)
        donor_diag = max(float(np.linalg.norm(donor_extent)), 1e-9)
        aligned = (
            (donor_vertices - donor_center)
            * (base_diag / donor_diag)
            + base_center
        )

        (
            transferred_joints,
            transferred_weights,
            surface_relation,
        ) = _surface_skin_transfer(
            base_vertices,
            base["faces"],
            base["joints"],
            base["weights"],
            aligned,
        )
        source_distance = np.asarray(
            surface_relation.surface_distance,
            dtype=np.float64,
        )
        nearest = np.asarray(
            surface_relation.nearest_vertex_ids,
            dtype=np.int64,
        )
        _require_exact_surface_relation(surface_relation)
        source_ratio = source_distance / base_diag
        max_source_ratio = (
            float(np.max(source_ratio)) if len(source_ratio) else 0.0
        )
        mean_source_ratio = (
            float(np.mean(source_ratio)) if len(source_ratio) else 0.0
        )
        if max_source_ratio > max_weight_source_distance_ratio:
            raise RuntimeError(
                "new accessory is too far from canonical body for safe "
                "nearest-surface weight transfer: "
                f"{max_source_ratio:.6f}>{max_weight_source_distance_ratio:.6f}"
            )

        sums = np.sum(transferred_weights, axis=1)
        if np.any(~np.isfinite(transferred_weights)) or np.any(sums <= 1e-8):
            raise RuntimeError("blended canonical skin weights are invalid")
        transferred_weights /= sums[:, None]

        before_doc = json.loads(json.dumps(base["doc"]))
        before_binary = bytes(base["binary"])
        doc = json.loads(json.dumps(base["doc"]))
        blob = bytearray(base["binary"])

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
        joint_accessor = _append_accessor(
            doc,
            blob,
            _pack_joints(
                transferred_joints,
                int(base["joint_component"]),
            ),
            component_type=int(base["joint_component"]),
            count=len(aligned),
            accessor_type="VEC4",
        )
        weight_accessor = _append_accessor(
            doc,
            blob,
            np.asarray(transferred_weights, dtype="<f4").tobytes(),
            component_type=5126,
            count=len(aligned),
            accessor_type="VEC4",
        )

        max_index = int(np.max(donor_faces))
        if max_index <= 65535:
            index_component = 5123
            index_bytes = np.asarray(donor_faces, dtype="<u2").reshape(-1).tobytes()
        else:
            index_component = 5125
            index_bytes = np.asarray(donor_faces, dtype="<u4").reshape(-1).tobytes()
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

        # Add computed normals. Keeping the new primitive independent from the
        # base UV/material topology prevents stale tangent-space evidence.
        import trimesh
        temp = trimesh.Trimesh(
            vertices=np.asarray(aligned, dtype=np.float64),
            faces=np.asarray(donor_faces, dtype=np.int64),
            process=False,
        )
        normals = np.asarray(temp.vertex_normals, dtype=np.float64)
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

        # Raw insertion deliberately does not bind donor appearance.
        # accessory_material_transfer.py owns the independent UV/PBR proof.
        material_index=None
        uv_accessor=None
        tangent_accessor=None
        transferred_material_channels=[]

        base_targets = base["primitive"].get("targets") or []
        new_targets = []
        semantics = sorted({
            semantic
            for target in base_targets
            for semantic in (target or {}).keys()
            if semantic in {"POSITION", "NORMAL", "TANGENT"}
        })
        transferred_semantics = set()
        for target_index in range(len(base_targets)):
            target_out = {}
            for semantic in semantics:
                deltas = _read_target_deltas(base, semantic)
                from surface_transfer import interpolate_vertex_values
                source = interpolate_vertex_values(
                    deltas[target_index],
                    surface_relation,
                )
                accessor = _append_accessor(
                    doc,
                    blob,
                    np.asarray(source, dtype="<f4").tobytes(),
                    component_type=5126,
                    count=len(source),
                    accessor_type="VEC3",
                    minimum=np.min(source, axis=0),
                    maximum=np.max(source, axis=0),
                )
                target_out[semantic] = accessor
                transferred_semantics.add(semantic)
            new_targets.append(target_out)

        new_attributes={
            "POSITION": position_accessor,
            "NORMAL": normal_accessor,
            "JOINTS_0": joint_accessor,
            "WEIGHTS_0": weight_accessor,
        }
        if (
            material_index is not None
            and uv_accessor is not None
            and tangent_accessor is not None
        ):
            new_attributes["TEXCOORD_0"]=uv_accessor
            new_attributes["TANGENT"]=tangent_accessor

        new_primitive = {
            "attributes": new_attributes,
            "indices": index_accessor,
            "mode": 4,
        }
        if material_index is not None:
            new_primitive["material"]=int(material_index)
        if new_targets:
            new_primitive["targets"] = new_targets

        meshes = doc.get("meshes") or []
        mesh = meshes[int(base["mesh_index"])]
        mesh.setdefault("primitives", []).append(new_primitive)

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
                "pre-existing GLB payload changed during accessory insertion"
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
            errors.append("rig audit failed after new accessory insertion")
            errors.extend(after_rig.errors or [])
        if not skin_ready:
            errors.append("skin-weight QA failed after new accessory insertion")
            errors.extend(after_skin.errors or [])
        if not morph_ready:
            errors.append(
                "morph structure changed or became invalid after new accessory insertion"
            )

        morph_deformation_ready = None
        if before_rig.morph_target_count > 0:
            from morph_deformation_qa import audit_morph_deformation
            morph = audit_morph_deformation(output_glb)
            morph_deformation_ready = bool(morph.applicable and morph.ready)
            warnings.extend(morph.warnings or [])
            if not morph_deformation_ready:
                errors.append(
                    "morph deformation QA failed after new accessory insertion"
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
                errors.append("animation QA failed after new accessory insertion")
                errors.extend(animation.errors or [])
            if not deformation_ready:
                errors.append("deformation QA failed after new accessory insertion")
                errors.extend(deformation.errors or [])

        from composite_attachment_qa import audit_composite_attachments
        attachment = audit_composite_attachments(
            output_glb,
            mode="character",
        )
        warnings.extend(attachment.warnings or [])
        attachment_ready = bool(attachment.applicable and attachment.ready)
        if not attachment_ready:
            errors.append(
                "new accessory does not remain coherently attached to canonical body"
            )
            errors.extend(attachment.errors or [])

        from component_crossing_qa import audit_component_crossings
        crossing = audit_component_crossings(output_glb)
        if not crossing.ready:
            errors.append(
                "new accessory insertion introduced major component crossings"
            )

        from self_intersection_qa import audit_self_intersections
        self_cross = audit_self_intersections(output_glb)
        if not self_cross.ready:
            errors.append(
                "new accessory insertion introduced self intersections"
            )

        from part_map import _load_mesh
        output_mesh = _load_mesh(output_glb)
        _, _, _, output_extent = _bbox(output_mesh.vertices)
        bbox_drift = float(np.max(
            np.abs(output_extent - base_extent)
            / np.maximum(base_extent, base_diag * 1e-6)
        ))
        if bbox_drift > max_bbox_drift_fraction:
            errors.append(
                "new accessory bbox drift "
                f"{bbox_drift:.6f}>{max_bbox_drift_fraction:.6f}"
            )

        if len(donor_component_ids) > 1:
            warnings.append(
                "multi_piece_accessory_cluster="
                + ",".join(str(x) for x in donor_component_ids)
            )

        geometry_ready=not errors
        inserted_primitive=(
            (after_doc.get("meshes") or [])[int(base["mesh_index"])]
            .get("primitives", [])[-1]
        )
        (
            material_ready,
            uv_ready,
            material_blockers,
        )=_inserted_primitive_material_evidence(
            after_doc,
            inserted_primitive,
        )
        uv_tangent_ready=False
        if material_ready and uv_ready:
            try:
                from uv_tangent_qa import audit_uv_tangents
                from shading_basis_qa import audit_shading_basis
                uv_audit=audit_uv_tangents(output_glb)
                shading_audit=audit_shading_basis(
                    output_glb,
                    require_explicit_tangents_for_normal_maps=True,
                )
                inserted_primitive_index=(
                    len(
                        (after_doc.get("meshes") or [])[
                            int(base["mesh_index"])
                        ].get("primitives",[])
                    )-1
                )
                uv_item=next(
                    (
                        item for item in uv_audit.primitives
                        if int(item.mesh_index)==int(base["mesh_index"])
                        and int(item.primitive_index)==inserted_primitive_index
                    ),
                    None,
                )
                shading_item=next(
                    (
                        item for item in shading_audit.primitives
                        if int(item.mesh_index)==int(base["mesh_index"])
                        and int(item.primitive_index)==inserted_primitive_index
                    ),
                    None,
                )
                uv_tangent_ready=bool(
                    uv_item is not None
                    and uv_item.ready
                    and shading_item is not None
                    and shading_item.ready
                )
                if not uv_tangent_ready:
                    material_blockers.append(
                        "inserted primitive UV/tangent/shading-basis QA failed"
                    )
                    if uv_item is not None:
                        material_blockers.extend(uv_item.errors or [])
                    if shading_item is not None:
                        material_blockers.extend(shading_item.errors or [])
            except Exception as exc:
                material_blockers.append(
                    "inserted primitive UV/tangent QA unavailable: "
                    f"{type(exc).__name__}:{exc}"
                )

        production_ready=bool(
            geometry_ready
            and material_ready
            and uv_ready
            and uv_tangent_ready
            and legacy_preserved
        )
        if not production_ready:
            warnings.append(
                "new-vertex accessory geometry/runtime proof passed, but "
                "inserted-primitive UV/material evidence is incomplete; "
                "Composite production promotion remains blocked"
            )

        return RiggedAccessoryInsertResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            attempted=True,
            ready=geometry_ready,
            geometry_ready=geometry_ready,
            material_ready=material_ready,
            uv_ready=uv_ready,
            uv_tangent_ready=uv_tangent_ready,
            material_channels=transferred_material_channels,
            production_ready=production_ready,
            legacy_payload_preserved=legacy_preserved,
            material_blockers=material_blockers,
            donor_component_id=int(selected.component_id),
            spatial_label=(
                str(selected.spatial_label)
                if len(donor_component_ids) == 1
                else "cluster"
            ),
            inserted_vertices=int(len(aligned)),
            inserted_faces=int(len(donor_faces)),
            transferred_weight_vertices=int(len(aligned)),
            weight_source_max_distance_ratio=round(max_source_ratio, 8),
            weight_source_mean_distance_ratio=round(mean_source_ratio, 8),
            morph_targets_transferred=int(len(new_targets)),
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
            surface_transfer_method=str(surface_relation.method),
            surface_transfer_fallback_vertices=int(
                surface_relation.fallback_vertices
            ),
            surface_transfer_max_examined_triangles=int(
                surface_relation.max_examined_triangles
            ),
            surface_transfer_max_visited_bvh_nodes=int(
                surface_relation.max_visited_bvh_nodes
            ),
            surface_skin_ambiguous_vertices=int(
                surface_relation.ambiguous_skin_vertices
            ),
            surface_skin_min_gap_ratio=(
                surface_relation.surface_skin_min_gap_ratio
            ),
            surface_skin_max_l1=float(
                surface_relation.surface_skin_max_l1
            ),
        )
    except Exception as exc:
        return _fail(
            base_mesh,
            donor_mesh,
            output_glb,
            f"{type(exc).__name__}:{exc}",
            warnings=warnings,
        )


def prepare_production_rigged_accessory_insert(
    base_mesh: Path,
    donor_mesh: Path,
    out_dir: Path,
    *,
    base_up_axis: str = "y",
    donor_up_axis: str | None = None,
) -> RiggedAccessoryInsertResult:
    """Build a missing skinned accessory and prove its donor appearance.

    Geometry/runtime insertion and UV/PBR transfer are intentionally separate
    proofs. This wrapper is the only path that may mark a new-vertex accessory
    production-ready.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "rigged_accessory_insert_raw.glb"
    final_path = out_dir / "rigged_accessory_insert_material.glb"

    use_split_insert = False
    try:
        from accessory_source_groups import audit_accessory_source_groups
        source_groups = audit_accessory_source_groups(
            donor_mesh,
            mode="character",
            up_axis=donor_up_axis or base_up_axis,
        )
        use_split_insert = bool(
            source_groups.ready
            and int(source_groups.group_count) > 1
        )
    except Exception:
        use_split_insert = False

    if use_split_insert:
        from rigged_accessory_split_insert import (
            insert_split_rigged_accessory,
        )
        result = insert_split_rigged_accessory(
            base_mesh,
            donor_mesh,
            raw_path,
            base_up_axis=base_up_axis,
            donor_up_axis=donor_up_axis,
        )
    else:
        result = insert_rigged_accessory(
            base_mesh,
            donor_mesh,
            raw_path,
            base_up_axis=base_up_axis,
            donor_up_axis=donor_up_axis,
        )
    if not result.geometry_ready:
        result.ready = False
        result.production_ready = False
        return result

    try:
        from accessory_material_transfer import (
            transfer_accessory_material,
        )
        transfer = transfer_accessory_material(
            donor_mesh,
            raw_path,
            final_path,
            donor_up_axis=donor_up_axis or base_up_axis,
        )
        result.warnings.extend(transfer.warnings or [])
        if not transfer.ready:
            result.ready = False
            result.material_ready = False
            result.uv_ready = False
            result.production_ready = False
            result.material_blockers = list(transfer.errors or [])
            result.errors.extend(
                "material_transfer:" + item
                for item in (transfer.errors or [])
            )
            return result

        from glb_images import read_glb
        final_doc, final_binary = read_glb(final_path)
        base = _base_primitive(base_mesh)
        mesh = (
            (final_doc.get("meshes") or [])
            [int(base["mesh_index"])]
        )
        primitives = mesh.get("primitives") or []
        if len(primitives) < 2:
            raise RuntimeError(
                "production accessory transfer lost the appended primitive"
            )

        inserted_primitives = [
            primitive
            for primitive in primitives
            if bool(
                (primitive.get("extras") or {}).get(
                    "hayuyaAccessorySplit"
                )
            )
        ]
        if not inserted_primitives:
            inserted_primitives = [primitives[-1]]

        material_proofs = [
            _inserted_primitive_material_evidence(
                final_doc,
                primitive,
            )
            for primitive in inserted_primitives
        ]
        material_ready = all(
            bool(item[0]) for item in material_proofs
        )
        uv_ready = all(
            bool(item[1]) for item in material_proofs
        )
        blockers = []
        for primitive_index, proof in enumerate(material_proofs):
            blockers.extend(
                f"inserted_primitive[{primitive_index}]:{item}"
                for item in (proof[2] or [])
            )

        result.inserted_primitives = int(len(inserted_primitives))
        result.material_groups = int(len({
            int(primitive["material"])
            for primitive in inserted_primitives
            if isinstance(primitive.get("material"), int)
        }))

        result.material_ready = bool(
            material_ready and transfer.ready
        )
        result.uv_ready = bool(uv_ready)
        result.uv_tangent_ready = bool(
            transfer.uv_tangent_ready
            and transfer.shading_basis_ready
        )
        result.material_channels = list(
            transfer.copied_channels or []
        )
        result.material_blockers = list(blockers)
        if not result.uv_tangent_ready:
            result.material_blockers.append(
                "accessory material transfer lacks valid UV/tangent/shading proof"
            )

        result.legacy_payload_preserved = _legacy_payload_preserved(
            base["doc"],
            bytes(base["binary"]),
            final_doc,
            final_binary,
        )
        if not result.legacy_payload_preserved:
            result.errors.append(
                "pre-existing GLB payload changed during donor material transfer"
            )

        from gltf_audit import audit_glb
        from skin_weight_qa import audit_skin_weights
        rig = audit_glb(final_path)
        skin = audit_skin_weights(final_path)
        result.rig_ready = bool(rig.rig_ready)
        result.skin_weights_ready = bool(
            skin.applicable and skin.ready
        )
        result.morph_ready = bool(rig.morph_ready)

        if rig.morph_target_count > 0:
            from morph_deformation_qa import audit_morph_deformation
            morph = audit_morph_deformation(final_path)
            result.morph_deformation_ready = bool(
                morph.applicable and morph.ready
            )
            result.warnings.extend(morph.warnings or [])
            if not result.morph_deformation_ready:
                result.errors.append(
                    "production accessory morph deformation QA failed"
                )
                result.errors.extend(morph.errors or [])

        if rig.animation_count > 0:
            from animation_qa import audit_animation
            from deformation_qa import audit_deformation
            animation = audit_animation(final_path)
            deformation = audit_deformation(
                final_path,
                max_frames_per_animation=6,
            )
            result.animation_ready = bool(
                animation.applicable and animation.ready
            )
            result.deformation_ready = bool(
                deformation.applicable and deformation.ready
            )
            result.warnings.extend(animation.warnings or [])
            result.warnings.extend(deformation.warnings or [])
            if not result.animation_ready:
                result.errors.append(
                    "production accessory animation QA failed"
                )
                result.errors.extend(animation.errors or [])
            if not result.deformation_ready:
                result.errors.append(
                    "production accessory deformation QA failed"
                )
                result.errors.extend(deformation.errors or [])

        from composite_attachment_qa import audit_composite_attachments
        attachment = audit_composite_attachments(
            final_path,
            mode="character",
        )
        result.attachment_ready = bool(
            attachment.applicable and attachment.ready
        )
        result.warnings.extend(attachment.warnings or [])
        if not result.attachment_ready:
            result.errors.append(
                "production accessory attachment QA failed"
            )
            result.errors.extend(attachment.errors or [])

        from component_crossing_qa import audit_component_crossings
        from self_intersection_qa import audit_self_intersections
        crossing = audit_component_crossings(final_path)
        self_cross = audit_self_intersections(final_path)
        result.component_crossing_ready = bool(crossing.ready)
        result.self_intersection_ready = bool(self_cross.ready)
        if not crossing.ready:
            result.errors.append(
                "production accessory component crossing QA failed"
            )
        if not self_cross.ready:
            result.errors.append(
                "production accessory self-intersection QA failed"
            )

        result.output_glb = str(final_path)
        result.production_ready = bool(
            result.geometry_ready
            and result.material_ready
            and result.uv_ready
            and result.uv_tangent_ready
            and result.legacy_payload_preserved
            and result.rig_ready
            and result.skin_weights_ready
            and result.morph_ready
            and (
                result.morph_deformation_ready is not False
            )
            and (
                result.animation_ready is not False
            )
            and (
                result.deformation_ready is not False
            )
            and result.attachment_ready
            and result.component_crossing_ready
            and result.self_intersection_ready
            and not result.material_blockers
            and not result.errors
        )
        result.ready = result.production_ready
        if not result.production_ready and not result.errors:
            result.errors.append(
                "new accessory did not satisfy the complete production proof"
            )
        return result
    except Exception as exc:
        result.ready = False
        result.material_ready = False
        result.uv_ready = False
        result.production_ready = False
        result.errors.append(
            f"production_material_transfer:{type(exc).__name__}:{exc}"
        )
        return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description=(
            "Insert one new detached accessory primitive into a validated "
            "skinned HAYUYA character with nearest-surface skin-weight and "
            "morph-delta transfer. Geometry/runtime readiness does not imply "
            "production readiness until donor UV/material transfer is proven."
        )
    )
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-up-axis", choices=["x", "y", "z"], default="y")
    parser.add_argument("--donor-up-axis", choices=["x", "y", "z"])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    result = insert_rigged_accessory(
        args.base,
        args.donor,
        args.output,
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
