#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class SourceMaterialRescueResult:
    source_image: str
    native_mesh: str
    diagnostic_material_donor: str
    output_glb: str
    texture_edge: int
    min_texture_edge: int
    geometry_preserved: bool
    projection_proxy_created: bool
    diagnostic_donor_production_eligible: bool
    final_native_candidate: bool
    final_volumetric: bool
    texture_gate_passed: bool
    material_bridge: dict
    texture_gate: dict
    projection_report: dict
    method: str = "hayuya-native-source-material-rescue-v3-visibility-materials"


def _scene_payload(path: Path):
    import numpy as np
    import trimesh

    scene = trimesh.load(path, force="scene", process=False)
    vertices_parts = []
    faces_parts = []
    offset = 0

    for node_name in scene.graph.nodes_geometry:
        transform, geom_name = scene.graph.get(node_name)
        geom = scene.geometry[geom_name]
        if not hasattr(geom, "vertices") or not hasattr(geom, "faces"):
            continue
        vertices = np.asarray(geom.vertices, dtype=np.float64)
        faces = np.asarray(geom.faces, dtype=np.int64)
        if not len(vertices) or not len(faces):
            continue

        hom = np.concatenate(
            [vertices, np.ones((len(vertices), 1), dtype=np.float64)],
            axis=1,
        )
        world = (hom @ np.asarray(transform, dtype=np.float64).T)[:, :3]
        vertices_parts.append(world)
        faces_parts.append(faces + offset)
        offset += len(vertices)

    if not vertices_parts:
        raise RuntimeError(f"no triangle geometry in {path}")

    return (
        np.concatenate(vertices_parts, axis=0),
        np.concatenate(faces_parts, axis=0),
    )


def _assert_geometry_preserved(before_path: Path, after_path: Path) -> dict:
    import numpy as np

    before_vertices, before_faces = _scene_payload(before_path)
    after_vertices, after_faces = _scene_payload(after_path)

    if before_vertices.shape != after_vertices.shape:
        raise RuntimeError(
            "source material rescue changed vertex count: "
            f"{before_vertices.shape}->{after_vertices.shape}"
        )
    if before_faces.shape != after_faces.shape:
        raise RuntimeError(
            "source material rescue changed face count: "
            f"{before_faces.shape}->{after_faces.shape}"
        )
    if not np.array_equal(before_faces, after_faces):
        raise RuntimeError("source material rescue changed triangle connectivity")

    extent = before_vertices.max(axis=0) - before_vertices.min(axis=0)
    scale = max(float(np.linalg.norm(extent)), 1e-9)
    delta = np.linalg.norm(after_vertices - before_vertices, axis=1)
    max_ratio = float(delta.max(initial=0.0) / scale)
    if max_ratio > 1e-7:
        raise RuntimeError(
            "source material rescue changed native vertex positions: "
            f"max_ratio={max_ratio:.10f}"
        )

    return {
        "vertices": int(len(before_vertices)),
        "faces": int(len(before_faces)),
        "max_vertex_displacement_ratio": max_ratio,
        "connectivity_identical": True,
        "positions_identical": bool(max_ratio <= 1e-7),
    }


