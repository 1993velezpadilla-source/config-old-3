#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class MeshScore:
    path: str
    backend: str
    score: float
    valid: bool
    production_score: float | None = None
    visual_score: float | None = None
    visual_views: list[dict] | None = None
    appearance_score: float | None = None
    appearance_views: list[dict] | None = None
    appearance_detail_score: float | None = None
    appearance_face_detail_score: float | None = None
    appearance_face_detail_min_score: float | None = None
    appearance_details: list[dict] | None = None
    normal_support_score: float | None = None
    normal_support_views: list[dict] | None = None
    vertices: int = 0
    faces: int = 0
    components: int = 0
    watertight: bool = False
    degenerate_ratio: float = 1.0
    has_uv: bool = False
    textured: bool = False
    pbr_channels: list[str] | None = None
    material_score: float = 0.0
    texture_max_edge: int = 0
    base_color_max_edge: int = 0
    base_color_min_edge: int = 0
    texture_resolution_score: float | None = None
    head_region_faces: int = 0
    head_region_vertices: int = 0
    head_region_face_fraction: float | None = None
    global_median_edge_normalized: float | None = None
    head_region_median_edge_normalized: float | None = None
    head_region_density_ratio: float | None = None
    head_density_score: float | None = None
    head_texel_density_ratio: float | None = None
    head_texel_density_score: float | None = None
    head_texture_detail_ratio: float | None = None
    head_texture_detail_score: float | None = None
    head_texture_detail_mean: float | None = None
    head_structure_score: float | None = None
    head_width_body_ratio: float | None = None
    head_depth_body_ratio: float | None = None
    head_flatness_ratio: float | None = None
    head_taper_ratio: float | None = None
    bbox: list[float] | None = None
    notes: list[str] | None = None


def _import_trimesh():
    try:
        import numpy as np
        import trimesh
        return np, trimesh
    except Exception:
        return None, None


def _material_channels(material) -> set[str]:
    channels: set[str] = set()
    if material is None:
        return channels

    if (
        getattr(material, "baseColorTexture", None) is not None
        or getattr(material, "image", None) is not None
        or getattr(material, "baseColorFactor", None) is not None
        or getattr(material, "diffuse", None) is not None
    ):
        channels.add("baseColor")

    if (
        getattr(material, "metallicRoughnessTexture", None) is not None
        or getattr(material, "metallicFactor", None) is not None
    ):
        channels.add("metallic")
    if (
        getattr(material, "metallicRoughnessTexture", None) is not None
        or getattr(material, "roughnessFactor", None) is not None
        or getattr(material, "glossiness", None) is not None
    ):
        channels.add("roughness")
    if getattr(material, "normalTexture", None) is not None:
        channels.add("normal")
    if getattr(material, "occlusionTexture", None) is not None:
        channels.add("occlusion")
    if (
        getattr(material, "emissiveTexture", None) is not None
        or getattr(material, "emissiveFactor", None) is not None
    ):
        channels.add("emissive")
    return channels


def head_density_score_from_ratio(ratio: float | None) -> float | None:
    """Map relative head-vs-global mesh density to a bounded QA score.

    A ratio of 1.0 means the head is at least as dense as the overall mesh.
    Denser heads are capped at 100; coarser heads lose score proportionally.
    Missing telemetry stays neutral rather than inventing a failure.
    """
    if ratio is None or not math.isfinite(float(ratio)):
        return None
    return round(max(0.0, min(100.0, float(ratio) * 100.0)), 3)


def _soft_range_score(value: float, *, hard_lo: float, soft_lo: float, soft_hi: float, hard_hi: float) -> float:
    """Return 0..100 with a flat healthy band and linear catastrophic shoulders."""
    value=float(value)
    if not math.isfinite(value) or value <= hard_lo or value >= hard_hi:
        return 0.0
    if soft_lo <= value <= soft_hi:
        return 100.0
    if value < soft_lo:
        return 100.0 * (value-hard_lo) / max(1e-12, soft_lo-hard_lo)
    return 100.0 * (hard_hi-value) / max(1e-12, hard_hi-soft_hi)


