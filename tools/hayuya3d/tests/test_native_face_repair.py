from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import trimesh
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from native_geometry_guard import assert_native_candidate
from native_360_geometry_gate import Native360GeometryRejected
from native_face_repair import (
    generate_source_head_donor,
    prepare_source_face_repair_challenger,
    select_head_donor_backend,
)


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
