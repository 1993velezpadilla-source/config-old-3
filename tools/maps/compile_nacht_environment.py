#!/usr/bin/env python3
"""Compile the Pavlov Nacht environment into XZIEL XZEN v2.

XZIEL consumes the persisted actor census plus a typed CUE4Parse local-light
scan generated from the same Nacht_de_Untoten.umap. The typed scan resolves
Point/Spot defaults that are present on ULightComponent even when the actor
property snapshot omitted them.

Header <4sIIIIII>:
  magic='XZEN', version=2, lightCount, pointCount, spotCount,
  directionalCount, skyCount

Light <II3f3f3ffffI>:
  type, flags,
  position.xyz meters in XZIEL basis,
  rotation.pitch/yaw/roll degrees,
  color.rgb sRGB 0..1,
  intensity,
  attenuationRadiusMeters,
  innerConeAngleDegrees,
  outerConeAngleDegrees,
  intensityUnits enum

Flags:
  bit0 HAS_POSITION
  bit1 HAS_ROTATION
  bit2 HAS_COLOR
  bit3 HAS_INTENSITY
  bit4 HAS_RADIUS
  bit5 HAS_UNITS
  bit6 HAS_CONE
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = ROOT / "assets/nacht_reference/pavlov_scene_reference/environment.json"

MAGIC = b"XZEN"
VERSION = 2
HEADER = struct.Struct("<4sIIIIII")
LIGHT = struct.Struct("<II3f3f3ffffI")

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
HAS_CONE = 1 << 6

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
    "Candelas": UNIT_CANDELAS,
    "ELightUnits::Lumens": UNIT_LUMENS,
    "Lumens": UNIT_LUMENS,
    "ELightUnits::Unitless": UNIT_UNIT_LESS,
    "Unitless": UNIT_UNIT_LESS,
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


def _color_hex3(value: object) -> tuple[float, float, float] | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lstrip("#")
    if len(value) < 6:
        return None
    try:
        return (
            int(value[0:2], 16) / 255.0,
            int(value[2:4], 16) / 255.0,
            int(value[4:6], 16) / 255.0,
        )
    except ValueError:
        return None


def _typed_float(values: dict, key: str) -> float | None:
    value = values.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _typed_rotation(values: dict) -> tuple[float, float, float] | None:
    raw = values.get("RelativeRotation")
    if not isinstance(raw, str):
        return None
    pieces = {}
    for token in raw.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        try:
            pieces[key] = float(value)
        except ValueError:
            return None
    if not all(k in pieces for k in ("P", "Y", "R")):
        return None
    return (pieces["P"], pieces["Y"], pieces["R"])


def _load_typed_local_lights(path: Path | None) -> dict[str, dict]:
    if path is None:
        raise SystemExit("XZIEL XZEN v2 requires --typed-lights")
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_POINT + EXPECTED_SPOT:
        raise SystemExit("XZIEL XZEN rejected: typed local-light census must be 98")
    result: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit("XZIEL XZEN rejected: malformed typed local-light row")
        actor = row.get("actor")
        component = row.get("component")
        values = component.get("values") if isinstance(component, dict) else None
        if not isinstance(actor, str) or not actor or not isinstance(values, dict):
            raise SystemExit("XZIEL XZEN rejected: malformed typed local-light component")
        if actor in result:
            raise SystemExit(f"XZIEL XZEN rejected: duplicate typed actor {actor}")
        result[actor] = values
    return result


def compile_environment(
    source: Path,
    typed_lights_path: Path | None,
    output: Path,
    report_path: Path | None,
) -> dict:
    doc = json.loads(source.read_text(encoding="utf-8"))
    typed_lights = _load_typed_local_lights(typed_lights_path)
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

        inner_cone = 0.0
        outer_cone = 0.0
        has_cone = False

        if light_type in (TYPE_POINT, TYPE_SPOT):
            name = actor.get("name")
            typed = typed_lights.get(name) if isinstance(name, str) else None
            if not isinstance(typed, dict):
                raise SystemExit(
                    f"XZIEL XZEN rejected: no typed local-light row for {name!r}"
                )

            typed_rotation = _typed_rotation(typed)
            typed_color = _color_hex3(typed.get("LightColor"))
            typed_intensity = _typed_float(typed, "Intensity")
            typed_radius = _typed_float(typed, "AttenuationRadius")
            typed_units = typed.get("IntensityUnits")

            if typed_rotation is None or typed_color is None:
                raise SystemExit(
                    f"XZIEL XZEN rejected: typed transform/color missing for {name}"
                )
            if typed_intensity is None or typed_radius is None or typed_radius <= 0.0:
                raise SystemExit(
                    f"XZIEL XZEN rejected: typed intensity/radius missing for {name}"
                )
            if not isinstance(typed_units, str) or not typed_units:
                raise SystemExit(
                    f"XZIEL XZEN rejected: typed units missing for {name}"
                )

            rotation = typed_rotation
            color = typed_color
            intensity_value = typed_intensity
            has_intensity = True
            radius_m = typed_radius / 100.0
            has_radius = True
            units_name = typed_units
            unit_value = UNIT_MAP.get(typed_units, UNIT_UNKNOWN)
            has_units = unit_value != UNIT_UNKNOWN

            if light_type == TYPE_SPOT:
                typed_inner = _typed_float(typed, "InnerConeAngle")
                typed_outer = _typed_float(typed, "OuterConeAngle")
                if (
                    typed_inner is None
                    or typed_outer is None
                    or typed_inner < 0.0
                    or typed_outer <= typed_inner
                    or typed_outer >= 90.0
                ):
                    raise SystemExit(
                        f"XZIEL XZEN rejected: invalid spot cone for {name}"
                    )
                inner_cone = typed_inner
                outer_cone = typed_outer
                has_cone = True

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
        if has_cone:
            flags |= HAS_CONE

        rows.append((
            light_type,
            flags,
            *position,
            *rotation,
            *color,
            intensity_value,
            radius_m,
            inner_cone,
            outer_cone,
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
            "innerConeAngleDegrees": inner_cone,
            "outerConeAngleDegrees": outer_cone,
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
        "withCone": sum(bool(row[1] & HAS_CONE) for row in rows),
        "typedLocalLightCount": len(typed_lights),
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
    ap.add_argument("--typed-lights", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    compile_environment(
        args.source,
        args.typed_lights,
        args.output,
        args.report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