def head_structure_metrics(np, vertices, *, up_axis: int, body_min: float, body_span: float) -> dict:
    """Robust humanoid upper-head sanity telemetry.

    This intentionally catches only gross structural collapses. It does not try
    to force realistic beauty/proportions onto stylized characters, hoods, hair,
    helmets or zombie silhouettes.
    """
    points=np.asarray(vertices,dtype=np.float64)
    if points.ndim!=2 or points.shape[1] < 3 or len(points) < 32:
        return {"score":None}

    norm=(points[:,up_axis]-float(body_min))/max(1e-12,float(body_span))
    head=points[(norm>=0.82)&(norm<=1.005)]
    if len(head)<24:
        return {"score":None}

    transverse=[axis for axis in (0,1,2) if axis!=up_axis]
    spans=[]
    for axis in transverse:
        lo=float(np.percentile(head[:,axis],5.0))
        hi=float(np.percentile(head[:,axis],95.0))
        spans.append(max(0.0,hi-lo))
    width=max(spans)
    depth=min(spans)
    width_ratio=width/max(1e-12,float(body_span))
    depth_ratio=depth/max(1e-12,float(body_span))
    flatness=depth/max(width,1e-12)

    upper=points[(norm>=0.90)&(norm<=0.985)]
    lower=points[(norm>=0.835)&(norm<0.90)]
    taper=None
    if len(upper)>=12 and len(lower)>=12:
        def robust_width(block):
            local=[]
            for axis in transverse:
                lo=float(np.percentile(block[:,axis],8.0))
                hi=float(np.percentile(block[:,axis],92.0))
                local.append(max(0.0,hi-lo))
            return max(local)
        upper_width=robust_width(upper)
        lower_width=robust_width(lower)
        if upper_width>1e-12:
            taper=lower_width/upper_width

    width_score=_soft_range_score(
        width_ratio,hard_lo=0.035,soft_lo=0.085,soft_hi=0.30,hard_hi=0.48
    )
    depth_score=_soft_range_score(
        depth_ratio,hard_lo=0.018,soft_lo=0.055,soft_hi=0.24,hard_hi=0.40
    )
    flat_score=_soft_range_score(
        flatness,hard_lo=0.10,soft_lo=0.30,soft_hi=1.0,hard_hi=1.01
    )
    if taper is None:
        taper_score=100.0
    else:
        taper_score=_soft_range_score(
            taper,hard_lo=0.18,soft_lo=0.42,soft_hi=1.55,hard_hi=2.25
        )

    score=0.30*width_score+0.25*depth_score+0.25*flat_score+0.20*taper_score
    return {
        "score":round(max(0.0,min(100.0,score)),3),
        "width_body_ratio":round(width_ratio,5),
        "depth_body_ratio":round(depth_ratio,5),
        "flatness_ratio":round(flatness,5),
        "taper_ratio":round(float(taper),5) if taper is not None else None,
        "samples":int(len(head)),
    }


def _sample_uv_luma_gradients(np, image, uv_centers, mask, max_samples: int = 4096):
    if image is None or uv_centers is None or mask is None:
        return np.asarray([], dtype=np.float64)
    try:
        rgb=np.asarray(image.convert("RGB"),dtype=np.float32)
    except Exception:
        return np.asarray([],dtype=np.float64)
    if rgb.ndim!=3 or rgb.shape[0]<2 or rgb.shape[1]<2:
        return np.asarray([],dtype=np.float64)
    indices=np.flatnonzero(mask)
    if len(indices)==0:
        return np.asarray([],dtype=np.float64)
    if len(indices)>max_samples:
        picks=np.linspace(0,len(indices)-1,max_samples,dtype=np.int64)
        indices=indices[picks]
    uv=np.asarray(uv_centers[indices],dtype=np.float64)
    u=np.mod(uv[:,0],1.0)
    v=np.mod(uv[:,1],1.0)
    height,width=rgb.shape[:2]
    x=np.clip((u*(width-1)).astype(np.int64),0,width-2)
    y=np.clip(((1.0-v)*(height-1)).astype(np.int64),0,height-2)
    luma=(
        rgb[:,:,0]*0.2126
        + rgb[:,:,1]*0.7152
        + rgb[:,:,2]*0.0722
    )
    center=luma[y,x]
    dx=np.abs(luma[y,x+1]-center)
    dy=np.abs(luma[y+1,x]-center)
    values=(dx+dy)*0.5
    return values[np.isfinite(values)]


def _component_count(faces) -> int:
    """Count vertex-connected triangle components without networkx/scipy."""
    import numpy as np

    faces = np.asarray(faces, dtype=np.int64)
    if faces.size == 0:
        return 0
    used = np.unique(faces.reshape(-1))
    parent = {int(v): int(v) for v in used}

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != x:
            nxt = parent[x]
            parent[x] = root
            x = nxt
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b, d in faces:
        union(int(a), int(b))
        union(int(a), int(d))

    return len({find(int(v)) for v in used})


