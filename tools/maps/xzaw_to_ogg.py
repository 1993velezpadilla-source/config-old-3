#!/usr/bin/env python3
"""Extract source OGG payloads from XZAW v1 without transcoding."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

HEADER_BYTES = 96
FORMAT_BYTES = 64


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def extract(src: Path, dst: Path, expected: dict) -> dict:
    data = src.read_bytes()
    if len(data) < HEADER_BYTES or data[:4] != b"XZAW":
        raise ValueError(f"{src}: invalid XZAW")
    version = u32(data, 4)
    flags = u32(data, 8)
    format_len = u32(data, 12)
    header_bytes = u32(data, 16)
    payload_offset = u32(data, 20)
    payload_bytes = u32(data, 24)
    fmt = data[32 : 32 + FORMAT_BYTES].split(b"\0", 1)[0].decode("ascii")

    if version != 1:
        raise ValueError(f"{src}: unsupported XZAW version {version}")
    if header_bytes != HEADER_BYTES or payload_offset != HEADER_BYTES:
        raise ValueError(f"{src}: unexpected XZAW layout")
    if format_len != len(fmt.encode("ascii")):
        raise ValueError(f"{src}: format length mismatch")
    if payload_offset + payload_bytes != len(data):
        raise ValueError(f"{src}: payload size mismatch")
    if str(expected.get("format", fmt)).upper() != fmt.upper():
        raise ValueError(f"{src}: report format drift {fmt}")
    if int(expected.get("payloadBytes", payload_bytes)) != payload_bytes:
        raise ValueError(f"{src}: report payload drift")
    if fmt.upper() != "OGG":
        raise ValueError(f"{src}: Nacht source audio is not OGG: {fmt}")

    payload = data[payload_offset:]
    if not payload.startswith(b"OggS"):
        raise ValueError(f"{src}: OGG payload missing OggS capture pattern")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(payload)
    return {
        "sourceFile": src.name,
        "runtimeFile": dst.name,
        "objectPath": expected.get("objectPath"),
        "packagePath": expected.get("packagePath"),
        "format": fmt,
        "streaming": bool(expected.get("streaming", bool(flags & 1))),
        "payloadBytes": payload_bytes,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("output_dir", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--output-report", type=Path)
    args = ap.parse_args()

    report_path = args.report or args.input_dir / "report.json"
    source = json.loads(report_path.read_text(encoding="utf-8"))
    rows = source.get("soundWaves", [])
    expected_count = int(source.get("convertedSoundWaves", len(rows)))
    if not rows or len(rows) != expected_count:
        raise ValueError(
            f"audio report count mismatch {len(rows)} != {expected_count}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for stale in args.output_dir.glob("*.ogg"):
        stale.unlink()

    outputs = []
    for row in rows:
        file_name = str(row.get("file", ""))
        if not file_name:
            raise ValueError("sound-wave row missing runtime file")
        src = args.input_dir / file_name
        if not src.is_file():
            raise FileNotFoundError(src)
        dst = args.output_dir / (Path(file_name).stem + ".ogg")
        outputs.append(extract(src, dst, row))

    actual = list(args.output_dir.glob("*.ogg"))
    if len(actual) != expected_count:
        raise RuntimeError(
            f"OGG count mismatch {len(actual)} != {expected_count}"
        )

    result = {
        "schemaVersion": 1,
        "sourceFormat": "XZAW",
        "audioCount": expected_count,
        "format": "OGG",
        "audio": outputs,
        "ready": True,
    }
    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        args.output_report.write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        "XZOGOT_XZAW_OGG_COMPLETE_GREEN",
        f"audio={expected_count}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
