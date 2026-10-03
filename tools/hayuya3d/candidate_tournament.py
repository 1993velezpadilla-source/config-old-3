#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from mesh_gate import inspect as inspect_mesh
from texture_gate import inspect as inspect_texture
from visual_judge import score_candidate as score_visual

NON_PRODUCTION_GENERATORS = {
    "tencent/Hunyuan3D-2.1",
    "tencent/Hunyuan3D-2mv",
}


@dataclass(frozen=True)
class CandidateSpec:
    path: Path
    generator: str
    family: str
    native_geometry: bool = True
    diagnostic_only: bool = False


@dataclass
class CandidateScore:
    path: str
    generator: str
    family: str
    native_geometry: bool
    diagnostic_only: bool
    production_eligible: bool
    eligible: bool
    visual_score: float
    source_views_judged: int
    source_views_expected: int
    source_coverage: float
    mesh_passed: bool
    texture_passed: bool
    faces: int
    vertices: int
    components: int
    largest_component_fraction: float
    degenerate_ratio: float
    base_color_min_edge: int
    texture_max_edge: int
    topology_score: float
    texture_score: float
    density_score: float
    composite_score: float
    reasons: list[str]


_GENERATOR_BY_NAME = {
    "trellis2_candidate.glb": (
        "microsoft/TRELLIS.2-4B",
        "trellis2",
        True,
        False,
    ),
    "trellis2_preview_recovered.glb": (
        "microsoft/TRELLIS.2-preview-recovery",
        "trellis2_preview",
        False,
        True,
    ),
    "trellis2_preview_normal_hero.glb": (
        "microsoft/TRELLIS.2-preview-normal-hero",
        "trellis2_preview",
        False,
        True,
    ),
    "triposr_cpu_candidate.glb": (
        "stabilityai/TripoSR",
        "triposr",
        True,
        False,
    ),
    "hunyuan3d_native_candidate.glb": (
        "tencent/Hunyuan3D-2.1",
        "hunyuan3d_2_1",
        True,
        False,
    ),
    "hunyuan3d_native_geometry.glb": (
        "tencent/Hunyuan3D-2.1",
        "hunyuan3d_2_1",
        True,
        False,
    ),
    "hunyuan3d_2mv_candidate.glb": (
        "tencent/Hunyuan3D-2mv",
        "hunyuan3d_2mv",
        True,
        False,
    ),
    "triposg_hero_candidate_material_bridge.glb": (
        "VAST-AI/TripoSG",
        "triposg",
        True,
        False,
    ),
    "triposg_hero_candidate.glb": (
        "VAST-AI/TripoSG",
        "triposg",
        True,
        False,
    ),
    "detailgen3d_hero_candidate.glb": (
        "VAST-AI/TripoSG+DetailGen3D",
        "detailgen3d",
        True,
        False,
    ),
    "unique3d_candidate.glb": (
        "AiuniAI/Unique3D",
        "unique3d",
        True,
        False,
    ),
    "unique3d_candidate_material_bridge.glb": (
        "AiuniAI/Unique3D",
        "unique3d",
        True,
        False,
    ),
    "hi3dgen_candidate.glb": (
        "Stable-X/Hi3DGen",
        "hi3dgen",
        True,
        False,
    ),
    "hi3dgen_candidate_material_bridge.glb": (
        "Stable-X/Hi3DGen",
        "hi3dgen",
        True,
        False,
    ),
}


def _texture_edge_for_quality(quality: str) -> int:
    q = str(quality or "").strip().lower()
    if q == "ultra":
        return 4096
    if q == "high":
        return 2048
    if q == "standard":
        return 1024
    return 512


def _target_faces_for_quality(quality: str) -> int:
    q = str(quality or "").strip().lower()
    if q == "ultra":
        return 2_000_000
    if q == "high":
        return 1_250_000
    if q == "standard":
        return 500_000
    return 150_000


