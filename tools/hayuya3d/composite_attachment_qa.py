#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ComponentAttachment:
    component_id: int
    faces: int
    face_fraction: float
    centroid: list[float]
    extent: list[float]
    main_component: bool
    accessory_candidate: bool
    reachable_from_main: bool
    nearest_gap_ratio: float | None
    nearest_component_id: int | None


@dataclass
class CompositeAttachmentAudit:
    path: str
    mode: str
    applicable: bool
    ready: bool
    component_count: int
    accessory_candidates: int
    anchored_accessories: int
    floating_components: int
    oversized_floating_components: int
    max_link_gap_ratio: float
    components: list[ComponentAttachment]
    warnings: list[str]
    errors: list[str]
    method: str = "hayuya-composite-attachment-qa-v1"


def _deps():
    import numpy as np
    import trimesh
    from scipy.spatial import cKDTree
    return np, trimesh, cKDTree


def _load_components(path: Path):
    np, trimesh, _ = _deps()
    loaded = trimesh.load(path, force="scene", process=False)
    meshes = []
    for node_name in loaded.graph.nodes_geometry:
        transform, geom_name = loaded.graph[node_name]
        geom = loaded.geometry[geom_name]
        if not hasattr(geom, "faces") or not len(geom.faces):
            continue
        copy = geom.copy()
        copy.apply_transform(transform)
        meshes.append(copy)
    if not meshes:
        raise ValueError("no triangle geometry")
    combined = trimesh.util.concatenate(meshes)
    pieces = list(combined.split(only_watertight=False))
    pieces = [p for p in pieces if len(p.faces) and len(p.vertices)]
    if not pieces:
        raise ValueError("no connected triangle components")
    pieces.sort(key=lambda item: (-len(item.faces), -len(item.vertices)))
    return pieces


def _bbox_gap(a_lo, a_hi, b_lo, b_hi) -> float:
    np, _, _ = _deps()
    delta = np.maximum(0.0, np.maximum(a_lo - b_hi, b_lo - a_hi))
    return float(np.linalg.norm(delta))


def _nearest_vertex_gap(a, b) -> float:
    np, _, cKDTree = _deps()
    av = np.asarray(a.vertices, dtype=np.float64)
    bv = np.asarray(b.vertices, dtype=np.float64)
    if len(av) > len(bv):
        av, bv = bv, av
    tree = cKDTree(bv)
    distance, _ = tree.query(av, k=1, workers=1)
    return float(np.min(distance))


def _mode_gap(mode: str) -> float:
    token = str(mode or "").strip().lower()
    if token == "character":
        # Calibrated against the matched detached-accessory swap fixture:
        # a valid local replacement can land at ~0.0542x of the canonical
        # body diagonal after coordinate normalization. 0.06 keeps that
        # bounded while remaining strict enough to reject true floating
        # islands exercised by the destructive fixtures.
        return 0.06
    if token == "architecture":
        return 0.08
    return 0.06


