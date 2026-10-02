#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AccessoryClusterMember:
    component_id: int
    face_count: int
    face_fraction: float
    spatial_label: str
    centroid: list[float]
    extent: list[float]
    gap_to_main_ratio: float
    linked_accessory_ids: list[int]


@dataclass
class AccessoryCluster:
    cluster_id: int
    component_ids: list[int]
    face_count: int
    face_fraction: float
    anchored_to_main: bool
    direct_main_anchors: list[int]
    min_main_gap_ratio: float
    max_internal_link_gap_ratio: float
    spatial_labels: list[str]
    members: list[AccessoryClusterMember]


@dataclass
class AccessoryClusterReport:
    path: str
    mode: str
    ready: bool
    main_component_id: int | None
    accessory_components: int
    cluster_count: int
    selected_cluster_id: int | None
    selected_component_ids: list[int]
    clusters: list[AccessoryCluster]
    warnings: list[str]
    errors: list[str]
    method: str = "hayuya-accessory-cluster-v1"


def _deps():
    import numpy as np
    from scipy.spatial import cKDTree
    return np, cKDTree


def _bbox_gap(a_lo, a_hi, b_lo, b_hi) -> float:
    np, _ = _deps()
    delta = np.maximum(0.0, np.maximum(a_lo - b_hi, b_lo - a_hi))
    return float(np.linalg.norm(delta))


def _nearest_gap(a, b) -> float:
    np, cKDTree = _deps()
    aa = np.asarray(a, dtype=np.float64)
    bb = np.asarray(b, dtype=np.float64)
    if len(aa) > len(bb):
        aa, bb = bb, aa
    tree = cKDTree(bb)
    distances, _ = tree.query(aa, k=1, workers=1)
    return float(np.min(distances))


