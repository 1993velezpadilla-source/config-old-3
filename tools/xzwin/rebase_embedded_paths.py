#!/usr/bin/env python3
"""Rebase embedded NUL-terminated absolute paths without growing binaries.

This is for the experimental XZWin Wine build imported from Winlator.  Some
Wine unix-side binaries contain /data/data/com.winlator/files/rootfs as a
compile-time prefix.  XZIEL replaces that prefix with a shorter private alias
and pads the remaining bytes with NUL so offsets and file sizes are unchanged.
"""
from __future__ import annotations

import argparse
import pathlib


def patch_file(path: pathlib.Path, old: bytes, new: bytes) -> tuple[int, list[str]]:
    data = bytearray(path.read_bytes())
    changed = 0
    examples: list[str] = []
    search_from = 0
    seen_spans: set[tuple[int, int]] = set()

    while True:
        hit = data.find(old, search_from)
        if hit < 0:
            break

        start = data.rfind(b"\0", 0, hit) + 1
        end = data.find(b"\0", hit)
        if end < 0:
            raise RuntimeError(
                f"{path}: old prefix occurs outside a NUL-terminated string"
            )

        span = (start, end)
        search_from = end + 1
        if span in seen_spans:
            continue
        seen_spans.add(span)

        original = bytes(data[start:end])
        if old not in original:
            continue

        rewritten = original.replace(old, new)
        if len(rewritten) > len(original):
            raise RuntimeError(
                f"{path}: replacement grows embedded string "
                f"({len(rewritten)} > {len(original)})"
            )

        padded = rewritten + (b"\0" * (len(original) - len(rewritten)))
        data[start:end] = padded
        changed += original.count(old)
        if len(examples) < 20:
            examples.append(
                original.decode("utf-8", "replace")
                + " -> "
                + rewritten.decode("utf-8", "replace")
            )

    if changed:
        path.write_bytes(data)
    return changed, examples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=pathlib.Path)
    parser.add_argument("old_prefix")
    parser.add_argument("new_prefix")
    args = parser.parse_args()

    old = args.old_prefix.encode()
    new = args.new_prefix.encode()
    if len(new) > len(old):
        raise SystemExit(
            f"new prefix must not be longer than old: {len(new)} > {len(old)}"
        )

    total = 0
    files = 0
    all_examples: list[str] = []
    for path in sorted(args.root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        if old not in blob:
            continue
        changed, examples = patch_file(path, old, new)
        if changed:
            files += 1
            total += changed
            print(f"PATCHED {path}: {changed}")
            all_examples.extend(examples)

    print(f"XZWIN_REBASE files={files} occurrences={total}")
    for value in all_examples[:50]:
        print(f"  {value}")

    leftovers = []
    for path in sorted(args.root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if old in path.read_bytes():
                leftovers.append(str(path))
        except OSError:
            pass

    if leftovers:
        print("UNPATCHED:")
        for value in leftovers:
            print(value)
        return 2

    if total == 0:
        print("No matching embedded paths found.")
        return 3

    print("XZWIN_REBASE_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
