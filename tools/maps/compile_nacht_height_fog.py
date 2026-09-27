#!/usr/bin/env python3
"""Compile resolved Nacht UE4 exponential height fog into XZIEL XZFG v1."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct

MAGIC = b"XZFG"
VERSION = 1
HEADER = struct.Struct("<4sII")
PAYLOAD = struct.Struct("<20f")

FLAG_VOLUMETRIC = 1 << 0
FLAG_CUBEMAP = 1 << 1
FLAG_SECOND_FOG = 1 << 2

EXPECTED_BYTES = HEADER.size + PAYLOAD.size


def _finite(value: object, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"XZIEL XZFG rejected: {name} is not numeric") from exc
    if not math.isfinite(number):
        raise SystemExit(f"XZIEL XZFG rejected: {name} is not finite")
    return number


def compile_fog(source: Path, output: Path, report_path: Path | None) -> dict:
    doc = json.loads(source.read_text(encoding="utf-8"))
    resolved = doc.get("resolved")
    if not isinstance(resolved, dict):
        raise SystemExit("XZIEL XZFG rejected: resolved fog object missing")

    color = resolved.get("fogColorLinear")
    directional_color = resolved.get("directionalInscatteringColorLinear")
    if not isinstance(color, dict) or not isinstance(directional_color, dict):
        raise SystemExit("XZIEL XZFG rejected: fog colors missing")

    fog_height = _finite(resolved.get("fogHeightMeters"), "fogHeightMeters")
    density = _finite(resolved.get("fogDensity"), "fogDensity")
    falloff = _finite(resolved.get("fogHeightFalloff"), "fogHeightFalloff")
    max_opacity = _finite(resolved.get("fogMaxOpacity"), "fogMaxOpacity")
    start_m = _finite(resolved.get("startDistanceMeters"), "startDistanceMeters")
    cutoff_m = _finite(resolved.get("fogCutoffDistanceMeters"), "fogCutoffDistanceMeters")
    color_rgb = tuple(_finite(color.get(k), f"fogColorLinear.{k}") for k in ("r", "g", "b"))

    second_density = _finite(resolved.get("secondFogDensity"), "secondFogDensity")
    second_falloff = _finite(resolved.get("secondFogHeightFalloff"), "secondFogHeightFalloff")
    second_height = _finite(resolved.get("secondFogHeightMeters"), "secondFogHeightMeters")

    directional_exponent = _finite(
        resolved.get("directionalInscatteringExponent"),
        "directionalInscatteringExponent",
    )
    directional_start_m = _finite(
        resolved.get("directionalInscatteringStartDistanceMeters"),
        "directionalInscatteringStartDistanceMeters",
    )
    directional_rgb = tuple(
        _finite(directional_color.get(k), f"directionalInscatteringColorLinear.{k}")
        for k in ("r", "g", "b")
    )

    volumetric_distance_m = _finite(
        resolved.get("volumetricFogDistanceMeters"),
        "volumetricFogDistanceMeters",
    )
    volumetric_enabled = bool(resolved.get("volumetricFogEnabled"))
    cubemap = resolved.get("inscatteringColorCubemap")

    if density < 0.0 or falloff < 0.0 or max_opacity < 0.0 or max_opacity > 1.0:
        raise SystemExit("XZIEL XZFG rejected: primary fog values out of range")
    if start_m < 0.0 or cutoff_m < 0.0:
        raise SystemExit("XZIEL XZFG rejected: fog distances out of range")
    if second_density < 0.0 or second_falloff < 0.0:
        raise SystemExit("XZIEL XZFG rejected: second fog values out of range")

    flags = 0
    if volumetric_enabled:
        flags |= FLAG_VOLUMETRIC
    if isinstance(cubemap, str) and cubemap:
        flags |= FLAG_CUBEMAP
    if second_density > 0.0:
        flags |= FLAG_SECOND_FOG

    values = (
        fog_height,
        density,
        falloff,
        max_opacity,
        start_m,
        cutoff_m,
        *color_rgb,
        second_density,
        second_falloff,
        second_height,
        directional_exponent,
        directional_start_m,
        *directional_rgb,
        volumetric_distance_m,
        0.0,
        0.0,
    )
    if len(values) != 20:
        raise AssertionError(len(values))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        HEADER.pack(MAGIC, VERSION, flags)
        + PAYLOAD.pack(*values)
    )

    if output.stat().st_size != EXPECTED_BYTES:
        raise SystemExit("XZIEL XZFG rejected: unexpected output size")

    report = {
        "format": "XZFG",
        "version": VERSION,
        "bytes": output.stat().st_size,
        "flags": flags,
        "volumetricEnabled": bool(flags & FLAG_VOLUMETRIC),
        "cubemapEnabled": bool(flags & FLAG_CUBEMAP),
        "secondFogEnabled": bool(flags & FLAG_SECOND_FOG),
        "resolved": resolved,
        "serializedOverrides": doc.get("serializedOverrides", {}),
        "sourcePackage": doc.get("sourcePackage"),
        "componentPath": doc.get("componentPath"),
    }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        "XZIEL_NACHT_XZFG_OK",
        json.dumps(
            {
                "bytes": report["bytes"],
                "flags": flags,
                "density": density,
                "heightFalloff": falloff,
                "maxOpacity": max_opacity,
                "startDistanceMeters": start_m,
                "volumetricEnabled": report["volumetricEnabled"],
            },
            sort_keys=True,
        ),
    )
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    compile_fog(args.source, args.output, args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