def validate_textured_native_rescue(
    native_mesh: Path,
    candidate_mesh: Path,
    *,
    min_texture_edge: int = 1024,
) -> dict:
    """Accept a texturing result only if it preserves native geometry exactly."""
    from native_360_geometry_gate import assert_native_volumetric
    from native_geometry_guard import assert_native_candidate
    from texture_gate import inspect as inspect_texture_gate

    native_mesh = Path(native_mesh)
    candidate_mesh = Path(candidate_mesh)

    native_report = assert_native_candidate(
        candidate_mesh,
        label="textured_native_rescue_output",
    )
    volume_report = assert_native_volumetric(
        candidate_mesh,
        label="textured_native_rescue_output",
    )
    preservation = _assert_geometry_preserved(native_mesh, candidate_mesh)
    texture_report = inspect_texture_gate(
        candidate_mesh,
        min_edge=max(1, int(min_texture_edge)),
        min_base_color_edge=max(1, int(min_texture_edge)),
    )
    if not texture_report.passed:
        raise RuntimeError(
            "textured native rescue did not satisfy texture gate: "
            + ";".join(texture_report.warnings)
        )

    return {
        "native_candidate": not bool(native_report["is_projection_proxy"]),
        "volumetric": not bool(volume_report["catastrophically_planar"]),
        "geometry_preserved": bool(
            preservation["connectivity_identical"]
            and preservation["positions_identical"]
        ),
        "preservation": preservation,
        "texture_gate": asdict(texture_report),
    }


def _edge_energy(rgb) -> float:
    import numpy as np

    arr = np.asarray(rgb, dtype=np.float32)
    if arr.ndim == 3:
        arr = (
            arr[:, :, 0] * 0.2126
            + arr[:, :, 1] * 0.7152
            + arr[:, :, 2] * 0.0722
        )
    if arr.shape[0] < 2 or arr.shape[1] < 2:
        return 0.0
    dx = np.abs(np.diff(arr, axis=1)).mean()
    dy = np.abs(np.diff(arr, axis=0)).mean()
    return float(dx + dy)


