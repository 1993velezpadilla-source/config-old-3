#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

TARGETS = [
    "levels/kino/theatre_shared.group.bin",
    "levels/kino/kino_dynamics.group.bin",
    "levels/kino/kino_statics.group.bin",
]

KNOWN_CLASSES = [
    "CIwTexture",
    "CIwMaterial",
    "CIwModel",
    "CIwGxFont",
    "CIwResGroup",
    "CIwResList",
    "CIwResTemplate",
]

BLOCKS = {
    0x8081E087: "ResGroupParams",
    0x3B495DC0: "NestedGroups",
    0xDC3C2177: "ResourceObjects",
}

def iw_hash_string(value: str) -> int:
    h = 0x1505
    for byte in value.encode():
        if 0x41 <= byte <= 0x5A:
            byte += 0x20
        h = (byte + h * 0x21) & 0xFFFFFFFF
    return h

CLASS_HASHES = {name: iw_hash_string(name) for name in KNOWN_CLASSES}

def resolve_case_insensitive(root: Path, rel: str) -> Path | None:
    direct = root / rel
    if direct.exists():
        return direct
    needle = rel.replace("\\", "/").lower()
    for p in root.rglob("*"):
        if p.is_file() and p.relative_to(root).as_posix().lower() == needle:
            return p
    return None

def all_offsets(data: bytes, needle: bytes, limit: int = 64) -> list[int]:
    out = []
    pos = 0
    while True:
        pos = data.find(needle, pos)
        if pos < 0:
            break
        out.append(pos)
        pos += 1
        if len(out) >= limit:
            break
    return out

def scan_blocks(data: bytes) -> list[dict]:
    out = []
    for value, name in BLOCKS.items():
        for pos in all_offsets(data, struct.pack("<I", value)):
            item = {
                "name": name,
                "hash": f"0x{value:08x}",
                "offset": pos,
            }
            if pos + 8 <= len(data):
                declared = struct.unpack_from("<I", data, pos + 4)[0]
                item["declaredLengthField"] = declared
                item["declaredPayloadBytesAssumingMinus4"] = max(0, declared - 4)
                item["bytesRemainingAfterHeader"] = len(data) - (pos + 8)
            out.append(item)
    return sorted(out, key=lambda x: x["offset"])

def scan_classes(data: bytes) -> list[dict]:
    out = []
    for name, value in CLASS_HASHES.items():
        needle = struct.pack("<I", value)
        for pos in all_offsets(data, needle):
            item = {
                "class": name,
                "hash": f"0x{value:08x}",
                "offset": pos,
            }
            if pos + 10 <= len(data):
                count = struct.unpack_from("<I", data, pos + 4)[0]
                flag_a = data[pos + 8]
                flag_b = data[pos + 9]
                item.update({
                    "countCandidate": count,
                    "flagA": flag_a,
                    "flagB": flag_b,
                    "plausibleHeader": (
                        0 < count < 100000
                        and flag_a in (0, 1)
                        and flag_b in (0, 1)
                    ),
                })
            out.append(item)
    return sorted(out, key=lambda x: x["offset"])

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    root = args.root.resolve()
    report = {
        "schemaVersion": 1,
        "method": "hash-header inventory; body parsing intentionally deferred",
        "targets": [],
    }

    passed = 0
    for rel in TARGETS:
        p = resolve_case_insensitive(root, rel)
        item = {"path": rel, "found": p is not None}
        if p is None:
            report["targets"].append(item)
            print("INVENTORY_MISSING", rel)
            continue

        data = p.read_bytes()
        blocks = scan_blocks(data)
        classes = scan_classes(data)
        plausible = [x for x in classes if x.get("plausibleHeader")]
        item.update({
            "bytes": len(data),
            "magicU32": f"0x{struct.unpack_from('<I', data, 0)[0]:08x}" if len(data) >= 4 else None,
            "blocks": blocks,
            "classHeaders": classes,
            "plausibleClassHeaders": plausible,
        })
        report["targets"].append(item)

        print("INVENTORY_GROUP", rel, "bytes", len(data))
        for b in blocks:
            print(
                "  BLOCK", b["name"],
                "offset", hex(b["offset"]),
                "lengthField", b.get("declaredLengthField"),
                "remaining", b.get("bytesRemainingAfterHeader"),
            )
        for c in classes:
            print(
                "  CLASS", c["class"],
                "offset", hex(c["offset"]),
                "count", c.get("countCandidate"),
                "flags", c.get("flagA"), c.get("flagB"),
                "plausible", c.get("plausibleHeader"),
            )

        if plausible:
            passed += 1

    report["groupsWithPlausibleClassHeaders"] = passed
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("GROUPS_WITH_PLAUSIBLE_CLASS_HEADERS", passed)
    if passed != len(TARGETS):
        raise SystemExit("XZIEL_BOZ_RESOURCE_INVENTORY_FAILED")
    print("XZIEL_BOZ_RESOURCE_INVENTORY_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