def _basic_valid(path: Path) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not path.is_file():
        return False, ["missing file"]
    size = path.stat().st_size
    if size < 256:
        return False, [f"file too small: {size} bytes"]
    if path.suffix.lower() == ".glb":
        if path.read_bytes()[:4] != b"glTF":
            return False, ["bad GLB magic"]
    elif path.suffix.lower() not in {".obj", ".gltf", ".ply", ".stl"}:
        notes.append(f"unrecognized mesh extension: {path.suffix}")
    return True, notes


def inspect_mesh(
    path: Path,
    *,
    backend: str = "unknown",
    mode: str = "prop",
    target_faces: int = 100_000,
    target_texture_size: int | None = None,
) -> MeshScore:
    valid, notes = _basic_valid(path)
    result = MeshScore(
        path=str(path),
        backend=backend,
        score=0.0,
        valid=valid,
        notes=notes,
    )
    if not valid:
        return result

    np, trimesh = _import_trimesh()
    if trimesh is None:
        # File-level fallback keeps Hayuya usable in lightweight CI.
        size_mb = path.stat().st_size / (1024 * 1024)
        result.score = round(min(45.0, 20.0 + math.log2(max(size_mb, 0.01) + 1) * 8.0), 3)
        result.notes.append("trimesh unavailable: file-level score only")
        return result

    try:
        loaded = trimesh.load(path, force="scene", process=False)
        if hasattr(loaded, "dump"):
            try:
                geometries = list(loaded.dump(concatenate=False))
            except Exception:
                geometries = list(loaded.geometry.values()) if hasattr(loaded, "geometry") else [loaded]
        else:
            geometries = [loaded]
        meshes = [g for g in geometries if hasattr(g, "faces") and len(g.faces)]
        if not meshes:
            result.valid = False
            result.notes.append("no triangle mesh geometry")
            return result

        # Build a geometry-only aggregate for topology metrics. Concatenating
        # textured/PBR visuals can invoke visual/material conversion paths and make
        # mesh health depend on material implementation details. Material evidence
        # is inspected separately on the original geometries below.
        metric_meshes = [
            trimesh.Trimesh(
                vertices=np.asarray(g.vertices),
                faces=np.asarray(g.faces),
                process=False,
            )
            for g in meshes
        ]
        mesh = trimesh.util.concatenate(metric_meshes)
        result.vertices = int(len(mesh.vertices))
        result.faces = int(len(mesh.faces))
        result.components = _component_count(mesh.faces)
        result.watertight = bool(mesh.is_watertight)

        areas = np.asarray(mesh.area_faces)
        if len(areas):
            finite = areas[np.isfinite(areas)]
            if len(finite):
                scale = max(float(np.median(finite)), 1e-15)
                result.degenerate_ratio = float(np.mean(areas <= scale * 1e-6))
            else:
                result.degenerate_ratio = 1.0

        extents = np.asarray(mesh.extents, dtype=float)
        result.bbox = [round(float(x), 8) for x in extents.tolist()]

        character_up_axis = None
        character_body_min = None
        character_body_span = None
        if mode == "character" and len(mesh.faces):
            up_axis = int(np.argmax(np.abs(extents)))
            body_min = float(np.min(mesh.vertices[:, up_axis]))
            body_span = max(1e-12, float(extents[up_axis]))
            character_up_axis = up_axis
            character_body_min = body_min
            character_body_span = body_span
            all_faces = np.asarray(mesh.faces)
            all_tri = np.asarray(mesh.vertices)[all_faces]
            all_edges = np.concatenate(
                (
                    np.linalg.norm(all_tri[:,0]-all_tri[:,1],axis=1),
                    np.linalg.norm(all_tri[:,1]-all_tri[:,2],axis=1),
                    np.linalg.norm(all_tri[:,2]-all_tri[:,0],axis=1),
                )
            )
            finite_global_edges = all_edges[
                np.isfinite(all_edges) & (all_edges>1e-12)
            ]
            body_diag = max(1e-12, float(np.linalg.norm(extents)))
            global_median_edge = None
            if len(finite_global_edges):
                global_median_edge = float(np.median(finite_global_edges))
                result.global_median_edge_normalized = round(
                    global_median_edge/body_diag,
                    8,
                )

            structure=head_structure_metrics(
                np,
                np.asarray(mesh.vertices,dtype=np.float64),
                up_axis=up_axis,
                body_min=body_min,
                body_span=body_span,
            )
            result.head_structure_score=structure.get("score")
            result.head_width_body_ratio=structure.get("width_body_ratio")
            result.head_depth_body_ratio=structure.get("depth_body_ratio")
            result.head_flatness_ratio=structure.get("flatness_ratio")
            result.head_taper_ratio=structure.get("taper_ratio")
            if result.head_structure_score is not None:
                result.notes.append(
                    "head structure "
                    f"score={result.head_structure_score:.1f} "
                    f"width/body={result.head_width_body_ratio:.3f} "
                    f"depth/body={result.head_depth_body_ratio:.3f} "
                    f"flatness={result.head_flatness_ratio:.3f} "
                    f"taper={result.head_taper_ratio if result.head_taper_ratio is not None else 'n/a'}"
                )
                if result.head_structure_score < 45.0:
                    result.notes.append(
                        "head structure is a gross-shape outlier; demote before character promotion"
                    )

            face_centers = np.asarray(mesh.triangles_center)[:, up_axis]
            head_mask = ((face_centers - body_min) / body_span) >= 0.72
            head_face_indices = np.nonzero(head_mask)[0]
            result.head_region_faces = int(len(head_face_indices))
            if len(head_face_indices):
                head_faces = all_faces[head_face_indices]
                head_vertices = np.unique(head_faces.reshape(-1))
                result.head_region_vertices = int(len(head_vertices))
                result.head_region_face_fraction = round(
                    result.head_region_faces / max(1, result.faces),
                    6,
                )
                tri = np.asarray(mesh.vertices)[head_faces]
                edges = np.concatenate(
                    (
                        np.linalg.norm(tri[:,0]-tri[:,1],axis=1),
                        np.linalg.norm(tri[:,1]-tri[:,2],axis=1),
                        np.linalg.norm(tri[:,2]-tri[:,0],axis=1),
                    )
                )
                finite_edges = edges[np.isfinite(edges) & (edges>1e-12)]
                if len(finite_edges):
                    head_median_edge=float(np.median(finite_edges))
                    result.head_region_median_edge_normalized = round(
                        head_median_edge/body_diag,
                        8,
                    )
                    if global_median_edge is not None and head_median_edge>1e-12:
                        result.head_region_density_ratio=round(
                            global_median_edge/head_median_edge,
                            4,
                        )
                        result.head_density_score=head_density_score_from_ratio(
                            result.head_region_density_ratio
                        )
                        if result.head_region_density_ratio < 1.0:
                            result.notes.append(
                                f"head region is coarser than global mesh: "
                                f"density_ratio={result.head_region_density_ratio:.3f}x"
                            )

        has_uv = False
        textured = False
        pbr_channels: set[str] = set()
        for g in meshes:
            visual = getattr(g, "visual", None)
            uv = getattr(visual, "uv", None)
            if uv is not None and len(uv):
                has_uv = True
            kind = str(getattr(visual, "kind", "")).lower()
            material = getattr(visual, "material", None)
            if "texture" in kind or material is not None:
                textured = True
            pbr_channels.update(_material_channels(material))
        result.has_uv = has_uv
        result.textured = textured
        result.pbr_channels = sorted(pbr_channels)

        if (
            mode == "character"
            and character_up_axis is not None
            and character_body_min is not None
            and character_body_span is not None
        ):
            global_surface_area = 0.0
            global_texel_area = 0.0
            head_surface_area = 0.0
            head_texel_area = 0.0
            global_texture_gradients = []
            head_texture_gradients = []

            for g in meshes:
                visual = getattr(g, "visual", None)
                uv = getattr(visual, "uv", None) if visual is not None else None
                material_obj = getattr(visual, "material", None) if visual is not None else None
                base_image = (
                    getattr(material_obj, "baseColorTexture", None)
                    if material_obj is not None else None
                )
                if base_image is None and material_obj is not None:
                    base_image = getattr(material_obj, "image", None)
                if uv is None or len(uv) != len(g.vertices) or base_image is None:
                    continue

                image_size = getattr(base_image, "size", None)
                if not image_size or len(image_size) < 2:
                    continue
                texture_pixels = max(1.0, float(image_size[0]) * float(image_size[1]))

                vertices_g = np.asarray(g.vertices, dtype=np.float64)
                faces_g = np.asarray(g.faces, dtype=np.int64)
                if not len(faces_g):
                    continue
                uv_arr = np.asarray(uv, dtype=np.float64)
                uv_tri = uv_arr[faces_g]
                uv_cross = (
                    (uv_tri[:,1,0]-uv_tri[:,0,0]) * (uv_tri[:,2,1]-uv_tri[:,0,1])
                    - (uv_tri[:,1,1]-uv_tri[:,0,1]) * (uv_tri[:,2,0]-uv_tri[:,0,0])
                )
                uv_area = 0.5 * np.abs(uv_cross) * texture_pixels
                surface_area = np.asarray(g.area_faces, dtype=np.float64)
                finite = (
                    np.isfinite(uv_area)
                    & np.isfinite(surface_area)
                    & (uv_area > 1e-12)
                    & (surface_area > 1e-12)
                )
                if not np.any(finite):
                    continue

                face_centers_g = vertices_g[faces_g].mean(axis=1)[:, character_up_axis]
                head_mask_g = (
                    (face_centers_g - character_body_min) / character_body_span
                ) >= 0.72
                valid_head = finite & head_mask_g
                uv_centers = uv_tri.mean(axis=1)
                global_gradients = _sample_uv_luma_gradients(
                    np,
                    base_image,
                    uv_centers,
                    finite,
                )
                head_gradients = _sample_uv_luma_gradients(
                    np,
                    base_image,
                    uv_centers,
                    valid_head,
                )
                if len(global_gradients):
                    global_texture_gradients.append(global_gradients)
                if len(head_gradients):
                    head_texture_gradients.append(head_gradients)

                global_surface_area += float(surface_area[finite].sum())
                global_texel_area += float(uv_area[finite].sum())
                if np.any(valid_head):
                    head_surface_area += float(surface_area[valid_head].sum())
                    head_texel_area += float(uv_area[valid_head].sum())

            if (
                global_surface_area > 1e-12
                and global_texel_area > 1e-12
                and head_surface_area > 1e-12
                and head_texel_area > 1e-12
            ):
                global_density = global_texel_area / global_surface_area
                head_density = head_texel_area / head_surface_area
                ratio = head_density / max(global_density, 1e-12)
                result.head_texel_density_ratio = round(float(ratio), 4)
                result.head_texel_density_score = round(
                    max(0.0, min(100.0, float(ratio) * 100.0)),
                    3,
                )
                if ratio < 1.0:
                    result.notes.append(
                        f"head visible-color texel density is below global mesh: "
                        f"ratio={ratio:.3f}x"
                    )

            if global_texture_gradients and head_texture_gradients:
                global_values=np.concatenate(global_texture_gradients)
                head_values=np.concatenate(head_texture_gradients)
                global_mean=float(np.mean(global_values)) if len(global_values) else 0.0
                head_mean=float(np.mean(head_values)) if len(head_values) else 0.0
                if global_mean>1e-6 and math.isfinite(global_mean) and math.isfinite(head_mean):
                    detail_ratio=head_mean/global_mean
                    result.head_texture_detail_ratio=round(detail_ratio,4)
                    result.head_texture_detail_score=round(
                        max(0.0,min(100.0,detail_ratio*100.0)),
                        3,
                    )
                    result.head_texture_detail_mean=round(head_mean,4)
                    result.notes.append(
                        f"head visible-color local detail ratio={detail_ratio:.3f}x "
                        f"gradient={head_mean:.3f}"
                    )

        texture_resolution_factor = 1.0
        if path.suffix.lower() == ".glb":
            try:
                from texture_gate import inspect as inspect_textures
                texture_report = inspect_textures(
                    path,
                    min_edge=1,
                    min_base_color_edge=1,
                )
                result.texture_max_edge = int(texture_report.max_edge)
                result.base_color_max_edge = int(texture_report.base_color_max_edge)
                result.base_color_min_edge = int(texture_report.base_color_min_edge)
                if result.base_color_min_edge > 0:
                    if target_texture_size is not None:
                        texture_resolution_factor = min(
                            1.0,
                            result.base_color_min_edge / max(1.0, float(target_texture_size)),
                        )
                        result.texture_resolution_score = round(
                            texture_resolution_factor * 100.0,
                            3,
                        )
                        result.notes.append(
                            f"baseColor resolution weakest={result.base_color_min_edge}px "
                            f"strongest={result.base_color_max_edge}px "
                            f"target={int(target_texture_size)}px"
                        )
                    else:
                        result.texture_resolution_score = 100.0
                        result.notes.append(
                            f"baseColor resolution weakest={result.base_color_min_edge}px "
                            f"strongest={result.base_color_max_edge}px "
                            "(no profile texture target applied)"
                        )
                elif texture_report.image_count and target_texture_size is not None:
                    texture_resolution_factor = 0.45
                    result.texture_resolution_score = 45.0
                    result.notes.append(
                        "embedded textures exist but no baseColor image binding was found"
                    )
            except Exception as exc:
                result.notes.append(
                    f"texture role inspection unavailable: {type(exc).__name__}: {exc}"
                )

        if result.faces < 50:
            result.notes.append("extremely low face count")
        if result.components > 12:
            result.notes.append(f"many disconnected components: {result.components}")
        if result.degenerate_ratio > 0.02:
            result.notes.append(f"high degenerate ratio: {result.degenerate_ratio:.4f}")
        if not np.all(np.isfinite(mesh.vertices)):
            result.valid = False
            result.notes.append("non-finite vertices")
            return result

        # Hayuya Judge v1: geometry capacity + topology health + production readiness.
        face_ratio = min(1.0, result.faces / max(1, target_faces))
        face_floor = min(1.0, result.faces / 5000.0)
        geometry = 0.70 * face_ratio + 0.30 * face_floor

        comp_penalty = min(0.45, max(0, result.components - 1) * 0.04)
        degen_penalty = min(0.55, result.degenerate_ratio * 12.0)
        health = max(0.0, 1.0 - comp_penalty - degen_penalty)

        # Closed meshes matter more for props/architecture; cloth/characters may intentionally be open.
        if mode in {"prop", "architecture"}:
            health = min(1.0, health + (0.10 if result.watertight else -0.05))
        elif result.watertight:
            health = min(1.0, health + 0.03)

        # Material readiness is channel-aware. This remains only 18% of
        # production score, so PBR completeness can improve a close call but cannot
        # override contradictory real-source visual evidence.
        material = 0.0
        channels = set(result.pbr_channels or [])
        if result.has_uv:
            material += 0.25
        if "baseColor" in channels:
            # A 1K visible baseColor should not receive the same production
            # credit as the 4K target of Monster/Ultra. Resolution influences
            # only the bounded material sub-score; source fidelity remains
            # dominated by the real-image Judges.
            material += 0.45 * (0.35 + 0.65 * texture_resolution_factor)
        elif result.textured:
            # Unknown/legacy texture still gets partial credit.
            material += 0.30 * (0.55 + 0.45 * texture_resolution_factor)
        if "normal" in channels:
            material += 0.10
        if "roughness" in channels:
            material += 0.10
        if "metallic" in channels:
            material += 0.05
        if "occlusion" in channels:
            material += 0.05
        material = min(1.0, material)
        result.material_score = round(material * 100.0, 3)
        if channels:
            result.notes.append("material channels: " + ",".join(sorted(channels)))

        bbox_health = 1.0
        if result.bbox:
            positive = [x for x in result.bbox if x > 1e-9]
            if len(positive) != 3:
                bbox_health = 0.0
                result.notes.append("collapsed bounding box axis")
            else:
                ratio = max(positive) / min(positive)
                if ratio > 100:
                    bbox_health = 0.55
                    result.notes.append(f"extreme bbox aspect ratio: {ratio:.1f}")

        if mode == "character" and result.head_density_score is not None:
            # Head quality has two independent failure modes: local resolution and
            # gross 3D structure. Keep both bounded so source-image Judges still
            # dominate identity, but a needle-flat/collapsed head cannot hide behind
            # a dense torso or a high-resolution texture.
            structure_factor=(
                result.head_structure_score/100.0
                if result.head_structure_score is not None else 0.75
            )
            raw = (
                geometry * 0.34
                + (result.head_density_score / 100.0) * 0.04
                + structure_factor * 0.04
                + health * 0.33
                + material * 0.18
                + bbox_health * 0.07
            )
        else:
            raw = (
                geometry * 0.42
                + health * 0.33
                + material * 0.18
                + bbox_health * 0.07
            )
        result.score = round(max(0.0, min(100.0, raw * 100.0)), 3)
        result.production_score = result.score
        return result
    except Exception as exc:
        result.valid = False
        result.notes.append(f"mesh inspection failed: {type(exc).__name__}: {exc}")
        return result


