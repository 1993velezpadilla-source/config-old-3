#!/usr/bin/env python3
"""Losslessly source-locked, geometry-preserving Tripo glTF quantization conversion.

Godot 4.6 cannot import KHR_mesh_quantization. The original GLBs are SHA-256
checked first. Only staged rendering copies are dequantized to float32, with
external shared 4K PBR textures preserved byte-for-byte across models.
No new geometry, mesh synthesis, stock substitutes, or polygon decimation.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Mapping
import io
import json

import trimesh


def convert_quantized_tripo_glb(
    source_glb: bytes, source_pbr: Mapping[str, bytes],
    output_dir: Path, stem: str,
) -> Path:
    original_scene = trimesh.load(
        io.BytesIO(source_glb), file_type="glb", force="scene",
        process=False, resolver=dict(source_pbr),
    )
    original_faces = sum(len(mesh.faces) for mesh in original_scene.geometry.values())
    if original_faces <= 0:
        raise RuntimeError("TRIPO_SOURCE_GLTF_NO_GEOMETRY " + stem)

    exported = trimesh.exchange.gltf.export_gltf(
        original_scene, include_normals=True, merge_buffers=False
    )
    document = json.loads(exported["model.gltf"])
    if document.get("extensionsRequired"):
        raise RuntimeError("TRIPO_GODOT_UNSUPPORTED_REQUIRED_EXTENSION " + stem)
    images = document.get("images", [])

    def externalize(tex_index: int, original_prefix: str) -> None:
        index = document["textures"][tex_index]["source"]
        matched = [name for name in source_pbr
                   if Path(name).name.casefold().startswith(original_prefix.casefold())]
        if len(matched) != 1:
            raise RuntimeError("TRIPO_PBR_SOURCE_AMBIGUOUS " + stem + " " + original_prefix)
        images[index] = {"uri": matched[0]}

    for material in document.get("materials", []):
        pbr = material.get("pbrMetallicRoughness", {})
        if "baseColorTexture" in pbr:
            externalize(pbr["baseColorTexture"]["index"], "Color_")
        if "metallicRoughnessTexture" in pbr:
            externalize(pbr["metallicRoughnessTexture"]["index"], "ORM_")
        if "normalTexture" in material:
            externalize(material["normalTexture"]["index"], "NormalGL_")
    if any("bufferView" in image for image in images):
        raise RuntimeError("TRIPO_PBR_NOT_EXTERNALIZED " + stem)

    # Retain only geometry buffers, discard image copies from export buffers.
    views = document["bufferViews"]
    buffers = document["buffers"]
    used_views = sorted(set(accessor["bufferView"] for accessor in document["accessors"]
                            if "bufferView" in accessor))
    used_buffers = sorted(set(views[idx]["buffer"] for idx in used_views))
    view_map = {idx: new for new, idx in enumerate(used_views)}
    buffer_map = {idx: new for new, idx in enumerate(used_buffers)}
    document["bufferViews"] = [
        dict(views[idx], buffer=buffer_map[views[idx]["buffer"]])
        for idx in used_views
    ]
    for accessor in document["accessors"]:
        if "bufferView" in accessor:
            accessor["bufferView"] = view_map[accessor["bufferView"]]
        if accessor["componentType"] not in (5125, 5126, 5123, 5121):
            raise RuntimeError("TRIPO_DEQUANTIZATION_COMPONENT_RED " + stem)
    document["buffers"] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for index in used_buffers:
        original_uri = buffers[index]["uri"]
        new_uri = f"{stem}_{original_uri}"
        payload = exported[original_uri]
        (output_dir / new_uri).write_bytes(payload)
        document["buffers"].append({"uri": new_uri, "byteLength": len(payload)})
    for filename, original_image in source_pbr.items():
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("TRIPO_PBR_UNSAFE_RELATIVE_PATH " + filename)
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and sha256(destination.read_bytes()).digest() != sha256(original_image).digest():
            raise RuntimeError("TRIPO_ORIGINAL_SHARED_PBR_MISMATCH " + filename)
        if not destination.exists():
            destination.write_bytes(original_image)
    target = output_dir / (stem + ".gltf")
    target.write_text(json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8")

    # Verify topology survives the conversion; retains original authored mesh.
    converted = trimesh.load(target, force="scene", process=False)
    converted_faces = sum(len(mesh.faces) for mesh in converted.geometry.values())
    if converted_faces != original_faces:
        raise RuntimeError(
            f"TRIPO_DEQUANTIZED_TRIANGLE_COUNT_RED {stem} "
            f"{converted_faces}!={original_faces}"
        )
    print("TRIPO_OWNER_GLTF_QUANTIZATION_DECODED", stem, original_faces, "triangles")
    return target
