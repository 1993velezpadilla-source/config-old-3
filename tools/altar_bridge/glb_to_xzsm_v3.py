#!/usr/bin/env python3
"""Godot 4.6 GLB -> XZSM v3 *static visual* bridge. No engine/gameplay rewrite.

Usage:
  python3 glb_to_xzsm_v3.py --glb altar.glb --out out/nzp
Output: models/xziel/godot_altar/altar.xzsm and textures/xziel/godot_altar/*.png

XZSM v3 = same batch/vertex binary layout as XZSM v2 (5f4B + uint16 indices)
but *activates RGBA vertex lighting* via GL_COLOR_ARRAY and GL_MODULATE.
This is an approximation of Godot static lighting, NOT Godot PBR or LightmapGI.
PBR metallic/roughness and post-processing do not transfer automatically.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import struct
from pathlib import Path

import numpy as np
from PIL import Image
import trimesh

SCALE = 39.3700787402
BATCH_TRIANGLES = 16000
VERSION = 3
CANDLE_POINTS = np.array(
    [[x + 17.81, 1.52, 15.62 - 15.82] for x in (-19.35, -18.55, -17.07, -16.27)],
    dtype=np.float64,
)
MOON = np.array((0.30, 0.83, -0.48), dtype=np.float64)
MOON /= np.linalg.norm(MOON)


def slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_").lower()[:55] or "material"


def rgba_factor(mat):
    if hasattr(mat, "baseColorFactor") and mat.baseColorFactor is not None:
        c = list(mat.baseColorFactor)
        if len(c) == 4:
            return np.clip(np.array(c, dtype=np.float64), 0.0, 1.0)
    color = getattr(mat, "diffuse", None)
    if color is not None:
        v = np.array(color, dtype=np.float64).reshape(-1)
        if len(v) >= 3:
            if np.max(v) > 1.0:
                v /= 255.0
            return np.append(np.clip(v[:3], 0, 1), 1.0)
    return np.ones(4)


def material_image(mat, max_texture: int) -> Image.Image:
    color = rgba_factor(mat)
    image = getattr(mat, "baseColorTexture", None)
    if image is None:
        image = getattr(mat, "image", None)
    if image is None:
        pixel = tuple(int(round(x * 255)) for x in color)
        return Image.new("RGBA", (4, 4), pixel)
    if not isinstance(image, Image.Image):
        raise RuntimeError(f"unhandled GLB material image type: {type(image)}")
    image = image.convert("RGBA").copy()
    if image.width > max_texture or image.height > max_texture:
        image.thumbnail((max_texture, max_texture), Image.Resampling.LANCZOS)
    arr = np.asarray(image, dtype=np.float64).copy()
    arr *= color.reshape(1, 1, 4)
    return Image.fromarray(np.uint8(np.round(arr).clip(0, 255)), "RGBA")


def vertex_light(positions, normals):
    """A tiny static candle + moon fill proxy. Only visual vertex RGB, no shadows."""
    nl = np.maximum(0.0, np.sum(normals * MOON[None, :], axis=1))
    strength = np.full(len(positions), 0.60) + 0.17 * nl
    warm = np.zeros(len(positions), dtype=np.float64)
    # Candle centers are from the actual Godot church_fresh.gd altar script.
    for candle in CANDLE_POINTS:
        distance = np.linalg.norm(positions - candle[None, :], axis=1)
        warm += 0.22 * np.maximum(0.0, 1.0 - distance / 2.7) ** 2
    warm = np.clip(warm, 0.0, 0.28)
    rgb = np.column_stack(
        (strength + warm, strength + 0.70 * warm, strength + 0.34 * warm)
    )
    rgb = np.uint8(np.round(np.clip(rgb, 0.38, 1.0) * 255))
    return np.column_stack([rgb, np.full(len(rgb), 255, dtype=np.uint8)])


def quake_xyz(v):
    # Godot/glTF: +Y up; Quake/Vril: +Z up. Rotation determinant +1.
    return np.column_stack((v[:, 0], -v[:, 2], v[:, 1])) * SCALE


def original_godot_materials(glb: Path):
    """Read glTF JSON directly: trimesh may discard material-only Godot surface colors."""
    blob = glb.read_bytes()
    if blob[:4] != b"glTF":
        raise RuntimeError("Godot export is not binary GLB")
    length, typ = struct.unpack_from("<II", blob, 12)
    if typ != 0x4e4f534a:
        raise RuntimeError("GLB has no JSON chunk")
    scene = json.loads(blob[20:20+length])
    mats = scene.get("materials", [])
    nodes = {}
    for n in scene.get("nodes", []):
        if "mesh" not in n:
            continue
        prims = scene["meshes"][n["mesh"]].get("primitives", [])
        if len(prims) != 1 or "material" not in prims[0]:
            raise RuntimeError("Original Godot altar has unexpected material/primitive layout")
        mat_index = prims[0]["material"]
        raw = mats[mat_index]
        pbr = raw.get("pbrMetallicRoughness", {})
        factor = np.array(pbr.get("baseColorFactor", [1, 1, 1, 1]), dtype=np.float64)
        if factor.size != 4:
            raise RuntimeError("Bad Godot material color factor")
        name = n.get("name")
        if not name:
            raise RuntimeError("Godot altar GLB missing node names")
        nodes[name] = (mat_index, factor, pbr)
    if len(nodes) < 11 or len(mats) < 4:
        raise RuntimeError(f"Lost Godot material identity: nodes={len(nodes)}, materials={len(mats)}")
    return nodes


def srgb_encode(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 12.92*x if x <= 0.0031308 else 1.055*x**(1.0/2.4)-0.055


def write_xzsm(glb: Path, out: Path, texture_max=2048, require_components=11):
    if not glb.is_file():
        raise FileNotFoundError(glb)
    obj = trimesh.load(str(glb), force="scene", process=False)
    if not isinstance(obj, trimesh.Scene):
        raise RuntimeError("GLB is not a scene")
    instances = sorted(obj.graph.nodes_geometry)
    source_materials = original_godot_materials(glb)
    if len(instances) < require_components:
        raise RuntimeError(f"altar incomplete: found {len(instances)} meshes, expected {require_components}+")
    tex_dir = out / "textures/xziel/godot_altar"
    mesh_path = out / "models/xziel/godot_altar/altar.xzsm"
    tex_dir.mkdir(parents=True, exist_ok=True)
    mesh_path.parent.mkdir(parents=True, exist_ok=True)

    batches = []
    materials = {}
    missing_uv = []
    triangle_count = 0
    # Group by actual Godot material and keep per-node transforms from GLB.
    for node in instances:
        transform, geom_id = obj.graph[node]
        mesh = obj.geometry[geom_id].copy()
        mesh.apply_transform(transform)
        if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
            continue
        mat = getattr(mesh.visual, "material", None)
        if str(node) not in source_materials:
            raise RuntimeError(f"Cannot associate Godot material with GLB node {node}")
        mat_index, factor, pbr = source_materials[str(node)]
        key = f"godot_material_{mat_index}"
        mat_key = key
        has_original_image = "baseColorTexture" in pbr
        if mat_key not in materials:
            path_stem = f"{len(materials):03d}_{slug(key)}"
            if has_original_image:
                if mat is None:
                    raise RuntimeError(f"Textured Godot material {key} was discarded by importer")
                image = material_image(mat, texture_max)
            else:
                # glTF baseColorFactor is linear. Quake's PNG texture sampler
                # consumes sRGB bytes, so convert linear factor to display RGB.
                pixel = tuple(int(round(srgb_encode(v)*255)) for v in factor[:3])
                pixel += (int(round(float(factor[3])*255)),)
                image = Image.new("RGBA", (4, 4), pixel)
            png = tex_dir / (path_stem + ".png")
            image.save(png, format="PNG", optimize=True)
            materials[mat_key] = {
                "name": key,
                "rel": f"textures/xziel/godot_altar/{path_stem}",
                "size": [image.width,image.height],
                "factor": factor.tolist(),
            }
        texture_path = materials[mat_key]["rel"]
        vertices = np.array(mesh.vertices, dtype=np.float64)
        faces = np.array(mesh.faces, dtype=np.int64)
        normals = np.array(mesh.vertex_normals, dtype=np.float64)
        uv = getattr(mesh.visual, "uv", None)
        has_image = has_original_image
        if uv is None or len(uv) != len(vertices):
            if has_image:
                missing_uv.append(str(node))
            # Godot solid-colored procedural BoxMesh can use a 4x4 fallback.
            uv = np.zeros((len(vertices), 2), dtype=np.float64)
        else:
            uv = np.asarray(uv, dtype=np.float64)
        if len(vertices) != len(normals):
            raise RuntimeError(f"{node}: invalid GLB normals")

        for start in range(0, len(faces), BATCH_TRIANGLES):
            chunk = faces[start:start + BATCH_TRIANGLES]
            indices_orig, inverse = np.unique(chunk.ravel(), return_inverse=True)
            if len(indices_orig) > 65535:
                raise RuntimeError("uint16 XZSM batch overflow")
            positions = vertices[indices_orig]
            quake = quake_xyz(positions)
            light = vertex_light(positions, normals[indices_orig])
            uvs = uv[indices_orig]
            vertex_bytes = bytearray()
            for q, t, c in zip(quake, uvs, light):
                vertex_bytes += struct.pack(
                    "<5f4B",float(q[0]),float(q[1]),float(q[2]),
                    float(t[0]),float(1.0-t[1]), *(int(x) for x in c)
                )
            ids = inverse.astype("<u2", copy=False)
            if len(ids) % 3:
                raise RuntimeError("bad triangle index count")
            bounds = [float(x) for x in np.min(quake,axis=0)]+[float(x) for x in np.max(quake,axis=0)]
            batches.append((texture_path, len(indices_orig), len(ids), bounds, bytes(vertex_bytes), ids.tobytes()))
            triangle_count += len(chunk)
    if missing_uv:
        raise RuntimeError("textured Godot GLB has missing UV coordinates: "+", ".join(missing_uv))
    if not batches:
        raise RuntimeError("GLB had no triangles")
    if len(batches)>512:
        raise RuntimeError("XZSM renderer max batch count exceeded: "+str(len(batches)))
    with mesh_path.open("wb") as f:
        f.write(struct.pack("<4sIIII",b"XZSM",VERSION,len(batches),
                            sum(b[1] for b in batches),sum(b[2] for b in batches)))
        for name, nvertex, nindices, bounds, vblob, iblob in batches:
            utf8 = name.encode("utf-8")
            if len(utf8)>95: raise RuntimeError("texture path > 95 bytes")
            f.write(struct.pack("<II96s6f",nvertex,nindices,
                                utf8.ljust(96,b"\0"),*bounds))
            f.write(vblob)
            f.write(iblob)
    report = {
        "source":str(glb),"output":str(mesh_path),"version":VERSION,
        "mode":"godot-glb-mesh-plus-static-candle-vertex-light-NOT-pbr",
        "source_mesh_nodes":len(instances),"batches":len(batches),
        "vertices":sum(b[1] for b in batches),"triangles":triangle_count,
        "textures":list(materials.values()),"lightmap_uv2_exported":False,
        "normal_map_runtime":False,"pbr_shader_runtime":False,
        "texture_max":texture_max,"xy_scale_m_to_quake":SCALE,
    }
    (out/"godot_altar_bridge_report.json").write_text(
        json.dumps(report, indent=2)+"\n",encoding="utf8"
    )
    print("XZIEL_ALTAR_XZSM_V3_GREEN",json.dumps({
        k:report[k] for k in ("version","source_mesh_nodes","batches","vertices","triangles")
    }))
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--glb",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--texture-max",type=int,default=2048)
    p.add_argument("--min-nodes",type=int,default=11)
    args=p.parse_args()
    if args.texture_max not in (256,512,1024,2048,4096):
        p.error("--texture-max must be 256,512,1024,2048,4096")
    write_xzsm(args.glb,args.out,args.texture_max,args.min_nodes)

if __name__=="__main__":
    main()
