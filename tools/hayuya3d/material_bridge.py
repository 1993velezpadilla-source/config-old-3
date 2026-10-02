#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from pathlib import Path


@dataclass
class MaterialBridgeResult:
    source_mesh: str
    refined_mesh: str
    output_glb: str
    sample_count: int
    refined_vertices: int
    method: str = "surface-sample nearest-color projection"
    preserves: str = "base color via vertex colors"
    channels: list[str] | None = None
    dropped_channels: list[str] | None = None
    rebake_required: list[str] | None = None
    fallback_used: bool = False
    future: str = "tangent-space normal + geometry-dependent AO rebake"


@dataclass
class MaterialTransferContext:
    mode: str
    points: Any
    values: Any
    material: Any = None
    channels: list[str] | None = None
    dropped_channels: list[str] | None = None
    max_texture_size: int = 2048


def _deps():
    import numpy as np
    import trimesh
    return np, trimesh


def _scene_meshes(path: Path):
    _, trimesh = _deps()
    scene = trimesh.load(path, force="scene", process=False)
    meshes = []

    if hasattr(scene, "graph") and hasattr(scene, "geometry"):
        for node_name in scene.graph.nodes_geometry:
            transform, geom_name = scene.graph[node_name]
            geom = scene.geometry[geom_name]
            if not hasattr(geom, "faces") or not len(geom.faces):
                continue
            mesh = geom.copy()
            mesh.apply_transform(transform)
            meshes.append(mesh)
    elif hasattr(scene, "faces") and len(scene.faces):
        meshes.append(scene.copy())

    if not meshes:
        raise ValueError(f"no triangle geometry in {path}")
    return meshes


def sample_texture_nearest(texture, uv):
    np, _ = _deps()
    texture = np.asarray(texture)
    if texture.ndim == 2:
        texture = np.repeat(texture[..., None], 3, axis=2)
    texture = texture[..., :3]
    h, w = texture.shape[:2]
    u = np.mod(uv[:, 0], 1.0)
    v = np.mod(uv[:, 1], 1.0)
    x = np.clip(np.rint(u * (w - 1)).astype(np.int64), 0, w - 1)
    y = np.clip(np.rint((1.0 - v) * (h - 1)).astype(np.int64), 0, h - 1)
    return texture[y, x, :3].astype(np.float32)


def _material_image(material):
    if material is None:
        return None
    image = getattr(material, "image", None)
    if image is None:
        image = getattr(material, "baseColorTexture", None)
    if image is None:
        return None

    np, _ = _deps()
    try:
        from PIL import Image
        if isinstance(image, Image.Image):
            return np.asarray(image.convert("RGB"), dtype=np.uint8)
        arr = np.asarray(image)
        if arr.ndim == 2:
            arr = np.repeat(arr[..., None], 3, axis=2)
        return np.clip(arr[..., :3], 0, 255).astype(np.uint8)
    except Exception:
        return None


def _surface_samples_with_color(mesh, count: int):
    np, trimesh = _deps()
    points, face_ids = trimesh.sample.sample_surface(mesh, count)
    face_ids = np.asarray(face_ids, dtype=np.int64)
    triangles = np.asarray(mesh.triangles[face_ids], dtype=np.float64)
    bary = trimesh.triangles.points_to_barycentric(
        triangles,
        np.asarray(points, dtype=np.float64),
    )

    visual = getattr(mesh, "visual", None)
    uv = getattr(visual, "uv", None) if visual is not None else None
    material = getattr(visual, "material", None) if visual is not None else None
    texture = _material_image(material)

    colors = None
    if uv is not None and len(uv) == len(mesh.vertices) and texture is not None:
        uv_arr = np.asarray(uv, dtype=np.float64)
        uv_tri = uv_arr[np.asarray(mesh.faces, dtype=np.int64)[face_ids]]
        sample_uv = np.sum(uv_tri * bary[..., None], axis=1)
        colors = sample_texture_nearest(texture, sample_uv)

    if colors is None and visual is not None:
        vertex_colors = None
        direct = getattr(visual, "vertex_colors", None)
        if direct is not None and len(direct) == len(mesh.vertices):
            vertex_colors = np.asarray(direct[:, :3], dtype=np.float32)
        else:
            try:
                converted = visual.to_color()
                converted_colors = getattr(converted, "vertex_colors", None)
                if converted_colors is not None and len(converted_colors) == len(mesh.vertices):
                    vertex_colors = np.asarray(converted_colors[:, :3], dtype=np.float32)
            except Exception:
                vertex_colors = None

        if vertex_colors is not None:
            color_tri = vertex_colors[
                np.asarray(mesh.faces, dtype=np.int64)[face_ids]
            ]
            colors = np.sum(color_tri * bary[..., None], axis=1)

    if colors is None:
        colors = np.full((len(points), 3), 190.0, dtype=np.float32)

    return np.asarray(points, dtype=np.float32), np.asarray(colors, dtype=np.float32)


