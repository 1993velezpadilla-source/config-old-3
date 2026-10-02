#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from material_bridge import _scene_meshes, transfer_best_material


@dataclass
class MeshDoctorAudit:
    path: str
    valid: bool
    vertices: int
    faces: int
    components: int
    watertight: bool
    winding_consistent: bool
    finite_vertices: bool
    duplicate_faces: int
    degenerate_faces: int
    unreferenced_vertices: int
    boundary_edges: int
    nonmanifold_edges: int
    broken_faces: int
    tiny_components: int
    euler_number: int | None
    bbox_extents: list[float]
    defect_score: float
    repair_recommended: bool
    warnings: list[str]


@dataclass
class MeshRepairResult:
    source_mesh: str
    repaired_geometry: str
    bridged_glb: str
    manifest: str
    mode: str
    before: MeshDoctorAudit
    after: MeshDoctorAudit
    max_extent_relative_drift: float
    centroid_drift_normalized: float
    vertex_surface_drift_normalized: float
    material_method: str
    material_channels: list[str]
    material_fallback: bool
    safe_for_arena: bool
    reasons: list[str]


def _deps():
    import numpy as np
    import trimesh
    return np, trimesh


def _combine(path: Path):
    np, trimesh = _deps()
    meshes = _scene_meshes(path)
    geometry = []
    for mesh in meshes:
        if not hasattr(mesh, "faces") or not len(mesh.faces):
            continue
        clean = trimesh.Trimesh(
            vertices=np.asarray(mesh.vertices).copy(),
            faces=np.asarray(mesh.faces).copy(),
            process=False,
        )
        # glTF legitimately duplicates vertices at UV/normal/material seams.
        # Weld coincident vertices inside each primitive for topology auditing so
        # rendering seams are not misclassified as geometric holes.
        clean.merge_vertices()
        geometry.append(clean)

    if not geometry:
        raise ValueError(f"no triangle geometry in {path}")
    return trimesh.util.concatenate(geometry)


