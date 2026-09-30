#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import lzma
import re
import sys
import zlib
from pathlib import Path


TARGETS = [
    "levels/kino/kino.group.bin",
    "levels/kino/kino_sectors.group.bin",
    "levels/kino/theatre_shared.group.bin",
    "levels/kino/kino_dynamics.group.bin",
    "levels/kino/kino_statics.group.bin",
]


def load_parser(root: Path):
    path = root / "tools" / "boz_mod" / "dtrz_replace.py"
    spec = importlib.util.spec_from_file_location("xziel_dtrz_parser", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def printable_strings(data: bytes, minimum: int = 5, limit: int = 80) -> list[str]:
    vals = re.findall(rb"[\x20-\x7e]{%d,}" % minimum, data)
    out = []
    for raw in vals:
        s = raw.decode("ascii", errors="ignore")
        if s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def decode_alone(slot: bytes):
    try:
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        out = dec.decompress(slot)
        if out:
            return out, "lzma-alone"
    except lzma.LZMAError:
        pass
    return None, None


def decode_raw_after_header(slot: bytes):
    if len(slot) < 13:
        return None, None
    prop = slot[0]
    pb = prop // 45
    rem = prop % 45
    lp = rem // 9
    lc = rem % 9
    if lc > 8 or lp > 4 or pb > 4:
        return None, None
    dict_size = int.from_bytes(slot[1:5], "little")
    if not (4096 <= dict_size <= (1 << 30)):
        return None, None

    filt = [{
        "id": lzma.FILTER_LZMA1,
        "dict_size": dict_size,
        "lc": lc,
        "lp": lp,
        "pb": pb,
    }]
    try:
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt)
        out = dec.decompress(slot[13:])
        if out:
            return out, "lzma-raw-after-alone-header"
    except lzma.LZMAError:
        pass
    return None, None


def decode_zlib(slot: bytes):
    for wbits, name in [(zlib.MAX_WBITS, "zlib"), (-zlib.MAX_WBITS, "deflate-raw")]:
        try:
            out = zlib.decompress(slot, wbits)
            if out:
                return out, name
        except zlib.error:
            pass
    return None, None


def decode_entry(slot: bytes, expected: int):
    attempts = []
    for fn in (decode_alone, decode_raw_after_header, decode_zlib):
        out, method = fn(slot)
        if out is not None:
            attempts.append((out, method))
            if expected <= 0 or len(out) == expected:
                return out, method, True
    if attempts:
        out, method = max(attempts, key=lambda x: len(x[0]))
        return out, method, len(out) == expected
    return None, None, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--dz", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    root = args.root.resolve()
    data = args.dz.read_bytes()
    parser = load_parser(root)
    layout = parser.parse_layout(data)
    by_path = {e.path.lower(): e for e in layout.entries}

    report = {
        "schemaVersion": 1,
        "archiveBytes": len(data),
        "targets": [],
    }

    decoded_count = 0
    for target in TARGETS:
        e = by_path.get(target.lower())
        if not e:
            report["targets"].append({"path": target, "found": False})
            continue

        slot = data[e.offset:e.offset + e.slot_size]
        expected = int(e.usize2)
        decoded, method, exact = decode_entry(slot, expected)

        item = {
            "path": e.path,
            "found": True,
            "index": e.index,
            "offset": e.offset,
            "slotSize": e.slot_size,
            "metadataSize1": e.usize,
            "metadataSize2": e.usize2,
            "flags": e.flags,
            "slotHeadHex": slot[:32].hex(),
            "decoder": method,
            "decoded": decoded is not None,
            "decodedBytes": len(decoded) if decoded is not None else 0,
            "expectedDecodedBytes": expected,
            "exactExpectedSize": exact,
        }

        if decoded is not None:
            decoded_count += 1
            item["decodedHeadHex"] = decoded[:64].hex()
            item["printableStrings"] = printable_strings(decoded)

        report["targets"].append(item)

        print("GROUP", e.path)
        print("  slot", e.slot_size, "meta1", e.usize, "meta2", e.usize2, "flags", hex(e.flags))
        print("  head", slot[:32].hex())
        print("  decoder", method, "decoded", len(decoded) if decoded else 0, "exact", exact)
        if decoded:
            for s in item["printableStrings"][:25]:
                print("  str", repr(s))

    report["decodedCount"] = decoded_count
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("DECODED_COUNT", decoded_count)
    if decoded_count == 0:
        raise SystemExit("XZIEL_BOZ_GROUP_DECODE_FAILED")
    print("XZIEL_BOZ_GROUP_DECODE_OK")


if __name__ == "__main__":
    main()
