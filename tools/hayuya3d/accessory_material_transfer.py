#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AccessoryMaterialTransferResult:
    donor_mesh: str
    inserted_mesh: str
    output_glb: str
    attempted: bool
    ready: bool
    donor_component_id: int | None
    donor_component_ids: list[int]
    donor_mesh_index: int | None
    donor_primitive_index: int | None
    material_index: int | None
    inserted_primitive_index: int | None
    uv_vertices: int
    copied_images: int
    copied_textures: int
    copied_samplers: int
    copied_channels: list[str]
    tangent_generated: bool
    uv_tangent_ready: bool
    shading_basis_ready: bool
    warnings: list[str]
    errors: list[str]
    method: str = "hayuya-accessory-material-transfer-v1"


def _deps():
    import numpy as np
    return np


def _bbox(vertices):
    np = _deps()
    vv = np.asarray(vertices, dtype=np.float64)
    lo = np.min(vv, axis=0)
    hi = np.max(vv, axis=0)
    return lo, hi, (lo + hi) * 0.5, hi - lo


def _primitive_triangles(doc: dict, binary: bytes, primitive: dict):
    np = _deps()
    from skin_weight_qa import _read_accessor

    attrs = primitive.get("attributes") or {}
    pos_index = attrs.get("POSITION")
    index_index = primitive.get("indices")
    if not isinstance(pos_index, int) or not isinstance(index_index, int):
        raise ValueError("material donor primitive must be indexed with POSITION")
    if int(primitive.get("mode", 4)) != 4:
        raise ValueError("material donor primitive must use TRIANGLES mode")

    positions = np.asarray(
        _read_accessor(doc, binary, pos_index),
        dtype=np.float64,
    )
    raw_indices = np.asarray(
        _read_accessor(doc, binary, index_index),
        dtype=np.int64,
    ).reshape(-1)
    if len(raw_indices) % 3:
        raise ValueError("material donor index count is not divisible by three")
    faces = raw_indices.reshape((-1, 3))
    if len(faces) and (
        int(np.min(faces)) < 0
        or int(np.max(faces)) >= len(positions)
    ):
        raise ValueError("material donor indices reference missing vertices")
    return positions, faces


def _world_components(path: Path):
    np = _deps()
    from deformation_qa import _global_matrices
    from gltf_position_patch import _doc_and_bin
    from part_map import _component_ids

    doc, binary, _ = _doc_and_bin(path)
    globals_ = _global_matrices(doc, {})
    meshes = doc.get("meshes") or []
    out = []

    for node_index, node in enumerate(doc.get("nodes") or []):
        mesh_index = node.get("mesh")
        if not isinstance(mesh_index, int) or not (0 <= mesh_index < len(meshes)):
            continue
        matrix = np.asarray(globals_[node_index], dtype=np.float64)
        for primitive_index, primitive in enumerate(
            meshes[mesh_index].get("primitives") or []
        ):
            try:
                positions, faces = _primitive_triangles(
                    doc,
                    binary,
                    primitive,
                )
            except Exception:
                continue
            homogeneous = np.concatenate(
                [
                    positions,
                    np.ones((len(positions), 1), dtype=np.float64),
                ],
                axis=1,
            )
            world = (matrix @ homogeneous.T).T[:, :3]
            component_ids = _component_ids(faces)
            for component_id in np.unique(component_ids):
                face_mask = component_ids == int(component_id)
                component_faces = faces[face_mask]
                used = np.unique(component_faces.reshape(-1))
                vv = world[used]
                if not len(vv):
                    continue
                out.append({
                    "node_index": int(node_index),
                    "mesh_index": int(mesh_index),
                    "primitive_index": int(primitive_index),
                    "component_id": int(component_id),
                    "face_count": int(len(component_faces)),
                    "used_vertex_ids": used,
                    "faces": component_faces,
                    "positions_local": positions,
                    "positions_world": world,
                    "centroid": np.mean(vv, axis=0),
                    "extent": np.max(vv, axis=0) - np.min(vv, axis=0),
                    "matrix": matrix,
                    "primitive": primitive,
                })
    if not out:
        raise RuntimeError("donor GLB exposes no indexed triangle components")
    return doc, binary, out


