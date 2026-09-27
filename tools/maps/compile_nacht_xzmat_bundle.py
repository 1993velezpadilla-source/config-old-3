#!/usr/bin/env python3
"""Build XZIEL's static-scene material pack for BO3 Nacht.

XZMT v1 keeps geometry (XZMS) stable while adding one global base-color texture
table plus one texture binding per static-scene submesh. Textures come from the
full-resolution XZTX decode manifest produced in CI and are downsampled only for
this first Android runtime residency tier; source XZTX remains untouched.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import struct

MAGIC = b"XZMT"
VERSION = 1
HEADER = struct.Struct("<4sIIIII")
TEXTURE = struct.Struct("<IIIII")
NO_TEXTURE = 0xFFFFFFFF
EXPECTED_MESHES = 492
EXPECTED_SUBMESHES = 1063
XZTX_HEADER = struct.Struct("<4sIIIII")


def parse_glb_json(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError(f"GLB too small: {path}")
    magic, version, declared = struct.unpack_from("<III", raw, 0)
    if magic != 0x46546C67 or version != 2 or declared != len(raw):
        raise ValueError(f"invalid GLB: {path}")
    off = 12
    while off + 8 <= len(raw):
        length, kind = struct.unpack_from("<II", raw, off)
        off += 8
        chunk = raw[off:off + length]
        off += length
        if kind == 0x4E4F534A:
            return json.loads(chunk.rstrip(b" \t\r\n\x00").decode("utf-8"))
    raise ValueError(f"GLB JSON missing: {path}")


def primitive_material_indices(doc: dict) -> list[int]:
    nodes = doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    scenes = doc.get("scenes", [])
    scene_index = int(doc.get("scene", 0) or 0)
    roots = (
        scenes[scene_index].get("nodes", [])
        if scenes and 0 <= scene_index < len(scenes)
        else list(range(len(nodes)))
    )
    out: list[int] = []

    def visit(index: int) -> None:
        if not isinstance(index, int) or not (0 <= index < len(nodes)):
            raise ValueError(f"invalid node {index}")
        node = nodes[index]
        mesh_index = node.get("mesh")
        if isinstance(mesh_index, int):
            if not (0 <= mesh_index < len(meshes)):
                raise ValueError(f"invalid mesh {mesh_index}")
            for primitive in meshes[mesh_index].get("primitives", []):
                material = primitive.get("material")
                out.append(int(material) if isinstance(material, int) else NO_TEXTURE)
        for child in node.get("children", []):
            visit(child)

    for root in roots:
        visit(root)
    return out


def canonical(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "", (value or "").lower())
    if value.endswith("mat"):
        value = value[:-3]
    return value


def binding_score(row: dict) -> int:
    source = str(row.get("source", "")).lower()
    name = str(row.get("textureName", "")).lower()
    score = 0

    if "albedotexture" in source:
        score += 10000
    elif "basecolor" in source or "diffuse" in source:
        score += 9000
    elif "albedo" in source or "color" in source:
        score += 7500

    if "diffuse" in name or "albedo" in name or "basecolor" in name:
        score += 5000
    if re.search(r"(?:^|_)c$", name):
        score += 4200
    if re.search(r"(?:^|_)d$", name):
        score += 3600

    # Cooked texture streaming can preserve the exact authored texture even
    # when semantic parameter names are stripped. Prefer an exact
    # material-name/texture-name match (e.g. Atlas_39246_Mat -> Atlas_39246).
    material_name = str(row.get("materialName", "")).lower()
    if canonical(name) and canonical(name) == canonical(material_name):
        score += 8000

    # The Nacht muddy-water material serializes a neutral White base texture
    # plus an explicitly named NormalTexture. The runtime's current XZMT tier
    # is base-color only, so select White only for water materials; keeping
    # this scoped avoids overriding authored vector/alias fallbacks elsewhere.
    if (
        source.startswith("streaming:")
        and name == "white"
        and "water" in material_name
    ):
        score += 500

    negative = (
        "normal", "_n", "mrs", "rough", "metal", "spec",
        "opacity", "mask", "_ao", "ambientocclusion",
    )
    if any(token in name for token in negative):
        score -= 6000
    if "normaltexture" in source:
        score -= 10000

    # Explicit material semantics beat filename heuristics, e.g. some blood
    # albedo textures end in _r.
    if "albedotexture" in source:
        score += 7000

    return score


def vector_binding_score(row: dict) -> int:
    """Rank only vector parameters that plausibly represent surface base color."""
    name = re.sub(
        r"[^a-z0-9]+",
        "",
        str(row.get("parameter", "")).lower(),
    )
    if not name:
        return -10000

    rejected = (
        "emissive", "emission", "normal", "rough", "metal",
        "specular", "opacity", "alphatest", "mask", "fresnel",
        "subsurface", "uv", "coordinate",
    )
    if any(token in name for token in rejected):
        return -10000

    score = 0
    exact = {
        "basecolor", "basecolour", "albedocolor", "albedocolour",
        "diffusecolor", "diffusecolour", "blendcolor", "blendcolour",
        "colortint", "colourtint", "basetint",
    }
    if name in exact:
        score += 12000
    if "base" in name and ("color" in name or "colour" in name):
        score += 10000
    if "albedo" in name:
        score += 9000
    if "diffuse" in name:
        score += 8500
    if "tint" in name:
        score += 8000
    if "color" in name or "colour" in name:
        score += 5000
    return score


def vector_rgba(row: dict) -> bytes:
    def component(key: str, default: float) -> int:
        raw = str(row.get(key, "")).strip()
        try:
            value = float(raw) if raw else default
        except ValueError:
            value = default
        if not math.isfinite(value):
            value = default
        value = min(1.0, max(0.0, value))
        return int(round(value * 255.0))

    return bytes((
        component("r", 1.0),
        component("g", 1.0),
        component("b", 1.0),
        # Unreal material color vectors frequently leave A at zero even when
        # alpha is not part of the shader path. Constant-color fallbacks are
        # therefore opaque; true invisibility is handled explicitly above.
        255,
    ))


def glb_base_color_rgba(material: dict) -> bytes | None:
    """Return an explicitly exported glTF baseColorFactor as RGBA8."""
    if not isinstance(material, dict):
        return None
    pbr = material.get("pbrMetallicRoughness")
    if not isinstance(pbr, dict) or "baseColorFactor" not in pbr:
        return None
    factor = pbr.get("baseColorFactor")
    if not isinstance(factor, list) or len(factor) < 3:
        return None

    values = list(factor[:4])
    while len(values) < 4:
        values.append(1.0)

    out = []
    for raw in values:
        if not isinstance(raw, (int, float)):
            return None
        value = float(raw)
        if not math.isfinite(value):
            return None
        value = min(1.0, max(0.0, value))
        out.append(int(round(value * 255.0)))
    return bytes(out)


def material_object_name(material_path: str) -> str:
    tail = str(material_path).replace("\\", "/").rsplit("/", 1)[-1]
    return tail.split(".", 1)[0].lower()


def is_global_invisible(material_path: str) -> bool:
    return material_object_name(material_path) == "global_invisible"


def read_xzt_header(path: Path) -> tuple[int, int, int, int]:
    raw = path.read_bytes()[:XZTX_HEADER.size]
    if len(raw) != XZTX_HEADER.size:
        raise ValueError(f"truncated XZTX: {path}")
    magic, version, width, height, fmt, data_bytes = XZTX_HEADER.unpack(raw)
    if magic != b"XZTX" or version != 1 or fmt != 1:
        raise ValueError(f"unsupported XZTX: {path}")
    if width <= 0 or height <= 0 or data_bytes != width * height * 4:
        raise ValueError(f"invalid XZTX dimensions: {path}")
    return width, height, fmt, data_bytes


def read_xzt_rgba(path: Path) -> tuple[int, int, bytes]:
    raw = path.read_bytes()
    if len(raw) < XZTX_HEADER.size:
        raise ValueError(f"truncated XZTX: {path}")
    magic, version, width, height, fmt, data_bytes = XZTX_HEADER.unpack_from(raw, 0)
    if magic != b"XZTX" or version != 1 or fmt != 1:
        raise ValueError(f"unsupported XZTX: {path}")
    rgba = raw[XZTX_HEADER.size:]
    if len(rgba) != data_bytes or data_bytes != width * height * 4:
        raise ValueError(f"XZTX payload mismatch: {path}")
    return width, height, rgba


def runtime_size(width: int, height: int, max_dimension: int) -> tuple[int, int]:
    longest = max(width, height)
    if longest <= max_dimension:
        return width, height
    scale = max_dimension / float(longest)
    return max(1, round(width * scale)), max(1, round(height * scale))


def resize_nearest_rgba(
    rgba: bytes,
    width: int,
    height: int,
    out_width: int,
    out_height: int,
) -> bytes:
    if width == out_width and height == out_height:
        return rgba

    xmap = [min(width - 1, (x * width) // out_width) * 4 for x in range(out_width)]
    out = bytearray(out_width * out_height * 4)
    dst = 0
    src_view = memoryview(rgba)

    for y in range(out_height):
        sy = min(height - 1, (y * height) // out_height)
        row = sy * width * 4
        for sx4 in xmap:
            at = row + sx4
            out[dst:dst + 4] = src_view[at:at + 4]
            dst += 4

    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", type=Path, required=True)
    ap.add_argument("--glb-root", type=Path, required=True)
    ap.add_argument("--texture-manifest", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--max-dimension", type=int, default=256)
    args = ap.parse_args()

    assets = json.loads(args.assets.read_text(encoding="utf-8"))
    rows = assets.get("meshes", [])
    if assets.get("uniqueMeshCount") != EXPECTED_MESHES or len(rows) != EXPECTED_MESHES:
        raise SystemExit(f"expected {EXPECTED_MESHES} mesh references")

    manifest = json.loads(args.texture_manifest.read_text(encoding="utf-8"))
    texture_rows = manifest.get("textures", [])
    binding_rows = manifest.get("bindings", [])
    mesh_material_rows = manifest.get("meshMaterials", [])
    vector_rows = manifest.get("materialVectors", [])
    if not texture_rows or not binding_rows or not mesh_material_rows:
        raise SystemExit("texture manifest missing textures/bindings/meshMaterials")

    # A proxy material can appear on multiple meshes while only one original
    # slot name resolves back to its authored material. Reuse that alias only
    # when all observed aliases for the proxy collapse to one exact path.
    alias_candidates_by_material: dict[str, set[str]] = {}
    for row in mesh_material_rows:
        material_path = str(row.get("materialPath", "")).lower()
        alias_path = str(row.get("slotAliasMaterialPath", "")).lower()
        if material_path and alias_path:
            alias_candidates_by_material.setdefault(
                material_path, set()
            ).add(alias_path)

    unique_alias_by_material = {
        material_path: next(iter(alias_paths))
        for material_path, alias_paths in alias_candidates_by_material.items()
        if len(alias_paths) == 1
    }

    textures_by_path = {
        str(row["texturePath"]).lower(): row
        for row in texture_rows
    }

    bindings_by_material: dict[str, list[dict]] = {}
    for row in binding_rows:
        key = str(row.get("materialPath", "")).lower()
        if key:
            bindings_by_material.setdefault(key, []).append(row)

    selected_by_material: dict[str, str] = {}
    for material_path, candidates in bindings_by_material.items():
        ranked = sorted(candidates, key=binding_score, reverse=True)
        if ranked and binding_score(ranked[0]) > 0:
            selected_by_material[material_path] = str(ranked[0]["texturePath"]).lower()

    vectors_by_material: dict[str, list[dict]] = {}
    for row in vector_rows:
        key = str(row.get("materialPath", "")).lower()
        if key:
            vectors_by_material.setdefault(key, []).append(row)

    material_paths = {
        str(row.get("materialPath", "")).lower()
        for row in mesh_material_rows
        if str(row.get("materialPath", "")).strip()
    }

    synthetic_textures: dict[str, dict] = {}
    synthetic_by_material: dict[str, str] = {}

    # global_invisible is helper geometry, not a visible gray surface. A
    # transparent 1x1 texture makes the existing GLES shader discard it while
    # keeping XZMT v1 and the runtime material ABI unchanged.
    for material_path in sorted(material_paths):
        if not is_global_invisible(material_path):
            continue
        key = f"synthetic://invisible/{material_path}"
        synthetic_textures[key] = {
            "kind": "global_invisible",
            "materialPath": material_path,
            "parameter": "",
            "rgba": bytes((0, 0, 0, 0)),
        }
        synthetic_by_material[material_path] = key

    # If a material genuinely has no usable base-color texture, preserve its
    # authored constant BaseColor/Tint vector instead of rendering flat gray.
    for material_path, candidates in vectors_by_material.items():
        if (
            material_path in synthetic_by_material
            or material_path in selected_by_material
        ):
            continue
        ranked = sorted(candidates, key=vector_binding_score, reverse=True)
        if not ranked or vector_binding_score(ranked[0]) <= 0:
            continue
        selected = ranked[0]
        key = f"synthetic://vector/{material_path}"
        synthetic_textures[key] = {
            "kind": "vector_color",
            "materialPath": material_path,
            "parameter": str(selected.get("parameter", "")),
            "rgba": vector_rgba(selected),
        }
        synthetic_by_material[material_path] = key

    # Final deterministic fallback for cooked UE4 TextureStreamingData.
    # Only touch materials that are STILL unresolved after explicit texture
    # semantics and constant-color fallbacks. This preserves all existing
    # mappings. Reject obvious normal/mask/roughness maps. Prefer an exact
    # canonical material-name match; otherwise accept a single remaining
    # non-normal streaming texture (e.g. shader-default White on water).
    streaming_fallback_bindings = 0
    streaming_rejected_tokens = (
        "normal", "_n", "mrs", "rough", "metal", "spec",
        "opacity", "mask", "_ao", "ambientocclusion",
    )
    for material_path, candidates in bindings_by_material.items():
        if (
            material_path in selected_by_material
            or material_path in synthetic_by_material
        ):
            continue

        streaming_candidates = []
        for row in candidates:
            source = str(row.get("source", "")).lower()
            name = str(row.get("textureName", "")).lower()
            if not source.startswith("streaming:"):
                continue
            if any(token in name for token in streaming_rejected_tokens):
                continue
            texture_path = str(row.get("texturePath", "")).lower()
            if texture_path not in textures_by_path:
                continue
            streaming_candidates.append(row)

        if not streaming_candidates:
            continue

        exact_name_matches = [
            row for row in streaming_candidates
            if (
                canonical(str(row.get("textureName", "")))
                == canonical(str(row.get("materialName", "")))
            )
        ]

        selected = None
        if len(exact_name_matches) == 1:
            selected = exact_name_matches[0]
        elif len(streaming_candidates) == 1:
            selected = streaming_candidates[0]

        if selected is None:
            continue

        selected_by_material[material_path] = str(
            selected["texturePath"]
        ).lower()
        streaming_fallback_bindings += 1

    mesh_slots: dict[str, list[dict]] = {}
    for row in mesh_material_rows:
        mesh_slots.setdefault(str(row["meshName"]).lower(), []).append(row)

    glbs: dict[str, Path] = {}
    for p in args.glb_root.rglob("*.glb"):
        key = p.stem.lower()
        if key in glbs:
            raise SystemExit(f"duplicate GLB stem {p.stem}")
        glbs[key] = p

    unresolved_slots: list[dict] = []
    raw_binding_texture_paths: list[str | None] = []
    mesh_reports = []

    for asset in rows:
        mesh_name = str(asset["sourcePath"]).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        glb = glbs.get(mesh_name.lower())
        if glb is None:
            raise SystemExit(f"missing GLB for {mesh_name}")

        doc = parse_glb_json(glb)
        materials = doc.get("materials", [])
        primitive_materials = primitive_material_indices(doc)
        slots = mesh_slots.get(mesh_name.lower(), [])

        by_exact: dict[str, dict] = {}
        by_canon: dict[str, list[dict]] = {}
        by_index: dict[int, dict] = {}
        for slot in slots:
            try:
                slot_index = int(slot.get("slotIndex", -1))
            except (TypeError, ValueError):
                slot_index = -1
            if slot_index >= 0:
                by_index.setdefault(slot_index, slot)

            names = {
                str(slot.get("slotName", "")),
                str(slot.get("materialSlotName", "")),
                str(slot.get("importedSlotName", "")),
            }
            for name in names:
                if not name:
                    continue
                by_exact.setdefault(name.lower(), slot)
                by_canon.setdefault(canonical(name), []).append(slot)

        mapped = 0
        for local_material in primitive_materials:
            material_name = ""
            if local_material != NO_TEXTURE and 0 <= local_material < len(materials):
                material_name = str(materials[local_material].get("name", ""))

            slot = by_exact.get(material_name.lower())
            if slot is None and material_name:
                candidates = by_canon.get(canonical(material_name), [])
                if len(candidates) == 1:
                    slot = candidates[0]

            # CUE4Parse/glTF may rename a material while preserving its
            # original slot ordering. Only use index fallback when both sides
            # expose the same material count, which makes the correspondence
            # unambiguous and avoids guessing across reordered multi-slot meshes.
            if (
                slot is None
                and local_material != NO_TEXTURE
                and len(slots) == len(materials)
            ):
                slot = by_index.get(local_material)

            texture_path: str | None = None
            material_path = ""
            alias_material_path = ""
            if slot is not None:
                material_path = str(slot.get("materialPath", "")).lower()
                alias_material_path = str(
                    slot.get("slotAliasMaterialPath", "")
                ).lower()
                if not alias_material_path:
                    alias_material_path = unique_alias_by_material.get(
                        material_path, ""
                    )
                synthetic_path = synthetic_by_material.get(material_path)

                # Invisible helper geometry wins over any inherited texture.
                # Otherwise prefer authored real albedo on the actual material,
                # then an exact original-slot material alias, then vector color.
                if (
                    synthetic_path
                    and synthetic_textures[synthetic_path]["kind"]
                    == "global_invisible"
                ):
                    texture_path = synthetic_path
                else:
                    texture_path = selected_by_material.get(material_path)
                    if texture_path is None and alias_material_path:
                        texture_path = (
                            selected_by_material.get(alias_material_path)
                            or synthetic_by_material.get(alias_material_path)
                        )
                    if texture_path is None:
                        texture_path = synthetic_path

            # CUE4Parse's glTF exporter can preserve an authored constant
            # base color even when the source material exposes no image/vector
            # binding. Use that exact factor as a 1x1 residency texture rather
            # than leaving the submesh unmapped or abusing a normal map.
            if (
                texture_path is None
                and local_material != NO_TEXTURE
                and 0 <= local_material < len(materials)
            ):
                rgba = glb_base_color_rgba(materials[local_material])
                if rgba is not None:
                    factor_key = (
                        f"synthetic://glb-base-color/"
                        f"{mesh_name.lower()}/{local_material}"
                    )
                    synthetic_textures.setdefault(
                        factor_key,
                        {
                            "kind": "glb_base_color",
                            "materialPath": (
                                alias_material_path
                                or material_path
                                or material_name.lower()
                            ),
                            "parameter": "pbrMetallicRoughness.baseColorFactor",
                            "rgba": rgba,
                        },
                    )
                    texture_path = factor_key

            if texture_path and (
                texture_path in textures_by_path
                or texture_path in synthetic_textures
            ):
                mapped += 1
                raw_binding_texture_paths.append(texture_path)
            else:
                raw_binding_texture_paths.append(None)
                if len(unresolved_slots) < 80:
                    unresolved_slots.append({
                        "mesh": mesh_name,
                        "glbMaterial": material_name,
                        "localMaterialIndex": local_material,
                        "slotFound": slot is not None,
                        "materialPath": str(slot.get("materialPath", "")) if slot else "",
                    })

        mesh_reports.append({
            "mesh": mesh_name,
            "submeshes": len(primitive_materials),
            "texturedSubmeshes": mapped,
        })

    if len(raw_binding_texture_paths) != EXPECTED_SUBMESHES:
        raise SystemExit(
            f"expected {EXPECTED_SUBMESHES} submesh bindings, "
            f"got {len(raw_binding_texture_paths)}"
        )

    used_paths = sorted({p for p in raw_binding_texture_paths if p is not None})
    texture_index = {path: i for i, path in enumerate(used_paths)}
    bindings = [
        texture_index[path] if path is not None else NO_TEXTURE
        for path in raw_binding_texture_paths
    ]

    runtime_textures = []
    data_offset = (
        HEADER.size
        + len(used_paths) * TEXTURE.size
        + len(bindings) * 4
    )

    for path in used_paths:
        if path in synthetic_textures:
            synthetic = synthetic_textures[path]
            runtime_textures.append({
                "texturePath": path,
                "textureName": material_object_name(
                    synthetic["materialPath"]
                ),
                "sourceKind": "synthetic",
                "kind": synthetic["kind"],
                "materialPath": synthetic["materialPath"],
                "parameter": synthetic["parameter"],
                "width": 1,
                "height": 1,
                "offset": data_offset,
                "bytes": 4,
                "rgba": synthetic["rgba"],
            })
            data_offset += 4
            continue

        row = textures_by_path[path]
        source = args.glb_root / str(row["file"])
        width, height, _fmt, _bytes = read_xzt_header(source)
        runtime_width, runtime_height = runtime_size(
            width, height, args.max_dimension
        )
        runtime_bytes = runtime_width * runtime_height * 4
        runtime_textures.append({
            "texturePath": path,
            "textureName": row.get("textureName", ""),
            "sourceKind": "xzt",
            "source": source,
            "sourceWidth": width,
            "sourceHeight": height,
            "width": runtime_width,
            "height": runtime_height,
            "offset": data_offset,
            "bytes": runtime_bytes,
        })
        data_offset += runtime_bytes

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as out:
        out.write(HEADER.pack(
            MAGIC,
            VERSION,
            len(runtime_textures),
            len(bindings),
            TEXTURE.size,
            1,  # RGBA8 / base-color residency tier
        ))
        for texture in runtime_textures:
            out.write(TEXTURE.pack(
                texture["width"],
                texture["height"],
                texture["offset"],
                texture["bytes"],
                1,
            ))
        for binding in bindings:
            out.write(struct.pack("<I", binding))

        for texture in runtime_textures:
            if texture.get("sourceKind") == "synthetic":
                runtime_rgba = texture["rgba"]
            else:
                width, height, rgba = read_xzt_rgba(texture["source"])
                runtime_rgba = resize_nearest_rgba(
                    rgba,
                    width,
                    height,
                    texture["width"],
                    texture["height"],
                )
            if len(runtime_rgba) != texture["bytes"]:
                raise SystemExit("runtime texture resize byte mismatch")
            out.write(runtime_rgba)

    mapped = sum(binding != NO_TEXTURE for binding in bindings)
    synthetic_mapped = sum(
        1 for path in raw_binding_texture_paths
        if path in synthetic_textures
    )
    transparent_mapped = sum(
        1 for path in raw_binding_texture_paths
        if (
            path in synthetic_textures
            and synthetic_textures[path]["kind"] == "global_invisible"
        )
    )
    vector_mapped = sum(
        1 for path in raw_binding_texture_paths
        if (
            path in synthetic_textures
            and synthetic_textures[path]["kind"] == "vector_color"
        )
    )
    glb_base_color_mapped = sum(
        1 for path in raw_binding_texture_paths
        if (
            path in synthetic_textures
            and synthetic_textures[path]["kind"] == "glb_base_color"
        )
    )
    report = {
        "schemaVersion": 1,
        "format": "XZMT",
        "version": VERSION,
        "mapId": "bo3_nacht_reference",
        "meshCount": EXPECTED_MESHES,
        "bindingCount": len(bindings),
        "mappedBindings": mapped,
        "unmappedBindings": len(bindings) - mapped,
        "textureCount": len(runtime_textures),
        "syntheticTextureCount": sum(
            1 for texture in runtime_textures
            if texture.get("sourceKind") == "synthetic"
        ),
        "transparentMaterialCount": sum(
            1 for item in synthetic_textures.values()
            if item["kind"] == "global_invisible"
        ),
        "vectorColorMaterialCount": sum(
            1 for item in synthetic_textures.values()
            if item["kind"] == "vector_color"
        ),
        "glbBaseColorMaterialCount": sum(
            1 for item in synthetic_textures.values()
            if item["kind"] == "glb_base_color"
        ),
        "syntheticMappedBindings": synthetic_mapped,
        "transparentMappedBindings": transparent_mapped,
        "vectorColorMappedBindings": vector_mapped,
        "glbBaseColorMappedBindings": glb_base_color_mapped,
        "streamingFallbackBindings": streaming_fallback_bindings,
        "runtimeMaxDimension": args.max_dimension,
        "runtimeBytes": args.output.stat().st_size,
        "unresolvedSamples": unresolved_slots,
        "meshes": mesh_reports,
        "textures": [
            {
                k: v
                for k, v in texture.items()
                if k not in {"source", "rgba"}
            }
            for texture in runtime_textures
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    if mapped == 0 or not runtime_textures:
        raise SystemExit("no static-scene material bindings resolved")
    if transparent_mapped == 0:
        raise SystemExit("global_invisible did not map to transparent runtime texture")

    print(
        "XZIEL_NACHT_XZMT_OK",
        f"textures={len(runtime_textures)}",
        f"bindings={len(bindings)}",
        f"mapped={mapped}",
        f"unmapped={len(bindings)-mapped}",
        f"synthetic={synthetic_mapped}",
        f"transparent={transparent_mapped}",
        f"vectorColor={vector_mapped}",
        f"glbBaseColor={glb_base_color_mapped}",
        f"streamingFallback={streaming_fallback_bindings}",
        f"maxDim={args.max_dimension}",
        f"bytes={args.output.stat().st_size}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
