#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path


def split_material_bind_supported(
    donor_mesh: Path,
    *,
    up_axis: str = "y",
) -> tuple[bool, str | None]:
    try:
        from accessory_source_groups import audit_accessory_source_groups
        from accessory_material_transfer import _copy_material_bundle
        from gltf_position_patch import _doc_and_bin

        source = audit_accessory_source_groups(
            donor_mesh,
            mode="character",
            up_axis=up_axis,
        )
        if not source.ready:
            return False, ";".join(source.errors or ["source-group audit failed"])
        if source.group_count <= 1:
            return False, "donor does not require split material binding"

        doc, binary, _ = _doc_and_bin(donor_mesh)
        materials = doc.get("materials") or []
        meshes = doc.get("meshes") or []
        for group in source.groups:
            if not group.ready:
                return False, ";".join(group.blockers or ["source group not ready"])
            if not isinstance(group.material_index, int):
                return False, "source group has no material"
            if not isinstance(group.texcoord0_accessor, int):
                return False, "source group has no TEXCOORD_0"
            if not (0 <= int(group.material_index) < len(materials)):
                return False, "source group material index invalid"
            if not (0 <= int(group.mesh_index) < len(meshes)):
                return False, "source group mesh index invalid"
            primitives = meshes[int(group.mesh_index)].get("primitives") or []
            if not (0 <= int(group.primitive_index) < len(primitives)):
                return False, "source group primitive index invalid"
            scratch_doc = {"bufferViews": []}
            scratch_blob = bytearray()
            _copy_material_bundle(
                doc,
                binary,
                scratch_doc,
                scratch_blob,
                int(group.material_index),
            )
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"