def _find_accessory_component(path: Path, *, up_axis: str):
    np = _deps()
    from accessory_match import inspect_accessories

    candidates = inspect_accessories(
        path,
        mode="character",
        up_axis=up_axis,
    )
    if not candidates:
        raise RuntimeError(
            "material transfer requires donor accessory evidence"
        )

    if len(candidates) == 1:
        selected = [candidates[0]]
    else:
        from accessory_cluster import inspect_accessory_clusters
        cluster = inspect_accessory_clusters(
            path,
            mode="character",
            up_axis=up_axis,
        )
        if not cluster.ready or not cluster.selected_component_ids:
            detail = ";".join(cluster.errors or [])
            raise RuntimeError(
                "multi-piece material transfer requires one proven "
                "anchored logical accessory cluster"
                + (f": {detail}" if detail else "")
            )
        by_id = {
            int(item.component_id): item
            for item in candidates
        }
        selected_ids = [
            int(x) for x in cluster.selected_component_ids
        ]
        if set(selected_ids) != set(by_id):
            raise RuntimeError(
                "accessory cluster material proof did not account for every "
                "donor accessory candidate"
            )
        selected = [by_id[x] for x in selected_ids]

    doc, binary, components = _world_components(path)
    all_points = np.concatenate([
        item["positions_world"][item["used_vertex_ids"]]
        for item in components
    ], axis=0)
    lo, hi, _, extent = _bbox(all_points)
    diagonal = max(float(np.linalg.norm(extent)), 1e-9)
    safe_extent = np.maximum(extent, diagonal * 1e-6)

    mapped = []
    used_rows = set()
    for wanted in selected:
        wanted_centroid = np.asarray(
            wanted.normalized_centroid,
            dtype=np.float64,
        )
        wanted_extent = np.asarray(
            wanted.normalized_extent,
            dtype=np.float64,
        )
        scored = []
        for item in components:
            if int(item["face_count"]) != int(wanted.face_count):
                continue
            row_key = (
                int(item["node_index"]),
                int(item["mesh_index"]),
                int(item["primitive_index"]),
                int(item["component_id"]),
            )
            if row_key in used_rows:
                continue
            normalized_centroid = (
                np.asarray(item["centroid"], dtype=np.float64) - lo
            ) / safe_extent
            normalized_extent = (
                np.asarray(item["extent"], dtype=np.float64)
            ) / safe_extent
            score = float(
                np.linalg.norm(normalized_centroid - wanted_centroid)
                + np.linalg.norm(normalized_extent - wanted_extent)
            )
            scored.append((score, row_key, item))

        if not scored:
            raise RuntimeError(
                "could not map flattened accessory candidate back to "
                "donor primitive"
            )
        scored.sort(key=lambda row: row[0])
        best_score, best_key, best = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else None
        if best_score > 0.02:
            raise RuntimeError(
                "donor accessory primitive mapping drift is too large: "
                f"{best_score:.6f}>0.020000"
            )
        if second_score is not None and second_score - best_score < 0.01:
            raise RuntimeError(
                "donor accessory primitive mapping is ambiguous"
            )
        used_rows.add(best_key)
        row = dict(best)
        row["candidate"] = wanted
        mapped.append(row)

    locations = {
        (
            int(item["node_index"]),
            int(item["mesh_index"]),
            int(item["primitive_index"]),
        )
        for item in mapped
    }
    if len(locations) != 1:
        raise RuntimeError(
            "multi-piece accessory material transfer currently requires "
            "every selected piece to share one donor primitive/atlas"
        )

    first = dict(mapped[0])
    primitive = first["primitive"]
    if not isinstance(primitive.get("material"), int):
        raise RuntimeError(
            "donor accessory primitive has no explicit material"
        )

    used = np.unique(np.concatenate([
        np.asarray(item["used_vertex_ids"], dtype=np.int64)
        for item in mapped
    ]))
    first["used_vertex_ids"] = used
    first["candidate"] = selected[0]
    first["candidates"] = selected
    first["candidate_component_ids"] = [
        int(item.component_id) for item in selected
    ]
    first["mapped_components"] = mapped
    first["face_count"] = int(sum(
        int(item["face_count"]) for item in mapped
    ))
    return doc, binary, first


