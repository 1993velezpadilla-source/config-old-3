#!/usr/bin/env python3
import struct
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdl_probe


def make_model(*, second_material_vertices=3):
    header = mdl_probe.HEADER.pack(
        b"MG",
        1,   # variances
        2,   # matrices/nodes
        2,   # materials
        6,   # vertices
        0,
        0,
        *([0] * 8),
    )

    verts = [
        (0, 0, 0,     0, 0, 32767, 0, 0),
        (64, 0, 0,    0, 0, 32767, 2048, 0),
        (0, 64, 0,    0, 0, 32767, 0, 2048),
        (0, 0, 64,    0, 0, 32767, 0, 0),
        (64, 0, 64,   0, 0, 32767, 2048, 0),
        (0, 64, 64,   0, 0, 32767, 0, 2048),
    ]
    vertices = b"".join(mdl_probe.VERTEX.pack(*v) for v in verts)

    matrix = mdl_probe.MATRIX.pack(
        4096, 0, 0,
        0, 4096, 0,
        0, 0, 4096,
        1, 0,
        0, 0, 4096,
    )

    materials = b"".join([
        mdl_probe.MATERIAL.pack(10, 3, 1, 0, 0),
        mdl_probe.MATERIAL.pack(11, second_material_vertices, 2, 1, 4),
    ])
    return header + vertices + matrix + materials


class MdlProbeTests(unittest.TestCase):
    def test_parses_geometry_nodes_materials_and_bounds(self):
        report = mdl_probe.parse_mdl_bytes(make_model())

        self.assertEqual(report["num_vertices"], 6)
        self.assertEqual(report["num_matrices"], 2)
        self.assertEqual(report["num_materials"], 2)
        self.assertEqual(report["unassigned_vertices"], 0)
        self.assertEqual(report["empty_nodes"], [])
        self.assertEqual(report["bounds"]["min"], [0.0, 0.0, 0.0])
        self.assertEqual(report["bounds"]["max"], [1.0, 1.0, 1.0])
        self.assertEqual(report["nodes"][0]["vertex_count"], 3)
        self.assertEqual(report["nodes"][0]["textures"], [10])
        self.assertEqual(report["nodes"][1]["vertex_count"], 3)
        self.assertEqual(report["nodes"][1]["textures"], [11])
        self.assertEqual(report["matrices"][1]["parent"], 0)
        self.assertEqual(report["matrices"][1]["position"], [0.0, 0.0, 1.0])

    def test_rejects_material_vertex_overrun(self):
        with self.assertRaises(ValueError):
            mdl_probe.parse_mdl_bytes(make_model(second_material_vertices=4))

    def test_rejects_bad_signature(self):
        blob = bytearray(make_model())
        blob[0:2] = b"NO"
        with self.assertRaises(ValueError):
            mdl_probe.parse_mdl_bytes(bytes(blob))


if __name__ == "__main__":
    unittest.main()
