#!/usr/bin/env python3
import struct
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mdl_probe
import ped_probe
from test_mdl_probe import make_model


BLOCK = 4096


def make_pak_with_peds() -> bytes:
    resource_count = 5
    # All resources stay in range 0 for the synthetic fixture.
    header = struct.pack(
        "<6I",
        0x43545731,
        resource_count,
        resource_count,
        resource_count,
        resource_count,
        1,
    )
    offsets = struct.pack("<5H", 1, 2, 3, 4, 5)

    blob = bytearray(6 * BLOCK)
    blob[:len(header)] = header
    blob[len(header):len(header) + len(offsets)] = offsets

    # Resource 0: maintable. Slot 8 points to pedinfos resource 1.
    ids = [-1] * 23
    ids[8] = 1
    struct.pack_into("<23h", blob, BLOCK, *ids)

    # Resource 1: padded pedinfos table.
    ped_start = 2 * BLOCK
    struct.pack_into("<I", blob, ped_start, 3)
    records = [
        (100, 2, 1, 2, 3, 4),
        (101, 3, 5, 6, 7, 8),
        (102, 4, 9, 10, 11, 12),
    ]
    for i, rec in enumerate(records):
        struct.pack_into("<6h", blob, ped_start + 4 + i * 12, *rec)

    # Resources 2..4: valid CTW MG models.
    model = make_model()
    for rid in (2, 3, 4):
        start = (rid + 1) * BLOCK
        blob[start:start + len(model)] = model

    return bytes(blob)


class PedProbeTests(unittest.TestCase):
    def test_infers_fixed_stride_model_field(self):
        records = b"".join([
            struct.pack("<6h", 10, 2, 0, 0, 0, 0),
            struct.pack("<6h", 11, 3, 0, 0, 0, 0),
            struct.pack("<6h", 12, 4, 0, 0, 0, 0),
        ])
        blob = struct.pack("<I", 3) + records + b"\0" * 512

        report = ped_probe.infer_layout(blob, {2, 3, 4})
        best = report["best"]

        self.assertIsNotNone(best)
        self.assertEqual(report["confidence"], "high")
        self.assertEqual(best["start"], 4)
        self.assertEqual(best["record_size"], 12)
        self.assertEqual(best["field_offset"], 2)
        self.assertEqual(best["record_count"], 3)
        self.assertEqual(best["match_count"], 3)
        self.assertEqual(best["unique_model_ids"], [2, 3, 4])

    def test_full_pak_ped_model_census(self):
        with tempfile.TemporaryDirectory() as td:
            pak = Path(td) / "game.pak"
            pak.write_bytes(make_pak_with_peds())
            report = ped_probe.inspect_ped_models(pak)

        self.assertEqual(report["pedinfos_resource_id"], 1)
        self.assertEqual(report["model_resource_count"], 3)
        self.assertEqual(report["layout_inference"]["confidence"], "high")
        best = report["layout_inference"]["best"]
        self.assertEqual(best["record_size"], 12)
        self.assertEqual(best["field_offset"], 2)
        self.assertEqual(best["unique_model_ids"], [2, 3, 4])
        self.assertEqual(report["linked_model_count"], 3)

        models = report["linked_models_by_skeleton_complexity"]
        self.assertEqual([m["resource_id"] for m in models], [2, 3, 4])
        self.assertTrue(all(m["parsed"] for m in models))
        self.assertTrue(all(m["num_matrices"] == 2 for m in models))
        self.assertTrue(all(m["num_vertices"] == 6 for m in models))

    def test_no_false_layout_without_model_hits(self):
        blob = struct.pack("<I", 3) + b"\0" * 128
        report = ped_probe.infer_layout(blob, {20, 21, 22})
        self.assertIsNone(report["best"])
        self.assertEqual(report["confidence"], "none")


if __name__ == "__main__":
    unittest.main()
