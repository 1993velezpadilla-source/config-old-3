#!/usr/bin/env python3
"""Read-only probe for GTA CTW mobile game.pak.

Layout is based on DK22Pac's CTW-Mobile-Explorer research. The probe is
intentionally conservative: it validates bounds before interpreting the
resource table and never writes to the package.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

HEADER = struct.Struct("<6I")
FIRST_TABLE_ENTRIES = 2036
BLOCK = 4096

def physical_offset(resource_id: int, packed: int, ranges: tuple[int, int, int]) -> int:
    offset = packed * BLOCK
    if resource_id >= ranges[0]:
        if resource_id >= ranges[1]:
            if resource_id >= ranges[2]:
                offset += 0x30000000
            else:
                offset += 0x20000000
        else:
            offset += 0x10000000
    return offset

def read_u16s(f, count: int) -> list[int]:
    if count <= 0:
        return []
    data = f.read(count * 2)
    if len(data) != count * 2:
        raise ValueError(f"short resource table: wanted {count*2} bytes, got {len(data)}")
    return list(struct.unpack(f"<{count}H", data))

def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("usage: ctw_pak_probe.py <game.pak> [manifest.json]")
        return 2

    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.is_file():
        print(f"PAK_RED: not found: {path}")
        return 2

    size = path.stat().st_size
    with path.open("rb") as f:
        raw = f.read(HEADER.size)
        if len(raw) != HEADER.size:
            print("PAK_RED: file too small for CTW header")
            return 1

        version, r0, r1, r2, resource_count, resource_blocks = HEADER.unpack(raw)
        ranges = (r0, r1, r2)

        if resource_count == 0 or resource_count > 1_000_000:
            print(f"PAK_RED: implausible resource_count={resource_count}")
            return 1
        if resource_blocks == 0:
            print("PAK_RED: resource_blocks_count is zero")
            return 1

        first_count = min(resource_count, FIRST_TABLE_ENTRIES)
        offsets = read_u16s(f, first_count)

        remaining = resource_count - first_count
        second_table_offset = resource_blocks * BLOCK
        if remaining:
            if second_table_offset >= size:
                print(f"PAK_RED: secondary table offset 0x{second_table_offset:X} beyond EOF")
                return 1
            f.seek(second_table_offset)
            offsets.extend(read_u16s(f, remaining))

    resolved = [physical_offset(i, offsets[i], ranges) for i in range(resource_count)]
    bad = []
    for i, off in enumerate(resolved):
        if off < 0 or off >= size:
            bad.append((i, off))
        if i + 1 < len(resolved) and resolved[i + 1] < off:
            bad.append((i, off))

    info = {
        "file": path.name,
        "file_size": size,
        "version_signature": f"0x{version:08X}",
        "ranges": list(ranges),
        "resource_count": resource_count,
        "resource_blocks_count": resource_blocks,
        "secondary_table_offset": second_table_offset,
        "first_resource_offset": resolved[0] if resolved else None,
        "last_resource_offset": resolved[-1] if resolved else None,
        "validation_errors": [{"resource": i, "offset": off} for i, off in bad[:32]],
    }

    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_text(json.dumps(info, indent=2), encoding="utf-8")

    if bad:
        print(f"PAK_RED: {len(bad)} resource-table validation error(s)")
        for i, off in bad[:8]:
            print(f"resource={i} offset=0x{off:X}")
        return 1

    print(
        "PAK_GREEN "
        f"resources={resource_count} blocks={resource_blocks} "
        f"ranges={r0},{r1},{r2} size={size}"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
