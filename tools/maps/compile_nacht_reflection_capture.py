#!/usr/bin/env python3
"""Compile Unreal FullHDR reflection capture bytes into XZIEL XZRC v2.

The payload is copied byte-for-byte. Unreal stores FullHDRCapturedData mip-major,
with six ECubeFace faces (+X,-X,+Y,-Y,+Z,-Z) consecutively inside each mip.
Each texel is PF_FloatRGBA / FFloat16Color = RGBA16F (8 bytes).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

MAGIC = b"XZRC"
VERSION = 2
FORMAT_RGBA16F = 1
FACE_COUNT = 6
BYTES_PER_TEXEL = 8
# v1 base (64 bytes) is preserved verbatim. v2 appends exact capture-shape
# metadata so the runtime can reproduce UE sphere projection without map
# hardcoding: XZIEL-space position/radius/offset in meters + shape id.
HEADER = struct.Struct("<4sIIIIIIIIff16sI7fI")
HEADER_BYTES = HEADER.size
SHAPE_SPHERE = 1
DEFAULT_UE_SPHERE_RADIUS_CM = 3000.0

EXPECTED_NACHT_SIZE = 128
EXPECTED_NACHT_BYTES = 1_048_560
EXPECTED_NACHT_SHA256 = (
    "b371451ee1e0aad877125b4f36eae584"
    "3a5009cb8e23143206bd54683d6b8843"
)
EXPECTED_NACHT_GUID = "26aeb6b544e0c552b1f0519279a3bf2d"


def normalize_guid(value: object) -> str:
    text = "" if value is None else str(value)
    compact = re.sub(r"[^0-9a-fA-F]", "", text).lower()
    if len(compact) != 32:
        raise ValueError(f"invalid reflection GUID: {text!r}")
    return compact


def expected_payload_bytes(size: int) -> tuple[int, int]:
    if size <= 0 or size & (size - 1):
        raise ValueError(f"cubemap size must be power-of-two, got {size}")
    mip_count = size.bit_length()
    texels_per_face = sum((size >> mip) ** 2 for mip in range(mip_count))
    return mip_count, texels_per_face * FACE_COUNT * BYTES_PER_TEXEL


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--census", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    payload = args.payload.read_bytes()
    census = json.loads(args.census.read_text(encoding="utf-8"))

    linked = [
        row
        for row in census.get("reflectionCaptureBuildData", [])
        if row.get("linkedToCapture")
    ]
    if len(linked) != 1:
        raise SystemExit(
            f"expected exactly one linked reflection build-data row, got {len(linked)}"
        )

    row = linked[0]

    captures = [
        capture
        for capture in census.get("reflectionCaptures", [])
        if capture.get("isComponent")
        and capture.get("captureKind") == "sphere"
        and normalize_guid(capture.get("mapBuildDataId"))
        == normalize_guid(row["mapBuildDataId"])
    ]
    if len(captures) != 1:
        raise SystemExit(
            "expected exactly one linked sphere reflection component, "
            f"got {len(captures)}"
        )

    capture = captures[0]
    hierarchy = capture.get("hierarchy") or []
    if len(hierarchy) != 1:
        raise SystemExit(
            "expected Nacht sphere capture to be an unattached root "
            f"component, hierarchy={len(hierarchy)}"
        )

    location = hierarchy[0].get("locationUEcm") or {}
    try:
        ue_x_cm = float(location["X"])
        ue_y_cm = float(location["Y"])
        ue_z_cm = float(location["Z"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(
            f"invalid Nacht reflection location: {location!r}"
        ) from exc

    properties = capture.get("properties") or {}
    raw_radius_cm = properties.get("influenceRadiusCm")
    radius_cm = (
        DEFAULT_UE_SPHERE_RADIUS_CM
        if raw_radius_cm is None
        else float(raw_radius_cm)
    )

    raw_offset = properties.get("captureOffsetCm")
    if raw_offset is None:
        offset_x_cm = 0.0
        offset_y_cm = 0.0
        offset_z_cm = 0.0
        radius_source = "UE4 sphere default"
        offset_source = "UE4 FVector default zero"
    else:
        offset_x_cm = float(raw_offset["X"])
        offset_y_cm = float(raw_offset["Y"])
        offset_z_cm = float(raw_offset["Z"])
        radius_source = (
            "serialized"
            if raw_radius_cm is not None
            else "UE4 sphere default"
        )
        offset_source = "serialized"

    if not (0.0 < radius_cm < 1_000_000.0):
        raise SystemExit(f"invalid reflection influence radius: {radius_cm}")

    # Match the established XZIEL world transform used by static-scene
    # instances/lights: UE (X,Y,Z) cm -> XZIEL (X,-Y,Z) meters.
    capture_position_m = (
        ue_x_cm / 100.0,
        -ue_y_cm / 100.0,
        ue_z_cm / 100.0,
    )
    influence_radius_m = radius_cm / 100.0
    capture_offset_m = tuple(
        0.0 if value == 0.0 else value
        for value in (
            offset_x_cm / 100.0,
            -offset_y_cm / 100.0,
            offset_z_cm / 100.0,
        )
    )

    size = int(row["cubemapSize"])
    mip_count, expected_bytes = expected_payload_bytes(size)
    average_brightness = float(row["averageBrightness"])
    brightness = float(row["brightness"])
    guid = normalize_guid(row["mapBuildDataId"])
    payload_sha = hashlib.sha256(payload).hexdigest()

    if size != EXPECTED_NACHT_SIZE:
        raise SystemExit(f"Nacht reflection size drifted: {size}")
    if len(payload) != expected_bytes or len(payload) != EXPECTED_NACHT_BYTES:
        raise SystemExit(
            f"Nacht FullHDR byte count mismatch: {len(payload)} != {expected_bytes}"
        )
    if payload_sha != EXPECTED_NACHT_SHA256:
        raise SystemExit(
            f"Nacht FullHDR SHA-256 mismatch: {payload_sha}"
        )
    if guid != EXPECTED_NACHT_GUID:
        raise SystemExit(f"Nacht reflection GUID mismatch: {guid}")
    if not (0.0 < average_brightness < 100000.0):
        raise SystemExit(f"invalid average brightness: {average_brightness}")
    if not (0.0 < brightness < 100000.0):
        raise SystemExit(f"invalid brightness: {brightness}")

    header = HEADER.pack(
        MAGIC,
        VERSION,
        size,
        mip_count,
        FACE_COUNT,
        FORMAT_RGBA16F,
        BYTES_PER_TEXEL,
        HEADER_BYTES,
        len(payload),
        average_brightness,
        brightness,
        bytes.fromhex(guid),
        0,
        capture_position_m[0],
        capture_position_m[1],
        capture_position_m[2],
        influence_radius_m,
        capture_offset_m[0],
        capture_offset_m[1],
        capture_offset_m[2],
        SHAPE_SPHERE,
    )
    assert len(header) == 96

    asset = header + payload
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(asset)

    report = {
        "schemaVersion": 1,
        "format": "XZRC",
        "version": VERSION,
        "headerBytes": HEADER_BYTES,
        "cubemapSize": size,
        "mipCount": mip_count,
        "faceCount": FACE_COUNT,
        "faceOrder": ["+X", "-X", "+Y", "-Y", "+Z", "-Z"],
        "payloadLayout": "mip-major-face-minor",
        "pixelFormat": "RGBA16F",
        "bytesPerTexel": BYTES_PER_TEXEL,
        "payloadBytes": len(payload),
        "assetBytes": len(asset),
        "averageBrightness": average_brightness,
        "brightness": brightness,
        "mapBuildDataId": guid.upper(),
        "payloadSha256": payload_sha.upper(),
        "assetSha256": hashlib.sha256(asset).hexdigest().upper(),
        "sourcePreservedByteForByte": True,
        "captureShape": "sphere",
        "capturePositionUeCm": [ue_x_cm, ue_y_cm, ue_z_cm],
        "capturePositionXzielMeters": list(capture_position_m),
        "influenceRadiusCm": radius_cm,
        "influenceRadiusMeters": influence_radius_m,
        "influenceRadiusSource": radius_source,
        "captureOffsetUeCm": [
            offset_x_cm,
            offset_y_cm,
            offset_z_cm,
        ],
        "captureOffsetXzielMeters": list(capture_offset_m),
        "captureOffsetSource": offset_source,
        "runtimeDirectionTransform": "XZIEL(X,-Y,Z)->UE(X,Y,Z): flip sample Y",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "XZIEL_NACHT_XZRC_OK",
        json.dumps(report, sort_keys=True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
