#!/usr/bin/env python3
"""Compile the persisted Pavlov Nacht environment into XZIEL XZEN v1.

XZEN v1 deliberately preserves authored values and presence bits instead of
inventing Unreal defaults. The runtime can therefore distinguish an explicitly
serialized value from one that still needs class-default resolution.

Header <4sIIIIII>:
  magic='XZEN', version=1, lightCount, pointCount, spotCount,
  directionalCount, skyCount

Light <II3f3f3fffI>:
  type, flags,
  position.xyz meters in XZIEL basis,
  rotation.pitch/yaw/roll degrees (only valid when HAS_ROTATION),
  color.rgb linear 0..1 from serialized byte color (only when HAS_COLOR),
  intensity (only valid when HAS_INTENSITY),
  attenuationRadiusMeters (only valid when HAS_RADIUS),
  intensityUnits enum

Flags:
  bit0 HAS_POSITION
  bit1 HAS_ROTATION
  bit2 HAS_COLOR
  bit3 HAS_INTENSITY
  bit4 HAS_RADIUS
  bit5 HAS_UNITS
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = ROOT / "assets/nacht_reference/pavlov_scene_reference/environment.json"

MAGIC = b"XZEN"
VERSION = 1
HEADER = struct.Struct("<4sIIIIII")
LIGHT = struct.Struct("<II3f3f3fffI")

TYPE_POINT = 1
TYPE_SPOT = 2
TYPE_DIRECTIONAL = 3
TYPE_SKY = 4

HAS_POSITION = 1 << 0
HAS_ROTATION = 1 << 1
HAS_COLOR = 1 << 2
HAS_INTENSITY = 1 << 3
HAS_RADIUS = 1 << 4
HAS_UNITS = 1 << 5

UNIT_UNKNOWN = 0
UNIT_CANDELAS = 1
UNIT_LUMENS = 2
UNIT_UNIT_LESS = 3
UNIT_EV100 = 4

EXPECTED_ENV_ACTORS = 129
EXPECTED_LIGHTS = 101
EXPECTED_POINT = 86
EXPECTED_SPOT = 12
EXPECTED_DIRECTIONAL = 2
EXPECTED_SKY = 1

CLASS_TO_TYPE = {
    "/Script/Engine/PointLight": TYPE_POINT,
    "/Script/Engine/SpotLight": TYPE_SPOT,
    "/Script/Engine/DirectionalLight": TYPE_DIRECTIONAL,
    "/Script/Engine/SkyLight": TYPE_SKY,
}

UNIT_MAP = {
    "ELightUnits::Candelas": UNIT_CANDELAS,
    "ELightUnits::Lumens": UNIT_LUMENS,
    "ELightUnits::Unitless": UNIT_UNIT_LESS,
    "ELightUnits::EV": UNIT_EV100,
    "ELightUnits::EV100": UNIT_EV100,
}


def _vec3_xyz(value: object, lower: bool = False) -> tuple[float, float, float] | None:
    if not isinstance(value, dict):
        return None
    keys = ("x", "y", "z") if lower else ("X", "Y", "Z")
    try:
        return tuple(float(value[k]) for k in keys)  # type: ignore[return-value]
    except (KeyError, TypeError, ValueError):
        return None


def _rot3(value: object) -> tuple[float, float, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        return (
            float(value["Pitch"]),
            float(value["Yaw"]),
            float(value["Roll"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _color3(value: object) -> tuple[float, float, float] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) < 3:
        return None
    try:
        rgb = [max(0, min(255, int(part))) / 255.0 for part in parts[:3]]
    except ValueError:
        return None
    return (rgb[0], rgb[1], rgb[2])


def compile_environment(source: Path, output: Path, report_path: Path | None) -> dict:
    doc = json.loads(source.read_text(encoding="utf-8"))
    actors = doc.get("actors")
    if not isinstance(actors, list) or len(actors) != EXPECTED_ENV_ACTORS:
        raise SystemExit(
            f"XZIEL XZEN rejected: expected {EXPECTED_ENV_ACTORS} environment actors"
        )

    rows: list[tuple] = []
    report_rows: list[dict] = []
    counts = {
        TYPE_POINT: 0,
        TYPE_SPOT: 0,
        TYPE_DIRECTIONAL: 0,
        TYPE_SKY: 0,
    }

    for actor in actors:
        if not isinstance(actor, dict):
            continue
        light_type = CLASS_TO_TYPE.get(actor.get("class"))
        if light_type is None:
            continue

        transform = actor.get("transform") or {}
        props = actor.get("properties") or {}

        position = _vec3_xyz(transform.get("position"), lower=True)
        rotation = _rot3(transform.get("sourceRotationUE"))
        color = _color3(props.get("lightColor"))

        intensity = props.get("intensity")
        has_intensity = isinstance(intensity, (int, float))
        intensity_value = float(intensity) if has_intensity else 0.0

        radius_cm = props.get("attenuationRadius")
        has_radius = isinstance(radius_cm, (int, float)) and float(radius_cm) > 0.0
        radius_m = float(radius_cm) / 100.0 if has_radius else 0.0

        units_name = props.get("intensityUnits")
        unit_value = UNIT_MAP.get(units_name, UNIT_UNKNOWN)
        has_units = isinstance(units_name, str) and bool(units_name)

        flags = 0
        if position is not None:
            flags |= HAS_POSITION
        else:
            position = (0.0, 0.0, 0.0)
        if rotation is not None:
            flags |= HAS_ROTATION
        else:
            rotation = (0.0, 0.0, 0.0)
        if color is not None:
            flags |= HAS_COLOR
        else:
            color = (0.0, 0.0, 0.0)
        if has_intensity:
            flags |= HAS_INTENSITY
        if has_radius:
            flags |= HAS_RADIUS
        if has_units:
            flags |= HAS_UNITS

        rows.append((
            light_type,
            flags,
            *position,
            *rotation,
            *color,
            intensity_value,
            radius_m,
            unit_value,
        ))
        counts[light_type] += 1
        report_rows.append({
            "id": actor.get("id"),
            "name": actor.get("name"),
            "class": actor.get("class"),
            "type": light_type,
            "flags": flags,
            "position": list(position),
            "rotation": list(rotation),
            "color": list(color),
            "intensity": intensity_value,
            "radiusMeters": radius_m,
            "units": units_name,
            "unitsEnum": unit_value,
        })

    expected = {
        TYPE_POINT: EXPECTED_POINT,
        TYPE_SPOT: EXPECTED_SPOT,
        TYPE_DIRECTIONAL: EXPECTED_DIRECTIONAL,
        TYPE_SKY: EXPECTED_SKY,
    }
    if len(rows) != EXPECTED_LIGHTS or counts != expected:
        raise SystemExit(
            f"XZIEL XZEN rejected: light census drift rows={len(rows)} counts={counts}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as f:
        f.write(HEADER.pack(
            MAGIC,
            VERSION,
            len(rows),
            counts[TYPE_POINT],
            counts[TYPE_SPOT],
            counts[TYPE_DIRECTIONAL],
            counts[TYPE_SKY],
        ))
        for row in rows:
            f.write(LIGHT.pack(*row))

    report = {
        "format": "XZEN",
        "version": VERSION,
        "bytes": output.stat().st_size,
        "recordBytes": LIGHT.size,
        "lightCount": len(rows),
        "pointCount": counts[TYPE_POINT],
        "spotCount": counts[TYPE_SPOT],
        "directionalCount": counts[TYPE_DIRECTIONAL],
        "skyCount": counts[TYPE_SKY],
        "withPosition": sum(bool(row[1] & HAS_POSITION) for row in rows),
        "withRotation": sum(bool(row[1] & HAS_ROTATION) for row in rows),
        "withColor": sum(bool(row[1] & HAS_COLOR) for row in rows),
        "withIntensity": sum(bool(row[1] & HAS_INTENSITY) for row in rows),
        "withRadius": sum(bool(row[1] & HAS_RADIUS) for row in rows),
        "withUnits": sum(bool(row[1] & HAS_UNITS) for row in rows),
        "lights": report_rows,
    }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

    print("XZIEL_NACHT_XZEN_OK", json.dumps({
        key: value
        for key, value in report.items()
        if key != "lights"
    }, sort_keys=True))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_ENV)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    compile_environment(args.source, args.output, args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