def _material_texture_indices(material: dict) -> list[int]:
    indices = []

    def add(info):
        if isinstance(info, dict) and isinstance(info.get("index"), int):
            indices.append(int(info["index"]))

    pbr = material.get("pbrMetallicRoughness") or {}
    add(pbr.get("baseColorTexture"))
    add(pbr.get("metallicRoughnessTexture"))
    add(material.get("normalTexture"))
    add(material.get("occlusionTexture"))
    add(material.get("emissiveTexture"))
    return sorted(set(indices))


def _material_channels(material: dict) -> list[str]:
    channels = []
    pbr = material.get("pbrMetallicRoughness") or {}
    if isinstance(pbr.get("baseColorTexture"), dict):
        channels.append("baseColor")
    if isinstance(pbr.get("metallicRoughnessTexture"), dict):
        channels.extend(["metallic", "roughness"])
    if isinstance(material.get("normalTexture"), dict):
        channels.append("normal")
    if isinstance(material.get("occlusionTexture"), dict):
        channels.append("occlusion")
    if isinstance(material.get("emissiveTexture"), dict):
        channels.append("emissive")
    return sorted(set(channels))


def _material_basecolor_texture(material: dict) -> bool:
    pbr = material.get("pbrMetallicRoughness") or {}
    return isinstance(pbr.get("baseColorTexture"), dict)


def _texture_source(texture: dict) -> tuple[str, int]:
    source = texture.get("source")
    if isinstance(source, int):
        return "source", int(source)
    basisu = (
        (texture.get("extensions") or {})
        .get("KHR_texture_basisu")
    )
    if isinstance(basisu, dict) and isinstance(basisu.get("source"), int):
        return "basisu", int(basisu["source"])
    raise RuntimeError("donor texture has no supported embedded image source")


