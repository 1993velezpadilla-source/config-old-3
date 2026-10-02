#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from qa import inspect_mesh
from visual_judge import score_candidate as score_visual


@dataclass
class GeometryEvidence:
    path: str
    valid: bool
    visual_score: float
    health_score: float
    normal_support_score: float | None
    combined_score: float
    faces: int
    components: int
    degenerate_ratio: float
    notes: list[str]


@dataclass
class RefinementDecision:
    source_backend: str
    source_path: str
    refined_path: str
    source: GeometryEvidence
    refined: GeometryEvidence
    preferred: str
    improvement: float
    promote_to_final_geometry: bool
    policy: str = "geometry-only challenger; final material promotion requires Material Bridge"


def geometry_health(mesh_score) -> float:
    if not mesh_score.valid:
        return 0.0

    component_penalty = min(0.45, max(0, mesh_score.components - 1) * 0.04)
    degenerate_penalty = min(0.55, mesh_score.degenerate_ratio * 12.0)
    health = max(0.0, 1.0 - component_penalty - degenerate_penalty)

    bbox = mesh_score.bbox or []
    if len(bbox) == 3:
        positive = [x for x in bbox if x > 1e-9]
        if len(positive) != 3:
            health *= 0.4
        else:
            aspect = max(positive) / min(positive)
            if aspect > 150:
                health *= 0.65

    if mesh_score.faces < 100:
        health *= 0.25
    return max(0.0, min(100.0, health * 100.0))


def restore_refined_bounds(source: Path, refined: Path, output: Path) -> Path:
    """
    TripoSF normalizes the input before VAE reconstruction. Restore the refined mesh
    to the original candidate's object-space center and maximum extent.
    """
    import numpy as np
    import trimesh

    original_scene = trimesh.load(source, force="scene", process=False)
    refined_scene = trimesh.load(refined, force="scene", process=False)

    original_geoms = list(original_scene.geometry.values())
    refined_geoms = list(refined_scene.geometry.values())
    original_meshes = [g for g in original_geoms if hasattr(g, "vertices") and len(g.vertices)]
    refined_meshes = [g for g in refined_geoms if hasattr(g, "vertices") and len(g.vertices)]
    if not original_meshes or not refined_meshes:
        raise ValueError("missing mesh geometry for TripoSF bounds restoration")

    original_mesh = trimesh.util.concatenate(original_meshes)
    refined_mesh = trimesh.util.concatenate(refined_meshes)

    source_min = np.asarray(original_mesh.bounds[0], dtype=np.float64)
    source_max = np.asarray(original_mesh.bounds[1], dtype=np.float64)
    source_center = (source_min + source_max) * 0.5
    source_extent = float(np.max(source_max - source_min))

    refined_min = np.asarray(refined_mesh.bounds[0], dtype=np.float64)
    refined_max = np.asarray(refined_mesh.bounds[1], dtype=np.float64)
    refined_center = (refined_min + refined_max) * 0.5
    refined_extent = float(np.max(refined_max - refined_min))
    if source_extent <= 1e-12 or refined_extent <= 1e-12:
        raise ValueError("collapsed bounds during TripoSF restoration")

    refined_mesh.apply_translation(-refined_center)
    refined_mesh.apply_scale(source_extent / refined_extent)
    refined_mesh.apply_translation(source_center)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".glb":
        scene = trimesh.Scene(refined_mesh)
        output.write_bytes(trimesh.exchange.gltf.export_glb(scene))
    else:
        refined_mesh.export(output)
    return output


def evaluate_geometry(
    path: Path,
    *,
    sources: list[Path],
    mode: str,
    target_faces: int,
    normal_support_images: dict[str, Path] | None = None,
) -> GeometryEvidence:
    inspected = inspect_mesh(
        path,
        backend=path.stem,
        mode=mode,
        target_faces=target_faces,
    )
    if not inspected.valid:
        return GeometryEvidence(
            path=str(path),
            valid=False,
            visual_score=0.0,
            health_score=0.0,
            normal_support_score=None,
            combined_score=0.0,
            faces=inspected.faces,
            components=inspected.components,
            degenerate_ratio=inspected.degenerate_ratio,
            notes=list(inspected.notes or []),
        )

    visual = score_visual(path, sources)
    health = geometry_health(inspected)
    normal_score = None

    if normal_support_images and visual.views:
        try:
            from normal_judge import score_candidate_normals
            support = score_candidate_normals(
                path,
                normal_support_images,
                visual.views[0],
            )
            normal_score = support.score
        except Exception as exc:
            inspected.notes.append(
                f"normal support unavailable during refinement decision: {type(exc).__name__}: {exc}"
            )

    # Real-source silhouette is dominant. Mesh health protects against a visually
    # plausible but broken high-resolution reconstruction. Synthetic normals can
    # contribute only a small tie-break.
    if normal_score is None:
        combined = 0.84 * visual.score + 0.16 * health
    else:
        combined = 0.79 * visual.score + 0.16 * health + 0.05 * normal_score

    return GeometryEvidence(
        path=str(path),
        valid=True,
        visual_score=round(visual.score, 3),
        health_score=round(health, 3),
        normal_support_score=normal_score,
        combined_score=round(combined, 3),
        faces=inspected.faces,
        components=inspected.components,
        degenerate_ratio=round(inspected.degenerate_ratio, 8),
        notes=list(inspected.notes or []),
    )


def compare_refinement(
    source_backend: str,
    source_path: Path,
    refined_path: Path,
    *,
    sources: list[Path],
    mode: str,
    target_faces: int,
    normal_support_images: dict[str, Path] | None = None,
    promotion_margin: float = 1.0,
) -> RefinementDecision:
    source = evaluate_geometry(
        source_path,
        sources=sources,
        mode=mode,
        target_faces=target_faces,
        normal_support_images=normal_support_images,
    )
    refined = evaluate_geometry(
        refined_path,
        sources=sources,
        mode=mode,
        target_faces=target_faces,
        normal_support_images=normal_support_images,
    )

    improvement = refined.combined_score - source.combined_score
    preferred = "refined" if refined.valid and improvement > promotion_margin else "source"

    # Geometry can be declared preferred, but asset finalization remains separate
    # until Material Bridge can reproject/preserve appearance onto the new topology.
    return RefinementDecision(
        source_backend=source_backend,
        source_path=str(source_path),
        refined_path=str(refined_path),
        source=source,
        refined=refined,
        preferred=preferred,
        improvement=round(improvement, 3),
        promote_to_final_geometry=(preferred == "refined"),
    )


def write_decision(path: Path, decision: RefinementDecision) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(decision), indent=2) + "\n", encoding="utf-8")
