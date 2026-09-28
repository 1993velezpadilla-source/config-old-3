#!/usr/bin/env python3
import struct
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pak_inventory
import world_census
from test_wbl_probe import make_wbl


def make_pak_with_worldblock() -> bytes:
    resource_count = 3
    header = struct.pack("<6I", 0x43545731, 3, 3, 3, resource_count, 1)
    table = struct.pack("<3H", 1, 2, 3)
    blob = bytearray(4 * 4096)
    blob[:len(header)] = header
    blob[len(header):len(header) + len(table)] = table

    # Resource 0: maintable -> resource 1 is worldstreamblocks.res.
    ids = [-1] * 23
    ids[0] = 1
    struct.pack_into("<23h", blob, 1 * 4096, *ids)

    # Resource 1: first worldblock id = resource 2, all remaining slots empty.
    world_table_start = 2 * 4096 + 8
    world_table_slots = (4096 - 8) // 2
    for i in range(world_table_slots):
        struct.pack_into("<h", blob, world_table_start + i * 2, -1)
    struct.pack_into("<h", blob, world_table_start, 2)

    wbl = make_wbl()
    blob[3 * 4096:3 * 4096 + len(wbl)] = wbl
    return bytes(blob)


class WorldCensusTests(unittest.TestCase):
    def test_census_one_worldblock(self):
        with tempfile.TemporaryDirectory() as td:
            pak = Path(td) / "game.pak"
            pak.write_bytes(make_pak_with_worldblock())
            report = world_census.census_pak(pak)

        self.assertEqual(report["worldblocks_named"], 1)
        self.assertEqual(report["worldblocks_parsed"], 1)
        self.assertEqual(report["parse_errors"], [])
        self.assertEqual(report["totals"]["instances"], 2)
        self.assertEqual(report["totals"]["levels"], 1)
        self.assertEqual(report["densest_worldblocks"][0]["name"], "worldblock0.wbl")
        self.assertEqual(report["densest_worldblocks"][0]["sector_instance_counts"], [2, 0, 0, 0])
        self.assertFalse(report["streaming_pressure_model"]["available"])


    def test_streaming_pressure_model(self):
        blocks = [
            {
                "name": "a",
                "resource_id": 1,
                "origin": [0.0, 0.0, 0.0],
                "instances": 10,
            },
            {
                "name": "b",
                "resource_id": 2,
                "origin": [10.0, 0.0, 0.0],
                "instances": 20,
            },
            {
                "name": "c",
                "resource_id": 3,
                "origin": [20.0, 0.0, 0.0],
                "instances": 30,
            },
        ]
        model = world_census.streaming_pressure_model(
            blocks,
            multipliers=(1.0, 2.0),
        )

        self.assertTrue(model["available"])
        self.assertEqual(
            model["baseline_nearest_neighbor_world_units"],
            10.0,
        )

        one_x, two_x = model["scenarios"]
        self.assertEqual(one_x["multiplier"], 1.0)
        self.assertEqual(one_x["loaded_blocks"]["max"], 3)
        self.assertEqual(one_x["loaded_instances"]["max"], 60)
        self.assertEqual(one_x["loaded_blocks"]["min"], 2)

        self.assertEqual(two_x["multiplier"], 2.0)
        self.assertEqual(two_x["loaded_blocks"]["min"], 3)
        self.assertEqual(two_x["loaded_blocks"]["max"], 3)
        self.assertEqual(two_x["loaded_instances"]["max"], 60)


if __name__ == "__main__":
    unittest.main()
