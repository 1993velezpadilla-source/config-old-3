#!/usr/bin/env python3
from __future__ import annotations

import argparse
import lzma
import struct
from dataclasses import dataclass
from pathlib import Path


class DTRZError(RuntimeError):
    pass


@dataclass
class Entry:
    index: int
    path: str
    offset: int
    slot_size: int
    usize: int
    usize2: int
    flags: int
    meta_pos: int


@dataclass
class Layout:
    file_count: int
    version: int
    names: list[str]
    directories: list[str]
    entries: list[Entry]
    ref_pos: int
    meta_pos: int


def read_c_string(data: bytes, pos: int) -> tuple[str, int]:
    try:
        end = data.index(b"\0", pos)
    except ValueError as exc:
        raise DTRZError(f"unterminated string at 0x{pos:x}") from exc
    raw = data[pos:end]
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError:
        value = raw.decode("latin1")
    return value, end + 1


def join_path(directory: str, name: str) -> str:
    directory = directory.replace("\\", "/").strip("/")
    name = name.replace("\\", "/").strip("/")
    return f"{directory}/{name}" if directory else name


def _refs_plausible(data: bytes, ref_pos: int, file_count: int, directory_count: int) -> bool:
    end = ref_pos + file_count * 6
    if end + 4 + file_count * 16 > len(data):
        return False
    for i in range(file_count):
        d_raw, name_index, parent_index = struct.unpack_from("<HHH", data, ref_pos + i * 6)
        if d_raw > directory_count:
            return False
        if name_index >= file_count:
            return False
        if parent_index != 0xFFFF and parent_index >= file_count:
            return False
    marker_a, marker_b = struct.unpack_from("<HH", data, end)
    if marker_b != file_count:
        return False

    meta_pos = end + 4
    offsets = [struct.unpack_from("<I", data, meta_pos + i * 16)[0] for i in range(file_count)]
    if offsets != sorted(offsets):
        return False
    if not offsets or offsets[0] < meta_pos + file_count * 16:
        return False
    if any(off <= 0 or off >= len(data) for off in offsets):
        return False
    return True


def parse_layout(data: bytes) -> Layout:
    if len(data) < 9 or data[:4] != b"DTRZ":
        raise DTRZError("not a DTRZ archive")

    file_count = struct.unpack_from("<H", data, 4)[0]
    version = struct.unpack_from("<H", data, 6)[0]
    if file_count <= 0:
        raise DTRZError("archive has no files")

    pos = 9
    names: list[str] = []
    for _ in range(file_count):
        name, pos = read_c_string(data, pos)
        names.append(name)

    directories: list[str] = []
    while True:
        if pos >= len(data):
            raise DTRZError("could not locate DTRZ reference table")
        directory, next_pos = read_c_string(data, pos)
        candidate_dirs = directories + [directory]
        if _refs_plausible(data, next_pos, file_count, len(candidate_dirs)):
            directories = candidate_dirs
            ref_pos = next_pos
            break
        directories = candidate_dirs
        pos = next_pos

    meta_header_pos = ref_pos + file_count * 6
    _marker_a, marker_b = struct.unpack_from("<HH", data, meta_header_pos)
    if marker_b != file_count:
        raise DTRZError("metadata count mismatch")
    meta_pos = meta_header_pos + 4

    raw_meta = [
        struct.unpack_from("<IIII", data, meta_pos + i * 16)
        for i in range(file_count)
    ]
    offsets = [m[0] for m in raw_meta]

    entries: list[Entry] = []
    for i, (off, usize, usize2, flags) in enumerate(raw_meta):
        d_raw, name_index, _parent_index = struct.unpack_from("<HHH", data, ref_pos + i * 6)
        directory = directories[d_raw - 1] if d_raw else ""
        path = join_path(directory, names[name_index])
        next_off = offsets[i + 1] if i + 1 < file_count else len(data)
        slot_size = next_off - off
        if slot_size <= 0:
            raise DTRZError(f"invalid payload slot for {path}")
        entries.append(
            Entry(
                index=i,
                path=path,
                offset=off,
                slot_size=slot_size,
                usize=usize,
                usize2=usize2,
                flags=flags,
                meta_pos=meta_pos + i * 16,
            )
        )

    return Layout(
        file_count=file_count,
        version=version,
        names=names,
        directories=directories,
        entries=entries,
        ref_pos=ref_pos,
        meta_pos=meta_pos,
    )


def compress_payload(payload: bytes) -> bytes:
    filters = [{
        "id": lzma.FILTER_LZMA1,
        "dict_size": 1 << 23,
        "lc": 3,
        "lp": 0,
        "pb": 2,
    }]
    return lzma.compress(payload, format=lzma.FORMAT_ALONE, filters=filters)


def decode_slot(slot: bytes, expected_size: int) -> bytes:
    dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    out = dec.decompress(slot)
    if len(out) != expected_size:
        raise DTRZError(f"verification size mismatch: got {len(out)}, expected {expected_size}")
    return out


def replace_inplace(data: bytes, entry_path: str, replacement: bytes) -> tuple[bytes, Entry, int]:
    layout = parse_layout(data)
    normalized = entry_path.replace("\\", "/").strip("/").lower()
    matches = [e for e in layout.entries if e.path.lower() == normalized]
    if not matches:
        available = "\n".join(e.path for e in layout.entries[:50])
        raise DTRZError(f"entry not found: {entry_path}\nfirst entries:\n{available}")
    if len(matches) != 1:
        raise DTRZError(f"ambiguous entry path: {entry_path}")

    entry = matches[0]
    compressed = compress_payload(replacement)
    if len(compressed) > entry.slot_size:
        raise DTRZError(
            f"REPLACEMENT_TOO_LARGE_FOR_INPLACE_SLOT: compressed={len(compressed)} "
            f"slot={entry.slot_size} entry={entry.path}"
        )

    out = bytearray(data)
    start = entry.offset
    end = start + entry.slot_size
    out[start:end] = compressed + bytes(entry.slot_size - len(compressed))

    struct.pack_into(
        "<IIII",
        out,
        entry.meta_pos,
        entry.offset,
        len(replacement),
        len(replacement),
        entry.flags,
    )

    verify = decode_slot(bytes(out[start:end]), len(replacement))
    if verify != replacement:
        raise DTRZError("replacement verification mismatch")

    return bytes(out), entry, len(compressed)


def main() -> int:
    p = argparse.ArgumentParser(description="Replace one Marmalade DTRZ entry without shifting offsets.")
    p.add_argument("-i", "--input", required=True, type=Path)
    p.add_argument("-o", "--output", required=True, type=Path)
    p.add_argument("-e", "--entry", required=True)
    p.add_argument("-r", "--replacement", required=True, type=Path)
    p.add_argument("--list", action="store_true")
    args = p.parse_args()

    data = args.input.read_bytes()
    layout = parse_layout(data)

    if args.list:
        for entry in layout.entries:
            print(
                f"{entry.path}\toffset=0x{entry.offset:x}\tslot={entry.slot_size}"
                f"\tusize={entry.usize}\tflags=0x{entry.flags:x}"
            )

    replacement = args.replacement.read_bytes()
    patched, entry, compressed_size = replace_inplace(data, args.entry, replacement)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patched)

    print("XZIEL_DTRZ_INPLACE_REPLACE_OK")
    print(f"entry={entry.path}")
    print(f"slot_size={entry.slot_size}")
    print(f"compressed_size={compressed_size}")
    print(f"replacement_size={len(replacement)}")
    print(f"offset=0x{entry.offset:x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
