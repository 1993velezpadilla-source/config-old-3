#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AccessorySourcePiece:
    candidate_component_id: int
    spatial_label: str
    node_index: int
    mesh_index: int
    primitive_index: int
    primitive_component_id: int
    face_count: int
    used_vertex_ids: list[int]
    material_index: int | None
    texcoord0_accessor: int | None
    basecolor_texture: bool
    ready: bool
    blockers: list[str]


@dataclass
class AccessorySourceGroup:
    node_index: int
    mesh_index: int
    primitive_index: int
    candidate_component_ids: list[int]
    primitive_component_ids: list[int]
    face_count: int
    used_vertex_ids: list[int]
    material_index: int | None
    texcoord0_accessor: int | None
    basecolor_texture: bool
    ready: bool
    blockers: list[str]


@dataclass
class AccessorySourceGroupReport:
    path: str
    mode: str
    ready: bool
    selected_component_ids: list[int]
    piece_count: int
    group_count: int
    groups: list[AccessorySourceGroup]
    pieces: list[AccessorySourcePiece]
    warnings: list[str]
    errors: list[str]
    method: str = "hayuya-accessory-source-groups-v1"


def _deps():
    import numpy as np
    return np


def _primitive_triangles(doc: dict, binary: bytes, primitive: dict):
    np = _deps()
    from skin_weight_qa import _read_accessor

    attrs = primitive.get("attributes") or {}
    position = attrs.get("POSITION")
    indices = primitive.get("indices")
    if not isinstance(position, int) or not isinstance(indices, int):
        raise ValueError("primitive must be indexed with POSITION")
    if int(primitive.get("mode", 4)) != 4:
        raise ValueError("primitive must use TRIANGLES mode")
    vertices = np.asarray(
        _read_accessor(doc, binary, position),
        dtype=np.float64,
    )
    raw = np.asarray(
        _read_accessor(doc, binary, indices),
        dtype=np.int64,
    ).reshape(-1)
    if len(raw) % 3:
        raise ValueError("primitive index count is not divisible by three")
    faces = raw.reshape((-1, 3))
    if len(faces) and (
        int(np.min(faces)) < 0
        or int(np.max(faces)) >= len(vertices)
    ):
        raise ValueError("primitive indices reference missing vertices")
    return vertices, faces


def _world_components(path: Path):
    np = _deps()
    from deformation_qa import _global_matrices
    from gltf_position_patch import _doc_and_bin
    from part_map import _component_ids

    doc, binary, _ = _doc_and_bin(path)
    globals_ = _global_matrices(doc, {})
    meshes = doc.get("meshes") or []
    rows = []
    for node_index, node in enumerate(doc.get("nodes") or []):
        mesh_index = node.get("mesh")
        if not isinstance(mesh_index, int) or not (0 <= mesh_index < len(meshes)):
            continue
        matrix = np.asarray(globals_[node_index], dtype=np.float64)
        for primitive_index, primitive in enumerate(
            meshes[mesh_index].get("primitives") or []
        ):
            try:
                positions, faces = _primitive_triangles(
                    doc,
                    binary,
                    primitive,
                )
            except Exception:
                continue
            homogeneous = np.concatenate(
                [
                    positions,
                    np.ones((len(positions), 1), dtype=np.float64),
                ],
                axis=1,
            )
            world = (matrix @ homogeneous.T).T[:, :3]
            component_ids = _component_ids(faces)
            for component_id in np.unique(component_ids):
                selected_faces = faces[component_ids == int(component_id)]
                used = np.unique(selected_faces.reshape(-1))
                points = world[used]
                if not len(points):
                    continue
                rows.append({
                    "node_index": int(node_index),
                    "mesh_index": int(mesh_index),
                    "primitive_index": int(primitive_index),
                    "primitive_component_id": int(component_id),
                    "face_count": int(len(selected_faces)),
                    "used_vertex_ids": used,
                    "centroid": np.mean(points, axis=0),
                    "extent": np.max(points, axis=0) - np.min(points, axis=0),
                    "primitive": primitive,
                })
    if not rows:
        raise RuntimeError("GLB exposes no indexed triangle components")
    return doc, binary, rows


def _basecolor_texture(material: dict) -> bool:
    pbr = material.get("pbrMetallicRoughness") or {}
    return isinstance(pbr.get("baseColorTexture"), dict)