def _material_channels(material) -> list[str]:
    channels = []
    if material is None:
        return channels
    if getattr(material, "baseColorTexture", None) is not None or getattr(material, "image", None) is not None:
        channels.append("baseColor")
    elif getattr(material, "baseColorFactor", None) is not None or getattr(material, "diffuse", None) is not None:
        channels.append("baseColor")
    if getattr(material, "metallicRoughnessTexture", None) is not None:
        channels.extend(["metallic", "roughness"])
    elif getattr(material, "metallicFactor", None) is not None or getattr(material, "roughnessFactor", None) is not None:
        channels.extend(["metallic", "roughness"])
    if getattr(material, "normalTexture", None) is not None:
        channels.append("normal")
    if getattr(material, "occlusionTexture", None) is not None:
        channels.append("occlusion")
    if getattr(material, "emissiveTexture", None) is not None or getattr(material, "emissiveFactor", None) is not None:
        channels.append("emissive")
    return sorted(set(channels))


def sanitize_topology_changed_material(material):
    """
    Return a copy safe for a mesh whose topology/tangent basis has changed.

    Tangent-space normal maps are invalid after arbitrary UV/topology reprojection.
    Baked AO is geometry-dependent and can also become stale after refinement/retopo.
    Preserve appearance/material channels that remain meaningful under UV reprojection,
    but require normal/AO rebake against the new geometry.
    """
    if material is None:
        return None, []

    copied = material.copy() if hasattr(material, "copy") else material
    dropped: list[str] = []

    if getattr(copied, "normalTexture", None) is not None:
        try:
            copied.normalTexture = None
            dropped.append("normal")
        except Exception:
            pass

    if getattr(copied, "occlusionTexture", None) is not None:
        try:
            copied.occlusionTexture = None
            dropped.append("occlusion")
        except Exception:
            pass

    return copied, sorted(set(dropped))


def _constant_material_from_mesh(mesh):
    np, trimesh = _deps()
    visual = getattr(mesh, "visual", None)
    color = np.array([190, 190, 190, 255], dtype=np.uint8)
    if visual is not None:
        direct = getattr(visual, "vertex_colors", None)
        if direct is not None and len(direct):
            arr = np.asarray(direct, dtype=np.float32)
            color = np.clip(np.mean(arr, axis=0), 0, 255).astype(np.uint8)
        else:
            try:
                main = getattr(getattr(visual, "material", None), "main_color", None)
                if main is not None:
                    color = np.asarray(main, dtype=np.uint8).reshape(-1)[:4]
                    if len(color) == 3:
                        color = np.concatenate([color, [255]]).astype(np.uint8)
            except Exception:
                pass
    return trimesh.visual.material.SimpleMaterial(diffuse=color)


def build_source_pbr_uv_cloud(
    source_mesh: Path,
    *,
    total_samples: int = 250_000,
    max_texture_size: int = 2048,
):
    """
    Pack source materials into one atlas, sample the source surface, and retain
    packed UV coordinates at those samples. Reprojecting these UVs to new topology
    lets the refined mesh reuse the same packed PBR textures without CPU rebaking.
    """
    np, trimesh = _deps()
    meshes = _scene_meshes(source_mesh)

    materials = []
    uv_sets = []
    vertices_parts = []
    faces_parts = []
    offset = 0
    any_real_uv = False
    any_pbr_signal = False

    for mesh in meshes:
        visual = getattr(mesh, "visual", None)
        uv = getattr(visual, "uv", None) if visual is not None else None
        material = getattr(visual, "material", None) if visual is not None else None

        if uv is not None and len(uv) == len(mesh.vertices):
            uv_arr = np.asarray(uv, dtype=np.float64)
            any_real_uv = True
        else:
            # Constant fallback UV is valid only for non-textured/constant material.
            uv_arr = np.full((len(mesh.vertices), 2), 0.5, dtype=np.float64)

        if material is None:
            material = _constant_material_from_mesh(mesh)

        channels = _material_channels(material)
        if any(name in channels for name in ("metallic", "roughness", "normal", "occlusion", "emissive")):
            any_pbr_signal = True
        if "baseColor" in channels and uv is not None:
            any_pbr_signal = True

        materials.append(material)
        uv_sets.append(uv_arr)
        vertices_parts.append(np.asarray(mesh.vertices, dtype=np.float64))
        faces_parts.append(np.asarray(mesh.faces, dtype=np.int64) + offset)
        offset += len(mesh.vertices)

    if not any_real_uv or not any_pbr_signal:
        raise ValueError("source has no transferable UV/PBR material evidence")

    packed_material, packed_uv = trimesh.visual.material.pack(
        materials,
        uv_sets,
        deduplicate=False,
        max_tex_size_individual=max_texture_size,
        max_tex_size_fused=max_texture_size,
    )
    packed_uv = np.asarray(packed_uv, dtype=np.float64)
    vertices = np.concatenate(vertices_parts, axis=0)
    faces = np.concatenate(faces_parts, axis=0)

    packed_mesh = trimesh.Trimesh(
        vertices=vertices,
        faces=faces,
        process=False,
        visual=trimesh.visual.TextureVisuals(
            uv=packed_uv,
            material=packed_material,
        ),
    )

    points, face_ids = trimesh.sample.sample_surface(packed_mesh, total_samples)
    face_ids = np.asarray(face_ids, dtype=np.int64)
    triangles = np.asarray(packed_mesh.triangles[face_ids], dtype=np.float64)
    bary = trimesh.triangles.points_to_barycentric(
        triangles,
        np.asarray(points, dtype=np.float64),
    )
    uv_tri = packed_uv[np.asarray(packed_mesh.faces, dtype=np.int64)[face_ids]]
    sample_uv = np.sum(uv_tri * bary[..., None], axis=1).astype(np.float32)

    channels = _material_channels(packed_material)
    if "baseColor" not in channels:
        channels.insert(0, "baseColor")

    return (
        np.asarray(points, dtype=np.float32),
        sample_uv,
        packed_material,
        channels,
    )


