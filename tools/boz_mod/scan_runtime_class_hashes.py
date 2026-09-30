#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

TARGETS = [
    "levels/kino/theatre_shared.group.bin",
    "levels/kino/kino_dynamics.group.bin",
    "levels/kino/kino_statics.group.bin",
]

def iw_hash_string(value: str) -> int:
    h = 0x1505
    for byte in value.encode("ascii", errors="ignore"):
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

def collect_names(paths: list[Path]) -> list[str]:
    names = set()
    rx = re.compile(rb"\bCIw[A-Za-z0-9_]{2,80}\b")
    for p in paths:
        if not p.is_file():
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        for m in rx.finditer(data):
            try:
                names.add(m.group(0).decode("ascii"))
            except UnicodeDecodeError:
                pass
    return sorted(names)

def scan_group(data: bytes, names: list[str]) -> list[dict]:
    hits = []
    for name in names:
        value = iw_hash_string(name)
        needle = struct.pack("<I", value)
        pos = 0
        occurrences = 0
        while True:
            pos = data.find(needle, pos)
            if pos < 0:
                break
            occurrences += 1
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
            hits.append(item)
            pos += 1
            if occurrences >= 16:
                break
    return sorted(hits, key=lambda x: x["offset"])

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group-root", type=Path, required=True)
    ap.add_argument("--binary", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    names = collect_names(args.binary)
    print("RUNTIME_CIW_CLASS_NAMES", len(names))
    for n in names[:300]:
        print("  CIW_CLASS_NAME", n, f"0x{iw_hash_string(n):08x}")

    report = {
        "schemaVersion": 1,
        "runtimeClassNameCount": len(names),
        "runtimeClassNames": [
            {"name": n, "hash": f"0x{iw_hash_string(n):08x}"}
            for n in names
        ],
        "targets": [],
    }

    groups_with_plausible = 0
    for rel in TARGETS:
        p = resolve_case_insensitive(args.group_root, rel)
        item = {"path": rel, "found": p is not None}
        if p is None:
            report["targets"].append(item)
            continue
        data = p.read_bytes()
        hits = scan_group(data, names)
        plausible = [h for h in hits if h.get("plausibleHeader")]
        item.update({
            "bytes": len(data),
            "hits": hits,
            "plausibleHeaders": plausible,
        })
        report["targets"].append(item)
        print("RUNTIME_HASH_SCAN", rel, "plausible", len(plausible))
        for h in plausible[:120]:
            print(
                "  MATCH", h["class"], h["hash"],
                "offset", hex(h["offset"]),
                "count", h["countCandidate"],
                "flags", h["flagA"], h["flagB"],
            )
        if plausible:
            groups_with_plausible += 1

    report["groupsWithRuntimeClassHeaders"] = groups_with_plausible
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not names:
        raise SystemExit("XZIEL_BOZ_RUNTIME_CLASS_DICTIONARY_EMPTY")
    if groups_with_plausible != len(TARGETS):
        raise SystemExit("XZIEL_BOZ_RUNTIME_CLASS_SCAN_FAILED")
    print("XZIEL_BOZ_RUNTIME_CLASS_SCAN_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
