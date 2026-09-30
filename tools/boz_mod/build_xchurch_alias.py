#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

GROUP_TAG = 0x3D
BLOCK_PARAMS = 0x8081E087
BLOCK_NESTED = 0x3B495DC0

SOURCE_PATH = "levels/kino//theatre_shared.group"
TARGET_PATH = "levels/kino//xchurch_shared.group"
SOURCE_GROUP = "theatre"
TARGET_GROUP = "xchurch"

def iw_hash_string(value: str) -> int:
    h = 0x1505
    for byte in value.encode("latin1"):
        if 0x41 <= byte <= 0x5A:
            byte += 0x20
        h = (byte + h * 0x21) & 0xFFFFFFFF
    return h

def read_cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.find(b"\0", pos)
    if end < 0:
        raise ValueError(f"unterminated string at 0x{pos:x}")
    return data[pos:end].decode("latin1"), end + 1

def iter_sections(data: bytes):
    if len(data) < 6 or data[0] != GROUP_TAG:
        raise ValueError(f"not a BOZ CIwResGroup: {data[:8].hex()}")
    p = 6
    while True:
        if p + 4 > len(data):
            raise ValueError("section hash out of range")
        h = struct.unpack_from("<I", data, p)[0]
        if h == 0:
            yield h, p, p + 4, p + 4
            return
        if p + 8 > len(data):
            raise ValueError("section header out of range")
        size = struct.unpack_from("<I", data, p + 4)[0]
        if size < 4:
            raise ValueError(f"invalid section size {size}")
        start = p + 8
        end = start + size - 4
        if end > len(data):
            raise ValueError(
                f"section 0x{h:08x} exceeds file; this helper is only for "
                "the small fully-serialized map graph groups"
            )
        yield h, p, start, end
        p = end

def patch_sector_group(data: bytes) -> tuple[bytes, dict]:
    if len(SOURCE_PATH) != len(TARGET_PATH):
        raise ValueError("alias path must preserve byte length")

    out = bytearray(data)
    found = []
    for h, section_pos, start, end in iter_sections(data):
        if h != BLOCK_NESTED:
            continue
        payload = data[start:end]
        if not payload:
            continue
        count = payload[0]
        p = start + 1
        for index in range(count):
            name, after_name = read_cstring(data, p)
            if after_name + 12 > end:
                raise ValueError(f"nested ref {index} metadata out of range")
            data0, data1, stored_hash = struct.unpack_from("<III", data, after_name)
            if name == SOURCE_PATH:
                expected = iw_hash_string(SOURCE_GROUP)
                if stored_hash != expected:
                    raise ValueError(
                        f"source hash mismatch: got 0x{stored_hash:08x}, "
                        f"expected 0x{expected:08x}"
                    )
                raw_target = TARGET_PATH.encode("latin1")
                raw_source = SOURCE_PATH.encode("latin1")
                if len(raw_target) != len(raw_source):
                    raise ValueError("replacement length changed")
                out[p:p + len(raw_source)] = raw_target
                struct.pack_into("<I", out, after_name + 8, iw_hash_string(TARGET_GROUP))
                found.append({
                    "index": index,
                    "sourcePath": name,
                    "targetPath": TARGET_PATH,
                    "sourceHash": f"0x{stored_hash:08x}",
                    "targetHash": f"0x{iw_hash_string(TARGET_GROUP):08x}",
                    "data0": data0,
                    "data1": data1,
                })
            p = after_name + 12

    if len(found) != 1:
        raise ValueError(f"expected exactly one theatre sector ref, found {len(found)}")
    return bytes(out), found[0]

