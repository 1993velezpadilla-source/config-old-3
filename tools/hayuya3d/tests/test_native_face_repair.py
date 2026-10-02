from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
import trimesh
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from native_geometry_guard import assert_native_candidate
from native_360_geometry_gate import Native360GeometryRejected
from native_face_repair import (
    generate_source_head_donor,
    prepare_source_face_repair_challenger,
    prepare_source_face_repair_tournament,
    select_head_donor_backend,
)
from regional_fusion import HeadWrapResult
from source_autofix import _foreground_head_zoom


def _write_native(path: Path) -> None:
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=0.5)
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name="HeadMesh", geom_name="HeadMesh")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(scene.export(file_type="glb"))

def _write_planar_native(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 0.0005))
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name="HeadMesh", geom_name="HeadMesh")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(scene.export(file_type="glb"))



def test_backend_selection_is_capability_based_not_asset_specific(tmp_path: Path):
    root = tmp_path / "models"
    (root / "triposg").mkdir(parents=True)
    (root / "triposr").mkdir(parents=True)

    assert (
        select_head_donor_backend(["triposr", "triposg"], root)
        == "triposg"
    )
    assert select_head_donor_backend(["triposr"], root) == "triposr"
    assert select_head_donor_backend(["trellis2"], root) is None


def test_foreground_head_fallback_rejects_horizontal_subject(tmp_path: Path):
    source = tmp_path / "horizontal_subject.png"
    image = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((30, 94, 94, 158), fill=(190, 140, 110, 255))
    draw.rectangle((92, 82, 430, 174), fill=(120, 120, 120, 255))
    draw.rectangle((150, 55, 360, 82), fill=(120, 120, 120, 255))
    draw.rectangle((150, 174, 360, 201), fill=(120, 120, 120, 255))
    image.save(source)

    result = _foreground_head_zoom(
        source,
        tmp_path / "should_not_exist.png",
    )
    assert result is None
    assert not (tmp_path / "should_not_exist.png").exists()


