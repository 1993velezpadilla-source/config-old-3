#!/usr/bin/env python3
"""Compile source-derived global static-scene lighting for XZIEL.

XZLT v1 intentionally carries only lighting that can be reproduced without
inventing UE/Pavlov post-processing state: one normalized SkyLight contribution
plus one normalized DirectionalLight contribution. Point/spot lights remain a
later format extension.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path


MAGIC = b"XZLT"
VERSION = 1
HEADER = struct.Struct("<4sIff3f3f")


def clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def srgb_to_linear(value: float) -> float:
    value = clamp01(value)
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def parse_light_color(raw: object) -> tuple[float, float, float]:
    if raw is None:
        return (1.0, 1.0, 1.0)
    if not isinstance(raw, str):
        raise ValueError(f"unsupported lightColor value: {raw!r}")
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) < 3:
        raise ValueError(f"invalid lightColor: {raw!r}")
    values = []
    for part in parts[:3]:
        value = float(part)
        values.append(srgb_to_linear(value / 255.0))
    return tuple(values)  # type: ignore[return-value]


def unreal_forward(rotation: dict) -> tuple[float, float, float]:
    pitch = math.radians(float(rotation["Pitch"]))
    yaw = math.radians(float(rotation["Yaw"]))
    cp = math.cos(pitch)
    # Unreal forward (X,Y,Z), then apply the same UE->XZIEL Y-axis flip used by
    # the extracted scene transforms.
    return (
        cp * math.cos(yaw),
        -(cp * math.sin(yaw)),
        math.sin(pitch),
    )


def normalized_surface_to_light(rotation: dict) -> tuple[float, float, float]:
    forward = unreal_forward(rotation)
    # A DirectionalLight's forward vector is the direction light travels.
    # Lambert shading needs the opposite vector: surface -> light.
    direction = (-forward[0], -forward[1], -forward[2])
    length = math.sqrt(sum(component * component for component in direction))
    if not math.isfinite(length) or length <= 1.0e-8:
        raise ValueError("directional light rotation produced zero direction")
    return tuple(component / length for component in direction)  # type: ignore[return-value]


def choose_actor(actors: list[dict], class_tail: str) -> dict:
    matches = []
    for actor in actors:
        if str(actor.get("class", "")).rsplit("/", 1)[-1] != class_tail:
            continue
        props = actor.get("properties") or {}
        intensity = props.get("intensity")
        if isinstance(intensity, (int, float)) and math.isfinite(float(intensity)):
            if float(intensity) > 0.0:
                matches.append(actor)
    if not matches:
        raise ValueError(f"no positive-intensity {class_tail} found")
    return max(
        matches,
        key=lambda actor: float((actor.get("properties") or {}).get("intensity", 0.0)),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--environment", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    doc = json.loads(args.environment.read_text(encoding="utf-8"))
    actors = doc.get("actors")
    if not isinstance(actors, list):
        raise SystemExit("environment.json missing actors")

    sky = choose_actor(actors, "SkyLight")
    directional = choose_actor(actors, "DirectionalLight")

    sky_props = sky.get("properties") or {}
    dir_props = directional.get("properties") or {}
    sky_intensity = float(sky_props["intensity"])
    directional_intensity = float(dir_props["intensity"])
    total = sky_intensity + directional_intensity
    if not math.isfinite(total) or total <= 0.0:
        raise SystemExit("invalid global light intensity sum")

    ambient_weight = sky_intensity / total
    directional_weight = directional_intensity / total

    rotation = (directional.get("transform") or {}).get("sourceRotationUE")
    if not isinstance(rotation, dict):
        raise SystemExit("directional light missing sourceRotationUE")

    directional_color = parse_light_color(dir_props.get("lightColor"))
    directional_direction = normalized_surface_to_light(rotation)

    payload = HEADER.pack(
        MAGIC,
        VERSION,
        ambient_weight,
        directional_weight,
        *directional_color,
        *directional_direction,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)

    report = {
        "schemaVersion": 1,
        "format": "XZLT",
        "version": VERSION,
        "bytes": len(payload),
        "source": str(args.environment),
        "skyLight": {
            "name": sky.get("name", ""),
            "intensity": sky_intensity,
            "weight": ambient_weight,
        },
        "directionalLight": {
            "name": directional.get("name", ""),
            "intensity": directional_intensity,
            "weight": directional_weight,
            "colorLinear": list(directional_color),
            "surfaceToLightDirection": list(directional_direction),
            "sourceRotationUE": rotation,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(
        "XZIEL_NACHT_XZLT_OK",
        f"bytes={len(payload)}",
        f"ambient={ambient_weight:.6f}",
        f"directional={directional_weight:.6f}",
        "dir="
        + ",".join(f"{value:.6f}" for value in directional_direction),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
