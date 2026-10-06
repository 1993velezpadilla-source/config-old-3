#!/usr/bin/env python3
"""Bridge XZIEL XZTX v1 textures to DDS without re-encoding source pixels.

Supported Nacht/UE4.21 cooked formats:
  PF_DXT1      -> DDS DXT1 / BC1 payload preserved
  PF_DXT5      -> DDS DXT5 / BC3 payload preserved
  PF_BC5       -> DDS ATI2 / BC5 payload preserved
  PF_B8G8R8A8  -> DDS BGRA8 payload preserved
  PF_G8        -> DDS L8 payload preserved

The XZTX source sRGB flag is preserved in the emitted JSON report. Legacy DDS
headers do not encode sRGB for DXT1/DXT5, so the Godot material binder remains
the authority for color-space intent.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

XZTX_MAGIC = b"XZTX"
XZTX_VERSION = 1
XZTX_HEADER_BYTES = 80
XZTX_MIP_RECORD_BYTES = 24
XZTX_FORMAT_BYTES = 32

DDS_MAGIC = b"DDS "
DDS_HEADER_SIZE = 124
DDS_PIXEL_FORMAT_SIZE = 32

DDSD_CAPS = 0x00000001
DDSD_HEIGHT = 0x00000002
DDSD_WIDTH = 0x00000004
DDSD_PITCH = 0x00000008
DDSD_PIXELFORMAT = 0x00001000
DDSD_MIPMAPCOUNT = 0x00020000
DDSD_LINEARSIZE = 0x00080000

DDSCAPS_COMPLEX = 0x00000008
DDSCAPS_TEXTURE = 0x00001000
DDSCAPS_MIPMAP = 0x00400000

DDPF_ALPHAPIXELS = 0x00000001
DDPF_FOURCC = 0x00000004
DDPF_RGB = 0x00000040
DDPF_LUMINANCE = 0x00020000

FLAG_SRGB = 1 << 0

SUPPORTED = {
    "PF_DXT1": {"kind": "fourcc", "fourcc": b"DXT1", "block_bytes": 8},
    "PF_DXT5": {"kind": "fourcc", "fourcc": b"DXT5", "block_bytes": 16},
    "PF_BC5": {"kind": "fourcc", "fourcc": b"ATI2", "block_bytes": 16},
    "PF_B8G8R8A8": {"kind": "bgra8", "bytes_per_pixel": 4},
    "PF_G8": {"kind": "g8", "bytes_per_pixel": 1},
}


def fourcc(value: bytes) -> int:
    if len(value) != 4:
        raise ValueError(value)
    return struct.unpack("<I", value)[0]


def parse_xztx(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < XZTX_HEADER_BYTES or data[:4] != XZTX_MAGIC:
        raise ValueError(f"{path}: invalid XZTX header")

    (
        version,
        width,
        height,
        depth,
        mip_count,
        flags,
        format_len,
        mip_record_bytes,
        header_bytes,
        payload_offset,
        payload_bytes,
    ) = struct.unpack_from("<11I", data, 4)

    if version != XZTX_VERSION:
        raise ValueError(f"{path}: unsupported XZTX version {version}")
    if header_bytes != XZTX_HEADER_BYTES:
        raise ValueError(f"{path}: header bytes {header_bytes}")
    if mip_record_bytes != XZTX_MIP_RECORD_BYTES:
        raise ValueError(f"{path}: mip record bytes {mip_record_bytes}")
    if not width or not height or depth != 1 or not mip_count:
        raise ValueError(f"{path}: invalid dimensions/mips")
    if format_len <= 0 or format_len >= XZTX_FORMAT_BYTES:
        raise ValueError(f"{path}: invalid format length")

    fmt = data[48:48 + format_len].decode("ascii")
    if fmt not in SUPPORTED:
        raise ValueError(f"{path}: unsupported format {fmt}")

    expected_payload_offset = XZTX_HEADER_BYTES + mip_count * XZTX_MIP_RECORD_BYTES
    if payload_offset != expected_payload_offset:
        raise ValueError(
            f"{path}: payload offset {payload_offset} != {expected_payload_offset}"
        )
    if payload_offset + payload_bytes != len(data):
        raise ValueError(f"{path}: payload size mismatch")

    mips = []
    next_offset = payload_offset
    for i in range(mip_count):
        off = XZTX_HEADER_BYTES + i * XZTX_MIP_RECORD_BYTES
        mw, mh, md, poff, plen, source_index = struct.unpack_from("<6I", data, off)
        if md != 1 or mw <= 0 or mh <= 0 or plen <= 0:
            raise ValueError(f"{path}: invalid mip {i}")
        if poff != next_offset or poff + plen > len(data):
            raise ValueError(f"{path}: invalid mip payload {i}")
        payload = data[poff:poff + plen]
        validate_mip_payload(fmt, mw, mh, payload, path, i)
        mips.append(
            {
                "width": mw,
                "height": mh,
                "depth": md,
                "source_index": source_index,
                "payload": payload,
            }
        )
        next_offset += plen

    if next_offset != len(data):
        raise ValueError(f"{path}: trailing/unaccounted payload")

    return {
        "width": width,
        "height": height,
        "depth": depth,
        "mip_count": mip_count,
        "srgb": bool(flags & FLAG_SRGB),
        "format": fmt,
        "mips": mips,
    }


def validate_mip_payload(
    fmt: str, width: int, height: int, payload: bytes, path: Path, mip: int
) -> None:
    info = SUPPORTED[fmt]
    if info["kind"] == "fourcc":
        blocks_x = max(1, (width + 3) // 4)
        blocks_y = max(1, (height + 3) // 4)
        expected = blocks_x * blocks_y * int(info["block_bytes"])
    else:
        expected = width * height * int(info["bytes_per_pixel"])

    if len(payload) != expected:
        raise ValueError(
            f"{path}: mip {mip} {fmt} bytes {len(payload)} != {expected}"
        )


def make_dds_header(tex: dict) -> bytes:
    width = int(tex["width"])
    height = int(tex["height"])
    mip_count = int(tex["mip_count"])
    fmt = str(tex["format"])
    first_bytes = len(tex["mips"][0]["payload"])
    info = SUPPORTED[fmt]

    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
    if info["kind"] == "fourcc":
        flags |= DDSD_LINEARSIZE
        pitch_or_linear = first_bytes
    else:
        flags |= DDSD_PITCH
        pitch_or_linear = width * int(info["bytes_per_pixel"])
    if mip_count > 1:
        flags |= DDSD_MIPMAPCOUNT

    caps = DDSCAPS_TEXTURE
    if mip_count > 1:
        caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP

    if info["kind"] == "fourcc":
        pf = struct.pack(
            "<8I",
            DDS_PIXEL_FORMAT_SIZE,
            DDPF_FOURCC,
            fourcc(info["fourcc"]),
            0, 0, 0, 0, 0,
        )
    elif info["kind"] == "bgra8":
        pf = struct.pack(
            "<8I",
            DDS_PIXEL_FORMAT_SIZE,
            DDPF_RGB | DDPF_ALPHAPIXELS,
            0,
            32,
            0x00FF0000,
            0x0000FF00,
            0x000000FF,
            0xFF000000,
        )
    elif info["kind"] == "g8":
        pf = struct.pack(
            "<8I",
            DDS_PIXEL_FORMAT_SIZE,
            DDPF_LUMINANCE,
            0,
            8,
            0x000000FF,
            0,
            0,
            0,
        )
    else:
        raise ValueError(fmt)

    fixed = struct.pack(
        "<7I",
        DDS_HEADER_SIZE,
        flags,
        height,
        width,
        pitch_or_linear,
        0,
        mip_count,
    )
    reserved = struct.pack("<11I", *([0] * 11))
    caps_tail = struct.pack("<5I", caps, 0, 0, 0, 0)
    header = fixed + reserved + pf + caps_tail
    if len(header) != DDS_HEADER_SIZE:
        raise AssertionError(len(header))
    return DDS_MAGIC + header


def convert(src: Path, dst: Path) -> dict:
    tex = parse_xztx(src)
    payload = b"".join(row["payload"] for row in tex["mips"])
    out = make_dds_header(tex) + payload
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    return {
        "source": src.name,
        "output": dst.name,
        "format": tex["format"],
        "srgb": tex["srgb"],
        "width": tex["width"],
        "height": tex["height"],
        "mip_count": tex["mip_count"],
        "source_payload_bytes": len(payload),
        "dds_bytes": len(out),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    rows = []
    failures = []
    for src in sorted(args.input_dir.glob("*.xzt")):
        try:
            rows.append(convert(src, args.output_dir / f"{src.stem}.dds"))
        except Exception as exc:
            failures.append({"source": src.name, "error": f"{type(exc).__name__}: {exc}"})

    report = {
        "schema": 1,
        "format": "xztx_to_dds_v1",
        "texture_count": len(rows),
        "failure_count": len(failures),
        "format_counts": {},
        "srgb_count": sum(1 for row in rows if row["srgb"]),
        "textures": rows,
        "failures": failures,
        "ready": bool(rows) and not failures,
    }
    for row in rows:
        fmt = row["format"]
        report["format_counts"][fmt] = report["format_counts"].get(fmt, 0) + 1

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(
        "XZOGOT_XZTX_DDS",
        f"textures={report['texture_count']}",
        f"formats={report['format_counts']}",
        f"srgb={report['srgb_count']}",
        f"failures={report['failure_count']}",
    )
    if failures:
        for row in failures[:30]:
            print("XZOGOT_XZTX_DDS_FAILURE", row)
        return 5
    if not rows:
        print("XZOGOT_XZTX_DDS_FAILURE no textures")
        return 5
    print("XZOGOT_XZTX_DDS_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
