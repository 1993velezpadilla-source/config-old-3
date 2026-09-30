#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    args = ap.parse_args()

    old = args.old.encode("latin1")
    new = args.new.encode("latin1")
    if len(old) != len(new):
        raise SystemExit(f"name lengths differ: {len(old)} != {len(new)}")

    data = bytearray(args.input.read_bytes())
    if data[:4] != b"DTRZ":
        raise SystemExit("not a DTRZ archive")

    oldz = old + b"\0"
    newz = new + b"\0"

    # DTRZ file/directory names are stored in the metadata prefix before
    # payload chunks. Restrict the replacement to the first 4 MiB to avoid
    # accidentally touching compressed payload bytes.
    prefix_end = min(len(data), 4 * 1024 * 1024)
    prefix = bytes(data[:prefix_end])
    hits = []
    pos = 0
    while True:
        pos = prefix.find(oldz, pos)
        if pos < 0:
            break
        hits.append(pos)
        pos += 1

    if len(hits) != 1:
        raise SystemExit(f"expected exactly one metadata name hit, found {len(hits)}")

    off = hits[0]
    data[off:off + len(oldz)] = newz
    if oldz in bytes(data[:prefix_end]):
        raise SystemExit("old name still present in metadata prefix")
    if bytes(data[:prefix_end]).count(newz) != 1:
        raise SystemExit("new name missing or duplicated")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)

    print("XZIEL_BOZ_DTRZ_ENTRY_RENAME_OK")
    print("OLD", args.old)
    print("NEW", args.new)
    print("OFFSET", hex(off))
    print("ARCHIVE_BYTES", len(data))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