def patch_group_name(data: bytes) -> tuple[bytes, dict]:
    if len(SOURCE_GROUP) != len(TARGET_GROUP):
        raise ValueError("group alias must preserve name byte length")
    out = bytearray(data)
    for h, section_pos, start, end in iter_sections(data):
        if h != BLOCK_PARAMS:
            continue
        name, after = read_cstring(data, start)
        if name != SOURCE_GROUP:
            continue
        raw_source = SOURCE_GROUP.encode("latin1")
        raw_target = TARGET_GROUP.encode("latin1")
        out[start:start + len(raw_source)] = raw_target
        return bytes(out), {
            "paramsSectionOffset": section_pos,
            "sourceGroup": name,
            "targetGroup": TARGET_GROUP,
            "sourceHash": f"0x{iw_hash_string(SOURCE_GROUP):08x}",
            "targetHash": f"0x{iw_hash_string(TARGET_GROUP):08x}",
        }
    raise ValueError("theatre group-name params block not found")

def validate_sector(data: bytes) -> dict:
    source_hits = data.count(SOURCE_PATH.encode("latin1"))
    target_hits = data.count(TARGET_PATH.encode("latin1"))
    target_hash = struct.pack("<I", iw_hash_string(TARGET_GROUP))
    return {
        "sourcePathHits": source_hits,
        "targetPathHits": target_hits,
        "targetHashHits": data.count(target_hash),
        "bytes": len(data),
    }

def validate_alias(data: bytes) -> dict:
    if not data or data[0] != GROUP_TAG:
        raise ValueError("alias lost CIwResGroup tag")
    first_name = None
    for h, _section_pos, start, _end in iter_sections(data):
        if h == BLOCK_PARAMS:
            first_name, _ = read_cstring(data, start)
            break
    return {
        "groupName": first_name,
        "bytes": len(data),
        "ciwResGroupTag": data[0] == GROUP_TAG,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sectors", type=Path, required=True)
    ap.add_argument("--theatre", type=Path, required=True)
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    sectors = args.sectors.read_bytes()
    theatre = args.theatre.read_bytes()

    patched_sectors, sector_change = patch_sector_group(sectors)
    alias_group, group_change = patch_group_name(theatre)

    if len(patched_sectors) != len(sectors):
        raise SystemExit("sector byte length changed")
    if len(alias_group) != len(theatre):
        raise SystemExit("room byte length changed")

    sector_check = validate_sector(patched_sectors)
    alias_check = validate_alias(alias_group)

    if sector_check["sourcePathHits"] != 0:
        raise SystemExit("source theatre path remains in patched sectors")
    if sector_check["targetPathHits"] != 1:
        raise SystemExit("xchurch path missing or duplicated")
    if alias_check["groupName"] != TARGET_GROUP:
        raise SystemExit(f"alias internal name mismatch: {alias_check}")

    sectors_out = args.out_root / "levels/kino/kino_sectors.group.bin"
    alias_out = args.out_root / "levels/kino/xchurch_shared.group.bin"
    sectors_out.parent.mkdir(parents=True, exist_ok=True)
    sectors_out.write_bytes(patched_sectors)
    alias_out.write_bytes(alias_group)

    report = {
        "schemaVersion": 1,
        "strategy": "same-length room alias",
        "sectorChange": sector_change,
        "groupChange": group_change,
        "sectorValidation": sector_check,
        "aliasValidation": alias_check,
        "output": {
            "sectors": str(sectors_out),
            "room": str(alias_out),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("SOURCE_ROOM", SOURCE_GROUP, f"0x{iw_hash_string(SOURCE_GROUP):08x}")
    print("TARGET_ROOM", TARGET_GROUP, f"0x{iw_hash_string(TARGET_GROUP):08x}")
    print("SECTOR_PATH_REWRITE_OK", SOURCE_PATH, "->", TARGET_PATH)
    print("ROOM_INTERNAL_NAME_REWRITE_OK", SOURCE_GROUP, "->", TARGET_GROUP)
    print("SECTOR_BYTES", len(sectors), "->", len(patched_sectors))
    print("ROOM_BYTES", len(theatre), "->", len(alias_group))
    print("XZIEL_BOZ_XCHURCH_ALIAS_BUILD_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