def _copy_material_bundle(
    donor_doc: dict,
    donor_binary: bytes,
    base_doc: dict,
    base_blob: bytearray,
    material_index: int,
):
    if (donor_doc.get("extensionsRequired") or []):
        unsupported = [
            ext
            for ext in donor_doc.get("extensionsRequired") or []
            if ext != "KHR_texture_basisu"
        ]
        if unsupported:
            raise RuntimeError(
                "donor material requires unsupported glTF extensions: "
                + ",".join(unsupported)
            )

    materials = donor_doc.get("materials") or []
    if not (0 <= int(material_index) < len(materials)):
        raise RuntimeError("donor accessory has invalid material index")
    source_material = materials[int(material_index)]
    if source_material.get("extensions"):
        raise RuntimeError(
            "accessory material extensions are not yet safe for transfer"
        )
    if not _material_basecolor_texture(source_material):
        raise RuntimeError(
            "accessory production transfer requires a donor baseColor texture"
        )

    donor_views = donor_doc.get("bufferViews") or []
    donor_images = donor_doc.get("images") or []
    donor_textures = donor_doc.get("textures") or []
    donor_samplers = donor_doc.get("samplers") or []

    image_map = {}
    sampler_map = {}
    texture_map = {}
    copied_images = 0
    copied_samplers = 0

    def copy_image(index: int) -> int:
        nonlocal copied_images
        if index in image_map:
            return image_map[index]
        if not (0 <= index < len(donor_images)):
            raise RuntimeError(f"donor image index out of range: {index}")
        image = donor_images[index]
        view_index = image.get("bufferView")
        if not isinstance(view_index, int) or not (0 <= view_index < len(donor_views)):
            raise RuntimeError(
                "accessory material images must be embedded GLB bufferViews"
            )
        view = donor_views[view_index]
        start = int(view.get("byteOffset") or 0)
        length = int(view.get("byteLength") or 0)
        payload = donor_binary[start:start + length]
        if len(payload) != length or not payload:
            raise RuntimeError("donor embedded image payload is missing")

        from rigged_accessory_insert import _append_bytes
        byte_offset, byte_length = _append_bytes(base_blob, payload)
        new_view = {
            "buffer": 0,
            "byteOffset": byte_offset,
            "byteLength": byte_length,
        }
        base_views = base_doc.setdefault("bufferViews", [])
        new_view_index = len(base_views)
        base_views.append(new_view)

        new_image = {
            key: copy.deepcopy(value)
            for key, value in image.items()
            if key not in {"bufferView", "uri"}
        }
        new_image["bufferView"] = new_view_index
        if not new_image.get("mimeType"):
            raise RuntimeError("embedded donor image is missing mimeType")
        base_images = base_doc.setdefault("images", [])
        new_index = len(base_images)
        base_images.append(new_image)
        image_map[index] = new_index
        copied_images += 1
        return new_index

    def copy_sampler(index: int | None) -> int | None:
        nonlocal copied_samplers
        if index is None:
            return None
        index = int(index)
        if index in sampler_map:
            return sampler_map[index]
        if not (0 <= index < len(donor_samplers)):
            raise RuntimeError(f"donor sampler index out of range: {index}")
        base_samplers = base_doc.setdefault("samplers", [])
        new_index = len(base_samplers)
        base_samplers.append(copy.deepcopy(donor_samplers[index]))
        sampler_map[index] = new_index
        copied_samplers += 1
        return new_index

    def copy_texture(index: int) -> int:
        if index in texture_map:
            return texture_map[index]
        if not (0 <= index < len(donor_textures)):
            raise RuntimeError(f"donor texture index out of range: {index}")
        texture = copy.deepcopy(donor_textures[index])
        source_kind, source_index = _texture_source(texture)
        new_image = copy_image(source_index)
        if source_kind == "source":
            texture["source"] = new_image
        else:
            texture.pop("source", None)
            ext = texture.setdefault("extensions", {})
            ext.setdefault("KHR_texture_basisu", {})["source"] = new_image

        sampler = texture.get("sampler")
        if sampler is not None:
            texture["sampler"] = copy_sampler(int(sampler))
        base_textures = base_doc.setdefault("textures", [])
        new_index = len(base_textures)
        base_textures.append(texture)
        texture_map[index] = new_index
        return new_index

    material = copy.deepcopy(source_material)

    def remap(info):
        if isinstance(info, dict) and isinstance(info.get("index"), int):
            info["index"] = copy_texture(int(info["index"]))

    pbr = material.get("pbrMetallicRoughness") or {}
    remap(pbr.get("baseColorTexture"))
    remap(pbr.get("metallicRoughnessTexture"))
    remap(material.get("normalTexture"))
    remap(material.get("occlusionTexture"))
    remap(material.get("emissiveTexture"))

    base_materials = base_doc.setdefault("materials", [])
    new_material_index = len(base_materials)
    base_materials.append(material)
    return {
        "material_index": new_material_index,
        "images": copied_images,
        "textures": len(texture_map),
        "samplers": copied_samplers,
        "channels": _material_channels(source_material),
        "has_normal_map": isinstance(
            source_material.get("normalTexture"),
            dict,
        ),
    }


