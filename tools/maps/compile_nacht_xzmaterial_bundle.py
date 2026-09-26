#!/usr/bin/env python3
"""Compile Nacht material/texture bindings into XZMT v1.

XZMT is a compact companion to XZMS/XZSC. Geometry remains untouched.
Each flattened XZMS submesh receives texture ordinals for base color,
normal, specular and blend roles. Texture pixels live in compact XZTX
files (t0000.xzt...) so Quake-era path limits are never involved.

The source manifest is produced by the CUE4Parse CI exporter and records:
- every decoded UTexture -> XZTX path
- effective material texture bindings, including parent inheritance
- every UStaticMesh material slot and resolved UMaterialInterface
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets/nacht_reference/pavlov_scene_reference/assets.json"
CONVERTER = ROOT / "tools/maps/convert_glb_to_xzmesh.py"

MAGIC = b"XZMT"
VERSION = 1
EXPECTED_MESHES = 492
EXPECTED_SUBMESHES = 1063
NO_TEXTURE = 0xFFFFFFFF

HEADER = struct.Struct("<4sIIIII")
MESH_SPAN = struct.Struct("<II")
BINDING = struct.Struct("<IIIII")

ROLE_BASE = 1 << 0
ROLE_NORMAL = 1 << 1
ROLE_SPECULAR = 1 << 2
ROLE_BLEND = 1 << 3


def load_converter():
    spec = importlib.util.spec_from_file_location("xzmesh_converter", CONVERTER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load {CONVERTER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


converter = load_converter()


def material_indices(doc: dict) -> list[int]:
    nodes = doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    scenes = doc.get("scenes", [])
    scene_index = int(doc.get("scene", 0) or 0)

    if scenes and 0 <= scene_index < len(scenes):
        roots = scenes[scene_index].get("nodes", [])
    elif nodes:
        roots = list(range(len(nodes)))
    else:
        raise ValueError("GLB has no scene nodes")

    out: list[int] = []

    def visit(node_index: int) -> None:
        if not isinstance(node_index, int) or not (0 <= node_index < len(nodes)):
            raise ValueError(f"invalid node index {node_index}")
        node = nodes[node_index]
        mesh_index = node.get("mesh")
        if isinstance(mesh_index, int):
            if not (0 <= mesh_index < len(meshes)):
                raise ValueError(f"invalid mesh index {mesh_index}")
            for primitive in meshes[mesh_index].get("primitives", []):
                material = primitive.get("material")
                out.append(int(material) if isinstance(material, int) else -1)
        for child in node.get("children", []):
            visit(child)

    for root in roots:
        visit(root)

    return out


def role_for(row: dict) -> tuple[str | None, int]:
    source = str(row.get("source", ""))
    texture = str(row.get("textureName", "")).lower()
    source_lower = source.lower()

    if source_lower == "parameter:albedotexture":
        return "base", 0
    if source_lower == "parameter:normaltexture":
        return "normal", 0
    if source_lower == "parameter:speculartexture":
        return "specular", 0
    if source_lower == "parameter:blendtexture":
        return "blend", 0

    if "albedo" in source_lower or "diffuse" in source_lower:
        return "base", 1
    if "normal" in source_lower:
        return "normal", 1
    if "specular" in source_lower:
        return "specular", 1
    if "blend" in source_lower:
        return "blend", 1

    stem = texture.rsplit(".", 1)[-1]
    if (
        stem.endswith("_c")
        or stem.endswith("_col")
        or stem.endswith("_color")
        or "diffuse" in stem
        or "albedo" in stem
    ):
        return "base", 2
    if (
        stem.endswith("_n")
        or stem.endswith("_nm")
        or "normal" in stem
        or "_norm" in stem
    ):
        return "normal", 2
    if (
        stem.endswith("_s")
        or stem.endswith("_sp")
        or "spec" in stem
        or "mrs" in stem
    ):
        return "specular", 2
    if "blend" in stem:
        return "blend", 2

    return None, 99


def normalize_name(value: str) -> str:
    return value.strip().lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", type=Path, default=ASSETS)
    ap.add_argument("--glb-root", type=Path, required=True)
    ap.add_argument("--texture-manifest", type=Path, required=True)
    ap.add_argument("--output-material", type=Path, required=True)
    ap.add_argument("--output-textures", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    assets = json.loads(args.assets.read_text(encoding="utf-8"))
    rows = assets.get("meshes", [])
    if assets.get("uniqueMeshCount") != EXPECTED_MESHES or len(rows) != EXPECTED_MESHES:
        raise SystemExit(f"expected {EXPECTED_MESHES} Nacht meshes")

    manifest = json.loads(args.texture_manifest.read_text(encoding="utf-8"))
    texture_rows = manifest.get("textures", [])
    binding_rows = manifest.get("bindings", [])
    mesh_material_rows = manifest.get("meshMaterials", [])

    texture_by_path = {
        str(row["texturePath"]): row
        for row in texture_rows
        if row.get("texturePath") and row.get("file")
    }
    if not texture_by_path:
        raise SystemExit("texture manifest has no decoded textures")

    # Pick one effective binding per material+semantic role. Child overrides
    # parent because lower inheritanceDepth wins. Explicit parameter names win
    # over filename inference at the same depth.
    effective: dict[str, dict[str, tuple[tuple[int, int, int], str]]] = {}
    for order, row in enumerate(binding_rows):
        material_path = str(row.get("materialPath", ""))
        texture_path = str(row.get("texturePath", ""))
        if not material_path or texture_path not in texture_by_path:
            continue

        role, source_priority = role_for(row)
        if role is None:
            continue

        try:
            depth = int(row.get("inheritanceDepth", 0))
        except (TypeError, ValueError):
            depth = 0

        key = (depth, source_priority, order)
        roles = effective.setdefault(material_path, {})
        previous = roles.get(role)
        if previous is None or key < previous[0]:
            roles[role] = (key, texture_path)

    slot_by_mesh_index: dict[tuple[str, int], dict] = {}
    slots_by_mesh_name: dict[str, list[dict]] = {}
    global_materials: dict[str, list[dict]] = {}

    for row in mesh_material_rows:
        mesh_name = normalize_name(str(row.get("meshName", "")))
        material_name = normalize_name(str(row.get("materialName", "")))
        if not mesh_name or not material_name:
            continue
        try:
            slot_index = int(row.get("slotIndex", -1))
        except (TypeError, ValueError):
            continue
        slot_by_mesh_index[(mesh_name, slot_index)] = row
        slots_by_mesh_name.setdefault(mesh_name, []).append(row)
        global_materials.setdefault(material_name, []).append(row)

    glbs: dict[str, Path] = {}
    for p in args.glb_root.rglob("*.glb"):
        key = normalize_name(p.stem)
        if key in glbs:
            raise SystemExit(f"duplicate GLB stem {p.stem}")
        glbs[key] = p

    # First resolve every submesh to a material path and collect texture paths.
    mesh_spans: list[tuple[int, int]] = []
    pending_bindings: list[dict[str, str | None]] = []
    unresolved: list[dict] = []
    material_name_mismatches: list[dict] = []

    for row in rows:
        source = str(row["sourcePath"]).replace("\\", "/").rstrip("/")
        mesh_name = source.rsplit("/", 1)[-1]
        mesh_key = normalize_name(mesh_name)
        glb = glbs.get(mesh_key)
        if glb is None:
            raise SystemExit(f"missing GLB for {mesh_name}")

        doc, _ = converter.parse_glb(glb)
        indices = material_indices(doc)
        materials = doc.get("materials", [])
        first = len(pending_bindings)

        for submesh_index, material_index in enumerate(indices):
            if material_index < 0:
                pending_bindings.append({
                    "base": None,
                    "normal": None,
                    "specular": None,
                    "blend": None,
                })
                continue

            glb_name = ""
            if 0 <= material_index < len(materials):
                material_doc = materials[material_index]
                if isinstance(material_doc, dict):
                    glb_name = str(material_doc.get("name", ""))

            resolved = slot_by_mesh_index.get((mesh_key, material_index))
            if resolved is not None and glb_name:
                expected = normalize_name(str(resolved.get("materialName", "")))
                actual = normalize_name(glb_name)
                if expected and actual and expected != actual:
                    # Some exporters compact/reorder material arrays. Prefer an
                    # exact material-name match inside this mesh when available.
                    matches = [
                        candidate
                        for candidate in slots_by_mesh_name.get(mesh_key, [])
                        if normalize_name(str(candidate.get("materialName", ""))) == actual
                    ]
                    if len(matches) == 1:
                        resolved = matches[0]
                    else:
                        material_name_mismatches.append({
                            "mesh": mesh_name,
                            "submesh": submesh_index,
                            "materialIndex": material_index,
                            "glbMaterial": glb_name,
                            "slotMaterial": str(resolved.get("materialName", "")),
                        })

            if resolved is None and glb_name:
                matches = [
                    candidate
                    for candidate in slots_by_mesh_name.get(mesh_key, [])
                    if normalize_name(str(candidate.get("materialName", ""))) == normalize_name(glb_name)
                ]
                if len(matches) == 1:
                    resolved = matches[0]

            if resolved is None and glb_name:
                matches = global_materials.get(normalize_name(glb_name), [])
                unique_paths = {
                    str(candidate.get("materialPath", ""))
                    for candidate in matches
                    if candidate.get("materialPath")
                }
                if len(unique_paths) == 1 and matches:
                    resolved = matches[0]

            if resolved is None:
                unresolved.append({
                    "mesh": mesh_name,
                    "submesh": submesh_index,
                    "materialIndex": material_index,
                    "glbMaterial": glb_name,
                })
                pending_bindings.append({
                    "base": None,
                    "normal": None,
                    "specular": None,
                    "blend": None,
                })
                continue

            material_path = str(resolved.get("materialPath", ""))
            roles = effective.get(material_path, {})
            pending_bindings.append({
                role: roles.get(role, ((0, 0, 0), None))[1]
                for role in ("base", "normal", "specular", "blend")
            })

        mesh_spans.append((first, len(indices)))

    if len(mesh_spans) != EXPECTED_MESHES:
        raise SystemExit(f"material spans={len(mesh_spans)}")
    if len(pending_bindings) != EXPECTED_SUBMESHES:
        raise SystemExit(
            f"expected {EXPECTED_SUBMESHES} submesh bindings, got {len(pending_bindings)}"
        )
    if unresolved:
        raise SystemExit(
            f"unresolved GLB materials={len(unresolved)} sample={unresolved[:12]}"
        )

    used_texture_paths = sorted({
        texture_path
        for row in pending_bindings
        for texture_path in row.values()
        if texture_path is not None
    })
    texture_ordinal = {
        texture_path: index
        for index, texture_path in enumerate(used_texture_paths)
    }

    args.output_textures.mkdir(parents=True, exist_ok=True)
    runtime_texture_rows = []
    runtime_texture_bytes = 0

    for texture_path, ordinal in texture_ordinal.items():
        source_row = texture_by_path[texture_path]
        source_file = args.glb_root / str(source_row["file"])
        if not source_file.is_file():
            raise SystemExit(f"missing XZTX {source_file}")

        runtime_name = f"t{ordinal:04d}.xzt"
        target = args.output_textures / runtime_name
        shutil.copyfile(source_file, target)
        runtime_texture_bytes += target.stat().st_size

        runtime_texture_rows.append({
            "ordinal": ordinal,
            "runtimeFile": runtime_name,
            "sourceFile": str(source_row["file"]),
            "texturePath": texture_path,
            "textureName": source_row.get("textureName", ""),
            "width": int(source_row.get("width", 0)),
            "height": int(source_row.get("height", 0)),
            "decodedFormat": source_row.get("decodedFormat", ""),
            "runtimeFormat": source_row.get("runtimeFormat", ""),
        })

    encoded_bindings: list[tuple[int, int, int, int, int]] = []
    counts = {
        "base": 0,
        "normal": 0,
        "specular": 0,
        "blend": 0,
    }

    for row in pending_bindings:
        values = []
        flags = 0
        for role, bit in (
            ("base", ROLE_BASE),
            ("normal", ROLE_NORMAL),
            ("specular", ROLE_SPECULAR),
            ("blend", ROLE_BLEND),
        ):
            texture_path = row[role]
            if texture_path is None:
                values.append(NO_TEXTURE)
            else:
                values.append(texture_ordinal[texture_path])
                flags |= bit
                counts[role] += 1
        encoded_bindings.append((*values, flags))

    args.output_material.parent.mkdir(parents=True, exist_ok=True)
    with args.output_material.open("wb") as f:
        f.write(HEADER.pack(
            MAGIC,
            VERSION,
            EXPECTED_MESHES,
            len(encoded_bindings),
            len(runtime_texture_rows),
            BINDING.size,
        ))
        for first, count in mesh_spans:
            f.write(MESH_SPAN.pack(first, count))
        for binding in encoded_bindings:
            f.write(BINDING.pack(*binding))

    expected_bytes = (
        HEADER.size
        + EXPECTED_MESHES * MESH_SPAN.size
        + len(encoded_bindings) * BINDING.size
    )
    if args.output_material.stat().st_size != expected_bytes:
        raise SystemExit("XZMT byte-size invariant failed")

    report = {
        "schemaVersion": 1,
        "format": "xziel_xzmaterial_v1",
        "meshCount": EXPECTED_MESHES,
        "submeshBindingCount": len(encoded_bindings),
        "textureCount": len(runtime_texture_rows),
        "runtimeTextureBytes": runtime_texture_bytes,
        "materialTableBytes": args.output_material.stat().st_size,
        "bindingsWithBaseColor": counts["base"],
        "bindingsWithNormal": counts["normal"],
        "bindingsWithSpecular": counts["specular"],
        "bindingsWithBlend": counts["blend"],
        "bindingsWithoutBaseColor": len(encoded_bindings) - counts["base"],
        "materialNameMismatchCount": len(material_name_mismatches),
        "materialNameMismatchSamples": material_name_mismatches[:20],
        "runtimeTextureMaxMipSize": manifest.get("runtimeTextureMaxMipSize"),
        "textures": runtime_texture_rows,
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(
        "XZIEL_NACHT_XZMT_OK",
        json.dumps(
            {
                "meshes": EXPECTED_MESHES,
                "bindings": len(encoded_bindings),
                "textures": len(runtime_texture_rows),
                "base": counts["base"],
                "normal": counts["normal"],
                "specular": counts["specular"],
                "blend": counts["blend"],
                "noBase": len(encoded_bindings) - counts["base"],
                "textureBytes": runtime_texture_bytes,
                "tableBytes": args.output_material.stat().st_size,
            },
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