def _topology_score(mesh) -> float:
    if not mesh.valid:
        return 0.0
    connected = max(0.0, min(1.0, float(mesh.largest_component_fraction)))
    degeneracy = max(0.0, min(1.0, float(mesh.degenerate_ratio) * 10.0))
    component_penalty = min(0.35, max(0, int(mesh.components) - 1) * 0.025)
    score = 100.0 * connected * (1.0 - degeneracy) * (1.0 - component_penalty)
    if not mesh.passed:
        score *= 0.35
    return max(0.0, min(100.0, score))


def _density_score(faces: int, target_faces: int) -> float:
    if faces <= 0 or target_faces <= 0:
        return 0.0
    # Density is deliberately capped at a small contribution. More polygons are
    # not allowed to beat a source-faithful silhouette.
    return 100.0 * min(1.0, float(faces) / float(target_faces))


def _texture_score(texture, required_edge: int) -> float:
    edge = int(getattr(texture, "base_color_min_edge", 0) or 0)
    if required_edge <= 0:
        return 100.0
    resolution = min(1.0, float(edge) / float(required_edge))
    return 100.0 if texture.passed else 70.0 * resolution


def discover_candidates(
    output_root: Path,
    *,
    current: Path | None = None,
    current_generator: str | None = None,
) -> list[CandidateSpec]:
    output_root = Path(output_root)
    specs: list[CandidateSpec] = []
    seen: set[str] = set()

    for name, meta in _GENERATOR_BY_NAME.items():
        path = output_root / name
        if not path.is_file():
            continue
        generator, family, native_geometry, diagnostic_only = meta
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        specs.append(
            CandidateSpec(
                path=path,
                generator=generator,
                family=family,
                native_geometry=native_geometry,
                diagnostic_only=diagnostic_only,
            )
        )

    if current is not None:
        current = Path(current)
        if current.is_file():
            resolved = str(current.resolve())
            if resolved not in seen:
                generator = str(current_generator or "hayuya/current")
                specs.append(
                    CandidateSpec(
                        path=current,
                        generator=generator,
                        family="current",
                        native_geometry=(
                            "preview-recovery" not in generator
                            and "preview-normal-hero" not in generator
                        ),
                        diagnostic_only=(
                            "preview-recovery" in generator
                            or "preview-normal-hero" in generator
                        ),
                    )
                )
    return specs


