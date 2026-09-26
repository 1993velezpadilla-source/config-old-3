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
    if not texture_rows or not binding_rows or not mesh_material_rows:
        raise SystemExit("texture manifest missing textures/bindings/meshMaterials")

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
        for slot in slots:
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

            texture_path: str | None = None
            if slot is not None:
                material_path = str(slot.get("materialPath", "")).lower()
                texture_path = selected_by_material.get(material_path)

            if texture_path and texture_path in textures_by_path:
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
        "runtimeMaxDimension": args.max_dimension,
        "runtimeBytes": args.output.stat().st_size,
        "unresolvedSamples": unresolved_slots,
        "meshes": mesh_reports,
        "textures": [
            {
                k: v
                for k, v in texture.items()
                if k != "source"
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

    print(
        "XZIEL_NACHT_XZMT_OK",
        f"textures={len(runtime_textures)}",
        f"bindings={len(bindings)}",
        f"mapped={mapped}",
        f"unmapped={len(bindings)-mapped}",
        f"maxDim={args.max_dimension}",
        f"bytes={args.output.stat().st_size}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
