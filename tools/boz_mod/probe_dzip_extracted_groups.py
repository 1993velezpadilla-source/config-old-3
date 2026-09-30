#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

TARGETS = [
    "levels/kino/kino.group.bin",
    "levels/kino/kino_sectors.group.bin",
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

def iw_hash_string(value: str) -> int:
    h = 0x1505
    for byte in value.encode():
        if 0x41 <= byte <= 0x5A:
            byte += 0x20
        h = (byte + h * 0x21) & 0xFFFFFFFF
    return h

H_MEMBERS = iw_hash_string("ResGroupMembers")
H_RESOURCES = iw_hash_string("ResGroupResources")
CLASS_BY_HASH = {iw_hash_string(n): n for n in KNOWN_CLASSES}

def read_cstring(data: bytes) -> str:
    end = data.find(b"\0")
    if end < 0:
        end = len(data)
    return data[:end].decode("latin1", errors="replace")

def parse_resource_summary(payload: bytes) -> dict:
    if len(payload) < 4:
        raise ValueError("ResGroupResources payload too short")
    q = 0
    num_types = struct.unpack_from("<I", payload, q)[0]
    q += 4
    classes = []
    for _ in range(num_types):
        if q + 10 > len(payload):
            raise ValueError("resource type header exceeds payload")
        class_hash, count = struct.unpack_from("<II", payload, q)
        names_omitted = payload[q + 8]
        has_size = payload[q + 9]
        q += 10
        cname = CLASS_BY_HASH.get(class_hash, f"class_{class_hash:08x}")
        classes.append({
            "class": cname,
            "classHash": f"0x{class_hash:08x}",
            "count": count,
            "namesOmitted": names_omitted,
            "hasSize": has_size,
        })
        if not has_size:
            raise ValueError(f"{cname} has no per-resource size; unsupported summary")
        for _item in range(count):
            start = q
            if q + 4 > len(payload):
                raise ValueError("resource size exceeds payload")
            size = struct.unpack_from("<I", payload, q)[0]
            if size < 8 or start + size > len(payload):
                raise ValueError(
                    f"resource size invalid for {cname}: size={size} at {start}"
                )
            q += 4
            if not names_omitted:
                q += 4
            q += 4
            q = start + size
    return {"numTypes": num_types, "classes": classes}

def parse_group(data: bytes) -> dict:
    if not data or data[0] != 0x3D:
        raise ValueError(f"not CIwResGroup: head={data[:16].hex()}")
    if len(data) < 10:
        raise ValueError("group too short")

    p = 6
    sections = []
    group_name = None
    resources = None
    terminated = False

    while True:
        if p + 4 > len(data):
            raise ValueError("section hash exceeds file")
        section_hash = struct.unpack_from("<I", data, p)[0]
        p += 4
        if section_hash == 0:
            terminated = True
            break
        if p + 4 > len(data):
            raise ValueError("section size exceeds file")
        size = struct.unpack_from("<I", data, p)[0]
        p += 4
        if size < 4:
            raise ValueError(f"invalid section size {size}")
        payload_len = size - 4
        if p + payload_len > len(data):
            raise ValueError(
                f"section 0x{section_hash:08x} exceeds file: {payload_len} bytes"
            )
        payload = data[p:p + payload_len]
        p += payload_len

        item = {
            "hash": f"0x{section_hash:08x}",
            "payloadBytes": payload_len,
        }
        if section_hash == H_MEMBERS:
            item["name"] = "ResGroupMembers"
            group_name = read_cstring(payload)
        elif section_hash == H_RESOURCES:
            item["name"] = "ResGroupResources"
            resources = parse_resource_summary(payload)
        else:
            item["name"] = "unknown"
        sections.append(item)

    return {
        "valid": True,
        "magic": "0x3d",
        "groupName": group_name,
        "terminated": terminated,
        "sectionCount": len(sections),
        "sections": sections,
        "resources": resources,
    }

def resolve_case_insensitive(root: Path, rel: str) -> Path | None:
    direct = root / rel
    if direct.exists():
        return direct
    needle = rel.replace("\\", "/").lower()
    for p in root.rglob("*"):
        if p.is_file():
            got = p.relative_to(root).as_posix().lower()
            if got == needle:
                return p
    return None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    root = args.root.resolve()
    report = {
        "schemaVersion": 2,
        "decoder": "CodexuRegexl/Dzip-Rust native DZ codec",
        "targets": [],
    }

    ok = 0
    for target in TARGETS:
        path = resolve_case_insensitive(root, target)
        item = {"path": target, "found": path is not None}
        if path is not None:
            data = path.read_bytes()
            item["bytes"] = len(data)
            item["headHex"] = data[:32].hex()
            try:
                item["group"] = parse_group(data)
                ok += 1
                print("GROUP_OK", target, "bytes", len(data),
                      "name", repr(item["group"]["groupName"]),
                      "sections", item["group"]["sectionCount"])
                if item["group"]["resources"]:
                    for cls in item["group"]["resources"]["classes"]:
                        print("  RESOURCE_CLASS", cls["class"], cls["count"])
            except Exception as exc:
                item["group"] = {"valid": False, "error": str(exc)}
                print("GROUP_BAD", target, str(exc))
        else:
            print("GROUP_MISSING", target)
        report["targets"].append(item)

    report["validGroupCount"] = ok
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("VALID_GROUP_COUNT", ok)
    if ok != len(TARGETS):
        raise SystemExit("XZIEL_BOZ_GROUP_DECODE_FAILED")
    print("XZIEL_BOZ_GROUP_DECODE_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
