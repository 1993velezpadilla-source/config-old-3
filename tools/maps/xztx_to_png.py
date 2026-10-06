#!/usr/bin/env python3
"""Decode complete XZTX mip0 catalogs to Godot-readable PNG sidecars.

Supports the cooked formats observed in the validated Nacht UE4.21 package:
PF_DXT1 (BC1), PF_DXT5 (BC3), PF_BC5, PF_G8 and PF_B8G8R8A8.
The XZTX source payload remains authoritative; decoding only creates a portable
mip0 sidecar and never changes source dimensions, sRGB intent or asset identity.
"""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

HEADER_BYTES = 80
MIP_RECORD_BYTES = 24
SUPPORTED = {
    "PF_DXT1",
    "PF_DXT5",
    "PF_BC5",
    "PF_G8",
    "PF_B8G8R8A8",
}


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return (
        struct.pack(">I", len(payload))
        + body
        + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    )


def write_rgba_png(
    path: Path,
    width: int,
    height: int,
    rgba: bytes,
    srgb: bool,
) -> None:
    expected = width * height * 4
    if len(rgba) != expected:
        raise ValueError(
            f"{path}: RGBA payload mismatch {len(rgba)} != {expected}"
        )
    stride = width * 4
    raw = b"".join(
        b"\x00" + rgba[y * stride : (y + 1) * stride]
        for y in range(height)
    )
    chunks = [
        png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0),
        )
    ]
    if srgb:
        chunks.append(png_chunk(b"sRGB", b"\x00"))
    chunks.append(png_chunk(b"IDAT", zlib.compress(raw, 9)))
    chunks.append(png_chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"".join(chunks))


def parse_mip0(path: Path, expected: dict) -> tuple[str, bytes, int, int, bool]:
    data = path.read_bytes()
    if len(data) < HEADER_BYTES or data[:4] != b"XZTX":
        raise ValueError(f"{path}: invalid XZTX")

    version = u32(data, 4)
    width = u32(data, 8)
    height = u32(data, 12)
    depth = u32(data, 16)
    mip_count = u32(data, 20)
    flags = u32(data, 24)
    format_name_bytes = u32(data, 28)
    record_bytes = u32(data, 32)
    table_offset = u32(data, 36)
    payload_offset = u32(data, 40)
    payload_bytes = u32(data, 44)
    fmt = data[48 : 48 + format_name_bytes].decode("ascii")
    srgb = bool(flags & 1)

    if version != 1 or depth != 1 or mip_count <= 0:
        raise ValueError(
            f"{path}: unsupported version/depth/mips "
            f"{version}/{depth}/{mip_count}"
        )
    if record_bytes != MIP_RECORD_BYTES or table_offset != HEADER_BYTES:
        raise ValueError(f"{path}: unexpected XZTX table layout")
    if payload_offset != HEADER_BYTES + mip_count * MIP_RECORD_BYTES:
        raise ValueError(f"{path}: unexpected payload offset")
    if payload_offset + payload_bytes != len(data):
        raise ValueError(f"{path}: payload size mismatch")

    if int(expected.get("width", width)) != width:
        raise ValueError(f"{path}: width drift")
    if int(expected.get("height", height)) != height:
        raise ValueError(f"{path}: height drift")
    if int(expected.get("mipCount", mip_count)) != mip_count:
        raise ValueError(f"{path}: mip-count drift")
    if str(expected.get("format", fmt)) != fmt:
        raise ValueError(f"{path}: format drift {fmt}")
    if bool(expected.get("srgb", srgb)) != srgb:
        raise ValueError(f"{path}: sRGB drift")

    r = HEADER_BYTES
    mw = u32(data, r + 0)
    mh = u32(data, r + 4)
    md = u32(data, r + 8)
    mo = u32(data, r + 12)
    ms = u32(data, r + 16)
    source_mip = u32(data, r + 20)
    if (mw, mh, md, source_mip) != (width, height, 1, 0):
        raise ValueError(f"{path}: invalid mip0 record")
    if mo < payload_offset or mo + ms > len(data):
        raise ValueError(f"{path}: mip0 range invalid")

    return fmt, data[mo : mo + ms], width, height, srgb