def audit_composite_attachments(
    path: Path,
    *,
    mode: str,
    max_link_gap_ratio: float | None = None,
    accessory_face_fraction: float = 0.08,
) -> CompositeAttachmentAudit:
    np, _, _ = _deps()
    warnings: list[str] = []
    errors: list[str] = []
    max_link_gap_ratio = (
        _mode_gap(mode)
        if max_link_gap_ratio is None
        else float(max_link_gap_ratio)
    )
    if not math.isfinite(max_link_gap_ratio) or max_link_gap_ratio <= 0.0:
        raise ValueError("max_link_gap_ratio must be finite and positive")

    try:
        pieces = _load_components(path)
        total_faces = max(sum(len(p.faces) for p in pieces), 1)
        main = pieces[0]
        main_vertices = np.asarray(main.vertices, dtype=np.float64)
        main_lo = np.min(main_vertices, axis=0)
        main_hi = np.max(main_vertices, axis=0)
        main_diagonal = max(float(np.linalg.norm(main_hi - main_lo)), 1e-9)
        max_gap = main_diagonal * max_link_gap_ratio

        bounds = []
        for piece in pieces:
            vertices = np.asarray(piece.vertices, dtype=np.float64)
            if not np.isfinite(vertices).all():
                raise ValueError("component contains non-finite vertices")
            bounds.append((np.min(vertices, axis=0), np.max(vertices, axis=0)))

        adjacency: list[set[int]] = [set() for _ in pieces]
        gaps: dict[tuple[int, int], float] = {}
        for i in range(len(pieces)):
            a_lo, a_hi = bounds[i]
            for j in range(i + 1, len(pieces)):
                b_lo, b_hi = bounds[j]
                bbox_gap = _bbox_gap(a_lo, a_hi, b_lo, b_hi)
                if bbox_gap > max_gap:
                    continue
                gap = _nearest_vertex_gap(pieces[i], pieces[j])
                gaps[(i, j)] = gap
                if gap <= max_gap:
                    adjacency[i].add(j)
                    adjacency[j].add(i)

        reachable = {0}
        queue = [0]
        while queue:
            current = queue.pop(0)
            for neighbor in sorted(adjacency[current]):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)

        component_rows: list[ComponentAttachment] = []
        accessory_candidates = 0
        anchored_accessories = 0
        floating = 0
        oversized_floating = 0

        for i, piece in enumerate(pieces):
            vertices = np.asarray(piece.vertices, dtype=np.float64)
            centroid = np.mean(vertices, axis=0)
            extent = np.max(vertices, axis=0) - np.min(vertices, axis=0)
            fraction = float(len(piece.faces) / total_faces)
            accessory = bool(i != 0 and fraction <= accessory_face_fraction)
            if accessory:
                accessory_candidates += 1
                if i in reachable:
                    anchored_accessories += 1

            nearest_gap_ratio = None
            nearest_component_id = None
            if i != 0:
                candidates = []
                for j in range(len(pieces)):
                    if i == j:
                        continue
                    key = (min(i, j), max(i, j))
                    if key in gaps:
                        gap = gaps[key]
                    else:
                        a_lo, a_hi = bounds[i]
                        b_lo, b_hi = bounds[j]
                        gap = _bbox_gap(a_lo, a_hi, b_lo, b_hi)
                    candidates.append((gap, j))
                if candidates:
                    gap, nearest_component_id = min(candidates)
                    nearest_gap_ratio = float(gap / main_diagonal)

            if i != 0 and i not in reachable:
                floating += 1
                if accessory:
                    errors.append(
                        "floating accessory component "
                        f"{i} has no proximity path to the main asset "
                        f"(nearest_gap_ratio={nearest_gap_ratio:.6f} "
                        f"limit={max_link_gap_ratio:.6f})"
                    )
                else:
                    oversized_floating += 1
                    errors.append(
                        "detached donor/component "
                        f"{i} is too large to classify as an accessory and "
                        "has no proximity path to the main asset "
                        f"(face_fraction={fraction:.6f} "
                        f"nearest_gap_ratio={nearest_gap_ratio:.6f})"
                    )

            component_rows.append(ComponentAttachment(
                component_id=i,
                faces=int(len(piece.faces)),
                face_fraction=round(fraction, 8),
                centroid=[round(float(x), 8) for x in centroid],
                extent=[round(float(x), 8) for x in extent],
                main_component=(i == 0),
                accessory_candidate=accessory,
                reachable_from_main=(i in reachable),
                nearest_gap_ratio=(
                    None if nearest_gap_ratio is None
                    else round(float(nearest_gap_ratio), 8)
                ),
                nearest_component_id=nearest_component_id,
            ))

        if len(pieces) == 1:
            warnings.append("single connected component; no detached accessory topology to audit")

        return CompositeAttachmentAudit(
            path=str(path),
            mode=str(mode),
            applicable=True,
            ready=not errors,
            component_count=len(pieces),
            accessory_candidates=accessory_candidates,
            anchored_accessories=anchored_accessories,
            floating_components=floating,
            oversized_floating_components=oversized_floating,
            max_link_gap_ratio=round(float(max_link_gap_ratio), 8),
            components=component_rows,
            warnings=warnings,
            errors=errors,
        )
    except Exception as exc:
        return CompositeAttachmentAudit(
            path=str(path),
            mode=str(mode),
            applicable=True,
            ready=False,
            component_count=0,
            accessory_candidates=0,
            anchored_accessories=0,
            floating_components=0,
            oversized_floating_components=0,
            max_link_gap_ratio=round(float(max_link_gap_ratio), 8),
            components=[],
            warnings=warnings,
            errors=[f"{type(exc).__name__}:{exc}"],
        )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="HAYUYA disconnected accessory / composite attachment QA."
    )
    parser.add_argument("asset", type=Path)
    parser.add_argument("--mode", choices=["character", "prop", "architecture"], default="character")
    parser.add_argument("--max-link-gap-ratio", type=float)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    report = audit_composite_attachments(
        args.asset,
        mode=args.mode,
        max_link_gap_ratio=args.max_link_gap_ratio,
    )
    payload = json.dumps(asdict(report), indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")
    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
