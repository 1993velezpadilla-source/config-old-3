#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class PartRegion:
    label: str
    face_count: int
    face_fraction: float
    component_ids: list[int]
    bbox_min: list[float]
    bbox_max: list[float]
    centroid: list[float]


@dataclass
class ComponentRegion:
    component_id: int
    face_count: int
    face_fraction: float
    centroid: list[float]
    extent: list[float]
    main_component: bool
    accessory_candidate: bool
    spatial_label: str


@dataclass
class PartMapResult:
    mesh: str
    mode: str
    up_axis: str
    face_count: int
    component_count: int
    regions: list[PartRegion]
    components: list[ComponentRegion]
    face_labels: list[str]
    accessory_component_ids: list[int]
    method: str = "hayuya-deterministic-spatial-component-partmap-v1"


def _deps():
    import numpy as np
    import trimesh
    return np, trimesh


def _load_mesh(path: Path):
    np, trimesh = _deps()
    loaded = trimesh.load(path, force="scene", process=False)
    if hasattr(loaded, "geometry"):
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
        return trimesh.util.concatenate(meshes)
    if hasattr(loaded, "faces") and len(loaded.faces):
        return loaded
    raise ValueError("no triangle geometry")


def _component_ids(faces):
    import numpy as np

    faces = np.asarray(faces, dtype=np.int64)
    count = len(faces)
    if count == 0:
        return np.empty(0, dtype=np.int64)

    vertex_to_faces: dict[int, list[int]] = {}
    for face_id, tri in enumerate(faces):
        for vertex in tri:
            vertex_to_faces.setdefault(int(vertex), []).append(face_id)

    parent = np.arange(count, dtype=np.int64)

    def find(x: int) -> int:
        while int(parent[x]) != x:
            parent[x] = parent[int(parent[x])]
            x = int(parent[x])
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for linked in vertex_to_faces.values():
        if len(linked) <= 1:
            continue
        anchor = linked[0]
        for other in linked[1:]:
            union(anchor, other)

    roots = [find(i) for i in range(count)]
    remap: dict[int, int] = {}
    ids = np.empty(count, dtype=np.int64)
    for i, root in enumerate(roots):
        if root not in remap:
            remap[root] = len(remap)
        ids[i] = remap[root]
    return ids


def _axis_index(up_axis: str) -> int:
    if up_axis == "x":
        return 0
    if up_axis == "y":
        return 1
    if up_axis == "z":
        return 2
    raise ValueError("up_axis must be x, y or z")


def _spatial_label(
    normalized_height: float,
    lateral: float,
    *,
    mode: str,
) -> str:
    if mode == "character":
        if normalized_height >= 0.80:
            region = "head"
        elif normalized_height >= 0.55:
            region = "upper_body"
        elif normalized_height >= 0.38:
            region = "lower_body"
        else:
            region = "legs_feet"

        # Side annotation is useful for asymmetric detail references without
        # pretending that geometry-only heuristics can identify exact hands.
        if abs(lateral) >= 0.22:
            side = "right" if lateral > 0 else "left"
            return f"{region}_{side}"
        return region

    if mode == "architecture":
        if normalized_height >= 0.78:
            return "roof_upper"
        if normalized_height >= 0.20:
            return "wall_body"
        return "foundation_base"

    # Props and unknown objects get neutral production regions.
    if normalized_height >= 0.72:
        return "upper"
    if normalized_height <= 0.25:
        return "base"
    return "body"