def _edge_counts(faces):
    np, _ = _deps()
    faces = np.asarray(faces, dtype=np.int64)
    if len(faces) == 0:
        return np.empty((0, 2), dtype=np.int64), np.empty(0, dtype=np.int64)
    edges = np.vstack([
        faces[:, [0, 1]],
        faces[:, [1, 2]],
        faces[:, [2, 0]],
    ])
    edges.sort(axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    return unique, counts


def _tiny_component_count(mesh) -> int:
    np, _ = _deps()
    try:
        parts = mesh.split(only_watertight=False)
    except Exception:
        return 0
    if len(parts) <= 1:
        return 0

    areas = np.asarray([max(float(part.area), 0.0) for part in parts], dtype=float)
    total = float(areas.sum())
    if total <= 1e-15:
        return 0
    # Audit only. Do not delete these automatically: accessories and architectural
    # detail can legitimately be tiny disconnected components.
    return int(sum(float(area / total) < 0.0005 for area in areas))


def audit_mesh(path: Path) -> MeshDoctorAudit:
    np, trimesh = _deps()
    warnings: list[str] = []

    try:
        mesh = _combine(path)
    except Exception as exc:
        return MeshDoctorAudit(
            path=str(path),
            valid=False,
            vertices=0,
            faces=0,
            components=0,
            watertight=False,
            winding_consistent=False,
            finite_vertices=False,
            duplicate_faces=0,
            degenerate_faces=0,
            unreferenced_vertices=0,
            boundary_edges=0,
            nonmanifold_edges=0,
            broken_faces=0,
            tiny_components=0,
            euler_number=None,
            bbox_extents=[],
            defect_score=100.0,
            repair_recommended=False,
            warnings=[f"{type(exc).__name__}: {exc}"],
        )

    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    finite_vertices = bool(np.all(np.isfinite(vertices)))

    duplicate_faces = 0
    if len(faces):
        canonical = np.sort(faces, axis=1)
        duplicate_faces = int(len(faces) - len(np.unique(canonical, axis=0)))

    areas = np.asarray(mesh.area_faces, dtype=float)
    if len(areas):
        finite_areas = areas[np.isfinite(areas)]
        scale = max(float(np.median(finite_areas)), 1e-15) if len(finite_areas) else 1e-15
        degenerate_faces = int(np.sum((~np.isfinite(areas)) | (areas <= scale * 1e-8)))
    else:
        degenerate_faces = 0

    referenced = np.unique(faces.reshape(-1)) if len(faces) else np.empty(0, dtype=np.int64)
    unreferenced_vertices = int(max(0, len(vertices) - len(referenced)))

    _, edge_counts = _edge_counts(faces)
    boundary_edges = int(np.sum(edge_counts == 1))
    nonmanifold_edges = int(np.sum(edge_counts > 2))

    try:
        broken_faces = int(len(trimesh.repair.broken_faces(mesh)))
    except Exception:
        broken_faces = 0

    try:
        components = int(len(mesh.split(only_watertight=False)))
    except Exception:
        components = 1 if len(faces) else 0

    tiny_components = _tiny_component_count(mesh)

    bbox = [float(x) for x in np.asarray(mesh.extents, dtype=float).tolist()]
    winding = bool(mesh.is_winding_consistent)
    watertight = bool(mesh.is_watertight)
    euler = int(mesh.euler_number) if hasattr(mesh, "euler_number") else None

    face_count = max(1, len(faces))
    score = 0.0
    score += min(22.0, duplicate_faces / face_count * 5000.0)
    score += min(25.0, degenerate_faces / face_count * 5000.0)
    score += min(18.0, nonmanifold_edges / max(1, len(edge_counts)) * 5000.0)
    score += min(12.0, unreferenced_vertices / max(1, len(vertices)) * 1000.0)
    if not winding:
        score += 12.0
    if not finite_vertices:
        score += 100.0
    if broken_faces:
        score += min(12.0, broken_faces / face_count * 1000.0)
    score = min(100.0, score)

    if duplicate_faces:
        warnings.append(f"duplicate faces: {duplicate_faces}")
    if degenerate_faces:
        warnings.append(f"degenerate faces: {degenerate_faces}")
    if unreferenced_vertices:
        warnings.append(f"unreferenced vertices: {unreferenced_vertices}")
    if nonmanifold_edges:
        warnings.append(f"non-manifold edges: {nonmanifold_edges}")
    if boundary_edges and not watertight:
        warnings.append(f"boundary edges: {boundary_edges}")
    if not winding:
        warnings.append("face winding is inconsistent")
    if not finite_vertices:
        warnings.append("non-finite vertices present")
    if tiny_components:
        warnings.append(f"tiny disconnected components (audit only): {tiny_components}")

    repair_recommended = bool(
        finite_vertices
        and (
            duplicate_faces
            or degenerate_faces
            or unreferenced_vertices
            or nonmanifold_edges
            or not winding
            or broken_faces
        )
    )

    return MeshDoctorAudit(
        path=str(path),
        valid=bool(finite_vertices and len(faces) > 0),
        vertices=int(len(vertices)),
        faces=int(len(faces)),
        components=components,
        watertight=watertight,
        winding_consistent=winding,
        finite_vertices=finite_vertices,
        duplicate_faces=duplicate_faces,
        degenerate_faces=degenerate_faces,
        unreferenced_vertices=unreferenced_vertices,
        boundary_edges=boundary_edges,
        nonmanifold_edges=nonmanifold_edges,
        broken_faces=broken_faces,
        tiny_components=tiny_components,
        euler_number=euler,
        bbox_extents=[round(x, 8) for x in bbox],
        defect_score=round(float(score), 3),
        repair_recommended=repair_recommended,
        warnings=warnings,
    )


def _fill_triangle_boundary_loops(mesh) -> int:
    """
    Deterministic fallback for the safest possible hole class: an isolated
    3-edge boundary loop. Larger/ambiguous holes are left untouched.
    """
    np, _ = _deps()
    faces = np.asarray(mesh.faces, dtype=np.int64)
    edges, counts = _edge_counts(faces)
    boundary = edges[counts == 1]
    if len(boundary) < 3:
        return 0

    adjacency: dict[int, set[int]] = {}
    for a, b in boundary:
        a, b = int(a), int(b)
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    seen: set[int] = set()
    additions: list[list[int]] = []
    vertices = np.asarray(mesh.vertices, dtype=np.float64)

    for start in sorted(adjacency):
        if start in seen:
            continue
        stack = [start]
        component: set[int] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency.get(current, ()))
        seen.update(component)

        if len(component) != 3:
            continue
        if any(len(adjacency[v] & component) != 2 for v in component):
            continue

        ordered = [min(component)]
        prev = None
        current = ordered[0]
        for _ in range(2):
            options = sorted(
                v for v in (adjacency[current] & component)
                if v != prev and v not in ordered
            )
            if not options:
                break
            nxt = options[0]
            ordered.append(nxt)
            prev, current = current, nxt
        if len(ordered) != 3:
            continue

        a, b, d = vertices[ordered]
        area2 = float(np.linalg.norm(np.cross(b - a, d - a)))
        if not math.isfinite(area2) or area2 <= 1e-12:
            continue
        additions.append(ordered)

    if additions:
        mesh.faces = np.vstack([faces, np.asarray(additions, dtype=np.int64)])
    return len(additions)


