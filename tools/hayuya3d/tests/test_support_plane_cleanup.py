#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

HAYUYA3D = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HAYUYA3D))

import support_plane_cleanup as mod


def subdivided_box(extents, transform=None, rounds=4):
    mesh = trimesh.creation.box(extents=extents, transform=transform)
    for _ in range(rounds):
        mesh = mesh.subdivide()
    return mesh


class SupportPlaneCleanupTests(unittest.TestCase):
    def test_removes_large_boundary_floor_and_backdrop(self):
        character = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
        character.apply_scale([0.75, 1.6, 0.45])

        floor = subdivided_box(
            [4.0, 0.035, 4.0],
            transform=trimesh.transformations.translation_matrix(
                [0.0, -2.0, 0.0]
            ),
        )
        backdrop = subdivided_box(
            [4.0, 4.0, 0.035],
            transform=trimesh.transformations.translation_matrix(
                [0.0, 0.0, -2.0]
            ),
        )
        combined = trimesh.util.concatenate([character, floor, backdrop])

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "candidate.glb"
            trimesh.Scene(combined).export(path)
            report = mod.strip_boundary_support_slabs(path)
            cleaned = trimesh.load(path, force="mesh", process=False)

        self.assertTrue(report["applied"])
        self.assertGreaterEqual(len(report["detected_slabs"]), 2)
        self.assertLess(len(cleaned.faces), len(combined.faces))
        self.assertGreater(len(cleaned.faces), 100)
        self.assertLess(cleaned.extents[0], combined.extents[0])
        self.assertLess(cleaned.extents[2], combined.extents[2])

    def test_keeps_normal_volumetric_mesh(self):
        character = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
        character.apply_scale([0.75, 1.6, 0.55])

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "character.glb"
            trimesh.Scene(character).export(path)
            before = path.read_bytes()
            report = mod.strip_boundary_support_slabs(path)
            after = path.read_bytes()

        self.assertFalse(report["applied"])
        self.assertEqual(report["detected_slabs"], [])
        self.assertEqual(before, after)

    def test_current_style_detector_requires_cross_axis_coverage(self):
        character = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
        small_plate = subdivided_box(
            [0.25, 0.02, 0.25],
            transform=trimesh.transformations.translation_matrix(
                [0.0, -1.05, 0.0]
            ),
        )
        combined = trimesh.util.concatenate([character, small_plate])
        remove, slabs = mod.detect_boundary_support_slabs(combined)
        self.assertFalse(remove.any())
        self.assertEqual(slabs, [])


if __name__ == "__main__":
    unittest.main()
