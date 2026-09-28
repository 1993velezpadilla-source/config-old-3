#!/usr/bin/env python3
import struct
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pak_inventory


def make_fixture() -> bytes:
    resource_count = 5
    header = struct.pack("<6I", 0x43545731, 5, 5, 5, resource_count, 1)
    table = struct.pack("<5H", 1, 2, 3, 4, 5)
    blob = bytearray(6 * 4096)
    blob[:len(header)] = header
    blob[len(header):len(header) + len(table)] = table

    # Resource 0: main table. Only worldstreamblocks.res is mapped.
    ids = [-1] * 23
    ids[0] = 1
    struct.pack_into("<23h", blob, 1 * 4096, *ids)

    # Resource 1: world stream table, first block id points to resource 2.
    struct.pack_into("<h", blob, 2 * 4096 + 8, 2)
    for i in range(1, 32):
        struct.pack_into("<h", blob, 2 * 4096 + 8 + i * 2, -1)

    # Resource 2: arbitrary WBL payload; naming table determines type.
    blob[3 * 4096:3 * 4096 + 8] = b"WBLTEST!"

    # Resource 3: model magic.
    blob[4 * 4096:4 * 4096 + 2] = b"MG"

    # Resource 4: plausible CTW texture header.
    tex = pak_inventory.TEXTURE_HEADER.pack(128, 64, 0x83F3, 32, 1, 4096)
    blob[5 * 4096:5 * 4096 + len(tex)] = tex
    return bytes(blob)


class PakInventoryTests(unittest.TestCase):
    def test_inventory_maps_worldblock_and_types(self):
        with tempfile.TemporaryDirectory() as td:
            pak = Path(td) / "game.pak"
            pak.write_bytes(make_fixture())
            report = pak_inventory.inventory_pak(pak)

        self.assertEqual(report["resource_count"], 5)
        by_id = {r["id"]: r for r in report["resources"]}
        self.assertEqual(by_id[2]["name"], "worldblock0.wbl")
        self.assertEqual(by_id[2]["type"], "worldblock")
        self.assertEqual(by_id[3]["type"], "model")
        self.assertEqual(by_id[4]["type"], "texture")

    def test_extract_selected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pak = root / "game.pak"
            out = root / "out"
            pak.write_bytes(make_fixture())
            report = pak_inventory.inventory_pak(pak)
            pak_inventory.extract_selected(pak, report, out, {3})
            files = list(out.iterdir())
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].name.startswith("00003_"))
            self.assertEqual(files[0].read_bytes()[:2], b"MG")


if __name__ == "__main__":
    unittest.main()
