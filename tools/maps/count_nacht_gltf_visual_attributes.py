#!/usr/bin/env python3
"""Build independent visual-attribute expectations from lossless Nacht GLB.

Counts every *reachable* mesh primitive for the 10,793 archived Pavlov UE4.21
map actors, not all stale/transcoded primitives in the GLB. Only the source
GLB's explicitly authored vertex formats and material slots count as claims.
Not a BO3 T7 provenance, rendered fidelity, or playable-game test.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct


SUPPORTED = {
    "NORMAL": "normals",
    "TANGENT": "tangents",
    "TEXCOORD_0": "uv0",
    "TEXCOORD_1": "uv1",
    "COLOR_0": "colors",
}


def glb_doc(path):
    with path.open("rb") as f:
        head = f.read(20)
        if len(head) != 20:
            raise ValueError("truncated GLB")
        magic, ver, size, json_size, kind = struct.unpack("<IIIII", head)
        if (magic, ver, kind) != (0x46546C67, 2, 0x4E4F534A):
            raise ValueError("invalid glTF v2 binary header")
        if size != path.stat().st_size or json_size + 28 > size:
            raise ValueError("mismatched GLB size")
        return json.loads(f.read(json_size))


def inspect(doc):
    marker = doc.get("extras", {}).get("xziel_native_glb_geometry_lossless_reinjected", {})
    if (marker.get("actors") != 10793 or marker.get("native_mesh_types") != 493
            or marker.get("original_static_glb_passthrough") is not True):
        raise ValueError("not the approved research lossless source GLB")
    actors = set()
    visited = set()
    mesh_nodes = []
    def walk(i, actor=None):
        if i in visited or not 0 <= i < len(doc["nodes"]):
            raise ValueError("cyclic/repeated/out-of-range scene node")
        visited.add(i)
        node = doc["nodes"][i]
        name = node.get("name", "")
        if name.startswith("ue_instance_") and "_native_exact_" not in name:
            if actor is not None:
                raise ValueError("nested source actor")
            actor = name
            if actor in actors:
                raise ValueError("duplicate source actor")
            actors.add(actor)
        if "mesh" in node:
            if actor is None:
                raise ValueError("unowned source mesh node")
            if "_native_exact_" not in name:
                raise ValueError("unapproved rendered transcode mesh " + name)
            mesh_nodes.append(node["mesh"])
        for child in node.get("children", []):
            walk(child, actor)
    for root in doc["scenes"][doc.get("scene", 0)]["nodes"]:
        walk(root)
    if len(actors) != 10793 or len(mesh_nodes) != 10793:
        raise ValueError(f"source actors={len(actors)} mesh attachments={len(mesh_nodes)}")
    assert len(doc.get("meshes", [])) > 493

    total = Counter()
    materials_used = set()
    for mi in mesh_nodes:
        for p in doc["meshes"][mi]["primitives"]:
            if p.get("mode", 4) != 4:
                raise ValueError("unhandled primitive mode")
            attributes = p["attributes"]
            count = doc["accessors"][attributes["POSITION"]]["count"]
            if count <= 0:
                raise ValueError("empty glTF POSITION accessor")
            total["surfaces"] += 1
            total["position_vertices"] += count
            for native, label in SUPPORTED.items():
                if native in attributes:
                    n = doc["accessors"][attributes[native]]["count"]
                    if n != count:
                        raise ValueError(f"{native} accessor count differs from positions")
                    total[label + "_surfaces"] += 1
                    total[label + "_vertices"] += n
            if "material" in p:
                if p["material"] >= len(doc.get("materials", [])):
                    raise ValueError("bad material reference")
                total["bound_material_surfaces"] += 1
                materials_used.add(p["material"])
            else:
                total["unbound_material_surfaces"] += 1
    # Textures declared by materials, independent of Godot runtime support.
    for mat in materials_used:
        m = doc["materials"][mat]
        refs = []
        pbr = m.get("pbrMetallicRoughness", {})
        for key in ("baseColorTexture", "metallicRoughnessTexture"):
            if isinstance(pbr.get(key), dict):
                refs.append(pbr[key]["index"])
        for key in ("normalTexture", "occlusionTexture", "emissiveTexture"):
            if isinstance(m.get(key), dict):
                refs.append(m[key]["index"])
        for tid in refs:
            if not 0 <= tid < len(doc.get("textures", [])):
                raise ValueError("material references absent texture")
            source = doc["textures"][tid].get("source")
            if source is not None and not 0 <= source < len(doc.get("images", [])):
                raise ValueError("texture references missing image")
            total["referenced_texture_slots"] += 1
    return {
        "source": "lossless glTF source, archived Pavlov UE4.21 (NOT BO3 T7)",
        "source_actor_count": len(actors),
        "mesh_instances": len(mesh_nodes),
        "used_materials": len(materials_used),
        "available_materials": len(doc.get("materials", [])),
        "available_images": len(doc.get("images", [])),
        "available_textures": len(doc.get("textures", [])),
        "counts": dict(total),
        "needs_3d_visual_review": True,
        "claims_identical_original_bo3_t7_materials": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(glb_doc(args.glb))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("XZOGOT_NACHT_GLTF_NATIVE_VISUAL_ATTRIBUTE_BASELINE_GREEN",
          json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
