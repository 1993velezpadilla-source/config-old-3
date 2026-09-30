#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

GROUP_TAG = 0x3D
BLOCK_PARAMS = 0x8081E087
BLOCK_NESTED = 0x3B495DC0
BLOCK_OBJECTS = 0xDC3C2177

TARGETS = [
    "levels/kino/kino.group.bin",
    "levels/kino/kino_sectors.group.bin",
]

def iw_hash_string(value: str) -> int:
    h = 0x1505
    for byte in value.encode("latin1", errors="ignore"):
        if 0x41 <= byte <= 0x5A:
            byte += 0x20
        h = (byte + h * 0x21) & 0xFFFFFFFF
    return h

def resolve_case_insensitive(root: Path, rel: str) -> Path | None:
    direct = root / rel
    if direct.exists():
        return direct
    needle = rel.replace("\\", "/").lower()
    for p in root.rglob("*"):
        if p.is_file() and p.relative_to(root).as_posix().lower() == needle:
            return p
    return None

def read_cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.find(b"\0", pos)
    if end < 0:
        raise ValueError(f"unterminated string at 0x{pos:x}")
    return data[pos:end].decode("latin1"), end + 1

def parse_sections(data: bytes) -> list[dict]:
    if len(data) < 6 or data[0] != GROUP_TAG:
        raise ValueError(f"invalid CIwResGroup tag: {data[:6].hex()}")
    p = 6
    out = []
    while True:
        if p + 4 > len(data):
            raise ValueError("section hash out of range")
        h = struct.unpack_from("<I", data, p)[0]
        if h == 0:
            out.append({"hash": 0, "offset": p, "payloadStart": p + 4, "payloadEnd": p + 4})
            break
        if p + 8 > len(data):
            raise ValueError("section header out of range")
        size = struct.unpack_from("<I", data, p + 4)[0]
        if size < 4:
            raise ValueError(f"invalid section size {size} at 0x{p:x}")
        start = p + 8
        end = start + size - 4
        if end > len(data):
            raise ValueError(f"section 0x{h:08x} exceeds file")
        out.append({
            "hash": h,
            "offset": p,
            "sizeField": size,
            "payloadStart": start,
            "payloadEnd": end,
        })
        p = end
    return out

def candidate_hashes(path: str) -> dict[str, str]:
    norm = path.replace("\\", "/")
    leaf = norm.rsplit("/", 1)[-1]
    leaf_no_ext = leaf
    if leaf_no_ext.lower().endswith(".group"):
        leaf_no_ext = leaf_no_ext[:-6]
    norm_no_ext = norm[:-6] if norm.lower().endswith(".group") else norm
    return {
        "fullPath": f"0x{iw_hash_string(path):08x}",
        "normalizedPath": f"0x{iw_hash_string(norm):08x}",
        "pathWithoutGroup": f"0x{iw_hash_string(norm_no_ext):08x}",
        "leaf": f"0x{iw_hash_string(leaf):08x}",
        "leafWithoutGroup": f"0x{iw_hash_string(leaf_no_ext):08x}",
    }

def parse_nested(payload: bytes) -> dict:
    if not payload:
        return {"count": 0, "refs": []}
    count = payload[0]
    p = 1
    refs = []
    for i in range(count):
        name, p = read_cstring(payload, p)
        if p + 12 > len(payload):
            raise ValueError(f"nested ref {i} metadata out of range")
        data0, data1, name_hash = struct.unpack_from("<III", payload, p)
        p += 12
        candidates = candidate_hashes(name)
        stored = f"0x{name_hash:08x}"
        matches = [k for k, v in candidates.items() if v == stored]
        refs.append({
            "index": i,
            "name": name,
            "data0": data0,
            "data1": data1,
            "storedHash": stored,
            "hashCandidates": candidates,
            "matchingHashForms": matches,
        })
    return {
        "count": count,
        "parsedBytes": p,
        "payloadBytes": len(payload),
        "trailingBytes": len(payload) - p,
        "refs": refs,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    root = args.root.resolve()
    report = {"schemaVersion": 1, "targets": []}
    theatre_found = False
    hashes_understood = 0
    total_refs = 0

    for rel in TARGETS:
        p = resolve_case_insensitive(root, rel)
        if p is None:
            raise SystemExit(f"missing {rel}")
        data = p.read_bytes()
        sections = parse_sections(data)
        item = {"path": rel, "bytes": len(data), "sections": [], "nested": None}
        for sec in sections:
            item["sections"].append({
                "hash": f"0x{sec['hash']:08x}",
                "offset": sec["offset"],
                "sizeField": sec.get("sizeField"),
            })
            if sec["hash"] == BLOCK_NESTED:
                payload = data[sec["payloadStart"]:sec["payloadEnd"]]
                nested = parse_nested(payload)
                item["nested"] = nested
                print("NESTED_GROUP", rel, "count", nested["count"])
                for ref in nested["refs"]:
                    total_refs += 1
                    if ref["matchingHashForms"]:
                        hashes_understood += 1
                    if "theatre_shared.group" in ref["name"].lower():
                        theatre_found = True
                    print(
                        "  REF", ref["index"], repr(ref["name"]),
                        "data0", hex(ref["data0"]),
                        "data1", hex(ref["data1"]),
                        "storedHash", ref["storedHash"],
                        "matches", ",".join(ref["matchingHashForms"]) or "NONE",
                    )
        report["targets"].append(item)

    report["totalRefs"] = total_refs
    report["refsWithUnderstoodHash"] = hashes_understood
    report["theatreReferenceFound"] = theatre_found
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("TOTAL_NESTED_REFS", total_refs)
    print("REFS_WITH_UNDERSTOOD_HASH", hashes_understood)
    print("THEATRE_REFERENCE_FOUND", theatre_found)
    if not theatre_found or total_refs == 0:
        raise SystemExit("XZIEL_BOZ_NESTED_GROUP_ANALYSIS_FAILED")
    print("XZIEL_BOZ_NESTED_GROUP_ANALYSIS_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