def _safe_repair_geometry(source: Path, output: Path, *, mode: str):
    np, trimesh = _deps()
    meshes = _scene_meshes(source)
    repaired = []

    for original in meshes:
        mesh = trimesh.Trimesh(
            vertices=np.asarray(original.vertices).copy(),
            faces=np.asarray(original.faces).copy(),
            process=False,
        )
        if not len(mesh.faces):
            continue

        # Only operations which preserve the visible surface or close very small
        # local holes. Material seams are restored later by Material Bridge.
        unique = mesh.unique_faces()
        if unique is not None and len(unique) == len(mesh.faces):
            mesh.update_faces(unique)

        nondegenerate = mesh.nondegenerate_faces()
        if nondegenerate is not None and len(nondegenerate) == len(mesh.faces):
            mesh.update_faces(nondegenerate)

        mesh.remove_unreferenced_vertices()
        mesh.merge_vertices()

        try:
            mesh.fix_normals(multibody=True)
        except TypeError:
            mesh.fix_normals()

        # Props/architecture generally should be closed. Trimesh's conservative
        # hole filler handles local simple holes; characters/cloth remain open.
        if mode in {"prop", "architecture"} and not mesh.is_watertight:
            try:
                trimesh.repair.fill_holes(mesh)
            except Exception:
                pass

            if not mesh.is_watertight:
                _fill_triangle_boundary_loops(mesh)

            # Re-orient after any inserted face. Do not attempt larger holes here.
            try:
                mesh.fix_normals(multibody=True)
            except TypeError:
                mesh.fix_normals()

        mesh.remove_unreferenced_vertices()
        repaired.append(mesh)

    if not repaired:
        raise RuntimeError("Mesh Doctor repair produced no geometry")

    combined = trimesh.util.concatenate(repaired)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(combined)))
    if output.read_bytes()[:4] != b"glTF":
        raise RuntimeError("Mesh Doctor geometry export is not a GLB")
    return output


def _shape_drift(source: Path, repaired: Path) -> tuple[float, float, float]:
    np, _ = _deps()
    from scipy.spatial import cKDTree

    src = _combine(source)
    dst = _combine(repaired)
    # Unreferenced vertices are not part of the visible surface and may sit at
    # arbitrary coordinates. Remove them before measuring geometry drift.
    src.remove_unreferenced_vertices()
    dst.remove_unreferenced_vertices()

    src_extent = np.asarray(src.extents, dtype=float)
    dst_extent = np.asarray(dst.extents, dtype=float)
    extent_rel = np.abs(dst_extent - src_extent) / np.maximum(src_extent, 1e-9)
    max_extent_drift = float(np.max(extent_rel))

    scale = max(float(np.max(src_extent)), 1e-9)
    src_center = (np.asarray(src.bounds[0]) + np.asarray(src.bounds[1])) * 0.5
    dst_center = (np.asarray(dst.bounds[0]) + np.asarray(dst.bounds[1])) * 0.5
    # Surface centroid changes when duplicate/degenerate faces are removed even
    # when vertex positions do not move. Bounding-box center measures spatial drift.
    centroid_drift = float(np.linalg.norm(dst_center - src_center) / scale)

    src_v = np.asarray(src.vertices, dtype=np.float32)
    dst_v = np.asarray(dst.vertices, dtype=np.float32)
    if not len(src_v) or not len(dst_v):
        vertex_drift = math.inf
    else:
        src_tree = cKDTree(src_v)
        dst_tree = cKDTree(dst_v)
        a = float(np.mean(dst_tree.query(src_v, k=1, workers=-1)[0]))
        b = float(np.mean(src_tree.query(dst_v, k=1, workers=-1)[0]))
        vertex_drift = max(a, b) / scale

    return max_extent_drift, centroid_drift, vertex_drift


