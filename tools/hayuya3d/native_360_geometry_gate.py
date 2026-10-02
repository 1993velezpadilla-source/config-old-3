#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


class Native360GeometryRejected(RuntimeError):
    """Raised only for catastrophically planar character candidates."""


def _load_vertices(path: Path) -> np.ndarray:
    import trimesh

    scene = trimesh.load(path, force="scene", process=False)
    chunks = []
    nodes = list(scene.graph.nodes_geometry)
    if nodes:
        for node in nodes:
            transform, geometry_name = scene.graph.get(node)
            geometry = scene.geometry[geometry_name]
            if not hasattr(geometry, "vertices") or len(geometry.vertices) == 0:
                continue
            local = np.asarray(geometry.vertices, dtype=np.float64)
            chunks.append(trimesh.transform_points(local, transform))
    else:
        for geometry in scene.geometry.values():
            if hasattr(geometry, "vertices") and len(geometry.vertices):
                chunks.append(np.asarray(geometry.vertices, dtype=np.float64))

    if not chunks:
        raise ValueError(f"no mesh vertices in {path}")
    return np.concatenate(chunks, axis=0)


def inspect_native_360_geometry(path: Path) -> dict:
    vertices = _load_vertices(Path(path))
    if len(vertices) < 8:
        raise ValueError("too few vertices for 360 geometry inspection")

    # Robust axis spans ignore single stray vertices/accessories.
    lo = np.percentile(vertices, 2.0, axis=0)
    hi = np.percentile(vertices, 98.0, axis=0)
    spans = np.maximum(hi - lo, 0.0)
    major = float(np.max(spans))
    minor = float(np.min(spans))
    middle = float(np.partition(spans, 1)[1])
    minor_span_ratio = minor / max(major, 1e-12)
    middle_span_ratio = middle / max(major, 1e-12)

    centered = vertices - np.median(vertices, axis=0)
    cov = np.cov(centered.T)
    eig = np.linalg.eigvalsh(cov)
    eig = np.maximum(np.asarray(eig, dtype=np.float64), 0.0)
    eig.sort()
    covariance_minor_ratio = float(eig[0] / max(eig[-1], 1e-12))

    # Fail closed only when both robust thickness and volumetric variance say
    # "this is effectively a sheet". This intentionally avoids rejecting thin
    # but legitimate 3D garments/accessories.
    catastrophically_planar = bool(
        minor_span_ratio < 0.012
        and covariance_minor_ratio < 0.0004
    )

    return {
        "schema": 1,
        "policy": "hayuya-native-360-geometry-gate-v1",
        "path": str(path),
        "vertex_count": int(len(vertices)),
        "robust_spans": [float(x) for x in spans],
        "minor_span_ratio": float(minor_span_ratio),
        "middle_span_ratio": float(middle_span_ratio),
        "covariance_eigenvalues": [float(x) for x in eig],
        "covariance_minor_ratio": float(covariance_minor_ratio),
        "catastrophically_planar": catastrophically_planar,
        "native_360_required_for_character": True,
        "note": (
            "This is a catastrophic sheet/proxy detector, not a beauty or "
            "proportion score. Normal thin 3D assets are allowed."
        ),
    }


def assert_native_character_360(path: Path, *, label: str | None = None) -> dict:
    report = inspect_native_360_geometry(path)
    if report["catastrophically_planar"]:
        prefix = f"{label}: " if label else ""
        raise Native360GeometryRejected(
            prefix
            + "character candidate is catastrophically planar and cannot be "
            "promoted as a native 360 model "
            + f"(minor_span_ratio={report['minor_span_ratio']:.6f}, "
            + f"covariance_minor_ratio={report['covariance_minor_ratio']:.8f})"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--character", action="store_true")
    args = parser.parse_args()
    report = (
        assert_native_character_360(args.mesh)
        if args.character
        else inspect_native_360_geometry(args.mesh)
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