def bind_split_accessory_materials(
    donor_mesh: Path,
    inserted_mesh: Path,
    output_glb: Path,
    *,
    donor_up_axis: str = "y",
):
    from accessory_material_transfer import AccessoryMaterialTransferResult

    warnings: list[str] = []
    errors: list[str] = []
    try:
        import numpy as np

        from accessory_source_groups import audit_accessory_source_groups
        from accessory_material_transfer import (
            _copy_material_bundle,
            _generate_tangents,
        )
        from glb_images import read_glb, write_glb
        from gltf_position_patch import _doc_and_bin
        from rigged_accessory_insert import _append_accessor
        from skin_weight_qa import _read_accessor

        source = audit_accessory_source_groups(
            donor_mesh,
            mode="character",
            up_axis=donor_up_axis,
        )
        if not source.ready or source.group_count <= 1:
            raise RuntimeError(
                "split material binding requires a ready multi-group donor"
            )

        donor_doc, donor_binary, _ = _doc_and_bin(donor_mesh)
        doc, binary = read_glb(inserted_mesh)
        doc = copy.deepcopy(doc)
        blob = bytearray(binary)

        groups = {
            (
                int(group.node_index),
                int(group.mesh_index),
                int(group.primitive_index),
            ): group
            for group in source.groups
        }

        split_primitives = []
        for mesh_index, mesh in enumerate(doc.get("meshes") or []):
            for primitive_index, primitive in enumerate(mesh.get("primitives") or []):
                extras = primitive.get("extras") or {}
                if not extras.get("hayuyaAccessorySplit"):
                    continue
                key = (
                    int(extras.get("hayuyaSourceNode", -1)),
                    int(extras.get("hayuyaSourceMesh", -1)),
                    int(extras.get("hayuyaSourcePrimitive", -1)),
                )
                split_primitives.append(
                    (mesh_index, primitive_index, primitive, key)
                )

        if len(split_primitives) != source.group_count:
            raise RuntimeError(
                "split inserted primitive count does not match donor source groups: "
                f"{len(split_primitives)}!={source.group_count}"
            )

        copied_images = 0
        copied_textures = 0
        copied_samplers = 0
        channels = set()
        tangent_generated = False
        uv_vertices = 0
        material_indices = []
        donor_component_ids = []

        donor_meshes = donor_doc.get("meshes") or []
        for mesh_index, primitive_index, primitive, key in split_primitives:
            group = groups.get(key)
            if group is None:
                raise RuntimeError(
                    "split primitive source identity has no matching donor group"
                )
            source_mesh = donor_meshes[int(group.mesh_index)]
            source_primitive = (
                source_mesh.get("primitives") or []
            )[int(group.primitive_index)]
            source_attrs = source_primitive.get("attributes") or {}
            uv_index = source_attrs.get("TEXCOORD_0")
            material_index = source_primitive.get("material")
            if not isinstance(uv_index, int) or not isinstance(material_index, int):
                raise RuntimeError(
                    "source group lost UV/material binding"
                )

            donor_uv_all = np.asarray(
                _read_accessor(donor_doc, donor_binary, uv_index),
                dtype=np.float64,
            )
            used = np.asarray(group.used_vertex_ids, dtype=np.int64)
            donor_uv = donor_uv_all[used]
            if (
                donor_uv.ndim != 2
                or donor_uv.shape[1] != 2
                or not np.isfinite(donor_uv).all()
            ):
                raise RuntimeError("source group UV payload is invalid")

            attrs = primitive.setdefault("attributes", {})
            pos_index = attrs.get("POSITION")
            normal_index = attrs.get("NORMAL")
            index_index = primitive.get("indices")
            if not all(isinstance(x, int) for x in (
                pos_index, normal_index, index_index
            )):
                raise RuntimeError(
                    "split inserted primitive lacks POSITION/NORMAL/indices"
                )
            positions = np.asarray(
                _read_accessor(doc, bytes(blob), int(pos_index)),
                dtype=np.float64,
            )
            normals = np.asarray(
                _read_accessor(doc, bytes(blob), int(normal_index)),
                dtype=np.float64,
            )
            raw = np.asarray(
                _read_accessor(doc, bytes(blob), int(index_index)),
                dtype=np.int64,
            ).reshape(-1)
            if len(raw) % 3:
                raise RuntimeError(
                    "split inserted primitive index count is not triangle-aligned"
                )
            faces = raw.reshape((-1, 3))
            if len(donor_uv) != len(positions):
                raise RuntimeError(
                    "source group UV vertex count does not match split primitive: "
                    f"{len(donor_uv)}!={len(positions)}"
                )

            uv_accessor = _append_accessor(
                doc,
                blob,
                np.asarray(donor_uv, dtype="<f4").tobytes(),
                component_type=5126,
                count=len(donor_uv),
                accessor_type="VEC2",
            )
            attrs["TEXCOORD_0"] = uv_accessor

            bundle = _copy_material_bundle(
                donor_doc,
                donor_binary,
                doc,
                blob,
                int(material_index),
            )
            primitive["material"] = int(bundle["material_index"])
            material_indices.append(int(bundle["material_index"]))

            if bundle["has_normal_map"]:
                tangents = _generate_tangents(
                    positions,
                    normals,
                    donor_uv,
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
                attrs["TANGENT"] = tangent_accessor
                tangent_generated = True

            copied_images += int(bundle["images"])
            copied_textures += int(bundle["textures"])
            copied_samplers += int(bundle["samplers"])
            channels.update(bundle["channels"])
            uv_vertices += int(len(donor_uv))
            donor_component_ids.extend(
                int(x) for x in group.candidate_component_ids
            )

        write_glb(output_glb, doc, bytes(blob))

        from uv_tangent_qa import audit_uv_tangents
        from shading_basis_qa import audit_shading_basis
        from texture_gate import embedded_images

        uv = audit_uv_tangents(output_glb)
        shading = audit_shading_basis(output_glb)
        uv_ready = bool(uv.applicable and uv.ready)
        shading_ready = bool(shading.applicable and shading.ready)
        warnings.extend(uv.warnings or [])
        warnings.extend(shading.warnings or [])
        if not uv_ready:
            errors.append(
                "UV/tangent QA failed after direct split material binding"
            )
            errors.extend(uv.errors or [])
        if not shading_ready:
            errors.append(
                "shading-basis QA failed after direct split material binding"
            )
            errors.extend(shading.errors or [])
        if not embedded_images(output_glb):
            errors.append(
                "direct split material binding produced no embedded images"
            )

        donor_component_ids = sorted(set(donor_component_ids))
        first_mesh, first_primitive, _, first_key = split_primitives[0]
        return AccessoryMaterialTransferResult(
            donor_mesh=str(donor_mesh),
            inserted_mesh=str(inserted_mesh),
            output_glb=str(output_glb),
            attempted=True,
            ready=not errors,
            donor_component_id=(
                donor_component_ids[0] if donor_component_ids else None
            ),
            donor_component_ids=donor_component_ids,
            donor_mesh_index=int(first_key[1]),
            donor_primitive_index=int(first_key[2]),
            material_index=(material_indices[0] if material_indices else None),
            inserted_primitive_index=int(first_primitive),
            uv_vertices=int(uv_vertices),
            copied_images=int(copied_images),
            copied_textures=int(copied_textures),
            copied_samplers=int(copied_samplers),
            copied_channels=sorted(channels),
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
