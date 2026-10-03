#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.hayuya3d.candidate_tournament import (
    CandidateSpec,
    run_tournament,
)


def mesh_report(*, faces:int, passed:bool=True):
    return SimpleNamespace(
        valid=True,
        passed=passed,
        vertices=max(3,faces//2),
        faces=faces,
        components=1,
        largest_component_fraction=1.0,
        degenerate_ratio=0.0,
        reasons=[] if passed else ["bad_mesh"],
        warnings=[],
    )


def texture_report(*, edge:int=4096, passed:bool=True):
    return SimpleNamespace(
        passed=passed,
        base_color_min_edge=edge,
        max_edge=edge,
        warnings=[] if passed else ["low_texture_resolution"],
    )


class CandidateTournamentTests(unittest.TestCase):
    def test_source_fidelity_beats_polygon_count(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"front.png"
            source.write_bytes(b"x")
            faithful=root/"faithful.glb"
            dense=root/"dense.glb"
            faithful.write_bytes(b"glTF")
            dense.write_bytes(b"glTF")

            specs=[
                CandidateSpec(faithful,"faithful","a"),
                CandidateSpec(dense,"dense","b"),
            ]

            def fake_mesh(path, require_normals=False):
                return mesh_report(
                    faces=400_000 if Path(path)==faithful else 2_000_000
                )

            def fake_visual(path, images, size=128, azimuth_step=45):
                score=94.0 if Path(path)==faithful else 70.0
                return SimpleNamespace(
                    score=score,
                    views=[SimpleNamespace(source=str(source))],
                )

            with patch("tools.hayuya3d.candidate_tournament.inspect_mesh",side_effect=fake_mesh), \
                 patch("tools.hayuya3d.candidate_tournament.inspect_texture",return_value=texture_report()), \
                 patch("tools.hayuya3d.candidate_tournament.score_visual",side_effect=fake_visual):
                report=run_tournament(
                    specs,
                    [source],
                    texture_quality="ultra",
                )

            self.assertEqual(report["winner"]["generator"],"faithful")
            self.assertGreater(
                report["candidates"][0]["visual_score"],
                report["candidates"][1]["visual_score"],
            )

    def test_diagnostic_candidate_cannot_beat_production_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"front.png"
            source.write_bytes(b"x")
            native=root/"native.glb"
            diagnostic=root/"preview.glb"
            native.write_bytes(b"glTF")
            diagnostic.write_bytes(b"glTF")

            specs=[
                CandidateSpec(native,"native","native"),
                CandidateSpec(
                    diagnostic,
                    "preview",
                    "preview",
                    native_geometry=False,
                    diagnostic_only=True,
                ),
            ]

            def fake_visual(path, images, size=128, azimuth_step=45):
                score=80.0 if Path(path)==native else 99.0
                return SimpleNamespace(
                    score=score,
                    views=[SimpleNamespace(source=str(source))],
                )

            with patch("tools.hayuya3d.candidate_tournament.inspect_mesh",return_value=mesh_report(faces=1_200_000)), \
                 patch("tools.hayuya3d.candidate_tournament.inspect_texture",return_value=texture_report()), \
                 patch("tools.hayuya3d.candidate_tournament.score_visual",side_effect=fake_visual):
                report=run_tournament(
                    specs,
                    [source],
                    texture_quality="ultra",
                )

            self.assertEqual(report["winner"]["generator"],"native")
            preview=next(x for x in report["candidates"] if x["generator"]=="preview")
            self.assertFalse(preview["eligible"])
            self.assertIn("diagnostic_geometry_only",preview["reasons"])


if __name__=="__main__":
    unittest.main()
