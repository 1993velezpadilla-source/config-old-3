#!/usr/bin/env python3
import struct
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wbl_probe


def make_sector0():
    parts = [
        wbl_probe.SECTOR.pack(1, 0, 2, 1, 1, 1, 2),
        wbl_probe.LEVEL.pack(4096, 8192, 0, 2, 3),
        wbl_probe.INSTANCE.pack(7, 1, 0, 100, 0x20, 0),
        wbl_probe.INSTANCE.pack(8, 2, 1, 101, 0x40, 0),
        wbl_probe.LIGHT.pack(1, 2, 3, 4, 5),
        wbl_probe.UNK20.pack(6, 7, 8, 9, 10),
        struct.pack("<2h", 10, 11),
    ]
    return b"".join(parts)


def make_wbl():
    sector0 = make_sector0()
    empty = wbl_probe.SECTOR.pack(0, 0, 0, 0, 0, 0, 0)
    payloads = [sector0, empty, empty, empty]

    offsets = []
    cursor = 0
    for payload in payloads:
        offsets.append(cursor)
        cursor += len(payload)

    header = wbl_probe.WORLD_SECTOR.pack(
        4096, 0, 0,
        0, 4096, 0,
        0, 0, 4096,
        0,
        4096, 8192, 12288,
        *offsets,
    )
    return header + b"".join(payloads)


class WblProbeTests(unittest.TestCase):
    def test_worldblock_census(self):
        report = wbl_probe.parse_wbl_bytes(make_wbl())

        self.assertEqual(report["transform"]["position"], [1.0, 2.0, 3.0])
        self.assertEqual(report["totals"]["levels"], 1)
        self.assertEqual(report["totals"]["instances"], 2)
        self.assertEqual(report["totals"]["lights"], 1)
        self.assertEqual(report["totals"]["unknown20"], 1)
        self.assertEqual(report["totals"]["texture_refs"], 2)
        self.assertEqual(report["unique_model_resource_ids"], [100, 101])
        self.assertEqual(report["unique_texture_ids"], [10, 11])
        self.assertEqual(report["sectors"][0]["levels"][0]["position"], [1.0, 2.0, 0.0])

    def test_truncated_sector_rejected(self):
        blob = make_wbl()[:-1]
        with self.assertRaises(ValueError):
            wbl_probe.parse_wbl_bytes(blob)


if __name__ == "__main__":
    unittest.main()