def score_one(
    spec: CandidateSpec,
    source_images: list[Path],
    *,
    texture_quality: str,
    visual_size: int = 128,
    azimuth_step: int = 45,
) -> CandidateScore:
    required_edge = _texture_edge_for_quality(texture_quality)
    target_faces = _target_faces_for_quality(texture_quality)
    reasons: list[str] = []
    production_eligible = spec.generator not in NON_PRODUCTION_GENERATORS

    mesh = inspect_mesh(spec.path, require_normals=False)
    try:
        texture = inspect_texture(
            spec.path,
            min_edge=required_edge,
            min_base_color_edge=required_edge,
        )
    except Exception as exc:
        class _MissingTexture:
            passed = False
            base_color_min_edge = 0
            max_edge = 0
        texture = _MissingTexture()
        reasons.append(f"texture_gate_error:{type(exc).__name__}")

    try:
        visual = score_visual(
            spec.path,
            source_images,
            size=visual_size,
            azimuth_step=azimuth_step,
        )
        visual_score = float(visual.score)
        judged = len(visual.views)
    except Exception as exc:
        visual_score = 0.0
        judged = 0
        reasons.append(f"visual_judge_error:{type(exc).__name__}")

    expected = len(source_images)
    coverage = float(judged) / float(expected) if expected else 0.0
    topology = _topology_score(mesh)
    texture_score = _texture_score(texture, required_edge)
    density = _density_score(int(mesh.faces), target_faces)

    # Source fidelity dominates. Topology/material quality are hard production
    # constraints; density is only a tie-breaker.
    composite = (
        visual_score * 0.70
        + topology * 0.15
        + texture_score * 0.10
        + density * 0.05
    )

    if not mesh.passed:
        reasons.extend(f"mesh:{x}" for x in mesh.reasons)
    if not texture.passed:
        reasons.extend(
            f"texture:{x}"
            for x in getattr(texture, "warnings", [])
        )
        if not getattr(texture, "warnings", None):
            reasons.append("texture:production_texture_gate_failed")
    if expected and judged != expected:
        reasons.append(f"source_coverage:{judged}/{expected}")
    if spec.diagnostic_only:
        reasons.append("diagnostic_geometry_only")
    if not production_eligible:
        reasons.append("license_not_production_eligible")

    eligible = bool(
        mesh.passed
        and texture.passed
        and expected > 0
        and judged == expected
        and not spec.diagnostic_only
        and production_eligible
    )

    return CandidateScore(
        path=str(spec.path),
        generator=spec.generator,
        family=spec.family,
        native_geometry=spec.native_geometry,
        diagnostic_only=spec.diagnostic_only,
        production_eligible=production_eligible,
        eligible=eligible,
        visual_score=round(visual_score, 4),
        source_views_judged=judged,
        source_views_expected=expected,
        source_coverage=round(coverage, 6),
        mesh_passed=bool(mesh.passed),
        texture_passed=bool(texture.passed),
        faces=int(mesh.faces),
        vertices=int(mesh.vertices),
        components=int(mesh.components),
        largest_component_fraction=round(float(mesh.largest_component_fraction), 6),
        degenerate_ratio=round(float(mesh.degenerate_ratio), 8),
        base_color_min_edge=int(getattr(texture, "base_color_min_edge", 0) or 0),
        texture_max_edge=int(getattr(texture, "max_edge", 0) or 0),
        topology_score=round(topology, 4),
        texture_score=round(texture_score, 4),
        density_score=round(density, 4),
        composite_score=round(composite, 4),
        reasons=list(dict.fromkeys(reasons)),
    )


def run_tournament(
    specs: Iterable[CandidateSpec],
    source_images: Iterable[Path],
    *,
    texture_quality: str,
    output_json: Path | None = None,
) -> dict:
    source_images = [Path(x) for x in source_images if Path(x).is_file()]
    rows = [
        score_one(
            spec,
            source_images,
            texture_quality=texture_quality,
        )
        for spec in specs
        if Path(spec.path).is_file()
    ]

    eligible = [row for row in rows if row.eligible]
    pool = eligible if eligible else [
        row for row in rows
        if row.mesh_passed and row.source_views_judged > 0
    ]
    pool.sort(
        key=lambda row: (
            row.composite_score,
            row.visual_score,
            row.topology_score,
            row.texture_score,
            row.density_score,
        ),
        reverse=True,
    )
    winner = pool[0] if pool else None
    report = {
        "schema": 1,
        "policy": "source-first-independent-hypothesis-tournament-v1",
        "texture_quality": texture_quality,
        "source_images": [str(x) for x in source_images],
        "candidate_count": len(rows),
        "eligible_count": len(eligible),
        "winner": asdict(winner) if winner else None,
        "candidates": [
            asdict(row)
            for row in sorted(
                rows,
                key=lambda row: (
                    row.composite_score,
                    row.visual_score,
                ),
                reverse=True,
            )
        ],
    }
    if output_json is not None:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def tournament_from_output(
    output_root: Path,
    source_images: Iterable[Path],
    *,
    texture_quality: str,
    current: Path | None = None,
    current_generator: str | None = None,
    output_json: Path | None = None,
) -> dict:
    specs = discover_candidates(
        output_root,
        current=current,
        current_generator=current_generator,
    )
    return run_tournament(
        specs,
        source_images,
        texture_quality=texture_quality,
        output_json=output_json,
    )