def audit_accessory_source_groups(
    path: Path,
    *,
    mode: str = "character",
    up_axis: str = "y",
) -> AccessorySourceGroupReport:
    np = _deps()
    warnings: list[str] = []
    errors: list[str] = []
    try:
        from accessory_match import inspect_accessories
        from accessory_cluster import inspect_accessory_clusters

        candidates = inspect_accessories(
            path,
            mode=mode,
            up_axis=up_axis,
        )
        if not candidates:
            return AccessorySourceGroupReport(
                path=str(path),
                mode=mode,
                ready=False,
                selected_component_ids=[],
                piece_count=0,
                group_count=0,
                groups=[],
                pieces=[],
                warnings=["no detached accessory candidates"],
                errors=[],
            )

        if len(candidates) == 1:
            selected = [candidates[0]]
        else:
            cluster = inspect_accessory_clusters(
                path,
                mode=mode,
                up_axis=up_axis,
            )
            if not cluster.ready or not cluster.selected_component_ids:
                detail = ";".join(cluster.errors or [])
                raise RuntimeError(
                    "accessory candidates are not one proven logical cluster"
                    + (f": {detail}" if detail else "")
                )
            by_id = {
                int(item.component_id): item
                for item in candidates
            }
            selected_ids = [
                int(x) for x in cluster.selected_component_ids
            ]
            if set(selected_ids) != set(by_id):
                raise RuntimeError(
                    "cluster proof did not account for every accessory candidate"
                )
            selected = [by_id[x] for x in selected_ids]

        doc, binary, components = _world_components(path)
        all_points = []
        for item in components:
            # Reconstruct the points used by this component from its own
            # primitive-space accessor, then use centroid/extent already in
            # world space for the mapping score.
            all_points.append(np.asarray(item["centroid"], dtype=np.float64))
        cloud = np.asarray(all_points, dtype=np.float64)
        lo = np.min(cloud, axis=0)
        hi = np.max(cloud, axis=0)
        extent = hi - lo
        diagonal = max(float(np.linalg.norm(extent)), 1e-9)
        safe_extent = np.maximum(extent, diagonal * 1e-6)

        # The flattened accessory detector normalizes against the complete
        # asset bounds, not centroid-cloud bounds. Get those exact bounds from
        # the canonical flattened mesh for score parity.
        from part_map import _load_mesh
        flat = _load_mesh(path)
        flat_vertices = np.asarray(flat.vertices, dtype=np.float64)
        asset_lo = np.min(flat_vertices, axis=0)
        asset_hi = np.max(flat_vertices, axis=0)
        asset_extent = asset_hi - asset_lo
        asset_diag = max(float(np.linalg.norm(asset_extent)), 1e-9)
        asset_safe_extent = np.maximum(
            asset_extent,
            asset_diag * 1e-6,
        )

        mapped = []
        used_rows = set()
        for candidate in selected:
            wanted_centroid = np.asarray(
                candidate.normalized_centroid,
                dtype=np.float64,
            )
            wanted_extent = np.asarray(
                candidate.normalized_extent,
                dtype=np.float64,
            )
            scored = []
            for item in components:
                if int(item["face_count"]) != int(candidate.face_count):
                    continue
                key = (
                    int(item["node_index"]),
                    int(item["mesh_index"]),
                    int(item["primitive_index"]),
                    int(item["primitive_component_id"]),
                )
                if key in used_rows:
                    continue
                normalized_centroid = (
                    np.asarray(item["centroid"], dtype=np.float64)
                    - asset_lo
                ) / asset_safe_extent
                normalized_extent = (
                    np.asarray(item["extent"], dtype=np.float64)
                ) / asset_safe_extent
                score = float(
                    np.linalg.norm(
                        normalized_centroid - wanted_centroid
                    )
                    + np.linalg.norm(
                        normalized_extent - wanted_extent
                    )
                )
                scored.append((score, key, item))

            if not scored:
                raise RuntimeError(
                    f"could not map accessory component "
                    f"{candidate.component_id} back to a donor primitive"
                )
            scored.sort(key=lambda row: row[0])
            best_score, best_key, best = scored[0]
            second_score = scored[1][0] if len(scored) > 1 else None
            if best_score > 0.02:
                raise RuntimeError(
                    "accessory source mapping drift is too large for component "
                    f"{candidate.component_id}: {best_score:.6f}>0.020000"
                )
            if (
                second_score is not None
                and second_score - best_score < 0.01
            ):
                raise RuntimeError(
                    "accessory source mapping is ambiguous for component "
                    f"{candidate.component_id}"
                )
            used_rows.add(best_key)
            mapped.append((candidate, best))

        materials = doc.get("materials") or []
        pieces: list[AccessorySourcePiece] = []
        grouped: dict[tuple[int, int, int], list[tuple]] = {}

        for candidate, item in mapped:
            primitive = item["primitive"]
            attrs = primitive.get("attributes") or {}
            material_index = primitive.get("material")
            texcoord = attrs.get("TEXCOORD_0")
            blockers = []
            material = None
            if (
                not isinstance(material_index, int)
                or not (0 <= material_index < len(materials))
            ):
                blockers.append("primitive has no valid material binding")
            else:
                material = materials[int(material_index)] or {}
                if not _basecolor_texture(material):
                    blockers.append(
                        "primitive material has no baseColor texture"
                    )
            if not isinstance(texcoord, int):
                blockers.append("primitive has no TEXCOORD_0")

            key = (
                int(item["node_index"]),
                int(item["mesh_index"]),
                int(item["primitive_index"]),
            )
            grouped.setdefault(key, []).append((candidate, item))
            pieces.append(AccessorySourcePiece(
                candidate_component_id=int(candidate.component_id),
                spatial_label=str(candidate.spatial_label),
                node_index=key[0],
                mesh_index=key[1],
                primitive_index=key[2],
                primitive_component_id=int(
                    item["primitive_component_id"]
                ),
                face_count=int(item["face_count"]),
                used_vertex_ids=[
                    int(x) for x in item["used_vertex_ids"].tolist()
                ],
                material_index=(
                    int(material_index)
                    if isinstance(material_index, int)
                    else None
                ),
                texcoord0_accessor=(
                    int(texcoord)
                    if isinstance(texcoord, int)
                    else None
                ),
                basecolor_texture=bool(
                    material is not None
                    and _basecolor_texture(material)
                ),
                ready=not blockers,
                blockers=blockers,
            ))

        groups: list[AccessorySourceGroup] = []
        for key in sorted(grouped):
            members = grouped[key]
            primitive = members[0][1]["primitive"]
            attrs = primitive.get("attributes") or {}
            material_index = primitive.get("material")
            texcoord = attrs.get("TEXCOORD_0")
            blockers = []
            material = None
            if (
                not isinstance(material_index, int)
                or not (0 <= material_index < len(materials))
            ):
                blockers.append("primitive has no valid material binding")
            else:
                material = materials[int(material_index)] or {}
                if not _basecolor_texture(material):
                    blockers.append(
                        "primitive material has no baseColor texture"
                    )
            if not isinstance(texcoord, int):
                blockers.append("primitive has no TEXCOORD_0")
            used = np.unique(np.concatenate([
                np.asarray(item["used_vertex_ids"], dtype=np.int64)
                for _, item in members
            ]))
            groups.append(AccessorySourceGroup(
                node_index=key[0],
                mesh_index=key[1],
                primitive_index=key[2],
                candidate_component_ids=[
                    int(candidate.component_id)
                    for candidate, _ in members
                ],
                primitive_component_ids=[
                    int(item["primitive_component_id"])
                    for _, item in members
                ],
                face_count=int(sum(
                    int(item["face_count"])
                    for _, item in members
                )),
                used_vertex_ids=[int(x) for x in used.tolist()],
                material_index=(
                    int(material_index)
                    if isinstance(material_index, int)
                    else None
                ),
                texcoord0_accessor=(
                    int(texcoord)
                    if isinstance(texcoord, int)
                    else None
                ),
                basecolor_texture=bool(
                    material is not None
                    and _basecolor_texture(material)
                ),
                ready=not blockers,
                blockers=blockers,
            ))

        failed = [item for item in pieces if not item.ready]
        if failed:
            errors.append(
                "one or more accessory source pieces lack complete "
                "material/UV evidence"
            )
        if len(groups) > 1:
            warnings.append(
                "multi-primitive accessory cluster requires split-preserving "
                "insertion to retain per-primitive materials"
            )

        return AccessorySourceGroupReport(
            path=str(path),
            mode=mode,
            ready=bool(not errors and all(group.ready for group in groups)),
            selected_component_ids=[
                int(item.component_id) for item in selected
            ],
            piece_count=len(pieces),
            group_count=len(groups),
            groups=groups,
            pieces=pieces,
            warnings=warnings,
            errors=errors,
        )
    except Exception as exc:
        return AccessorySourceGroupReport(
            path=str(path),
            mode=mode,
            ready=False,
            selected_component_ids=[],
            piece_count=0,
            group_count=0,
            groups=[],
            pieces=[],
            warnings=warnings,
            errors=[f"{type(exc).__name__}:{exc}"],
        )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description=(
            "Map one proven logical accessory cluster back to donor glTF "
            "primitives/materials so split-preserving insertion can retain "
            "piece-specific UV/PBR evidence."
        )
    )
    parser.add_argument("mesh", type=Path)
    parser.add_argument(
        "--mode",
        choices=["character", "prop", "architecture"],
        default="character",
    )
    parser.add_argument("--up-axis", choices=["x", "y", "z"], default="y")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    report = audit_accessory_source_groups(
        args.mesh,
        mode=args.mode,
        up_axis=args.up_axis,
    )
    payload = json.dumps(asdict(report), indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")
    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
