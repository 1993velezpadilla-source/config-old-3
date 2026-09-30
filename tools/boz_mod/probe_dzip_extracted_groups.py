#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

TARGETS = [
    "levels/kino/kino.group.bin",
    "levels/kino/kino_sectors.group.bin",
    "levels/kino/theatre_shared.group.bin",
    "levels/kino/kino_dynamics.group.bin",
    "levels/kino/kino_statics.group.bin",
]

KNOWN_NAMES = [
    "ResGroupMembers",
    "ResGroupResources",
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

HASHES = {name: iw_hash_string(name) for name in KNOWN_NAMES}
H_MEMBERS = HASHES["ResGroupMembers"]
H_RESOURCES = HASHES["ResGroupResources"]

def read_cstring(data: bytes) -> str:
    end = data.find(b"\0")
    if end < 0:
        end = len(data)
    return data[:end].decode("latin1", errors="replace")

def printable_strings(data: bytes, minimum: int = 4, limit: int = 80) -> list[str]:
    values = re.findall(rb"[\x20-\x7e]{%d,}" % minimum, data)
    out: list[str] = []
    for raw in values:
        value = raw.decode("ascii", errors="ignore")
        if value and value not in out:
            out.append(value)
        if len(out) >= limit:
            break
    return out

def count_hash_occurrences(data: bytes) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for name, value in HASHES.items():
        needle = struct.pack("<I", value)
        offsets: list[int] = []
        start = 0
        while True:
            pos = data.find(needle, start)
            if pos < 0:
                break
            offsets.append(pos)
            start = pos + 1
            if len(offsets) >= 64:
                break
        entry: dict[str, object] = {
            "hash": f"0x{value:08x}",
            "count": len(offsets),
            "offsets": offsets[:16],
        }
        if name.startswith("CIw") and offsets:
            headers = []
            for pos in offsets[:16]:
                if pos + 10 > len(data):
                    continue
                count = struct.unpack_from("<I", data, pos + 4)[0]
                names_omitted = data[pos + 8]
                has_size = data[pos + 9]
                plausible = (
                    count < 100000
                    and names_omitted in (0, 1)
                    and has_size in (0, 1)
                )
                headers.append({
                    "offset": pos,
                    "resourceCount": count,
                    "namesOmitted": names_omitted,
                    "hasSize": has_size,
                    "plausibleResourceClassHeader": plausible,
                })
            entry["resourceClassHeaders"] = headers
        out[name] = entry
    return out

def parse_top_level_best_effort(data: bytes) -> dict:
    result: dict[str, object] = {
        "magic": "0x3d",
        "groupName": None,
        "sections": [],
        "terminated": False,
        "complete": False,
        "warning": None,
    }
    if not data or data[0] != 0x3D:
        raise ValueError(f"not CIwResGroup: head={data[:16].hex()}")
    if len(data) < 10:
        raise ValueError("group too short")

    p = 6
    sections: list[dict[str, object]] = []
    try:
        for _ in range(256):
            if p + 4 > len(data):
                raise ValueError(f"section hash exceeds file at 0x{p:x}")
            section_offset = p
            section_hash = struct.unpack_from("<I", data, p)[0]
            p += 4
            if section_hash == 0:
                result["terminated"] = True
                result["complete"] = True
                break
            if p + 4 > len(data):
                raise ValueError(f"section size exceeds file at 0x{p:x}")
            size = struct.unpack_from("<I", data, p)[0]
            p += 4
            if size < 4:
                raise ValueError(f"invalid section size {size} at 0x{section_offset:x}")
            payload_len = size - 4
            if p + payload_len > len(data):
                raise ValueError(
                    f"section 0x{section_hash:08x} at 0x{section_offset:x} "
                    f"claims {payload_len} bytes beyond file"
                )

            payload = data[p:p + payload_len]
            p += payload_len
            name = next(
                (n for n, h in HASHES.items() if h == section_hash),
                "unknown",
            )
            section = {
                "offset": section_offset,
                "hash": f"0x{section_hash:08x}",
                "name": name,
                "payloadBytes": payload_len,
            }
            if section_hash == H_MEMBERS:
                group_name = read_cstring(payload)
                section["groupName"] = group_name
                result["groupName"] = group_name
            sections.append(section)
        else:
            result["warning"] = "top-level section guard reached"
    except Exception as exc:
        result["warning"] = str(exc)

    result["sections"] = sections
    result["sectionCount"] = len(sections)
    result["parsedBytes"] = p
    return result

def resolve_case_insensitive(root: Path, rel: str) -> Path | None:
    direct = root / rel
    if direct.exists():
        return direct
    needle = rel.replace("\\", "/").lower()
    for p in root.rglob("*"):
        if p.is_file() and p.relative_to(root).as_posix().lower() == needle:
            return p
    return None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    root = args.root.resolve()
    report: dict[str, object] = {
        "schemaVersion": 3,
        "decoder": "CodexuRegexl/Dzip-Rust native DZ codec",
        "gateDefinition": (
            "All five Kino resources must exist after native-DZ extraction and "
            "begin with Marmalade CIwResGroup magic 0x3d. Deep structural parsing "
            "is best-effort and cannot invalidate successful archive decoding."
        ),
        "targets": [],
    }

    decoded_group_count = 0
    complete_deep_parse_count = 0

    for target in TARGETS:
        path = resolve_case_insensitive(root, target)
        item: dict[str, object] = {"path": target, "found": path is not None}

        if path is None:
            print("GROUP_MISSING", target)
            report["targets"].append(item)
            continue

        data = path.read_bytes()
        is_group = bool(data) and data[0] == 0x3D
        item["bytes"] = len(data)
        item["headHex"] = data[:32].hex()
        item["ciwResGroupMagic"] = is_group
        item["hashInventory"] = count_hash_occurrences(data)
        item["printableStrings"] = printable_strings(data)

        if not is_group:
            print("GROUP_INVALID_MAGIC", target, data[:16].hex())
            report["targets"].append(item)
            continue

        decoded_group_count += 1
        top = parse_top_level_best_effort(data)
        item["topLevel"] = top
        if top["complete"]:
            complete_deep_parse_count += 1

        def class_count(name: str) -> int | None:
            headers = item["hashInventory"][name].get("resourceClassHeaders", [])
            for header in headers:
                if header.get("plausibleResourceClassHeader"):
                    return int(header["resourceCount"])
            return None

        models = class_count("CIwModel")
        materials = class_count("CIwMaterial")
        textures = class_count("CIwTexture")

        status = "complete" if top["complete"] else "variant"
        print(
            "GROUP_DECODED",
            target,
            "bytes",
            len(data),
            "name",
            repr(top["groupName"]),
            "top_parse",
            status,
            "CIwModels",
            models,
            "CIwMaterials",
            materials,
            "CIwTextures",
            textures,
        )
        if top["warning"]:
            print("  DEEP_PARSE_WARNING", top["warning"])
        for s in item["printableStrings"][:12]:
            print("  STRING", repr(s))

        report["targets"].append(item)

    report["decodedCIwResGroupCount"] = decoded_group_count
    report["completeDeepParseCount"] = complete_deep_parse_count
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("DECODED_CIW_RESGROUP_COUNT", decoded_group_count)
    print("COMPLETE_DEEP_PARSE_COUNT", complete_deep_parse_count)

    if decoded_group_count != len(TARGETS):
        raise SystemExit("XZIEL_BOZ_GROUP_DECODE_FAILED")

    print("XZIEL_BOZ_GROUP_DECODE_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