def _generate_tangents(positions, normals, uvs, faces):
    np = _deps()
    positions = np.asarray(positions, dtype=np.float64)
    normals = np.asarray(normals, dtype=np.float64)
    uvs = np.asarray(uvs, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    tan1 = np.zeros((len(positions), 3), dtype=np.float64)
    tan2 = np.zeros((len(positions), 3), dtype=np.float64)

    for tri in faces:
        i1, i2, i3 = (int(x) for x in tri)
        p1, p2, p3 = positions[[i1, i2, i3]]
        w1, w2, w3 = uvs[[i1, i2, i3]]
        x1 = p2 - p1
        x2 = p3 - p1
        s1, t1 = w2 - w1
        s2, t2 = w3 - w1
        denom = s1 * t2 - s2 * t1
        if abs(float(denom)) <= 1e-12:
            raise RuntimeError("donor accessory UVs contain degenerate triangles")
        r = 1.0 / float(denom)
        sdir = (x1 * t2 - x2 * t1) * r
        tdir = (x2 * s1 - x1 * s2) * r
        for idx in (i1, i2, i3):
            tan1[idx] += sdir
            tan2[idx] += tdir

    out = np.zeros((len(positions), 4), dtype=np.float64)
    for index in range(len(positions)):
        n = normals[index]
        t = tan1[index]
        n_norm = max(float(np.linalg.norm(n)), 1e-12)
        n = n / n_norm
        t = t - n * float(np.dot(n, t))
        t_norm = float(np.linalg.norm(t))
        if t_norm <= 1e-10:
            raise RuntimeError(
                f"cannot derive stable tangent for accessory vertex {index}"
            )
        t = t / t_norm
        handedness = (
            -1.0
            if float(np.dot(np.cross(n, t), tan2[index])) < 0.0
            else 1.0
        )
        out[index, :3] = t
        out[index, 3] = handedness
    return out


def accessory_material_transfer_supported(
    donor_mesh: Path,
    *,
    up_axis: str = "y",
) -> tuple[bool, str | None]:
    try:
        donor_doc, donor_binary, component = _find_accessory_component(
            donor_mesh,
            up_axis=up_axis,
        )
        primitive = component["primitive"]
        attrs = primitive.get("attributes") or {}
        material_index = primitive.get("material")
        if not isinstance(material_index, int):
            raise RuntimeError(
                "donor accessory primitive has no explicit material"
            )
        if not isinstance(attrs.get("TEXCOORD_0"), int):
            raise RuntimeError(
                "donor accessory primitive has no TEXCOORD_0"
            )
        materials = donor_doc.get("materials") or []
        material = materials[int(material_index)]
        if not _material_basecolor_texture(material):
            raise RuntimeError(
                "donor accessory material has no baseColor texture"
            )
        # Dry-run texture/image dependency validation.
        scratch_doc = {"bufferViews": []}
        scratch_blob = bytearray()
        _copy_material_bundle(
            donor_doc,
            donor_binary,
            scratch_doc,
            scratch_blob,
            int(material_index),
        )
        return True, None
    except Exception as exc:
        primary = f"{type(exc).__name__}:{exc}"
        try:
            from accessory_split_material_bind import (
                split_material_bind_supported,
            )
            split_ready, split_blocker = split_material_bind_supported(
                donor_mesh,
                up_axis=up_axis,
            )
            if split_ready:
                return True, None
            return False, (
                primary
                + " | split_material="
                + str(split_blocker or "unsupported")
            )
        except Exception as split_exc:
            return False, (
                primary
                + " | split_material="
                + f"{type(split_exc).__name__}:{split_exc}"
            )


def transfer_accessory_material(
    donor_mesh: Path,
    inserted_mesh: Path,
    output_glb: Path,
    *,
    donor_up_axis: str = "y",
) -> AccessoryMaterialTransferResult:
    np = _deps()
    warnings: list[str] = []
    errors: list[str] = []
    try:
        try:
            donor_doc, donor_binary, component = _find_accessory_component(
                donor_mesh,
                up_axis=donor_up_axis,
            )
        except Exception as primary_exc:
            from accessory_split_material_bind import (
                bind_split_accessory_materials,
            )
            split = bind_split_accessory_materials(
                donor_mesh,
                inserted_mesh,
                output_glb,
                donor_up_axis=donor_up_axis,
            )
            if not split.ready:
                split.errors.insert(
                    0,
                    "shared_atlas_material_path:"
                    + f"{type(primary_exc).__name__}:{primary_exc}",
                )
            return split

        primitive = component["primitive"]
        attrs = primitive.get("attributes") or {}
        material_index = primitive.get("material")
        uv_index = attrs.get("TEXCOORD_0")
        if not isinstance(material_index, int):
            raise RuntimeError(
                "donor accessory primitive has no explicit material"
            )
        if not isinstance(uv_index, int):
            raise RuntimeError(
                "donor accessory primitive has no TEXCOORD_0"
            )

        from skin_weight_qa import _read_accessor
        donor_uvs_all = np.asarray(
            _read_accessor(donor_doc, donor_binary, int(uv_index)),
            dtype=np.float64,
        )
        used = np.asarray(component["used_vertex_ids"], dtype=np.int64)
        donor_uvs = donor_uvs_all[used]
        if (
            donor_uvs.ndim != 2
            or donor_uvs.shape[1] != 2
            or not np.isfinite(donor_uvs).all()
        ):
            raise RuntimeError(
                "donor accessory TEXCOORD_0 is invalid"
            )

        from glb_images import read_glb, write_glb
        from skin_weight_qa import _read_accessor as read_accessor
        base_doc, base_binary = read_glb(inserted_mesh)
        doc = copy.deepcopy(base_doc)
        blob = bytearray(base_binary)

        skinned_nodes = [
            node
            for node in doc.get("nodes") or []
            if isinstance(node.get("mesh"), int)
            and isinstance(node.get("skin"), int)
        ]
        if len(skinned_nodes) != 1:
            raise RuntimeError(
                "material transfer requires exactly one skinned mesh node"
            )
        mesh_index = int(skinned_nodes[0]["mesh"])
        mesh = (doc.get("meshes") or [])[mesh_index]
        primitives = mesh.get("primitives") or []
        if len(primitives) < 2:
            raise RuntimeError(
                "inserted GLB has no appended accessory primitive"
            )
        inserted_primitive_index = len(primitives) - 1
        inserted = primitives[inserted_primitive_index]
        inserted_attrs = inserted.setdefault("attributes", {})
        position_index = inserted_attrs.get("POSITION")
        normal_index = inserted_attrs.get("NORMAL")
        if not isinstance(position_index, int) or not isinstance(normal_index, int):
            raise RuntimeError(
                "inserted accessory primitive is missing POSITION/NORMAL"
            )
        positions = np.asarray(
            read_accessor(doc, bytes(blob), int(position_index)),
            dtype=np.float64,
        )
        normals = np.asarray(
            read_accessor(doc, bytes(blob), int(normal_index)),
            dtype=np.float64,
        )
        if len(donor_uvs) != len(positions):
            raise RuntimeError(
                "donor accessory UV vertex count does not match inserted geometry: "
                f"{len(donor_uvs)}!={len(positions)}"
            )

        from rigged_accessory_insert import _append_accessor
        uv_accessor = _append_accessor(
            doc,
            blob,
            np.asarray(donor_uvs, dtype="<f4").tobytes(),
            component_type=5126,
            count=len(donor_uvs),
            accessor_type="VEC2",
        )
        inserted_attrs["TEXCOORD_0"] = uv_accessor

        bundle = _copy_material_bundle(
            donor_doc,
            donor_binary,
            doc,
            blob,
            int(material_index),
        )
        inserted["material"] = int(bundle["material_index"])

        tangent_generated = False
        if bundle["has_normal_map"]:
            index_accessor = inserted.get("indices")
            if not isinstance(index_accessor, int):
                raise RuntimeError(
                    "inserted accessory primitive has no indices for tangent generation"
                )
            raw = np.asarray(
                read_accessor(doc, bytes(blob), int(index_accessor)),
                dtype=np.int64,
            ).reshape(-1)
            if len(raw) % 3:
                raise RuntimeError(
                    "inserted accessory index count is not divisible by three"
                )
            faces = raw.reshape((-1, 3))
            tangents = _generate_tangents(
                positions,
                normals,
                donor_uvs,
                faces,
            )
            tangent_accessor = _append_accessor(
                doc,
                blob,
                np.asarray(tangents, dtype="<f4").tobytes(),
                component_type=5126,
                count=len(tangents),
                accessor_type="VEC4",
            )
            inserted_attrs["TANGENT"] = tangent_accessor
            tangent_generated = True

        write_glb(output_glb, doc, bytes(blob))

        from uv_tangent_qa import audit_uv_tangents
        uv = audit_uv_tangents(output_glb)
        uv_ready = bool(uv.applicable and uv.ready)
        warnings.extend(uv.warnings or [])
        if not uv_ready:
            errors.append("UV/tangent QA failed after accessory material transfer")
            errors.extend(uv.errors or [])

        from shading_basis_qa import audit_shading_basis
        shading = audit_shading_basis(output_glb)
        shading_ready = bool(shading.applicable and shading.ready)
        warnings.extend(shading.warnings or [])
        if not shading_ready:
            errors.append(
                "shading-basis QA failed after accessory material transfer"
            )
            errors.extend(shading.errors or [])

        from texture_gate import embedded_images
        images = embedded_images(output_glb)
        if not images:
            errors.append(
                "material transfer produced no embedded image evidence"
            )

        return AccessoryMaterialTransferResult(
            donor_mesh=str(donor_mesh),
            inserted_mesh=str(inserted_mesh),
            output_glb=str(output_glb),
            attempted=True,
            ready=not errors,
            donor_component_id=int(component["candidate"].component_id),
            donor_component_ids=[
                int(x) for x in component.get(
                    "candidate_component_ids",
                    [component["candidate"].component_id],
                )
            ],
            donor_mesh_index=int(component["mesh_index"]),
            donor_primitive_index=int(component["primitive_index"]),
            material_index=int(bundle["material_index"]),
            inserted_primitive_index=int(inserted_primitive_index),
            uv_vertices=int(len(donor_uvs)),
            copied_images=int(bundle["images"]),
            copied_textures=int(bundle["textures"]),
            copied_samplers=int(bundle["samplers"]),
            copied_channels=list(bundle["channels"]),
            tangent_generated=bool(tangent_generated),
            uv_tangent_ready=uv_ready,
            shading_basis_ready=shading_ready,
            warnings=warnings,
            errors=errors,
        )
    except Exception as exc:
        return AccessoryMaterialTransferResult(
            donor_mesh=str(donor_mesh),
            inserted_mesh=str(inserted_mesh),
            output_glb=str(output_glb),
            attempted=True,
            ready=False,
            donor_component_id=None,
            donor_component_ids=[],
            donor_mesh_index=None,
            donor_primitive_index=None,
            material_index=None,
            inserted_primitive_index=None,
            uv_vertices=0,
            copied_images=0,
            copied_textures=0,
            copied_samplers=0,
            copied_channels=[],
            tangent_generated=False,
            uv_tangent_ready=False,
            shading_basis_ready=False,
            warnings=warnings,
            errors=[f"{type(exc).__name__}:{exc}"],
        )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description=(
            "Transfer donor accessory UV/PBR material dependencies onto the "
            "new skinned accessory primitive without rewriting existing GLB payload."
        )
    )
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--inserted", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--up-axis", choices=["x", "y", "z"], default="y")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    result = transfer_accessory_material(
        args.donor,
        args.inserted,
        args.output,
        donor_up_axis=args.up_axis,
    )
    payload = json.dumps(asdict(result), indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")
    return 0 if result.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
