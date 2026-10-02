from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from native_360_geometry_gate import (
    Native360GeometryRejected,
    assert_native_character_360,
    assert_native_volumetric,
    inspect_native_360_geometry,
)


def _write_mesh(path: Path, mesh: trimesh.Trimesh):
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name="Mesh", geom_name="Mesh")
    path.write_bytes(scene.export(file_type="glb"))


def test_real_volume_passes(tmp_path: Path):
    path = tmp_path / "volume.glb"
    _write_mesh(path, trimesh.creation.box(extents=(0.8, 2.0, 0.45)))
    report = assert_native_character_360(path, label="volume")
    assert report["catastrophically_planar"] is False
    assert report["minor_span_ratio"] > 0.012


def test_generic_volumetric_gate_rejects_planar_native_donor(tmp_path: Path):
    path = tmp_path / "head_sheet.glb"
    _write_mesh(path, trimesh.creation.box(extents=(1.0, 1.0, 0.0005)))

    try:
        assert_native_volumetric(path, label="head-donor")
    except Native360GeometryRejected as exc:
        assert "volumetric 3D evidence" in str(exc)
        assert "head-donor" in str(exc)
    else:
        raise AssertionError("planar native donor must be rejected")


def test_sheet_like_character_is_rejected(tmp_path: Path):
    path = tmp_path / "sheet.glb"
    # Deliberately non-zero thickness so this catches "almost PNG" geometry,
    # not only a mathematically perfect plane.
    _write_mesh(path, trimesh.creation.box(extents=(0.9, 2.0, 0.001)))
    report = inspect_native_360_geometry(path)
    assert report["catastrophically_planar"] is True
    try:
        assert_native_character_360(path, label="sheet")
    except Native360GeometryRejected as exc:
        assert "catastrophically planar" in str(exc)
    else:
        raise AssertionError("sheet-like character must be rejected")


def test_thin_but_real_volume_is_not_overrejected(tmp_path: Path):
    path = tmp_path / "thin.glb"
    _write_mesh(path, trimesh.creation.box(extents=(0.75, 2.0, 0.08)))
    report = assert_native_character_360(path)
    assert report["catastrophically_planar"] is False