def character_quality_evidence_complete(
    item: MeshScore,
    *,
    identity_required: bool=False,
) -> bool:
    """Return whether a character candidate has the evidence QA needs to ship."""
    names=[
        "head_density_score",
        "head_texel_density_score",
        "head_texture_detail_score",
    ]
    if identity_required:
        names.append("appearance_face_detail_min_score")
    for name in names:
        value=getattr(item,name,None)
        try:
            if not math.isfinite(float(value)):
                return False
        except (TypeError,ValueError):
            return False
    return True


def candidate_rank_key(
    item: MeshScore,
    *,
    mode: str,
    identity_required: bool=False,
) -> tuple:
    evidence_ready=(
        character_quality_evidence_complete(
            item,
            identity_required=identity_required,
        )
        if mode=="character"
        else True
    )
    structure=getattr(item,"head_structure_score",None)
    structure_ready=True
    if mode=="character" and structure is not None:
        try:
            structure_ready=math.isfinite(float(structure)) and float(structure)>=45.0
        except (TypeError,ValueError):
            structure_ready=False
    return (
        bool(item.valid),
        bool(evidence_ready),
        bool(structure_ready),
        float(item.score),
    )


def rank_candidates(
    candidates: Iterable[tuple[str, Path]],
    *,
    mode: str,
    target_faces: int,
    target_texture_size: int | None = None,
    source_images: list[Path] | None = None,
    detail_images: list[Path] | None = None,
    visual_weight: float = 0.55,
    appearance_mode: str = "off",
    appearance_model_root: Path | None = None,
    appearance_render_root: Path | None = None,
    appearance_weight: float = 0.25,
    normal_support_images: dict[str, Path] | None = None,
    normal_support_weight: float = 0.06,
) -> list[MeshScore]:
    scores = [
        inspect_mesh(
            path,
            backend=backend,
            mode=mode,
            target_faces=target_faces,
            target_texture_size=target_texture_size,
        )
        for backend, path in candidates
    ]

    if source_images:
        try:
            from visual_judge import score_candidate as score_visual
            from dataclasses import asdict as _asdict
        except Exception:
            score_visual = None
            _asdict = None

        if score_visual is not None:
            for item in scores:
                if not item.valid:
                    continue
                try:
                    visual = score_visual(Path(item.path), source_images)
                    item.production_score = item.production_score if item.production_score is not None else item.score
                    item.visual_score = visual.score
                    item.visual_views = [_asdict(v) for v in visual.views]
                    item.score = round(
                        item.production_score * (1.0 - visual_weight)
                        + item.visual_score * visual_weight,
                        3,
                    )
                    item.notes.append(
                        f"Judge v2 combined production={item.production_score:.3f} "
                        f"visual={item.visual_score:.3f} visual_weight={visual_weight:.2f}"
                    )

                    should_try_appearance = appearance_mode in {"auto", "required"}
                    if should_try_appearance:
                        model_root = appearance_model_root
                        dino_ready = bool(model_root and (model_root / "dinov2").is_dir())
                        if not dino_ready and appearance_mode == "required":
                            raise RuntimeError(
                                "Judge v3 required but DINOv2 is not bootstrapped under model_root"
                            )
                        if dino_ready:
                            try:
                                from appearance_judge import score_candidate_appearance
                                render_dir = (
                                    appearance_render_root / item.backend
                                    if appearance_render_root is not None
                                    else None
                                )
                                appearance = score_candidate_appearance(
                                    Path(item.path),
                                    source_images,
                                    visual.views,
                                    model_root=model_root,
                                    detail_images=detail_images or [],
                                    render_dir=render_dir,
                                )
                                item.appearance_score = appearance.score
                                item.appearance_views = [_asdict(v) for v in appearance.views]
                                item.appearance_detail_score = appearance.detail_score
                                item.appearance_details = (
                                    [_asdict(v) for v in (appearance.details or [])]
                                    if appearance.details is not None else None
                                )
                                face_detail_scores = [
                                    float(v.score)
                                    for v in (appearance.details or [])
                                    if str(getattr(v,"region_hint","") or "").lower()=="head"
                                ]
                                if face_detail_scores:
                                    ordered_face=sorted(face_detail_scores)
                                    mean_face=sum(ordered_face)/len(ordered_face)
                                    item.appearance_face_detail_min_score=round(
                                        ordered_face[0],
                                        3,
                                    )
                                    item.appearance_face_detail_score=round(
                                        mean_face if len(ordered_face)==1
                                        else 0.80*mean_face+0.20*ordered_face[0],
                                        3,
                                    )
                                    item.notes.append(
                                        f"face_detail_fidelity={item.appearance_face_detail_score:.3f} "
                                        f"face_detail_min={item.appearance_face_detail_min_score:.3f} "
                                        f"face_detail_refs={len(face_detail_scores)}"
                                    )
                                if item.appearance_detail_score is not None:
                                    item.notes.append(
                                        f"detail_fidelity={item.appearance_detail_score:.3f} "
                                        f"detail_refs={len(item.appearance_details or [])}"
                                    )

                                # Preserve the proven v2 production:silhouette ratio inside
                                # the non-appearance share, then add DINO appearance evidence.
                                remaining = 1.0 - appearance_weight
                                production_w = (1.0 - visual_weight) * remaining
                                silhouette_w = visual_weight * remaining
                                item.score = round(
                                    item.production_score * production_w
                                    + item.visual_score * silhouette_w
                                    + item.appearance_score * appearance_weight,
                                    3,
                                )
                                item.notes.append(
                                    f"Judge v3 combined production={item.production_score:.3f} "
                                    f"silhouette={item.visual_score:.3f} "
                                    f"appearance={item.appearance_score:.3f} "
                                    f"weights={production_w:.4f}/{silhouette_w:.4f}/{appearance_weight:.4f}"
                                )
                            except Exception as exc:
                                item.notes.append(
                                    f"Judge v3 appearance unavailable: {type(exc).__name__}: {exc}"
                                )
                                if appearance_mode == "required":
                                    raise
                        else:
                            item.notes.append(
                                "Judge v3 auto skipped: DINOv2 evaluator not bootstrapped"
                            )
                except Exception as exc:
                    item.notes.append(
                        f"Judge v2/v3 score unavailable: {type(exc).__name__}: {exc}"
                    )
                    if appearance_mode == "required":
                        raise

                # Wonder3D normals are synthetic support evidence only. They never
                # replace real-source silhouette/appearance evidence and carry a
                # deliberately small final weight.
                if normal_support_images and item.valid and item.visual_views:
                    try:
                        from normal_judge import score_candidate_normals
                        from visual_judge import SourceViewScore

                        first = item.visual_views[0]
                        anchor = SourceViewScore(**first)
                        normal_support = score_candidate_normals(
                            Path(item.path),
                            normal_support_images,
                            anchor,
                        )
                        item.normal_support_score = normal_support.score
                        item.normal_support_views = [_asdict(v) for v in normal_support.views]
                        prior = item.score
                        item.score = round(
                            prior * (1.0 - normal_support_weight)
                            + item.normal_support_score * normal_support_weight,
                            3,
                        )
                        item.notes.append(
                            f"synthetic normal support={item.normal_support_score:.3f} "
                            f"weight={normal_support_weight:.3f}"
                        )
                    except Exception as exc:
                        item.notes.append(
                            f"synthetic normal support unavailable: {type(exc).__name__}: {exc}"
                        )

    identity_required=False
    if mode=="character" and detail_images:
        try:
            from reference_pool import infer_detail_region_hint
            identity_required=any(
                infer_detail_region_hint(path)=="head"
                for path in detail_images
            )
        except Exception:
            identity_required=False

    return sorted(
        scores,
        key=lambda x: candidate_rank_key(
            x,
            mode=mode,
            identity_required=identity_required,
        ),
        reverse=True,
    )


