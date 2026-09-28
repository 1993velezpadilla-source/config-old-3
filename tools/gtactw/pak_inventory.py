#!/usr/bin/env python3
"""Inventory/extract CTW Android game.pak resources from a user-owned copy.

This follows the public CTW-Mobile-Explorer resource table layout.  It never
fetches game data; it only operates on a local game.pak supplied by the user.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import struct

PAK_HEADER = struct.Struct("<6I")
FIRST_OFFSET_COUNT = 2036
BLOCK_SIZE = 4096
RANGE_BASES = (0x00000000, 0x10000000, 0x20000000, 0x30000000)
TEXTURE_HEADER = struct.Struct("<HHHBBI")
MODEL_MAGIC = b"MG"

KNOWN_TEX_FORMATS = {
    0x8363, 0xBEEF, 0x83F0, 0x83F3, 0x87EE,
    0x8C00, 0x8C01, 0x8C02,
    *range(0x1900, 0x190B),
}


def sanitize(name: str) -> str:
    name = name.strip().replace("\\", "_").replace("/", "_")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "unnamed"


def read_index(fp):
    fp.seek(0, os.SEEK_END)
    file_size = fp.tell()
    fp.seek(0)
    raw = fp.read(PAK_HEADER.size)
    if len(raw) != PAK_HEADER.size:
        raise ValueError("truncated PAK header")

    version, r0, r1, r2, resource_count, resource_blocks = PAK_HEADER.unpack(raw)
    ranges = (r0, r1, r2)
    if resource_count == 0:
        raise ValueError("PAK reports zero resources")
    if not (r0 <= r1 <= r2 <= resource_count):
        raise ValueError(f"invalid ranges={ranges} resource_count={resource_count}")

    first = min(resource_count, FIRST_OFFSET_COUNT)
    raw_first = fp.read(first * 2)
    if len(raw_first) != first * 2:
        raise ValueError("truncated first offset table")
    blocks = list(struct.unpack(f"<{first}H", raw_first)) if first else []

    if resource_count > FIRST_OFFSET_COUNT:
        count = resource_count - FIRST_OFFSET_COUNT
        second_pos = resource_blocks * BLOCK_SIZE
        if second_pos + count * 2 > file_size:
            raise ValueError("second offset table lies outside PAK")
        fp.seek(second_pos)
        raw_second = fp.read(count * 2)
        if len(raw_second) != count * 2:
            raise ValueError("truncated second offset table")
        blocks.extend(struct.unpack(f"<{count}H", raw_second))

    offsets = []
    for rid, block in enumerate(blocks):
        base = RANGE_BASES[0]
        if rid >= r0:
            base = RANGE_BASES[1]
            if rid >= r1:
                base = RANGE_BASES[2]
                if rid >= r2:
                    base = RANGE_BASES[3]
        offsets.append(base + block * BLOCK_SIZE)

    for rid, off in enumerate(offsets):
        if off >= file_size:
            raise ValueError(f"resource {rid} offset 0x{off:X} outside PAK size 0x{file_size:X}")
        if rid and off < offsets[rid - 1]:
            raise ValueError(f"resource offsets are not monotonic at id {rid}")

    return {
        "version_signature": version,
        "ranges": ranges,
        "resource_count": resource_count,
        "resource_blocks_count": resource_blocks,
        "file_size": file_size,
        "offsets": offsets,
    }


def resource_span(index, rid: int):
    offsets = index["offsets"]
    if rid < 0 or rid >= len(offsets):
        raise IndexError(rid)
    start = offsets[rid]
    end = offsets[rid + 1] if rid + 1 < len(offsets) else index["file_size"]
    if end < start:
        raise ValueError(f"negative span for resource {rid}")
    return start, end


def classify_prefix(prefix: bytes) -> str:
    if prefix.startswith(MODEL_MAGIC):
        return "model"
    if len(prefix) >= TEXTURE_HEADER.size:
        width, height, fmt, depth, has_alpha, pixels_size = TEXTURE_HEADER.unpack_from(prefix)
        if (
            1 < width <= 2048
            and 1 < height <= 2048
            and fmt in KNOWN_TEX_FORMATS
            and depth <= 64
            and has_alpha <= 1
            and pixels_size >= 0
        ):
            return "texture"
    return "unknown"


def map_known_names(fp, index) -> dict[int, str]:
    names = {0: "maintable.res"}
    offsets = index["offsets"]
    if not offsets:
        return names

    start, end = resource_span(index, 0)
    fp.seek(start)
    raw = fp.read(min(56, end - start))
    if len(raw) < 46:
        return names
    ids = struct.unpack_from("<23h", raw, 0)

    def valid(rid):
        return 0 <= rid < index["resource_count"]

    fixed = {
        0: "worldstreamblocks.res",
        1: "globaltextures.res",
        2: "globalalphatextures.res",
        4: "vehicleinfos.res",
        5: "vehiclepalettes.res",
        8: "pedinfos.res",
        19: "dynamiclights.res",
        22: "radar.res",
    }
    for slot, label in fixed.items():
        rid = ids[slot]
        if valid(rid):
            names[rid] = label

    world_table = ids[0]
    if valid(world_table):
        ws, we = resource_span(index, world_table)
        fp.seek(ws + 8)
        raw_blocks = fp.read(min(2478 * 2, max(0, we - (ws + 8))))
        count = len(raw_blocks) // 2
        if count:
            block_ids = struct.unpack(f"<{count}h", raw_blocks[:count * 2])
            for block_no, rid in enumerate(block_ids):
                if valid(rid):
                    names[rid] = f"worldblock{block_no}.wbl"

    vehicle_info = ids[4]
    if valid(vehicle_info):
        vs, ve = resource_span(index, vehicle_info)
        fp.seek(vs)
        raw_count = fp.read(4)
        if len(raw_count) == 4:
            n = struct.unpack("<I", raw_count)[0]
            record_size = 0x138
            max_records = max(0, (ve - vs - 4) // record_size)
            n = min(n, max_records, 4096)
            for _ in range(n):
                rec = fp.read(record_size)
                if len(rec) != record_size:
                    break
                rid = struct.unpack_from("<h", rec, 2)[0]
                raw_name = rec[8:40].split(b"\0", 1)[0]
                try:
                    veh = raw_name.decode("ascii", "replace").strip()
                except Exception:
                    veh = ""
                if valid(rid) and veh:
                    stem = veh.split(".", 1)[0]
                    names[rid] = sanitize(stem) + ".mdl"

    radar = ids[22]
    if valid(radar):
        rs, re = resource_span(index, radar)
        fp.seek(rs + 8)
        raw_radar = fp.read(min(118, max(0, re - (rs + 8))))
        if len(raw_radar) >= 2:
            full = struct.unpack_from("<h", raw_radar, 0)[0]
            if valid(full):
                names[full] = "radarmap.tex"
        if len(raw_radar) >= 6 + 56 * 2:
            chunk_ids = struct.unpack_from("<56h", raw_radar, 6)
            for i, rid in enumerate(chunk_ids):
                if valid(rid):
                    names[rid] = f"radar{i:02d}.tex"

    return names


def inventory_pak(path: Path):
    with path.open("rb") as fp:
        index = read_index(fp)
        names = map_known_names(fp, index)
        resources = []
        counts = {"model": 0, "texture": 0, "worldblock": 0, "named_data": 0, "unknown": 0}
        for rid in range(index["resource_count"]):
            start, end = resource_span(index, rid)
            fp.seek(start)
            prefix = fp.read(min(32, end - start))
            kind = classify_prefix(prefix)
            name = names.get(rid)
            if name and name.endswith(".wbl"):
                kind = "worldblock"
            elif name and kind == "unknown":
                kind = "named_data"

            counts[kind] = counts.get(kind, 0) + 1
            ext = {
                "model": ".mdl",
                "texture": ".tex",
                "worldblock": ".wbl",
                "named_data": ".bin",
                "unknown": ".bin",
            }[kind]
            filename = sanitize(name) if name else f"res_{rid:05d}{ext}"
            resources.append({
                "id": rid,
                "offset": start,
                "size": end - start,
                "type": kind,
                "name": name,
                "filename": filename,
            })

    return {
        "pak": str(path),
        "version_signature": index["version_signature"],
        "version_signature_hex": f"0x{index['version_signature']:08X}",
        "resource_count": index["resource_count"],
        "counts": counts,
        "resources": resources,
    }


def extract_selected(path: Path, report: dict, out_dir: Path, ids: set[int] | None = None):
    out_dir.mkdir(parents=True, exist_ok=True)
    with path.open("rb") as fp:
        for r in report["resources"]:
            rid = r["id"]
            if ids is not None and rid not in ids:
                continue
            fp.seek(r["offset"])
            data = fp.read(r["size"])
            dest = out_dir / f"{rid:05d}_{r['filename']}"
            dest.write_bytes(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pak", type=Path)
    ap.add_argument("--manifest", type=Path, help="Write full JSON inventory")
    ap.add_argument("--extract", type=Path, help="Extract resources locally")
    ap.add_argument("--ids", help="Comma-separated resource ids to extract")
    args = ap.parse_args()

    try:
        report = inventory_pak(args.pak)
        if args.manifest:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.extract:
            ids = None
            if args.ids:
                ids = {int(x.strip(), 0) for x in args.ids.split(",") if x.strip()}
            extract_selected(args.pak, report, args.extract, ids)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    summary = {k: v for k, v in report.items() if k != "resources"}
    summary["ok"] = True
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
