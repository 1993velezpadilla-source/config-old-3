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
from visual_judge import render_silhouette, score_masks
from silhouette_conform import _require_legacy_projection_profile
from native_silhouette_conform import (
    _assert_roundtrip_preserved,
    _bounded_render_faces,
    _collateral_view_preservation,
    _front_surface_vertex_mask,
    _load_editable_scene,
    _smooth_topology_displacements,
    _write_world_vertices,
    conform_native_silhouette,
)


def _box(
    path: Path,
    extents=(1.0, 2.0, 0.45),
    *,
    subdivisions: int = 0,
):
    mesh = trimesh.creation.box(extents=extents)
    for _ in range(max(0, int(subdivisions))):
        mesh = mesh.subdivide()
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name="CharacterMesh", geom_name="CharacterMesh")
    path.write_bytes(scene.export(file_type="glb"))


def _textured_box(path: Path):
    mesh = trimesh.creation.box(extents=(1.0, 2.0, 0.45))
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    x = vertices[:, 0]
    y = vertices[:, 1]
    u = (x - x.min()) / max(float(x.max() - x.min()), 1e-9)
    v = (y - y.min()) / max(float(y.max() - y.min()), 1e-9)
    uv = np.stack([u, v], axis=1)

    texture = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
    draw = ImageDraw.Draw(texture)
    draw.rectangle((0, 0, 3, 7), fill=(255, 0, 0, 255))
    draw.rectangle((4, 0, 7, 7), fill=(0, 255, 0, 255))

    material = trimesh.visual.texture.SimpleMaterial(image=texture)
    mesh.visual = trimesh.visual.texture.TextureVisuals(
        uv=uv,
        material=material,
    )
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name="TexturedMesh", geom_name="TexturedMesh")
    path.write_bytes(scene.export(file_type="glb"))


def _scene_world_vertices(path: Path) -> np.ndarray:
    scene = trimesh.load(path, force="scene", process=False)
    chunks = []
    for node in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph.get(node)
        geometry = scene.geometry[geometry_name]
        if not hasattr(geometry, "vertices") or not len(geometry.vertices):
            continue
        chunks.append(
            trimesh.transform_points(
                np.asarray(geometry.vertices, dtype=np.float64),
                np.asarray(transform, dtype=np.float64),
            )
        )
    if not chunks:
        raise AssertionError(f"no geometry in {path}")
    return np.concatenate(chunks, axis=0)


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


def test_roundtrip_preserves_uv_and_texture_fingerprints_when_geometry_moves(
    tmp_path: Path,
):
    source = tmp_path / "textured.glb"
    output = tmp_path / "textured_moved.glb"
    _textured_box(source)

    scene, records, vertices_world, _faces = _load_editable_scene(source)
    moved = np.asarray(vertices_world, dtype=np.float64).copy()
    moved[0, 0] += 0.01
    _write_world_vertices(scene, records, moved, output)

    preservation = _assert_roundtrip_preserved(source, output)
    assert preservation["preserved"] is True
    before = preservation["before_mesh"]
    after = preservation["after_mesh"]
    assert before["uv_fingerprints"] == after["uv_fingerprints"]
    assert (
        before["base_color_texture_fingerprints"]
        == after["base_color_texture_fingerprints"]
    )
    assert before["base_color_texture_fingerprints"]


def test_generic_pipeline_does_not_import_legacy_projection_conform():
    pipeline = (HERE / "hayuya.py").read_text(encoding="utf-8")
    assert "from native_silhouette_conform import conform_native_silhouette" in pipeline
    assert "from silhouette_conform import" not in pipeline
    assert "import silhouette_conform" not in pipeline


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


def test_render_face_budget_clusters_surface_and_preserves_components():
    primary = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    secondary = trimesh.creation.icosphere(subdivisions=3, radius=0.22)
    secondary.apply_translation((1.75, 0.35, 0.10))

    primary_vertex_count = len(primary.vertices)
    mesh = trimesh.util.concatenate([primary, secondary])
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    original_vertices = vertices.copy()
    original_faces = faces.copy()

    subset_a, meta_a = _bounded_render_faces(
        vertices,
        faces,
        max_faces=1200,
    )
    subset_b, meta_b = _bounded_render_faces(
        vertices,
        faces,
        max_faces=1200,
    )

    assert 0 < len(subset_a) <= 1200
    assert np.array_equal(subset_a, subset_b)
    assert np.array_equal(vertices, original_vertices)
    assert np.array_equal(faces, original_faces)
    assert meta_a == meta_b
    assert meta_a["input_faces"] == len(faces)
    assert meta_a["render_faces"] == len(subset_a)
    assert meta_a["subsampled"] is True
    assert meta_a["policy"] == "deterministic-vertex-clustered-surface-proxy"
    assert meta_a["proxy_grid"] is not None
    assert meta_a["proxy_vertices_used"] > 0

    # The render proxy must preserve evidence from both disconnected objects,
    # not merely sample whichever faces happen to dominate array order.
    assert np.any(np.all(subset_a < primary_vertex_count, axis=1))
    assert np.any(np.all(subset_a >= primary_vertex_count, axis=1))


