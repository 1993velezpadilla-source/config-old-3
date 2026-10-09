#!/usr/bin/env python3
"""Lossless research GLB mesh passthrough: Meridian scene nodes + raw native GLB meshes.

Blender's glTF importer AND exporter discard 1,051 valid original triangles
across 13 Pavlov UE4.21 source GLBs. This post-processor leaves Meridian's
original actor node hierarchy and full source affine matrices intact, but
replaces Blender-transcoded geometry references with raw original native GLB
primitives, accessors, indices, UVs, normals, textures and binary payloads.

The source XZIEL glTF encodes native Z-UP vertices with xziel_basis_preserved;
placing the ORIGINAL source mesh under an XZIEL->glTF-YUP child transform C
preserves world geometry. No per-actor geometric guesses or synthetic meshes.
Research ONLY: not official BO3 T7 assets; no automatic production merge.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import struct
import sys

from validate_meridian_source_geometry import identity, load_glb, local

C = [[1.,0.,0.,0.], [0.,0.,1.,0.], [0.,-1.,0.,0.], [0.,0.,0.,1.]]
C_GLTF_COLUMN_MAJOR = [C[i][j] for j in range(4) for i in range(4)]


def append_binary(out, data):
    extra = (-len(out)) % 4
    if extra:
        out.extend(b"\0" * extra)
    start = len(out)
    out.extend(data)
    return start


def graft_native(doc, native_doc, source_binary, merged_binary, mesh_type):
    if len(native_doc.get("buffers", [])) != 1 or len(doc.get("buffers", [])) != 1:
        raise ValueError("only single-buffer GLB native source supported")
    if native_doc.get("extras", {}).get("xziel_basis_preserved") is not True:
        raise ValueError(f"native Z-UP source contract missing mesh_type={mesh_type}")
    if len(native_doc.get("meshes", [])) == 0:
        raise ValueError(f"native geometry absent mesh_type={mesh_type}")
    if any(local(node) != identity() for node in native_doc.get("nodes", [])):
        raise ValueError(f"unproven local source GLB node transforms type={mesh_type}")
    if any(uri.get("uri") for uri in native_doc.get("images", [])):
        raise ValueError("external image URI unsupported - do not drop textures")
    if native_doc.get("skins") or native_doc.get("animations"):
        raise ValueError("skinned/animated source not a static-map native GLB")
    if any(p.get("extensions") for m in native_doc["meshes"] for p in m["primitives"]):
        raise ValueError("compressed or extended source geometry unsupported")
    if any("extensions" in tex for tex in native_doc.get("textures", [])):
        raise ValueError("extended texture unsupported - fail closed")

    offset = append_binary(merged_binary, bytes(source_binary))
    view_shift = len(doc.setdefault("bufferViews", []))
    accessor_shift = len(doc.setdefault("accessors", []))
    image_shift = len(doc.setdefault("images", []))
    sampler_shift = len(doc.setdefault("samplers", []))
    texture_shift = len(doc.setdefault("textures", []))
    material_shift = len(doc.setdefault("materials", []))
    mesh_shift = len(doc.setdefault("meshes", []))

    for view in native_doc.get("bufferViews", []):
        if view.get("buffer", 0) != 0:
            raise ValueError("multi-buffer source view unsupported")
        item = deepcopy(view)
        item["buffer"] = 0
        item["byteOffset"] = offset + item.get("byteOffset", 0)
        doc["bufferViews"].append(item)

    for a in native_doc.get("accessors", []):
        item = deepcopy(a)
        if "bufferView" in item:
            item["bufferView"] += view_shift
        if "sparse" in item:
            s = item["sparse"]
            s["indices"]["bufferView"] += view_shift
            s["values"]["bufferView"] += view_shift
        doc["accessors"].append(item)

    for image in native_doc.get("images", []):
        item = deepcopy(image)
        if "bufferView" in item:
            item["bufferView"] += view_shift
        doc["images"].append(item)
    for sampler in native_doc.get("samplers", []):
        doc["samplers"].append(deepcopy(sampler))
    for texture in native_doc.get("textures", []):
        item = deepcopy(texture)
        if "sampler" in item:
            item["sampler"] += sampler_shift
        if "source" in item:
            item["source"] += image_shift
        doc["textures"].append(item)

    def fix_texture(info):
        if isinstance(info, dict) and "index" in info:
            info["index"] += texture_shift

    for material in native_doc.get("materials", []):
        item = deepcopy(material)
        pbr = item.get("pbrMetallicRoughness", {})
        for name in ("baseColorTexture", "metallicRoughnessTexture"):
            fix_texture(pbr.get(name))
        for name in ("normalTexture", "occlusionTexture", "emissiveTexture"):
            fix_texture(item.get(name))
        if any(e not in ("KHR_materials_unlit", "KHR_materials_ior",
                         "KHR_materials_emissive_strength")
               for e in item.get("extensions", {})):
            raise ValueError("unsupported material extension would lose texture link")
        doc["materials"].append(item)

    for material_ext in native_doc.get("extensionsUsed", []):
        arr = doc.setdefault("extensionsUsed", [])
        if material_ext not in arr:
            arr.append(material_ext)
    for required in native_doc.get("extensionsRequired", []):
        arr = doc.setdefault("extensionsRequired", [])
        if required not in arr:
            arr.append(required)

    for mesh in native_doc["meshes"]:
        item = deepcopy(mesh)
        for prim in item["primitives"]:
            if prim.get("mode", 4) != 4:
                raise ValueError("only triangles source static GLB allowed")
            prim["attributes"] = {k: v + accessor_shift
                                  for k, v in prim["attributes"].items()}
            if "indices" in prim:
                prim["indices"] += accessor_shift
            if "material" in prim:
                prim["material"] += material_shift
            for target in prim.get("targets", []):
                for k in list(target):
                    target[k] += accessor_shift
        doc["meshes"].append(item)

    return list(range(mesh_shift, len(doc["meshes"])))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scene", type=Path, required=True)
    p.add_argument("--native-glb-dir", type=Path, required=True)
    p.add_argument("--meridian-glb", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    source = json.loads(args.scene.read_text())
    actors = source["instances"]
    if (source.get("format") != "xziel_visual_scene_v1"
            or not source.get("summary", {}).get("ready")
            or len(actors) != 10793 or len(source["meshes"]) != 493):
        raise ValueError("only original archived full Pavlov source is allowed")
    actor_types = {str(a["instanceId"]): int(a["meshIndex"]) for a in actors}
    if len(actor_types) != 10793:
        raise ValueError("source actor IDs duplicated")
    mesh_rows = {int(m["index"]): m for m in source["meshes"]}
    if set(actor_types.values()) != set(mesh_rows):
        raise ValueError("full 493 original source types absent")
    doc, existing_bin = load_glb(args.meridian_glb)
    if len(doc["buffers"]) != 1:
        raise ValueError("Meridian GLB output has unexpected buffers")
    merged = bytearray(bytes(existing_bin))
    old_nodes = doc["nodes"]
    actor_node = {}
    for node in old_nodes:
        if node.get("name") in actor_types:
            name = node["name"]
            if name in actor_node:
                raise ValueError("duplicated emitted actor")
            actor_node[name] = node
    if set(actor_node) != set(actor_types):
        raise ValueError("Meridian missing native source actors")
    native_indices = {}
    sizes = {}
    for type_idx in sorted(mesh_rows):
        source_path = (args.native_glb_dir /
                       (Path(mesh_rows[type_idx]["runtimeFile"]).stem+".glb"))
        if not source_path.is_file():
            raise ValueError("native GLB absent: "+str(source_path))
        native_doc, binary = load_glb(source_path)
        native_indices[type_idx] = graft_native(
            doc, native_doc, binary, merged, type_idx
        )
        sizes[type_idx] = source_path.stat().st_size

    old_refs = 0
    new_refs = 0
    for iid, mesh_type in actor_types.items():
        actor_node_ref = actor_node[iid]
        existing = actor_node_ref.get("children", [])
        if not existing:
            raise ValueError("Meridian actor had no original meshes "+iid)
        # The generated scene has only old Blender-transcoded chunks under
        # these source actors; detach, never replace gameplay or source actor.
        old_refs += len(existing)
        actor_node_ref["children"] = []
        for n, mesh_idx in enumerate(native_indices[mesh_type]):
            node = {"name": iid+"_native_exact_%03d"%n,
                    "mesh": mesh_idx, "matrix": C_GLTF_COLUMN_MAJOR}
            child_idx = len(doc["nodes"])
            doc["nodes"].append(node)
            actor_node_ref["children"].append(child_idx)
            new_refs += 1
    doc["buffers"][0]["byteLength"] = len(merged)
    doc.setdefault("extras", {})["xziel_native_glb_geometry_lossless_reinjected"] = {
        "actors":len(actor_types),
        "native_mesh_types":len(mesh_rows),
        "original_bo3_t7":False,
        "original_static_glb_passthrough":True,
    }
    packed_json = json.dumps(doc, separators=(",", ":"), allow_nan=False).encode()
    packed_json += b" " * ((-len(packed_json)) % 4)
    merged += b"\0" * ((-len(merged)) % 4)
    output_length = 12 + 8 + len(packed_json) + 8 + len(merged)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(
        struct.pack("<III",0x46546C67,2,output_length) +
        struct.pack("<II",len(packed_json),0x4E4F534A) + packed_json +
        struct.pack("<II",len(merged),0x004E4942) + merged
    )
    report = {
        "authority":"archived Pavlov UE4.21 NOT original BO3 T7",
        "original_source_actors":len(actor_types),
        "original_unique_glb_types":len(mesh_rows),
        "source_file_bytes_total":sum(sizes.values()),
        "original_blender_chunk_nodes_detached":old_refs,
        "raw_source_native_glb_mesh_nodes_attached":new_refs,
        "exported_binary_bytes":args.output.stat().st_size,
        "source_affine_matrices_changed":False,
        "independent_world_primitive_parity_not_yet_proven":True,
        "original_BO3_T7_proven":False,
    }
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print("XZOGOT_NACHT_LOSSLESS_RAW_GLTF_REINJECTION_COMPILED",
          "actors",len(actor_types),"mesh_types",len(mesh_rows),
          "raw_mesh_nodes",new_refs,
          "glb_bytes",args.output.stat().st_size)


if __name__=="__main__":
    sys.exit(main())
