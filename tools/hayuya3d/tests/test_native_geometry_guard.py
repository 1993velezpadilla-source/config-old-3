from __future__ import annotations

import json
import struct
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from native_geometry_guard import (
    ProjectionProxyRejected,
    assert_native_candidate,
    inspect_candidate,
)


def _write_glb(path: Path, payload: dict) -> None:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    raw += b" " * ((4 - len(raw) % 4) % 4)
    chunk = struct.pack("<II", len(raw), 0x4E4F534A) + raw
    total = 12 + len(chunk)
    path.write_bytes(b"glTF" + struct.pack("<II", 2, total) + chunk)


def test_rejects_front_projection_nodes(tmp_path: Path):
    model = tmp_path / "candidate.glb"
    _write_glb(
        model,
        {
            "asset": {"version": "2.0"},
            "nodes": [
                {"name": "source_visible_front"},
                {"name": "occluded_low_frequency"},
            ],
        },
    )
    report = inspect_candidate(model)
    assert report["is_projection_proxy"] is True
    try:
        assert_native_candidate(model, label="bad")
    except ProjectionProxyRejected as exc:
        assert "front-projection" in str(exc)
    else:
        raise AssertionError("projection proxy must be rejected")


def test_accepts_unmarked_native_glb(tmp_path: Path):
    model = tmp_path / "native.glb"
    _write_glb(
        model,
        {
            "asset": {"version": "2.0", "generator": "Hunyuan3D"},
            "nodes": [{"name": "CharacterMesh"}],
        },
    )
    report = assert_native_candidate(model, label="hunyuan")
    assert report["is_projection_proxy"] is False
    assert report["projection_proxy_nodes"] == []


def test_filename_marker_is_rejected_even_without_named_nodes(tmp_path: Path):
    model = tmp_path / "source_front_projection.glb"
    _write_glb(
        model,
        {"asset": {"version": "2.0"}, "nodes": [{"name": "Mesh"}]},
    )
    assert inspect_candidate(model)["is_projection_proxy"] is True