def repair_candidate(
    source_mesh: Path,
    out_dir: Path,
    *,
    mode: str,
    texture_size: int,
) -> MeshRepairResult:
    before = audit_mesh(source_mesh)
    if not before.valid:
        raise RuntimeError("Mesh Doctor cannot safely repair an invalid/non-finite mesh")

    out_dir.mkdir(parents=True, exist_ok=True)
    geometry = _safe_repair_geometry(
        source_mesh,
        out_dir / "mesh_doctor_geometry.glb",
        mode=mode,
    )
    after_geometry = audit_mesh(geometry)

    max_extent_drift, centroid_drift, vertex_drift = _shape_drift(
        source_mesh,
        geometry,
    )

    bridged = out_dir / "mesh_doctor_material_bridge.glb"
    bridge = transfer_best_material(
        source_mesh,
        geometry,
        bridged,
        total_samples=160_000,
        max_texture_size=texture_size,
    )
    after = audit_mesh(bridged)

    reasons: list[str] = []
    if after.defect_score > before.defect_score + 1e-6:
        reasons.append(
            f"defect score worsened {before.defect_score:.3f}->{after.defect_score:.3f}"
        )
    if after.nonmanifold_edges > before.nonmanifold_edges:
        reasons.append("non-manifold edge count increased")
    if max_extent_drift > 0.02:
        reasons.append(f"extent drift too high: {max_extent_drift:.4f}")
    if centroid_drift > 0.01:
        reasons.append(f"centroid drift too high: {centroid_drift:.4f}")
    if vertex_drift > 0.01:
        reasons.append(f"surface vertex drift too high: {vertex_drift:.4f}")
    if not after.valid:
        reasons.append("repaired/material-bridged mesh is invalid")

    meaningful_improvement = bool(
        after.defect_score + 1e-6 < before.defect_score
        or after.duplicate_faces < before.duplicate_faces
        or after.degenerate_faces < before.degenerate_faces
        or after.nonmanifold_edges < before.nonmanifold_edges
        or after.boundary_edges < before.boundary_edges
        or (not before.winding_consistent and after.winding_consistent)
        or (not before.watertight and after.watertight and mode in {"prop", "architecture"})
    )
    if not meaningful_improvement:
        reasons.append("repair produced no measurable structural improvement")

    safe = not reasons
    manifest = out_dir / "mesh_doctor_manifest.json"
    result = MeshRepairResult(
        source_mesh=str(source_mesh),
        repaired_geometry=str(geometry),
        bridged_glb=str(bridged),
        manifest=str(manifest),
        mode=mode,
        before=before,
        after=after,
        max_extent_relative_drift=round(max_extent_drift, 8),
        centroid_drift_normalized=round(centroid_drift, 8),
        vertex_surface_drift_normalized=round(vertex_drift, 8),
        material_method=bridge.method,
        material_channels=list(bridge.channels or []),
        material_fallback=bridge.fallback_used,
        safe_for_arena=safe,
        reasons=reasons,
    )
    manifest.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="HAYUYA Mesh Doctor v1 audit/repair.")
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--mode", choices=["prop", "character", "architecture"], default="prop")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--texture-size", type=int, default=2048)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()

    if args.repair:
        if args.output is None:
            parser.error("--output is required with --repair")
        result = repair_candidate(
            args.mesh,
            args.output,
            mode=args.mode,
            texture_size=args.texture_size,
        )
        print(json.dumps(asdict(result), indent=2))
        return 0 if result.safe_for_arena else 3

    audit = audit_mesh(args.mesh)
    print(json.dumps(asdict(audit), indent=2))
    return 0 if audit.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
