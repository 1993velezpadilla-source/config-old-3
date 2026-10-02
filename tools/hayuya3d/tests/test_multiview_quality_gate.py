from __future__ import annotations

from pathlib import Path
import sys

import trimesh

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))

from multiview_quality_gate import render_multiview


def test_multiview_gate_renders_untextured_native_geometry(tmp_path:Path):
    source=tmp_path/"untextured.glb"
    out=tmp_path/"views"

    mesh=trimesh.creation.icosphere(subdivisions=2,radius=1.0)
    scene=trimesh.Scene()
    scene.add_geometry(
        mesh,
        node_name="NativeMesh",
        geom_name="NativeMesh",
    )
    source.write_bytes(scene.export(file_type="glb"))

    angles=[0,30,45,90,180,-90,-45,-30]
    payload=render_multiview(
        source,
        out,
        size=128,
        supersample=1,
        angles=angles,
    )

    assert payload["geometry_evidence_available"] is True
    assert payload["appearance_evidence_available"] is False
    assert len(payload["views"])==8
    assert Path(payload["contact_sheet"]).is_file()

    for view in payload["views"]:
        assert view["visible_pixels_raw"]>0
        assert view["textured_geometry_count"]==0
        assert view["appearance_evidence"] is False
        assert view["render_evidence"]=="native-flat-triangle-zbuffer"
        assert Path(view["image"]).is_file()
