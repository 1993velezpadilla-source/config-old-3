from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
HAYUYA_DIR = ROOT / "tools" / "hayuya3d"
sys.path.insert(0, str(HAYUYA_DIR))

from native_geometry_guard import inspect_candidate
from source_material_rescue import rescue_source_material, validate_textured_native_rescue
from texture_gate import inspect as inspect_texture_gate


def _native_character(path: Path) -> None:
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    vertices[:, 0] *= 0.55
    vertices[:, 1] *= 1.25
    vertices[:, 2] *= 0.38
    mesh = trimesh.Trimesh(
        vertices=vertices,
        faces=np.asarray(mesh.faces, dtype=np.int64).copy(),
        process=False,
    )
    path.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh)))


def _source(path: Path) -> None:
    image = Image.new("RGB", (320, 512), (210, 210, 210))
    draw = ImageDraw.Draw(image)
    draw.ellipse((112, 35, 208, 132), fill=(190, 170, 160))
    draw.polygon(
        [(88, 118), (232, 118), (268, 465), (52, 465)],
        fill=(28, 30, 34),
    )
    draw.rectangle((126, 132, 194, 260), fill=(78, 68, 65))
    draw.line((160, 150, 160, 260), fill=(220, 210, 185), width=5)
    image.save(path)


def test_source_material_rescue_keeps_native_geometry_and_embeds_basecolor(
    tmp_path: Path,
):
    source = tmp_path / "front.png"
    native = tmp_path / "native.glb"
    output = tmp_path / "rescued.glb"
    _source(source)
    _native_character(native)

    before = inspect_texture_gate(native, min_edge=512)
    assert before.passed is False
    assert before.base_color_image_count == 0

    result = rescue_source_material(
        source,
        native,
        output,
        texture_edge=1024,
        min_texture_edge=512,
        total_samples=30000,
    )

    assert result.geometry_preserved is True
    assert result.projection_proxy_created is False
    assert result.diagnostic_donor_production_eligible is False
    assert result.final_native_candidate is True
    assert result.final_volumetric is True
    assert result.texture_gate_passed is True

    donor_report = inspect_candidate(Path(result.diagnostic_material_donor))
    assert donor_report["is_projection_proxy"] is True

    final_report = inspect_candidate(output)
    assert final_report["is_projection_proxy"] is False

    after = inspect_texture_gate(
        output,
        min_edge=512,
        min_base_color_edge=512,
    )
    assert after.passed is True
    assert after.base_color_image_count >= 1
    assert after.base_color_min_edge >= 512


def test_textured_native_validation_rejects_geometry_mutation(tmp_path: Path):
    source = tmp_path / "front.png"
    native = tmp_path / "native.glb"
    textured = tmp_path / "textured.glb"
    mutated = tmp_path / "mutated.glb"
    _source(source)
    _native_character(native)

    rescue_source_material(
        source,
        native,
        textured,
        texture_edge=1024,
        min_texture_edge=512,
        total_samples=30000,
    )

    validated = validate_textured_native_rescue(
        native,
        textured,
        min_texture_edge=512,
    )
    assert validated["geometry_preserved"] is True
    assert validated["texture_gate"]["passed"] is True

    scene = trimesh.load(textured, force="scene", process=False)
    geom_name = next(iter(scene.geometry))
    mesh = scene.geometry[geom_name].copy()
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    vertices[0, 0] += 0.02
    mesh.vertices = vertices
    mutated.write_bytes(
        trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh))
    )

    import pytest
    with pytest.raises(RuntimeError, match="changed native vertex positions"):
        validate_textured_native_rescue(
            native,
            mutated,
            min_texture_edge=512,
        )