def test_full_body_source_can_derive_head_evidence_for_native_donor(tmp_path: Path):
    source = tmp_path / "anonymous_full_body.png"
    image = Image.new("RGBA", (256, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((94, 28, 162, 96), fill=(190, 140, 110, 255))
    draw.rectangle((76, 94, 180, 390), fill=(120, 120, 120, 255))
    draw.rectangle((58, 120, 76, 300), fill=(120, 120, 120, 255))
    draw.rectangle((180, 120, 198, 300), fill=(120, 120, 120, 255))
    image.save(source)

    seen = {}

    def fake_generator(**kwargs):
        seen.update(kwargs)
        output = Path(kwargs["out_dir"]) / "native_head.glb"
        _write_native(output)
        return SimpleNamespace(model_path=output)

    donor = generate_source_head_donor(
        source,
        tmp_path / "fallback_run",
        backend="triposg",
        seed=88,
        hero_faces=250000,
        trellis2_resolution=1024,
        texture_size=4096,
        model_root=tmp_path / "models",
        generator_override=fake_generator,
        derive_head_from_full_source=True,
    )

    assert donor.is_file()
    staged = Image.open(seen["image"]).convert("RGBA")
    assert staged.size == (1024, 1024)
    alpha = staged.getchannel("A")
    assert alpha.getbbox() is not None
    assert alpha.getextrema()[0] == 0
    assert Path(seen["image"]).name == "source_head_rgba.png"


def test_face_repair_tournament_keeps_every_ready_backend_for_judge(
    tmp_path: Path,
    monkeypatch,
):
    base = tmp_path / "base.glb"
    detail = tmp_path / "head.png"
    _write_native(base)
    Image.new("RGBA", (96, 96), (180, 120, 90, 255)).save(detail)

    model_root = tmp_path / "models"
    (model_root / "trellis2").mkdir(parents=True)
    (model_root / "triposg").mkdir(parents=True)

    generated = []

    def fake_generator(**kwargs):
        backend = kwargs["backend"]
        generated.append(backend)
        output = Path(kwargs["out_dir"]) / f"{backend}.glb"
        _write_native(output)
        return SimpleNamespace(model_path=output)

    def fake_fusion(base_mesh, donor_mesh, out_dir, **kwargs):
        return HeadWrapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            raw_output_glb=str(donor_mesh),
            output_glb=str(donor_mesh),
            attempted=True,
            geometry_ready=True,
            rebake_ready=True,
            ready_for_judge=True,
            up_axis=1,
            alignment_scale=1.0,
            head_vertices=100,
            changed_vertices=50,
            clamped_vertices=0,
            mean_displacement_normalized=0.001,
            max_displacement_normalized=0.002,
            seam_max_displacement_normalized=0.001,
            bbox_drift_fraction=0.001,
            rebake_required=[],
            rebake_resolved=[],
            donor_scope="head",
        )

    import regional_fusion
    monkeypatch.setattr(
        regional_fusion,
        "prepare_head_wrap_challenger",
        fake_fusion,
    )

    tournament = prepare_source_face_repair_tournament(
        base,
        detail,
        tmp_path / "tournament",
        selected_backends=["triposg", "trellis2"],
        seed=21,
        hero_faces=250000,
        trellis2_resolution=1024,
        texture_size=4096,
        model_root=model_root,
        generator_override=fake_generator,
    )

    assert tournament.attempted is True
    assert tournament.ready is True
    assert tournament.backend_order == ["trellis2", "triposg"]
    assert tournament.ready_backends == ["trellis2", "triposg"]
    assert len(tournament.results) == 2
    assert all(result.ready for result in tournament.results)
    assert generated == ["trellis2", "triposg"]


def test_face_repair_falls_back_to_next_backend_after_planar_donor(
    tmp_path: Path,
    monkeypatch,
):
    base = tmp_path / "base.glb"
    detail = tmp_path / "head.png"
    _write_native(base)
    Image.new("RGBA", (96, 96), (180, 120, 90, 255)).save(detail)

    model_root = tmp_path / "models"
    (model_root / "trellis2").mkdir(parents=True)
    (model_root / "triposg").mkdir(parents=True)

    generated = []

    def fake_generator(**kwargs):
        backend = kwargs["backend"]
        generated.append(backend)
        output = Path(kwargs["out_dir"]) / f"{backend}.glb"
        if backend == "trellis2":
            _write_planar_native(output)
        else:
            _write_native(output)
        return SimpleNamespace(model_path=output)

    def fake_fusion(base_mesh, donor_mesh, out_dir, **kwargs):
        return HeadWrapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            raw_output_glb=str(donor_mesh),
            output_glb=str(donor_mesh),
            attempted=True,
            geometry_ready=True,
            rebake_ready=True,
            ready_for_judge=True,
            up_axis=1,
            alignment_scale=1.0,
            head_vertices=100,
            changed_vertices=50,
            clamped_vertices=0,
            mean_displacement_normalized=0.001,
            max_displacement_normalized=0.002,
            seam_max_displacement_normalized=0.001,
            bbox_drift_fraction=0.001,
            rebake_required=[],
            rebake_resolved=[],
            donor_scope="head",
        )

    import regional_fusion
    monkeypatch.setattr(
        regional_fusion,
        "prepare_head_wrap_challenger",
        fake_fusion,
    )

    result = prepare_source_face_repair_challenger(
        base,
        detail,
        tmp_path / "repair",
        selected_backends=["triposg", "trellis2"],
        seed=11,
        hero_faces=250000,
        trellis2_resolution=1024,
        texture_size=4096,
        model_root=model_root,
        generator_override=fake_generator,
    )

    assert result.ready is True
    assert result.backend == "triposg"
    assert generated == ["trellis2", "triposg"]
    assert result.backend_attempts is not None
    assert len(result.backend_attempts) == 2
    assert result.backend_attempts[0]["backend"] == "trellis2"
    assert result.backend_attempts[0]["ready"] is False
    assert "Native360GeometryRejected" in result.backend_attempts[0]["error"]
    assert result.backend_attempts[1]["backend"] == "triposg"
    assert result.backend_attempts[1]["ready"] is True


def test_face_repair_rejects_planar_base_before_any_fusion(tmp_path: Path):
    base = tmp_path / "flat_base.glb"
    detail = tmp_path / "head.png"
    _write_planar_native(base)
    Image.new("RGBA", (96, 96), (180, 120, 90, 255)).save(detail)

    result = prepare_source_face_repair_challenger(
        base,
        detail,
        tmp_path / "repair",
        selected_backends=[],
        seed=5,
        hero_faces=250000,
        trellis2_resolution=1024,
        texture_size=4096,
        model_root=tmp_path / "models",
    )

    assert result.ready is False
    assert result.attempted is True
    assert result.candidate_mesh is None
    assert "Native360GeometryRejected" in str(result.error)


