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
    method: str = "hayuya-native-source-material-rescue-v1"


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


def rescue_source_material(
    source_image: Path,
    native_mesh: Path,
    output_glb: Path,
    *,
    texture_edge: int = 2048,
    min_texture_edge: int = 1024,
    total_samples: int = 250_000,
) -> SourceMaterialRescueResult:
    """Texture an untextured native mesh without promoting projection geometry.

    A visibility-aware projection is allowed only as a temporary *material
    donor*. Material Bridge transfers that evidence back onto the original
    native mesh. The diagnostic donor itself is never production eligible and
    is rejected by the normal native-geometry provenance guard.
    """
    from material_bridge import transfer_best_material
    from native_360_geometry_gate import assert_native_volumetric
    from native_geometry_guard import assert_native_candidate
    from source_front_projection import project_source_front
    from texture_gate import inspect as inspect_texture_gate

    source_image = Path(source_image)
    native_mesh = Path(native_mesh)
    output_glb = Path(output_glb)

    assert_native_candidate(native_mesh, label="source_material_rescue_input")
    assert_native_volumetric(native_mesh, label="source_material_rescue_input")

    work = output_glb.parent / (output_glb.stem + "_material_rescue")
    work.mkdir(parents=True, exist_ok=True)
    donor = work / "diagnostic_projection_material_donor.glb"

    projection_report = project_source_front(
        source_image,
        native_mesh,
        donor,
        texture_edge=max(512, int(texture_edge)),
    )

    bridge = transfer_best_material(
        donor,
        native_mesh,
        output_glb,
        total_samples=max(20_000, int(total_samples)),
        max_texture_size=max(512, int(texture_edge)),
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
        diagnostic_material_donor=str(donor),
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
        material_bridge=asdict(bridge),
        texture_gate=asdict(texture_report),
        projection_report={
            **projection_report,
            "temporary_material_donor_only": True,
            "production_eligible": False,
        },
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
