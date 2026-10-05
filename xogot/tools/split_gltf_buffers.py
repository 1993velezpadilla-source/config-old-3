#!/usr/bin/env python3
"""Split one external glTF binary buffer into multiple Git-safe buffers.

No mesh, accessor, animation, skin, image, or numeric payload is modified.
Only bufferView locations are repacked with 4-byte alignment.
"""

import argparse
import json
from pathlib import Path


def align4(value: int) -> int:
    return (value + 3) & ~3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("gltf", type=Path)
    ap.add_argument("--max-bytes", type=int, default=85_000_000)
    args = ap.parse_args()

    gltf_path = args.gltf.resolve()
    root = gltf_path.parent
    doc = json.loads(gltf_path.read_text(encoding="utf-8"))
    buffers = doc.get("buffers", [])
    views = doc.get("bufferViews", [])
    if len(buffers) != 1:
        raise SystemExit(f"expected exactly one source buffer, got {len(buffers)}")
    uri = buffers[0].get("uri")
    if not uri or uri.startswith("data:"):
        raise SystemExit("source buffer must be an external .bin URI")
    src_path = root / uri
    src = src_path.read_bytes()
    if len(src) < int(buffers[0].get("byteLength", 0)):
        raise SystemExit("source buffer shorter than declared byteLength")

    indexed = []
    for i, view in enumerate(views):
        if int(view.get("buffer", 0)) != 0:
            raise SystemExit(f"bufferView {i} does not reference source buffer 0")
        off = int(view.get("byteOffset", 0))
        length = int(view["byteLength"])
        if off < 0 or length < 0 or off + length > len(src):
            raise SystemExit(f"bufferView {i} range invalid")
        if length > args.max_bytes:
            raise SystemExit(
                f"bufferView {i} alone is {length} bytes > max {args.max_bytes}; "
                "cannot split without changing accessor layout"
            )
        indexed.append((i, off, length))

    # Preserve original byte order for deterministic output and cache-friendly
    # grouping. Each complete bufferView moves as an opaque byte span.
    indexed.sort(key=lambda x: (x[1], x[0]))
    groups = []
    current = []
    current_size = 0
    for entry in indexed:
        _, _, length = entry
        aligned = align4(current_size)
        projected = aligned + length
        if current and projected > args.max_bytes:
            groups.append(current)
            current = []
            current_size = 0
            aligned = 0
            projected = length
        current.append(entry)
        current_size = projected
    if current:
        groups.append(current)

    stem = gltf_path.stem
    new_buffers = []
    written = []
    for group_index, group in enumerate(groups):
        blob = bytearray()
        for view_index, old_off, length in group:
            pad = align4(len(blob)) - len(blob)
            if pad:
                blob.extend(b"\x00" * pad)
            new_off = len(blob)
            blob.extend(src[old_off:old_off + length])
            views[view_index]["buffer"] = group_index
            if new_off:
                views[view_index]["byteOffset"] = new_off
            else:
                views[view_index].pop("byteOffset", None)
        out_name = f"{stem}_buffer_{group_index:02d}.bin"
        out_path = root / out_name
        out_path.write_bytes(blob)
        new_buffers.append({"uri": out_name, "byteLength": len(blob)})
        written.append((out_name, len(blob)))

    doc["buffers"] = new_buffers
    gltf_path.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")

    # Delete the original source buffer only after the rewritten glTF and all
    # replacement buffers exist.
    replacement_names = {name for name, _ in written}
    if src_path.name not in replacement_names and src_path.exists():
        src_path.unlink()

    for name, size in written:
        if size > args.max_bytes:
            raise SystemExit(f"split output exceeds max: {name} {size}")
    print("XZOGOT_GLTF_BUFFER_SPLIT_GREEN", gltf_path.name, written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