def build_part_map(
    mesh_path: Path,
    *,
    mode: str,
    up_axis: str = "y",
    accessory_face_fraction: float = 0.08,
) -> PartMapResult:
    np, _ = _deps()
    mesh = _load_mesh(mesh_path)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if not len(faces):
        raise ValueError("empty mesh")

    face_centroids = vertices[faces].mean(axis=1)
    axis = _axis_index(up_axis)
    low = float(vertices[:, axis].min())
    high = float(vertices[:, axis].max())
    span = max(high - low, 1e-9)
    normalized_height = (face_centroids[:, axis] - low) / span

    lateral_axes = [i for i in range(3) if i != axis]
    # Choose the wider horizontal axis as left/right. This remains deterministic
    # and avoids assuming a particular front-facing coordinate convention.
    extents = vertices.max(axis=0) - vertices.min(axis=0)
    lateral_axis = max(lateral_axes, key=lambda i: float(extents[i]))
    lateral_center = float((vertices[:, lateral_axis].min() + vertices[:, lateral_axis].max()) * 0.5)
    lateral_span = max(float(extents[lateral_axis]), 1e-9)
    lateral = (face_centroids[:, lateral_axis] - lateral_center) / lateral_span

    component_ids = _component_ids(faces)
    unique_components, counts = np.unique(component_ids, return_counts=True)
    main_component_id = int(unique_components[int(np.argmax(counts))])
    component_count = len(unique_components)

    labels = [
        _spatial_label(float(h), float(side), mode=mode)
        for h, side in zip(normalized_height, lateral)
    ]

    # Small disconnected components are deliberately preserved and annotated as
    # accessory candidates. This metadata informs repair/retopo; it is not an
    # automatic deletion instruction.
    components: list[ComponentRegion] = []
    accessory_ids: list[int] = []
    for component_id, count in zip(unique_components, counts):
        mask = component_ids == component_id
        component_faces = faces[mask]
        used = np.unique(component_faces.reshape(-1))
        vv = vertices[used]
        centroid = vv.mean(axis=0)
        extent = vv.max(axis=0) - vv.min(axis=0)
        fraction = float(count / len(faces))
        is_main = int(component_id) == main_component_id
        accessory = bool(
            not is_main
            and fraction <= accessory_face_fraction
        )
        if accessory:
            accessory_ids.append(int(component_id))

        local_labels = [labels[i] for i in np.nonzero(mask)[0]]
        dominant = max(set(local_labels), key=local_labels.count)
        components.append(
            ComponentRegion(
                component_id=int(component_id),
                face_count=int(count),
                face_fraction=round(fraction, 6),
                centroid=[round(float(x), 8) for x in centroid],
                extent=[round(float(x), 8) for x in extent],
                main_component=is_main,
                accessory_candidate=accessory,
                spatial_label=dominant,
            )
        )

    grouped: dict[str, list[int]] = {}
    for face_id, label in enumerate(labels):
        grouped.setdefault(label, []).append(face_id)

    regions: list[PartRegion] = []
    for label in sorted(grouped):
        ids = np.asarray(grouped[label], dtype=np.int64)
        region_faces = faces[ids]
        used = np.unique(region_faces.reshape(-1))
        vv = vertices[used]
        centroid = vv.mean(axis=0)
        region_components = sorted(
            {int(component_ids[i]) for i in ids.tolist()}
        )
        regions.append(
            PartRegion(
                label=label,
                face_count=int(len(ids)),
                face_fraction=round(float(len(ids) / len(faces)), 6),
                component_ids=region_components,
                bbox_min=[round(float(x), 8) for x in vv.min(axis=0)],
                bbox_max=[round(float(x), 8) for x in vv.max(axis=0)],
                centroid=[round(float(x), 8) for x in centroid],
            )
        )

    return PartMapResult(
        mesh=str(mesh_path),
        mode=mode,
        up_axis=up_axis,
        face_count=int(len(faces)),
        component_count=component_count,
        regions=regions,
        components=components,
        face_labels=labels,
        accessory_component_ids=sorted(accessory_ids),
    )


def write_part_map(result: PartMapResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="HAYUYA deterministic semantic-lite mesh Part Map.")
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--mode", choices=["prop", "character", "architecture"], default="prop")
    parser.add_argument("--up-axis", choices=["x", "y", "z"], default="y")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_part_map(
        args.mesh,
        mode=args.mode,
        up_axis=args.up_axis,
    )
    write_part_map(result, args.output)
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
