from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest
import trimesh
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from native_geometry_guard import assert_native_candidate
from silhouette_conform import _require_legacy_projection_profile
from native_silhouette_conform import (
    _bounded_render_faces,
    _front_surface_vertex_mask,
    _smooth_topology_displacements,
    conform_native_silhouette,
)


def _box(path: Path, extents=(1.0, 2.0, 0.45)):
    mesh = trimesh.creation.box(extents=extents)
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name="CharacterMesh", geom_name="CharacterMesh")
    path.write_bytes(scene.export(file_type="glb"))


def _source_rect(path: Path, *, width: int, height: int):
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    cx = 128
    cy = 128
    draw.rectangle(
        (
            cx - width // 2,
            cy - height // 2,
            cx + width // 2,
            cy + height // 2,
        ),
        fill=(180, 180, 180, 255),
    )
    image.save(path)


def test_legacy_projection_conform_rejects_generic_and_unprofiled_assets():
    with pytest.raises(RuntimeError, match="forbidden for generic/new assets"):
        _require_legacy_projection_profile(None)

    with pytest.raises(RuntimeError, match="forbidden for generic/new assets"):
        _require_legacy_projection_profile(
            {
                "name": "generic",
                "legacy_monja_targeting": False,
            }
        )

    legacy = _require_legacy_projection_profile(
        {
            "name": "monja-mugfwln6",
            "legacy_monja_targeting": True,
        }
    )
    assert legacy["name"] == "monja-mugfwln6"
    assert legacy["legacy_monja_targeting"] is True


def test_render_face_budget_is_deterministic_and_never_changes_source_faces():
    faces = np.arange(90000, dtype=np.int64).reshape(-1, 3)
    original = faces.copy()

    subset_a, meta_a = _bounded_render_faces(faces, max_faces=1200)
    subset_b, meta_b = _bounded_render_faces(faces, max_faces=1200)

    assert len(subset_a) <= 1200
    assert np.array_equal(subset_a, subset_b)
    assert np.array_equal(faces, original)
    assert meta_a == meta_b
    assert meta_a["input_faces"] == len(faces)
    assert meta_a["render_faces"] == len(subset_a)
    assert meta_a["subsampled"] is True
    assert np.array_equal(subset_a[0], faces[0])
    assert np.array_equal(subset_a[-1], faces[-1])


def test_topology_smoothing_reduces_isolated_active_spike_without_moving_inactive():
    faces = np.asarray(
        [
            [0, 1, 2],
            [1, 3, 2],
        ],
        dtype=np.int64,
    )
    active = np.asarray([True, True, True, False])
    delta = np.asarray(
        [
            [1.0, 0.0],
            [7.0, 0.0],
            [1.0, 0.0],
            [0.0, 0.0],
        ],
        dtype=np.float64,
    )

    smoothed, meta = _smooth_topology_displacements(
        delta,
        faces,
        active,
        iterations=2,
        blend=0.5,
    )

    assert smoothed[1, 0] < delta[1, 0]
    assert smoothed[1, 0] > 1.0
    assert np.array_equal(smoothed[3], np.asarray([0.0, 0.0]))
    assert meta["active_vertices"] == 3
    assert meta["active_vertices_with_neighbors"] == 3
    assert meta["can_activate_new_vertices"] is False


def test_front_surface_gate_blocks_rear_vertices_at_same_projection():
    depth = np.asarray([0.42, -0.31, 0.37, -0.22], dtype=np.float64)
    px = np.asarray([40, 40, 90, 90], dtype=np.int64)
    py = np.asarray([60, 60, 110, 110], dtype=np.int64)

    visible, telemetry = _front_surface_vertex_mask(
        depth,
        px,
        py,
        size=160,
        depth_tolerance_ratio=0.025,
        neighborhood_px=1,
    )

    assert visible.tolist() == [True, False, True, False]
    assert telemetry["visible_vertices"] == 2
    assert telemetry["occluded_vertices"] == 2
    assert telemetry["depth_tolerance_ratio"] == 0.025


def test_native_conform_keeps_real_geometry_and_never_creates_proxy_nodes(tmp_path: Path):
    native = tmp_path / "native.glb"
    source = tmp_path / "source.png"
    output = tmp_path / "conformed.glb"
    report = tmp_path / "conformed.json"

    _box(native, extents=(1.0, 2.0, 0.45))
    # Wider target silhouette than the input box. The source is intentionally
    # simple so this test checks generic source-driven behavior, not Monja data.
    _source_rect(source, width=118, height=190)

    result = conform_native_silhouette(
        native,
        source,
        output,
        report=report,
        size=192,
        azimuth_step=30,
        iterations=4,
        boundary_band_px=8.0,
        max_target_px=18.0,
        per_vertex_cap_px=4.0,
    )

    assert output.is_file()
    assert report.is_file()
    assert result["projection_proxy_created"] is False
    assert result["asset_specific_coordinates"] is False
    assert result["native_geometry_preserved"] is True
    assert result["visibility_policy"]["mode"] == "camera-front-surface-only"
    assert result["visibility_policy"]["rear_occluded_vertices_are_editable"] is False
    assert result["render_budget"]["render_faces"] <= 12000
    assert result["render_budget"]["input_faces"] >= result["render_budget"]["render_faces"]
    assert result["topology_smoothing"]["mode"] == "active-visible-one-ring-only"
    assert result["topology_smoothing"]["can_activate_new_vertices"] is False
    preservation = result["roundtrip_preservation"]
    assert preservation["preserved"] is True
    assert preservation["regressions"] == []
    assert preservation["before_mesh"]["vertices"] == preservation["after_mesh"]["vertices"]
    assert preservation["before_mesh"]["faces"] == preservation["after_mesh"]["faces"]
    assert preservation["before_mesh"]["uv_mesh_nodes"] <= preservation["after_mesh"]["uv_mesh_nodes"]
    assert result["final"]["score"] >= result["initial"]["score"]
    assert_native_candidate(output, label="test-output")

    scene = trimesh.load(output, force="scene", process=False)
    names = {str(n) for n in scene.graph.nodes_geometry}
    assert "source_visible_front" not in names
    assert "occluded_low_frequency" not in names


def test_native_conform_is_source_specific_not_monja_specific(tmp_path: Path):
    native = tmp_path / "creature.glb"
    narrow = tmp_path / "narrow.png"
    wide = tmp_path / "wide.png"
    narrow_out = tmp_path / "narrow.glb"
    wide_out = tmp_path / "wide.glb"

    _box(native, extents=(1.0, 2.0, 0.45))
    _source_rect(narrow, width=82, height=190)
    _source_rect(wide, width=132, height=190)

    narrow_result = conform_native_silhouette(
        native,
        narrow,
        narrow_out,
        size=160,
        iterations=3,
        boundary_band_px=8.0,
        max_target_px=20.0,
        per_vertex_cap_px=4.0,
    )
    wide_result = conform_native_silhouette(
        native,
        wide,
        wide_out,
        size=160,
        iterations=3,
        boundary_band_px=8.0,
        max_target_px=20.0,
        per_vertex_cap_px=4.0,
    )

    assert narrow_result["source_image"] != wide_result["source_image"]
    assert "monja" not in narrow_result["policy"].lower()
    assert "monja" not in wide_result["policy"].lower()
    assert_native_candidate(narrow_out)
    assert_native_candidate(wide_out)
