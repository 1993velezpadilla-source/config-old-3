from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import trimesh
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from native_geometry_guard import assert_native_candidate
from native_silhouette_conform import conform_native_silhouette


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