def prepare_material_transfer(
    source_mesh: Path,
    *,
    total_samples: int = 250_000,
    max_texture_size: int = 2048,
) -> MaterialTransferContext:
    try:
        points, uvs, material, channels = build_source_pbr_uv_cloud(
            source_mesh,
            total_samples=total_samples,
            max_texture_size=max_texture_size,
        )
        safe_material, dropped = sanitize_topology_changed_material(material)
        safe_channels = [channel for channel in channels if channel not in set(dropped)]
        return MaterialTransferContext(
            mode="pbr_uv",
            points=points,
            values=uvs,
            material=safe_material,
            channels=safe_channels,
            dropped_channels=dropped,
            max_texture_size=max_texture_size,
        )
    except Exception:
        points, colors = build_source_color_cloud(
            source_mesh,
            total_samples=total_samples,
        )
        return MaterialTransferContext(
            mode="base_color",
            points=points,
            values=colors,
            material=None,
            channels=["baseColor"],
            dropped_channels=[],
            max_texture_size=max_texture_size,
        )


def transfer_material_from_context(
    source_mesh: Path,
    context: MaterialTransferContext,
    refined_mesh: Path,
    output_glb: Path,
) -> MaterialBridgeResult:
    np, trimesh = _deps()
    from scipy.spatial import cKDTree

    points = np.asarray(context.points, dtype=np.float32)
    values = np.asarray(context.values)
    if len(points) == 0 or len(points) != len(values):
        raise ValueError("invalid Material Bridge transfer context")

    tree = cKDTree(points)
    refined_meshes = _scene_meshes(refined_mesh)
    refined = trimesh.util.concatenate(refined_meshes)
    vertices = np.asarray(refined.vertices, dtype=np.float32)

    projected_ids = np.empty(len(vertices), dtype=np.int64)
    chunk = 200_000
    for start in range(0, len(vertices), chunk):
        end = min(len(vertices), start + chunk)
        _, ids = tree.query(vertices[start:end], k=1, workers=-1)
        projected_ids[start:end] = ids

    if context.mode == "pbr_uv":
        projected_uv = np.asarray(values[projected_ids], dtype=np.float64)
        refined.visual = trimesh.visual.TextureVisuals(
            uv=projected_uv,
            material=context.material.copy() if hasattr(context.material, "copy") else context.material,
        )
        method = "surface-sample nearest-UV topology-safe PBR atlas projection"
        preserves = "baseColor/metallic/roughness/emissive PBR evidence through reprojected UVs; topology-dependent channels are stripped"
        fallback = False
    elif context.mode == "base_color":
        projected = np.clip(values[projected_ids], 0, 255).astype(np.uint8)
        alpha = np.full((len(vertices), 1), 255, dtype=np.uint8)
        rgba = np.concatenate([projected, alpha], axis=1)
        refined.visual = trimesh.visual.ColorVisuals(
            refined,
            vertex_colors=rgba,
        )
        method = "surface-sample nearest-color projection"
        preserves = "base color via vertex colors"
        fallback = True
    else:
        raise ValueError(f"unknown Material Bridge context mode: {context.mode}")

    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_glb.write_bytes(
        trimesh.exchange.gltf.export_glb(
            trimesh.Scene(refined),
            include_normals=True,
        )
    )
    if output_glb.read_bytes()[:4] != b"glTF":
        raise RuntimeError("Material Bridge produced invalid GLB")

    return MaterialBridgeResult(
        source_mesh=str(source_mesh),
        refined_mesh=str(refined_mesh),
        output_glb=str(output_glb),
        sample_count=len(points),
        refined_vertices=len(vertices),
        method=method,
        preserves=preserves,
        channels=list(context.channels or []),
        dropped_channels=list(context.dropped_channels or []),
        rebake_required=list(context.dropped_channels or []),
        fallback_used=fallback,
    )


