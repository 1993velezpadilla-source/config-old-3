#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import trimesh


AXIS_NAMES = ("x", "y", "z")


def _json_vec(values) -> list[float]:
    return [round(float(v), 8) for v in values]


def detect_boundary_support_slabs(
    mesh: trimesh.Trimesh,
    *,
    band_fraction: float = 0.015,
    min_face_fraction: float = 0.10,
    min_area_fraction: float = 0.12,
    min_cross_axis_coverage: float = 0.80,
    max_thickness_fraction: float = 0.0225,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Detect giant thin slabs hugging a mesh bounding-box boundary.

    This is intentionally shape-agnostic. It does not know about humans,
    clothing, nuns, floors, or backgrounds. A region qualifies only when it:
      * hugs one global boundary,
      * consumes a large fraction of faces and area,
      * spans most of both orthogonal axes, and
      * is thin along its boundary axis.

    Typical false geometry from image-to-3D systems is a reconstructed photo
    backdrop/floor. Normal character/object geometry is far too localized to
    satisfy all of these gates simultaneously.
    """
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) < 32:
        return np.zeros(len(getattr(mesh, "faces", [])), dtype=bool), []

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    centers = np.asarray(mesh.triangles_center, dtype=np.float64)
    face_areas = np.asarray(mesh.area_faces, dtype=np.float64)

    bounds_min = vertices.min(axis=0)
    bounds_max = vertices.max(axis=0)
    extents = bounds_max - bounds_min
    total_area = max(float(face_areas.sum()), 1e-12)
    total_faces = max(int(len(faces)), 1)

    remove = np.zeros(len(faces), dtype=bool)
    slabs: list[dict[str, Any]] = []

    for axis in range(3):
        axis_extent = float(extents[axis])
        if axis_extent <= 1e-9:
            continue
        orthogonal = [idx for idx in range(3) if idx != axis]

        for side in ("min", "max"):
            boundary = (
                float(bounds_min[axis])
                if side == "min"
                else float(bounds_max[axis])
            )
            band = float(band_fraction) * axis_extent
            if side == "min":
                mask = centers[:, axis] <= boundary + band
            else:
                mask = centers[:, axis] >= boundary - band

            face_ids = np.flatnonzero(mask)
            if not len(face_ids):
                continue

            vertex_ids = np.unique(faces[face_ids].ravel())
            region_vertices = vertices[vertex_ids]
            region_span = region_vertices.max(axis=0) - region_vertices.min(axis=0)

            face_fraction = float(len(face_ids) / total_faces)
            area_fraction = float(face_areas[face_ids].sum() / total_area)
            coverage = [
                float(region_span[idx] / extents[idx])
                if float(extents[idx]) > 1e-9
                else 0.0
                for idx in orthogonal
            ]
            thickness_fraction = float(region_span[axis] / axis_extent)

            qualifies = (
                face_fraction >= float(min_face_fraction)
                and area_fraction >= float(min_area_fraction)
                and min(coverage) >= float(min_cross_axis_coverage)
                and thickness_fraction <= float(max_thickness_fraction)
            )
            if not qualifies:
                continue

            remove |= mask
            slabs.append(
                {
                    "axis": AXIS_NAMES[axis],
                    "axis_index": axis,
                    "side": side,
                    "faces": int(len(face_ids)),
                    "face_fraction": round(face_fraction, 6),
                    "area_fraction": round(area_fraction, 6),
                    "cross_axis_coverage": [
                        round(float(v), 6) for v in coverage
                    ],
                    "thickness_fraction": round(thickness_fraction, 6),
                    "boundary": round(boundary, 8),
                    "band_fraction": float(band_fraction),
                }
            )

    return remove, slabs


def strip_boundary_support_slabs(
    path: Path,
    *,
    band_fraction: float = 0.015,
) -> dict[str, Any]:
    """Remove detected support/backdrop slabs in-place from a geometry GLB.

    The cleanup is conservative and self-vetoing: even if a boundary slab is
    detected, the proposed residual must retain a substantial 3D object.
    """
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    loaded = trimesh.load(path, force="mesh", process=False)
    if not isinstance(loaded, trimesh.Trimesh):
        raise RuntimeError(f"support cleanup expected mesh: {type(loaded)!r}")

    before_faces = int(len(loaded.faces))
    before_vertices = int(len(loaded.vertices))
    before_bounds = np.asarray(loaded.bounds, dtype=np.float64)
    before_extents = np.asarray(loaded.extents, dtype=np.float64)
    before_area = max(float(loaded.area), 1e-12)

    remove, slabs = detect_boundary_support_slabs(
        loaded,
        band_fraction=band_fraction,
    )

    report: dict[str, Any] = {
        "schema": 1,
        "method": "boundary_support_slab_cleanup_v1",
        "applied": False,
        "detected_slabs": slabs,
        "before": {
            "faces": before_faces,
            "vertices": before_vertices,
            "bounds": [_json_vec(row) for row in before_bounds],
            "extents": _json_vec(before_extents),
            "area": round(before_area, 8),
            "bytes": int(path.stat().st_size),
        },
    }

    if not slabs or not bool(remove.any()):
        report["reason"] = "no_support_slabs_detected"
        return report

    keep_ids = np.flatnonzero(~remove)
    if len(keep_ids) < max(32, int(before_faces * 0.15)):
        report["reason"] = "residual_too_small_faces"
        return report

    cleaned = loaded.submesh([keep_ids], append=True, repair=False)
    if not isinstance(cleaned, trimesh.Trimesh) or len(cleaned.faces) < 32:
        report["reason"] = "residual_invalid"
        return report

    after_extents = np.asarray(cleaned.extents, dtype=np.float64)
    relative_extents = np.divide(
        after_extents,
        np.maximum(before_extents, 1e-12),
    )
    if float(np.min(relative_extents)) < 0.05:
        report["reason"] = "residual_collapsed_axis"
        report["candidate_relative_extents"] = _json_vec(relative_extents)
        return report

    removed_area_fraction = 1.0 - (float(cleaned.area) / before_area)
    if removed_area_fraction < 0.10:
        report["reason"] = "removed_area_too_small"
        return report

    tmp = path.with_name(path.stem + ".support-clean.tmp.glb")
    try:
        trimesh.Scene(cleaned).export(tmp)
        blob = tmp.read_bytes()
        if len(blob) < 1024 or blob[:4] != b"glTF":
            raise RuntimeError(
                f"support cleanup exported invalid GLB: bytes={len(blob)}"
            )
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()

    after_bounds = np.asarray(cleaned.bounds, dtype=np.float64)
    report.update(
        {
            "applied": True,
            "reason": "giant_boundary_support_removed",
            "removed_faces": int(remove.sum()),
            "removed_face_fraction": round(
                float(remove.sum() / before_faces), 6
            ),
            "removed_area_fraction": round(removed_area_fraction, 6),
            "after": {
                "faces": int(len(cleaned.faces)),
                "vertices": int(len(cleaned.vertices)),
                "bounds": [_json_vec(row) for row in after_bounds],
                "extents": _json_vec(after_extents),
                "relative_extents": _json_vec(relative_extents),
                "area": round(float(cleaned.area), 8),
                "bytes": int(path.stat().st_size),
            },
        }
    )
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Strip giant boundary support slabs from a geometry GLB"
    )
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    report = strip_boundary_support_slabs(args.input)
    print("HAYUYA_SUPPORT_CLEANUP", json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
