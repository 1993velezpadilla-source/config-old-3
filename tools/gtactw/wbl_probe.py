#!/usr/bin/env python3
"""Inspect GTA Chinatown Wars .wbl world-streaming resources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

MATRIX = struct.Struct("<9hh3i")
WORLD_SECTOR = struct.Struct("<9hh3i4H")
SECTOR = struct.Struct("<BB5H")
LEVEL = struct.Struct("<3iHH")
INSTANCE = struct.Struct("<hBBiII")
LIGHT = struct.Struct("<5i")
UNK20 = struct.Struct("<5i")

assert MATRIX.size == 32
assert WORLD_SECTOR.size == 40
assert SECTOR.size == 12
assert LEVEL.size == 16
assert INSTANCE.size == 16
assert LIGHT.size == 20
assert UNK20.size == 20


def matrix_report(raw):
    return {
        "right": [raw[0] / 4096.0, raw[1] / 4096.0, raw[2] / 4096.0],
        "top": [raw[3] / 4096.0, raw[4] / 4096.0, raw[5] / 4096.0],
        "at": [raw[6] / 4096.0, raw[7] / 4096.0, raw[8] / 4096.0],
        "padding": raw[9],
        "position": [raw[10] / 4096.0, raw[11] / 4096.0, raw[12] / 4096.0],
    }


def parse_wbl_bytes(blob: bytes) -> dict:
    if len(blob) < WORLD_SECTOR.size:
        raise ValueError("worldblock is smaller than its 40-byte header")

    ws = WORLD_SECTOR.unpack_from(blob, 0)
    transform = matrix_report(ws[:13])
    offsets = list(ws[13:17])

    sectors = []
    totals = {
        "levels": 0,
        "instances": 0,
        "lights": 0,
        "unknown20": 0,
        "texture_refs": 0,
    }
    unique_resources = set()
    unique_textures = set()

    for sector_id, rel in enumerate(offsets):
        pos = WORLD_SECTOR.size + rel
        if pos + SECTOR.size > len(blob):
            raise ValueError(
                f"sector {sector_id} header outside worldblock: offset=0x{pos:X}"
            )

        bool1, bool2, num_instances, num_lights, num_levels, count6, num_textures = SECTOR.unpack_from(blob, pos)
        cursor = pos + SECTOR.size

        need = (
            num_levels * LEVEL.size
            + num_instances * INSTANCE.size
            + num_lights * LIGHT.size
            + count6 * UNK20.size
            + num_textures * 2
        )
        if cursor + need > len(blob):
            raise ValueError(
                f"sector {sector_id} payload truncated: needs {need} bytes"
            )

        levels = []
        for _ in range(num_levels):
            x, y, z, level_instances, flags = LEVEL.unpack_from(blob, cursor)
            cursor += LEVEL.size
            levels.append({
                "position_raw": [x, y, z],
                "position": [x / 4096.0, y / 4096.0, z / 4096.0],
                "num_instances": level_instances,
                "flags": flags,
            })

        instances = []
        for _ in range(num_instances):
            instance_id, render_list, building_swap, resource_id, mesh_offset, ptr_unused = INSTANCE.unpack_from(blob, cursor)
            cursor += INSTANCE.size
            instances.append({
                "id": instance_id,
                "render_list_id": render_list,
                "building_swap": building_swap,
                "resource_id": resource_id,
                "offset_to_mesh": mesh_offset,
                "ptr_unused_raw": ptr_unused,
            })
            if resource_id >= 0:
                unique_resources.add(resource_id)

        lights = []
        for _ in range(num_lights):
            values = list(LIGHT.unpack_from(blob, cursor))
            cursor += LIGHT.size
            lights.append(values)

        unknown20 = []
        for _ in range(count6):
            values = list(UNK20.unpack_from(blob, cursor))
            cursor += UNK20.size
            unknown20.append(values)

        texture_ids = []
        if num_textures:
            texture_ids = list(struct.unpack_from(f"<{num_textures}h", blob, cursor))
            cursor += num_textures * 2
            unique_textures.update(t for t in texture_ids if t >= 0)

        totals["levels"] += num_levels
        totals["instances"] += num_instances
        totals["lights"] += num_lights
        totals["unknown20"] += count6
        totals["texture_refs"] += num_textures

        sectors.append({
            "sector": sector_id,
            "relative_offset": rel,
            "absolute_offset": pos,
            "bool1": bool1,
            "bool2": bool2,
            "num_instances": num_instances,
            "num_lights": num_lights,
            "num_levels": num_levels,
            "count6": count6,
            "num_textures": num_textures,
            "payload_end": cursor,
            "levels": levels,
            "instances": instances,
            "lights": lights,
            "unknown20": unknown20,
            "texture_ids": texture_ids,
        })

    return {
        "file_size": len(blob),
        "transform": transform,
        "sector_offsets": offsets,
        "sectors": sectors,
        "totals": totals,
        "unique_model_resource_ids": sorted(unique_resources),
        "unique_texture_ids": sorted(unique_textures),
    }


def parse_wbl(path: Path) -> dict:
    report = parse_wbl_bytes(path.read_bytes())
    report["path"] = str(path)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wbl", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        report = parse_wbl(args.wbl)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    report["ok"] = True
    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