def inspect_accessory_clusters(
    path: Path,
    *,
    mode: str = "character",
    up_axis: str = "y",
    max_link_gap_ratio: float = 0.06,
) -> AccessoryClusterReport:
    np, _ = _deps()
    warnings: list[str] = []
    errors: list[str] = []
    try:
        from part_map import _component_ids, _load_mesh, build_part_map

        mesh = _load_mesh(path)
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        if not len(vertices) or not len(faces):
            raise ValueError("mesh has no triangle geometry")
        if not math.isfinite(max_link_gap_ratio) or max_link_gap_ratio <= 0.0:
            raise ValueError("max_link_gap_ratio must be finite and positive")

        part = build_part_map(
            path,
            mode=mode,
            up_axis=up_axis,
        )
        main = next(
            (item for item in part.components if item.main_component),
            None,
        )
        if main is None:
            raise RuntimeError("part map has no main component")
        accessory_ids = sorted(int(x) for x in part.accessory_component_ids)
        if not accessory_ids:
            return AccessoryClusterReport(
                path=str(path),
                mode=mode,
                ready=False,
                main_component_id=int(main.component_id),
                accessory_components=0,
                cluster_count=0,
                selected_cluster_id=None,
                selected_component_ids=[],
                clusters=[],
                warnings=["no detached accessory candidates"],
                errors=[],
            )

        component_ids = _component_ids(faces)
        all_components = {
            int(item.component_id): item
            for item in part.components
        }

        def component_points(component_id: int):
            mask = component_ids == int(component_id)
            comp_faces = faces[mask]
            used = np.unique(comp_faces.reshape(-1))
            points = vertices[used]
            if not len(points):
                raise RuntimeError(
                    f"component {component_id} has no vertices"
                )
            return points, int(len(comp_faces))

        main_points, _ = component_points(int(main.component_id))
        main_lo = np.min(main_points, axis=0)
        main_hi = np.max(main_points, axis=0)
        main_diag = max(float(np.linalg.norm(main_hi - main_lo)), 1e-9)
        max_gap = main_diag * float(max_link_gap_ratio)

        geometry = {}
        for component_id in accessory_ids:
            points, face_count = component_points(component_id)
            geometry[component_id] = {
                "points": points,
                "face_count": face_count,
                "lo": np.min(points, axis=0),
                "hi": np.max(points, axis=0),
                "centroid": np.mean(points, axis=0),
                "extent": np.max(points, axis=0) - np.min(points, axis=0),
                "main_gap": _nearest_gap(points, main_points),
            }

        adjacency = {component_id: set() for component_id in accessory_ids}
        pair_gap = {}
        for i, left in enumerate(accessory_ids):
            a = geometry[left]
            for right in accessory_ids[i + 1:]:
                b = geometry[right]
                bbox_gap = _bbox_gap(
                    a["lo"], a["hi"], b["lo"], b["hi"]
                )
                if bbox_gap > max_gap:
                    continue
                gap = _nearest_gap(a["points"], b["points"])
                pair_gap[(left, right)] = gap
                if gap <= max_gap:
                    adjacency[left].add(right)
                    adjacency[right].add(left)

        groups = []
        remaining = set(accessory_ids)
        while remaining:
            seed = min(remaining)
            queue = [seed]
            group = set()
            while queue:
                current = queue.pop(0)
                if current in group:
                    continue
                group.add(current)
                remaining.discard(current)
                queue.extend(sorted(adjacency[current] - group))
            groups.append(sorted(group))

        total_faces = max(int(len(faces)), 1)
        clusters: list[AccessoryCluster] = []
        for cluster_index, members in enumerate(groups):
            member_rows = []
            min_main_gap = float("inf")
            max_internal = 0.0
            labels = set()
            cluster_faces = 0

            for component_id in members:
                g = geometry[component_id]
                comp = all_components[component_id]
                main_gap_ratio = float(g["main_gap"] / main_diag)
                min_main_gap = min(min_main_gap, main_gap_ratio)
                cluster_faces += int(g["face_count"])
                labels.add(str(comp.spatial_label))

                linked = sorted(
                    int(x)
                    for x in adjacency[component_id]
                    if x in members
                )
                for other in linked:
                    key = (min(component_id, other), max(component_id, other))
                    if key in pair_gap:
                        max_internal = max(
                            max_internal,
                            float(pair_gap[key] / main_diag),
                        )

                member_rows.append(AccessoryClusterMember(
                    component_id=int(component_id),
                    face_count=int(g["face_count"]),
                    face_fraction=round(
                        float(g["face_count"] / total_faces), 8
                    ),
                    spatial_label=str(comp.spatial_label),
                    centroid=[
                        round(float(x), 8)
                        for x in g["centroid"]
                    ],
                    extent=[
                        round(float(x), 8)
                        for x in g["extent"]
                    ],
                    gap_to_main_ratio=round(main_gap_ratio, 8),
                    linked_accessory_ids=linked,
                ))

            direct_main_anchors = sorted(
                int(component_id)
                for component_id in members
                if (
                    float(
                        geometry[component_id]["main_gap"]
                        / main_diag
                    )
                    <= max_link_gap_ratio
                )
            )
            anchored = bool(direct_main_anchors)
            clusters.append(AccessoryCluster(
                cluster_id=int(cluster_index),
                component_ids=members,
                face_count=int(cluster_faces),
                face_fraction=round(
                    float(cluster_faces / total_faces), 8
                ),
                anchored_to_main=anchored,
                direct_main_anchors=direct_main_anchors,
                min_main_gap_ratio=round(float(min_main_gap), 8),
                max_internal_link_gap_ratio=round(float(max_internal), 8),
                spatial_labels=sorted(labels),
                members=member_rows,
            ))

        anchored = [cluster for cluster in clusters if cluster.anchored_to_main]
        if len(anchored) != 1:
            if not anchored:
                errors.append(
                    "no accessory cluster is anchored to the donor main body"
                )
            else:
                errors.append(
                    "multiple independent accessory clusters are anchored to "
                    "the donor main body; automatic insertion is ambiguous"
                )
        floating = [
            cluster for cluster in clusters
            if not cluster.anchored_to_main
        ]
        if floating:
            errors.append(
                "floating accessory clusters are present: "
                + ",".join(str(x.cluster_id) for x in floating)
            )

        selected = anchored[0] if len(anchored) == 1 and not floating else None
        if (
            selected is not None
            and len(selected.component_ids) > 1
            and len(selected.direct_main_anchors) == len(selected.component_ids)
        ):
            errors.append(
                "multi-piece candidates are all independently anchored to the "
                "main body; automatic grouping would be ambiguous"
            )
            selected = None
        if selected is not None and len(selected.component_ids) == 1:
            warnings.append(
                "single-component accessory; cluster audit remains valid "
                "but multi-piece insertion is not required"
            )

        return AccessoryClusterReport(
            path=str(path),
            mode=mode,
            ready=bool(selected is not None and not errors),
            main_component_id=int(main.component_id),
            accessory_components=len(accessory_ids),
            cluster_count=len(clusters),
            selected_cluster_id=(
                None if selected is None else int(selected.cluster_id)
            ),
            selected_component_ids=(
                [] if selected is None else list(selected.component_ids)
            ),
            clusters=clusters,
            warnings=warnings,
            errors=errors,
        )
    except Exception as exc:
        return AccessoryClusterReport(
            path=str(path),
            mode=mode,
            ready=False,
            main_component_id=None,
            accessory_components=0,
            cluster_count=0,
            selected_cluster_id=None,
            selected_component_ids=[],
            clusters=[],
            warnings=warnings,
            errors=[f"{type(exc).__name__}:{exc}"],
        )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description=(
            "Audit detached accessory candidates as proximity-connected logical "
            "clusters, rejecting ambiguous independent accessory groups."
        )
    )
    parser.add_argument("mesh", type=Path)
    parser.add_argument(
        "--mode",
        choices=["character", "prop", "architecture"],
        default="character",
    )
    parser.add_argument(
        "--up-axis",
        choices=["x", "y", "z"],
        default="y",
    )
    parser.add_argument("--max-link-gap-ratio", type=float, default=0.06)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    result = inspect_accessory_clusters(
        args.mesh,
        mode=args.mode,
        up_axis=args.up_axis,
        max_link_gap_ratio=args.max_link_gap_ratio,
    )
    payload = json.dumps(asdict(result), indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")
    return 0 if result.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