def export_glb(src: Path, dst: Path) -> Path:
    if src.suffix.lower() == ".glb":
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        return dst

    np, trimesh = _import_trimesh()
    if trimesh is None:
        raise RuntimeError("trimesh is required to normalize non-GLB candidates")

    scene = trimesh.load(src, force="scene", process=False)
    dst.parent.mkdir(parents=True, exist_ok=True)
    blob = trimesh.exchange.gltf.export_glb(scene)
    dst.write_bytes(blob)
    if dst.read_bytes()[:4] != b"glTF":
        raise RuntimeError("normalized GLB failed magic check")
    return dst


def main() -> int:
    parser = argparse.ArgumentParser(description="Score Hayuya candidate meshes.")
    parser.add_argument("mesh", type=Path, nargs="+")
    parser.add_argument("--mode", choices=["auto", "prop", "character", "architecture"], default="prop")
    parser.add_argument("--target-faces", type=int, default=100000)
    parser.add_argument("--target-texture-size", type=int)
    parser.add_argument("--source", type=Path, action="append", help="real geometry source image; repeatable")
    parser.add_argument("--detail", type=Path, action="append", help="detail/close-up reference image; repeatable")
    parser.add_argument("--visual-weight", type=float, default=0.55)
    parser.add_argument("--appearance-mode", choices=["off", "auto", "required"], default="off")
    parser.add_argument("--appearance-model-root", type=Path)
    parser.add_argument("--appearance-render-root", type=Path)
    parser.add_argument("--appearance-weight", type=float, default=0.25)
    parser.add_argument("--normal-support", type=Path, action="append", default=[], help="view=path")
    parser.add_argument("--normal-support-weight", type=float, default=0.06)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    normal_support_images = {}
    for item in args.normal_support:
        view, raw = str(item).split("=", 1)
        normal_support_images[view] = Path(raw)

    ranked = rank_candidates(
        [(p.stem, p) for p in args.mesh],
        mode="prop" if args.mode == "auto" else args.mode,
        target_faces=args.target_faces,
        target_texture_size=args.target_texture_size,
        source_images=args.source,
        detail_images=args.detail,
        visual_weight=args.visual_weight,
        appearance_mode=args.appearance_mode,
        appearance_model_root=args.appearance_model_root,
        appearance_render_root=args.appearance_render_root,
        appearance_weight=args.appearance_weight,
        normal_support_images=normal_support_images or None,
        normal_support_weight=args.normal_support_weight,
    )
    data = [asdict(x) for x in ranked]
    print(json.dumps(data, indent=2))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return 0 if ranked and ranked[0].valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