def build_source_color_cloud(source_mesh: Path, total_samples: int = 250_000):
    np, _ = _deps()
    meshes = _scene_meshes(source_mesh)
    areas = np.asarray([max(float(m.area), 1e-9) for m in meshes], dtype=np.float64)
    weights = areas / areas.sum()

    points_all = []
    colors_all = []
    remaining = total_samples
    for index, (mesh, weight) in enumerate(zip(meshes, weights)):
        if index == len(meshes) - 1:
            count = max(1000, remaining)
        else:
            count = max(1000, int(round(total_samples * float(weight))))
            remaining -= count
        points, colors = _surface_samples_with_color(mesh, count)
        points_all.append(points)
        colors_all.append(colors)

    return np.concatenate(points_all, axis=0), np.concatenate(colors_all, axis=0)


def transfer_base_color_from_cloud(
    source_mesh: Path,
    points,
    colors,
    refined_mesh: Path,
    output_glb: Path,
) -> MaterialBridgeResult:
    np, trimesh = _deps()
    from scipy.spatial import cKDTree

    points = np.asarray(points, dtype=np.float32)
    colors = np.asarray(colors, dtype=np.float32)
    if len(points) == 0 or len(points) != len(colors):
        raise ValueError("invalid Material Bridge color cloud")

    tree = cKDTree(points)
    refined_meshes = _scene_meshes(refined_mesh)
    refined = trimesh.util.concatenate(refined_meshes)
    vertices = np.asarray(refined.vertices, dtype=np.float32)

    projected = np.empty((len(vertices), 3), dtype=np.uint8)
    chunk = 200_000
    for start in range(0, len(vertices), chunk):
        end = min(len(vertices), start + chunk)
        _, ids = tree.query(vertices[start:end], k=1, workers=-1)
        projected[start:end] = np.clip(colors[ids], 0, 255).astype(np.uint8)

    alpha = np.full((len(vertices), 1), 255, dtype=np.uint8)
    rgba = np.concatenate([projected, alpha], axis=1)
    refined.visual = trimesh.visual.ColorVisuals(
        refined,
        vertex_colors=rgba,
    )

    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_glb.write_bytes(
        trimesh.exchange.gltf.export_glb(
            trimesh.Scene(refined),
            include_normals=True,
        )
    )
    if output_glb.read_bytes()[:4] != b"glTF":
        raise RuntimeError("Material Bridge produced invalid GLB")

    return MaterialBridgeResult(
        source_mesh=str(source_mesh),
        refined_mesh=str(refined_mesh),
        output_glb=str(output_glb),
        sample_count=len(points),
        refined_vertices=len(vertices),
        channels=["baseColor"],
        dropped_channels=[],
        rebake_required=[],
        fallback_used=True,
    )


def transfer_best_material(
    source_mesh: Path,
    refined_mesh: Path,
    output_glb: Path,
    *,
    total_samples: int = 250_000,
    max_texture_size: int = 2048,
) -> MaterialBridgeResult:
    context = prepare_material_transfer(
        source_mesh,
        total_samples=total_samples,
        max_texture_size=max_texture_size,
    )
    return transfer_material_from_context(
        source_mesh,
        context,
        refined_mesh,
        output_glb,
    )


def transfer_base_color(
    source_mesh: Path,
    refined_mesh: Path,
    output_glb: Path,
    *,
    total_samples: int = 250_000,
) -> MaterialBridgeResult:
    points, colors = build_source_color_cloud(
        source_mesh,
        total_samples=total_samples,
    )
    return transfer_base_color_from_cloud(
        source_mesh,
        points,
        colors,
        refined_mesh,
        output_glb,
    )


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="HAYUYA Material Bridge v2 PBR/UV transfer with v1 fallback.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--refined", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=250000)
    parser.add_argument("--texture-size", type=int, default=2048)
    parser.add_argument("--base-color-only", action="store_true")
    args = parser.parse_args()

    if args.base_color_only:
        result = transfer_base_color(
            args.source,
            args.refined,
            args.output,
            total_samples=args.samples,
        )
    else:
        result = transfer_best_material(
            args.source,
            args.refined,
            args.output,
            total_samples=args.samples,
            max_texture_size=args.texture_size,
        )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