def test_face_repair_rejects_planar_fusion_output_even_if_fusion_marks_ready(
    tmp_path: Path,
    monkeypatch,
):
    base = tmp_path / "base.glb"
    detail = tmp_path / "head.png"
    _write_native(base)
    Image.new("RGBA", (96, 96), (180, 120, 90, 255)).save(detail)

    model_root = tmp_path / "models"
    (model_root / "triposg").mkdir(parents=True)

    def fake_generator(**kwargs):
        output = Path(kwargs["out_dir"]) / "native_head.glb"
        _write_native(output)
        return SimpleNamespace(model_path=output)

    planar_output = tmp_path / "fusion_planar.glb"
    _write_planar_native(planar_output)

    def fake_fusion(*args, **kwargs):
        return HeadWrapResult(
            base_mesh=str(base),
            donor_mesh="native_head.glb",
            raw_output_glb=str(planar_output),
            output_glb=str(planar_output),
            attempted=True,
            geometry_ready=True,
            rebake_ready=True,
            ready_for_judge=True,
            up_axis=1,
            alignment_scale=1.0,
            head_vertices=100,
            changed_vertices=50,
            clamped_vertices=0,
            mean_displacement_normalized=0.001,
            max_displacement_normalized=0.002,
            seam_max_displacement_normalized=0.001,
            bbox_drift_fraction=0.001,
            rebake_required=[],
            rebake_resolved=[],
            donor_scope="head",
        )

    import regional_fusion

    monkeypatch.setattr(
        regional_fusion,
        "prepare_head_wrap_challenger",
        fake_fusion,
    )

    result = prepare_source_face_repair_challenger(
        base,
        detail,
        tmp_path / "repair",
        selected_backends=["triposg"],
        seed=6,
        hero_faces=250000,
        trellis2_resolution=1024,
        texture_size=4096,
        model_root=model_root,
        generator_override=fake_generator,
    )

    assert result.ready is False
    assert "Native360GeometryRejected" in str(result.error)
    assert result.candidate_mesh is None


def test_source_head_donor_rejects_planar_native_generator_output(tmp_path: Path):
    detail = tmp_path / "head.png"
    Image.new("RGBA", (96, 96), (180, 120, 90, 255)).save(detail)

    def fake_planar_generator(**kwargs):
        output = Path(kwargs["out_dir"]) / "planar_head.glb"
        _write_planar_native(output)
        return SimpleNamespace(model_path=output)

    try:
        generate_source_head_donor(
            detail,
            tmp_path / "planar_run",
            backend="triposg",
            seed=91,
            hero_faces=250000,
            trellis2_resolution=1024,
            texture_size=4096,
            model_root=tmp_path / "models",
            generator_override=fake_planar_generator,
        )
    except Native360GeometryRejected as exc:
        assert "source_head_donor:triposg" in str(exc)
    else:
        raise AssertionError("planar native head donor must be rejected before fusion")


def test_source_head_donor_is_native_and_uses_current_detail(tmp_path: Path):
    detail = tmp_path / "different_person_head.png"
    Image.new("RGBA", (96, 96), (180, 120, 90, 255)).save(detail)

    seen = {}

    def fake_generator(**kwargs):
        seen.update(kwargs)
        output = Path(kwargs["out_dir"]) / "native_head.glb"
        _write_native(output)
        return SimpleNamespace(model_path=output)

    donor = generate_source_head_donor(
        detail,
        tmp_path / "run",
        backend="triposg",
        seed=77,
        hero_faces=250000,
        trellis2_resolution=1024,
        texture_size=4096,
        model_root=tmp_path / "models",
        generator_override=fake_generator,
    )

    assert donor.is_file()
    assert seen["backend"] == "triposg"
    assert Path(seen["image"]).name == "source_head_rgba.png"
    assert seen["seed"] == 77
    report = assert_native_candidate(donor, label="unit-test")
    assert report["is_projection_proxy"] is False