def test_clustered_render_proxy_tracks_full_mesh_silhouette():
    primary = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    secondary = trimesh.creation.icosphere(subdivisions=3, radius=0.22)
    secondary.apply_translation((1.75, 0.35, 0.10))
    mesh = trimesh.util.concatenate([primary, secondary])

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    center = (vertices.min(axis=0) + vertices.max(axis=0)) * 0.5
    scale = float(np.max(vertices.max(axis=0) - vertices.min(axis=0)))
    vertices_norm = (vertices - center) / max(scale, 1e-9)

    proxy_faces, _meta = _bounded_render_faces(
        vertices_norm,
        faces,
        max_faces=1200,
    )
    full_mask = render_silhouette(
        vertices_norm,
        faces,
        35.0,
        8.0,
        "y",
        size=192,
    )
    proxy_mask = render_silhouette(
        vertices_norm,
        proxy_faces,
        35.0,
        8.0,
        "y",
        size=192,
    )
    _score, iou, boundary_f1 = score_masks(full_mask, proxy_mask)

    assert iou >= 0.90
    assert boundary_f1 >= 0.70


def test_collateral_view_gate_preserves_unseen_side_and_back_shape():
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    reference = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    camera = (
        0.0,
        0.0,
        0.0,
        "y",
        0.0,
        0.0,
        "orthographic",
        None,
    )

    allowed_same, same = _collateral_view_preservation(
        reference,
        reference.copy(),
        faces,
        camera,
        size=160,
        min_iou=0.90,
        min_boundary_f1=0.68,
    )
    assert allowed_same is True
    assert same["allowed"] is True
    assert same["min_iou_observed"] >= 0.99
    assert same["min_boundary_f1_observed"] >= 0.99

    collapsed_side = reference.copy()
    collapsed_side[:, 2] *= 0.20
    allowed_bad, bad = _collateral_view_preservation(
        reference,
        collapsed_side,
        faces,
        camera,
        size=160,
        min_iou=0.90,
        min_boundary_f1=0.68,
    )
    assert allowed_bad is False
    assert bad["allowed"] is False
    assert (
        bad["min_iou_observed"] < 0.90
        or bad["min_boundary_f1_observed"] < 0.68
    )


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


def test_native_conform_noop_preserves_exact_glb_bytes(tmp_path: Path):
    native = tmp_path / "native.glb"
    source = tmp_path / "source.png"
    output = tmp_path / "noop.glb"

    _box(native, extents=(1.0, 2.0, 0.45), subdivisions=1)
    _source_rect(source, width=118, height=190)

    before = native.read_bytes()
    result = conform_native_silhouette(
        native,
        source,
        output,
        size=160,
        iterations=1,
        boundary_band_px=8.0,
        max_target_px=20.0,
        per_vertex_cap_px=0.0,
    )

    assert result["geometry_changed"] is False
    assert result["accepted_passes"] == 0
    assert result["no_op_preserves_exact_input_bytes"] is True
    assert output.read_bytes() == before


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
    assert result["collateral_360_policy"]["mode"] == "preserve-unseen-native-silhouettes-v1"
    assert result["collateral_360_policy"]["reference"] == "original-native-hero-master"
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

    # Native generators emit dense surfaces. Use a locally editable contour
    # instead of an 8-vertex primitive whose corners cannot express shape change.
    _box(native, extents=(1.0, 2.0, 0.45), subdivisions=3)
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

    narrow_vertices = _scene_world_vertices(narrow_out)
    wide_vertices = _scene_world_vertices(wide_out)
    assert narrow_vertices.shape == wide_vertices.shape
    assert not np.allclose(narrow_vertices, wide_vertices, atol=1e-7)
    assert (
        abs(
            narrow_result["max_displacement_body_span_ratio"]
            - wide_result["max_displacement_body_span_ratio"]
        )
        > 1e-7
        or not np.allclose(narrow_vertices, wide_vertices, atol=1e-7)
    )