def bgra_to_rgba(bgra: bytes, width: int, height: int) -> bytes:
    expected = width * height * 4
    if len(bgra) != expected:
        raise ValueError(
            f"decoded BGRA mismatch {len(bgra)} != {expected}"
        )
    out = bytearray(expected)
    for i in range(0, expected, 4):
        b, g, r, a = bgra[i : i + 4]
        out[i : i + 4] = bytes((r, g, b, a))
    return bytes(out)


def decode(fmt: str, payload: bytes, width: int, height: int) -> bytes:
    if fmt == "PF_B8G8R8A8":
        return bgra_to_rgba(payload, width, height)

    if fmt == "PF_G8":
        expected = width * height
        if len(payload) != expected:
            raise ValueError(
                f"G8 payload mismatch {len(payload)} != {expected}"
            )
        out = bytearray(expected * 4)
        for i, value in enumerate(payload):
            o = i * 4
            out[o : o + 4] = bytes((value, value, value, 255))
        return bytes(out)

    try:
        import texture2ddecoder  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "texture2ddecoder is required for BC/DXT XZTX decoding"
        ) from exc

    if fmt == "PF_DXT1":
        decoded = texture2ddecoder.decode_bc1(payload, width, height)
    elif fmt == "PF_DXT5":
        decoded = texture2ddecoder.decode_bc3(payload, width, height)
    elif fmt == "PF_BC5":
        decoded = texture2ddecoder.decode_bc5(payload, width, height)
    else:
        raise ValueError(f"unsupported XZTX format {fmt}")

    return bgra_to_rgba(decoded, width, height)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("output_dir", type=Path)
    ap.add_argument(
        "--report",
        type=Path,
        help="UETextureXZTX report.json; defaults to input_dir/report.json",
    )
    ap.add_argument("--decode-report", type=Path)
    args = ap.parse_args()

    report_path = args.report or (args.input_dir / "report.json")
    source = json.loads(report_path.read_text(encoding="utf-8"))
    rows = source.get("textures", [])
    expected_count = int(source.get("convertedTextures", len(rows)))
    if not rows or len(rows) != expected_count:
        raise ValueError(
            f"texture report count mismatch {len(rows)} != {expected_count}"
        )

    formats = {}
    output_rows = []
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for stale in args.output_dir.glob("*.png"):
        stale.unlink()

    for row in rows:
        runtime_file = str(row.get("file", ""))
        if not runtime_file:
            raise ValueError("texture row missing XZTX file")
        src = args.input_dir / runtime_file
        if not src.is_file():
            raise FileNotFoundError(src)

        fmt, payload, width, height, srgb = parse_mip0(src, row)
        if fmt not in SUPPORTED:
            raise ValueError(f"{src}: unsupported source format {fmt}")

        rgba = decode(fmt, payload, width, height)
        dst = args.output_dir / (Path(runtime_file).stem + ".png")
        write_rgba_png(dst, width, height, rgba, srgb)
        formats[fmt] = formats.get(fmt, 0) + 1
        output_rows.append(
            {
                "sourceFile": runtime_file,
                "outputFile": dst.name,
                "objectPath": row.get("objectPath"),
                "format": fmt,
                "width": width,
                "height": height,
                "srgb": srgb,
                "bytes": dst.stat().st_size,
            }
        )

    outputs = list(args.output_dir.glob("*.png"))
    if len(outputs) != expected_count:
        raise RuntimeError(
            f"PNG count mismatch {len(outputs)} != {expected_count}"
        )

    result = {
        "schemaVersion": 1,
        "sourceFormat": "XZTX",
        "textureCount": expected_count,
        "formatCounts": dict(sorted(formats.items())),
        "textures": output_rows,
        "ready": True,
    }
    if args.decode_report:
        args.decode_report.parent.mkdir(parents=True, exist_ok=True)
        args.decode_report.write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        "XZOGOT_XZTX_PNG_COMPLETE_GREEN",
        f"textures={expected_count}",
        "formats=" + json.dumps(result["formatCounts"], sort_keys=True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
