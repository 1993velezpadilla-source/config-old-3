#!/usr/bin/env python3
"""Decode the complete Nuketown XZTX mip0 catalog to PNG sidecars.

PF_ASTC_6x6 is decoded losslessly from the recovered compressed source payload
through Arm astcenc. PF_B8G8R8A8 is converted directly from the recovered BGRA
bytes to RGBA PNG with no resampling. The complete source catalog therefore
remains available to Godot instead of silently dropping non-ASTC textures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

XZTX_HEADER_BYTES = 80
XZTX_MIP_RECORD_BYTES = 24
ASTC_MAGIC = bytes((0x13, 0xAB, 0xA1, 0x5C))
BLOCK_X = 6
BLOCK_Y = 6
BLOCK_Z = 1
BLOCK_BYTES = 16
DEFAULT_MAP_REL = Path("vfs/xziel/maps/xziel_nuketown_zombies")


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def u24le(value: int) -> bytes:
    if value < 0 or value > 0xFFFFFF:
        raise ValueError(f"ASTC dimension out of range: {value}")
    return bytes((value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF))


def mip_bytes(width: int, height: int) -> int:
    return math.ceil(width / BLOCK_X) * math.ceil(height / BLOCK_Y) * BLOCK_BYTES


def chain_bytes(width: int, height: int, mip_count: int) -> int:
    return sum(
        mip_bytes(max(1, width >> level), max(1, height >> level))
        for level in range(mip_count)
    )

def png_chunk(kind: bytes, payload: bytes) -> bytes:
    import zlib

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
    import zlib

    expected = width * height * 4
    if len(rgba) != expected:
        raise ValueError(
            f"{path}: RGBA payload mismatch {len(rgba)} != {expected}"
        )

    stride = width * 4
    scanlines = b"".join(
        b"\x00" + rgba[row * stride : (row + 1) * stride]
        for row in range(height)
    )
    chunks = [
        png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0),
        )
    ]
    if srgb:
        chunks.append(png_chunk(b"sRGB", b"\x00"))
    chunks.append(png_chunk(b"IDAT", zlib.compress(scanlines, 9)))
    chunks.append(png_chunk(b"IEND", b""))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"".join(chunks)
    )


def parse_xztx_mip0(
    path: Path,
    expected: dict,
) -> tuple[str, bytes, int, int]:
    data = path.read_bytes()
    if len(data) < XZTX_HEADER_BYTES or data[:4] != b"XZTX":
        raise ValueError(f"{path}: invalid XZTX magic/header")

    version = u32(data, 4)
    width = u32(data, 8)
    height = u32(data, 12)
    depth = u32(data, 16)
    mip_count = u32(data, 20)
    format_name_bytes = u32(data, 28)
    mip_record_bytes = u32(data, 32)
    mip_table_offset = u32(data, 36)
    payload_offset = u32(data, 40)
    payload_bytes = u32(data, 44)
    format_name = data[48 : 48 + format_name_bytes].decode("ascii")

    if version != 1 or depth != 1:
        raise ValueError(
            f"{path}: unsupported XZTX version/depth {version}/{depth}"
        )
    if mip_count <= 0:
        raise ValueError(f"{path}: no mips")
    if (
        mip_record_bytes != XZTX_MIP_RECORD_BYTES
        or mip_table_offset != XZTX_HEADER_BYTES
    ):
        raise ValueError(f"{path}: unexpected mip table layout")
    if payload_offset != XZTX_HEADER_BYTES + mip_count * XZTX_MIP_RECORD_BYTES:
        raise ValueError(f"{path}: unexpected payload offset {payload_offset}")
    if payload_offset + payload_bytes != len(data):
        raise ValueError(f"{path}: payload size mismatch")

    if int(expected.get("width", width)) != width:
        raise ValueError(f"{path}: report width mismatch")
    if int(expected.get("height", height)) != height:
        raise ValueError(f"{path}: report height mismatch")
    if int(expected.get("mipCount", mip_count)) != mip_count:
        raise ValueError(f"{path}: report mip count mismatch")
    if str(expected.get("format", format_name)) != format_name:
        raise ValueError(f"{path}: report format mismatch")

    record = XZTX_HEADER_BYTES
    mip_width = u32(data, record + 0)
    mip_height = u32(data, record + 4)
    mip_depth = u32(data, record + 8)
    mip_offset = u32(data, record + 12)
    mip_size = u32(data, record + 16)
    source_mip = u32(data, record + 20)
    if (
        mip_width != width
        or mip_height != height
        or mip_depth != 1
        or source_mip != 0
    ):
        raise ValueError(f"{path}: invalid mip0 record")
    if mip_offset < payload_offset or mip_offset + mip_size > len(data):
        raise ValueError(f"{path}: mip0 range invalid")

    payload = data[mip_offset : mip_offset + mip_size]
    return format_name, payload, width, height


def bgra8_to_rgba(payload: bytes, width: int, height: int) -> bytes:
    expected = width * height * 4
    if len(payload) != expected:
        raise ValueError(
            f"BGRA8 mip0 bytes mismatch {len(payload)} != {expected}"
        )
    out = bytearray(expected)
    for offset in range(0, expected, 4):
        b, g, r, a = payload[offset : offset + 4]
        out[offset : offset + 4] = bytes((r, g, b, a))
    return bytes(out)



def parse_xztx(path: Path, expected: dict) -> tuple[bytes, int, int]:
    format_name, base_payload, width, height = parse_xztx_mip0(
        path, expected
    )
    if format_name != "PF_ASTC_6x6":
        raise ValueError(
            f"{path}: expected PF_ASTC_6x6, got {format_name}"
        )
    expected_base = mip_bytes(width, height)
    if len(base_payload) != expected_base:
        raise ValueError(
            f"{path}: ASTC mip0 bytes mismatch "
            f"{len(base_payload)} != {expected_base}"
        )

    # The complete ASTC chain remains validated against the source report.
    data = path.read_bytes()
    mip_count = u32(data, 20)
    payload_bytes = u32(data, 44)
    expected_chain = chain_bytes(width, height, mip_count)
    if payload_bytes != expected_chain:
        raise ValueError(
            f"{path}: ASTC mip-chain bytes mismatch "
            f"{payload_bytes} != {expected_chain}"
        )
    return base_payload, width, height

def astc_file(payload: bytes, width: int, height: int) -> bytes:
    header = (
        ASTC_MAGIC
        + bytes((BLOCK_X, BLOCK_Y, BLOCK_Z))
        + u24le(width)
        + u24le(height)
        + u24le(1)
    )
    if len(header) != 16:
        raise AssertionError("ASTC header must be 16 bytes")
    return header + payload


def decode_one(astcenc: str, astc_path: Path, png_path: Path, srgb: bool) -> None:
    mode = "-ds" if srgb else "-dl"
    proc = subprocess.run(
        [astcenc, mode, str(astc_path), str(png_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"astcenc failed ({proc.returncode}) for {astc_path.name}:\n{proc.stdout}"
        )
    if not png_path.is_file() or png_path.stat().st_size <= 8:
        raise RuntimeError(f"astcenc produced no PNG for {astc_path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Mounted Nuketown benchmark root")
    parser.add_argument("--astcenc", default="astcenc")
    parser.add_argument("--map-rel", default=str(DEFAULT_MAP_REL))
    args = parser.parse_args()

    root = args.root
    map_rel = Path(args.map_rel)
    if map_rel.is_absolute() or ".." in map_rel.parts:
        raise ValueError("map-rel must be a safe relative path")
    report_path = root / "xzml-report.json"
    complete_report_path = root / "complete-xztx-report.json"
    texture_dir = root / map_rel / "textures"
    output_dir = root / map_rel / "textures_png"
    report = json.loads(report_path.read_text())
    runtime_rows = report.get("textureAssets", [])
    if len(runtime_rows) != int(report.get("textureAssetCount", len(runtime_rows))):
        raise ValueError("xzml-report textureAssetCount mismatch")
    if not runtime_rows:
        raise ValueError("xzml-report contains no textures")

    rows = runtime_rows
    if complete_report_path.is_file():
        complete_report = json.loads(complete_report_path.read_text())
        complete_rows = complete_report.get("textureAssets", [])
        if len(complete_rows) != int(
            complete_report.get("textureAssetCount", len(complete_rows))
        ):
            raise ValueError("complete-xztx-report textureAssetCount mismatch")
        if complete_rows:
            rows = complete_rows

    astc_rows = [
        row for row in rows
        if str(row.get("format", "")) == "PF_ASTC_6x6"
    ]
    bgra_rows = [
        row for row in rows
        if str(row.get("format", "")) == "PF_B8G8R8A8"
    ]
    unsupported = [
        row for row in rows
        if str(row.get("format", ""))
        not in {"PF_ASTC_6x6", "PF_B8G8R8A8"}
    ]
    if unsupported:
        raise ValueError(
            "unsupported complete-source texture formats: "
            + str(sorted({str(row.get("format", "")) for row in unsupported}))
        )
    if not astc_rows:
        raise ValueError(
            "source texture catalog contains no PF_ASTC_6x6 textures"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.png"):
        stale.unlink()

    decoded = 0
    cache: dict[tuple[str, bool], Path] = {}
    with tempfile.TemporaryDirectory(prefix="xogot-astc6-") as tmp_raw:
        tmp = Path(tmp_raw)
        for row in astc_rows:
            runtime_file = str(row.get("runtimeFile", ""))
            if not runtime_file:
                raise ValueError("texture row missing runtimeFile")

            src = texture_dir / runtime_file
            if not src.is_file():
                raise FileNotFoundError(src)

            payload, width, height = parse_xztx(src, row)
            srgb = bool(row.get("srgb", False))
            key = (
                hashlib.sha256(
                    payload + struct.pack("<II", width, height)
                ).hexdigest(),
                srgb,
            )
            dst = output_dir / (Path(runtime_file).stem + ".png")

            cached = cache.get(key)
            if cached is not None:
                shutil.copyfile(cached, dst)
            else:
                astc_path = tmp / (Path(runtime_file).stem + ".astc")
                astc_path.write_bytes(astc_file(payload, width, height))
                decode_one(args.astcenc, astc_path, dst, srgb)
                cache[key] = dst
            decoded += 1

    bgra_cache: dict[tuple[str, bool], Path] = {}
    for row in bgra_rows:
        runtime_file = str(row.get("runtimeFile", ""))
        if not runtime_file:
            raise ValueError("texture row missing runtimeFile")
        src = texture_dir / runtime_file
        if not src.is_file():
            raise FileNotFoundError(src)
        format_name, payload, width, height = parse_xztx_mip0(src, row)
        if format_name != "PF_B8G8R8A8":
            raise ValueError(
                f"{src}: expected PF_B8G8R8A8, got {format_name}"
            )
        srgb = bool(row.get("srgb", False))
        key = (
            hashlib.sha256(
                payload + struct.pack("<II", width, height)
            ).hexdigest(),
            srgb,
        )
        dst = output_dir / (Path(runtime_file).stem + ".png")
        cached = bgra_cache.get(key)
        if cached is not None:
            shutil.copyfile(cached, dst)
        else:
            rgba = bgra8_to_rgba(payload, width, height)
            write_rgba_png(dst, width, height, rgba, srgb)
            bgra_cache[key] = dst
        decoded += 1

    png_count = len(list(output_dir.glob("*.png")))
    if decoded != len(rows) or png_count != len(rows):
        raise RuntimeError(
            f"decoded PNG count mismatch decoded={decoded} "
            f"png={png_count} expected={len(rows)}"
        )

    srgb_count = sum(
        1 for row in rows if bool(row.get("srgb", False))
    )
    astc_srgb = sum(
        1 for row in astc_rows if bool(row.get("srgb", False))
    )
    print(
        "XZOGOT_ASTC6_DECODE_GREEN",
        f"textures={len(astc_rows)}",
        f"catalog={len(rows)}",
        f"unique_payloads={len(cache)}",
        f"srgb={astc_srgb}",
        f"linear={len(astc_rows) - astc_srgb}",
    )
    print(
        "XZOGOT_XZTX_COMPLETE_DECODE_GREEN",
        f"textures={decoded}",
        f"astc6={len(astc_rows)}",
        f"bgra8={len(bgra_rows)}",
        f"srgb={srgb_count}",
        f"linear={len(rows) - srgb_count}",
        f"png={png_count}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