def _cylindrical_delivery_atlas(
    source_image: Path,
    edge: int,
    *,
    front_core_degrees: float = 30.0,
    front_fade_degrees: float = 72.0,
):
    """Build a wrap-safe atlas from one front photo."""
    import math

    import numpy as np
    from PIL import Image

    from source_front_projection import _delivery_texture

    edge = max(256, int(edge))
    sharp, low, _normal, _orm, source_meta = _delivery_texture(
        Path(source_image),
        edge,
    )
    sharp_rgba = np.asarray(
        sharp.resize((edge, edge), Image.Resampling.LANCZOS).convert("RGBA"),
        dtype=np.float32,
    )
    low_rgb = np.asarray(
        low.resize((edge, edge), Image.Resampling.BICUBIC).convert("RGB"),
        dtype=np.float32,
    )

    hidden_column = low_rgb[:, edge // 2 : edge // 2 + 1, :]
    hidden = np.repeat(hidden_column, edge, axis=1)

    u = (np.arange(edge, dtype=np.float64) + 0.5) / float(edge)
    theta = (u - 0.5) * (2.0 * math.pi)
    abs_theta = np.abs(theta)

    core = math.radians(float(front_core_degrees))
    fade = math.radians(float(front_fade_degrees))
    if not (0.0 < core < fade < math.pi * 0.5):
        raise ValueError(
            "cylindrical source-material angles must satisfy "
            "0 < core < fade < 90 degrees"
        )

    t = np.clip((abs_theta - core) / max(fade - core, 1e-8), 0.0, 1.0)
    smooth = t * t * (3.0 - 2.0 * t)
    front_weight = 1.0 - smooth

    sin_limit = max(math.sin(fade), 1e-8)
    source_x = 0.5 + 0.5 * np.sin(theta) / sin_limit
    source_x = np.clip(source_x, 0.0, 1.0)
    source_ix = np.clip(
        np.rint(source_x * (edge - 1)).astype(np.int64),
        0,
        edge - 1,
    )

    sampled_rgb = sharp_rgba[:, source_ix, :3]
    sampled_alpha = sharp_rgba[:, source_ix, 3:4] / 255.0
    weights = (
        front_weight.reshape(1, edge, 1).astype(np.float32)
        * sampled_alpha
    )
    atlas = hidden * (1.0 - weights) + sampled_rgb * weights
    atlas = np.clip(atlas, 0.0, 255.0).astype(np.uint8)

    orm = np.zeros((edge, edge, 3), dtype=np.uint8)
    orm[:, :, 0] = 255
    orm[:, :, 1] = 218
    orm[:, :, 2] = 0

    front_slice = atlas[:, int(edge * 0.42) : int(edge * 0.58)]
    rear_w = max(1, edge // 12)
    rear = np.concatenate(
        [atlas[:, :rear_w], atlas[:, -rear_w:]],
        axis=1,
    )
    front_energy = _edge_energy(front_slice)
    rear_energy = _edge_energy(rear)
    ratio = rear_energy / max(front_energy, 1e-6)

    report = {
        "schema": 1,
        "method": "native-cylindrical-source-atlas-v1",
        "source_meta": source_meta,
        "texture_edge": int(edge),
        "front_core_degrees": float(front_core_degrees),
        "front_fade_degrees": float(front_fade_degrees),
        "source_alpha_gated": True,
        "rear_uses_source_pixels": False,
        "hidden_surface_strategy": "height-band-low-frequency-only",
        "front_edge_energy": float(front_energy),
        "rear_edge_energy": float(rear_energy),
        "rear_to_front_high_frequency_ratio": float(ratio),
    }
    return Image.fromarray(atlas, "RGB"), Image.fromarray(orm, "RGB"), report


def _apply_native_cylindrical_material(
    source_image: Path,
    native_mesh: Path,
    output_glb: Path,
    *,
    texture_edge: int,
) -> dict:
    import math

    import numpy as np
    import trimesh

    scene = trimesh.load(native_mesh, force="scene", process=False)
    records = []
    all_world = []
    geom_to_transform = {}

    for node_name in scene.graph.nodes_geometry:
        transform, geom_name = scene.graph.get(node_name)
        geom = scene.geometry[geom_name]
        if not hasattr(geom, "vertices") or not hasattr(geom, "faces"):
            continue
        transform = np.asarray(transform, dtype=np.float64)
        previous = geom_to_transform.get(geom_name)
        if previous is not None and not np.allclose(previous, transform):
            raise RuntimeError(
                "source material rescue cannot safely UV-bake one shared "
                f"geometry under multiple transforms: {geom_name}"
            )
        geom_to_transform[geom_name] = transform

        local = np.asarray(geom.vertices, dtype=np.float64)
        hom = np.concatenate(
            [local, np.ones((len(local), 1), dtype=np.float64)],
            axis=1,
        )
        world = (hom @ transform.T)[:, :3]
        records.append((node_name, geom_name, geom, world))
        all_world.append(world)

    if not records:
        raise RuntimeError(f"no triangle geometry in {native_mesh}")

    world_all = np.concatenate(all_world, axis=0)
    lo = world_all.min(axis=0)
    hi = world_all.max(axis=0)
    ext = hi - lo
    if int(np.argmax(ext)) != 1:
        raise RuntimeError(
            "native cylindrical material rescue expects Y-up geometry; "
            f"extents={ext.tolist()}"
        )

    cx = float((lo[0] + hi[0]) * 0.5)
    cz = float((lo[2] + hi[2]) * 0.5)
    dy = max(float(ext[1]), 1e-8)

    base_color, orm, atlas_report = _cylindrical_delivery_atlas(
        source_image,
        texture_edge,
    )
    material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=base_color,
        metallicRoughnessTexture=orm,
        metallicFactor=0.0,
        roughnessFactor=1.0,
    )

    for _node_name, geom_name, geom, world in records:
        theta = np.arctan2(world[:, 0] - cx, world[:, 2] - cz)
        u = np.mod(theta / (2.0 * math.pi) + 0.5, 1.0)
        v = np.clip((world[:, 1] - lo[1]) / dy, 0.0, 1.0)
        uv = np.stack([u, v], axis=1)
        geom.visual = trimesh.visual.TextureVisuals(
            uv=uv,
            material=material,
        )
        scene.geometry[geom_name] = geom

    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_glb.write_bytes(
        trimesh.exchange.gltf.export_glb(
            scene,
            include_normals=True,
        )
    )
    blob = output_glb.read_bytes()
    if blob[:4] != b"glTF" or len(blob) < 1024:
        raise RuntimeError("native cylindrical material rescue produced invalid GLB")

    return {
        **atlas_report,
        "source_image": str(source_image),
        "native_mesh": str(native_mesh),
        "output_glb": str(output_glb),
        "geometry_nodes": int(len(records)),
        "front_axis": "+Z",
        "up_axis": "Y",
        "uv_mapping": "cylindrical-around-Y-seam-at-rear",
        "geometry_replacement_allowed": False,
        "projection_proxy_created": False,
        "bytes": int(len(blob)),
    }


def rescue_source_material(
    source_image: Path,
    native_mesh: Path,
    output_glb: Path,
    *,
    texture_edge: int = 2048,
    min_texture_edge: int = 1024,
    total_samples: int = 250_000,
) -> SourceMaterialRescueResult:
    """Texture native geometry locally with visibility-gated face materials."""
    from native_360_geometry_gate import assert_native_volumetric
    from native_geometry_guard import assert_native_candidate
    from texture_gate import inspect as inspect_texture_gate

    source_image = Path(source_image)
    native_mesh = Path(native_mesh)
    output_glb = Path(output_glb)

    assert_native_candidate(native_mesh, label="source_material_rescue_input")
    assert_native_volumetric(native_mesh, label="source_material_rescue_input")

    from native_visibility_material import apply_visibility_material

    projection_report = apply_visibility_material(
        source_image,
        native_mesh,
        output_glb,
        texture_edge=max(512, int(texture_edge)),
    )

    native_report = assert_native_candidate(
        output_glb,
        label="source_material_rescue_output",
    )
    volume_report = assert_native_volumetric(
        output_glb,
        label="source_material_rescue_output",
    )
    preservation = _assert_geometry_preserved(native_mesh, output_glb)

    texture_report = inspect_texture_gate(
        output_glb,
        min_edge=max(1, int(min_texture_edge)),
        min_base_color_edge=max(1, int(min_texture_edge)),
    )
    if not texture_report.passed:
        raise RuntimeError(
            "source material rescue did not satisfy texture gate: "
            + ";".join(texture_report.warnings)
        )

    result = SourceMaterialRescueResult(
        source_image=str(source_image),
        native_mesh=str(native_mesh),
        diagnostic_material_donor="",
        output_glb=str(output_glb),
        texture_edge=int(texture_edge),
        min_texture_edge=int(min_texture_edge),
        geometry_preserved=bool(
            preservation["connectivity_identical"]
            and preservation["positions_identical"]
        ),
        projection_proxy_created=False,
        diagnostic_donor_production_eligible=False,
        final_native_candidate=not bool(native_report["is_projection_proxy"]),
        final_volumetric=not bool(volume_report["catastrophically_planar"]),
        texture_gate_passed=bool(texture_report.passed),
        material_bridge={
            "used": False,
            "method": "direct-native-visibility-face-materials",
            "legacy_nearest_uv_proxy_bridge_removed": True,
            "geometry_replacement_allowed": False,
            "total_samples_compatibility_argument": int(total_samples),
        },
        texture_gate=asdict(texture_report),
        projection_report=projection_report,
    )

    report_path = output_glb.with_suffix(".source_material_rescue.json")
    report_path.write_text(
        json.dumps(asdict(result), indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Rescue embedded source-derived material on native HAYUYA geometry."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--texture-edge", type=int, default=2048)
    parser.add_argument("--min-texture-edge", type=int, default=1024)
    parser.add_argument("--samples", type=int, default=250000)
    args = parser.parse_args()

    result = rescue_source_material(
        args.source,
        args.mesh,
        args.output,
        texture_edge=args.texture_edge,
        min_texture_edge=args.min_texture_edge,
        total_samples=args.samples,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
