#!/usr/bin/env python3
"""Compile generic cooked-UE light extraction into XZIEL XZEN v2.

No map names or expected light counts are embedded here. The source extractor
provides exact serialized/default-resolved component values through CUE4Parse.
Unsupported local-light semantics fail closed instead of being guessed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct

MAGIC = b"XZEN"
VERSION = 2
HEADER = struct.Struct("<4sIIIIII")
LIGHT = struct.Struct("<II3f3f3f9fII")

TYPE_POINT = 1
TYPE_SPOT = 2
TYPE_DIRECTIONAL = 3
TYPE_SKY = 4

TYPE_MAP = {
    "point": TYPE_POINT,
    "spot": TYPE_SPOT,
    "directional": TYPE_DIRECTIONAL,
    "sky": TYPE_SKY,
}

HAS_POSITION = 1 << 0
HAS_ROTATION = 1 << 1
HAS_COLOR = 1 << 2
HAS_INTENSITY = 1 << 3
HAS_RADIUS = 1 << 4
HAS_UNITS = 1 << 5
HAS_INNER_CONE = 1 << 6
HAS_OUTER_CONE = 1 << 7
HAS_FALLOFF_EXPONENT = 1 << 8
HAS_TEMPERATURE = 1 << 9
HAS_SOURCE_RADIUS = 1 << 10
HAS_SOFT_SOURCE_RADIUS = 1 << 11
HAS_SOURCE_LENGTH = 1 << 12
HAS_INVERSE_SQUARED = 1 << 13
HAS_USE_TEMPERATURE = 1 << 14
HAS_CAST_SHADOWS = 1 << 15
HAS_VISIBLE = 1 << 16
HAS_ATMOSPHERE_SUN = 1 << 17

BEHAVIOR_INVERSE_SQUARED = 1 << 0
BEHAVIOR_USE_TEMPERATURE = 1 << 1
BEHAVIOR_CAST_SHADOWS = 1 << 2
BEHAVIOR_VISIBLE = 1 << 3
BEHAVIOR_ATMOSPHERE_SUN = 1 << 4

UNIT_UNKNOWN = 0
UNIT_CANDELAS = 1
UNIT_LUMENS = 2
UNIT_UNITLESS = 3
UNIT_EV100 = 4

UNIT_MAP = {
    "Candelas": UNIT_CANDELAS,
    "ELightUnits::Candelas": UNIT_CANDELAS,
    "Lumens": UNIT_LUMENS,
    "ELightUnits::Lumens": UNIT_LUMENS,
    "Unitless": UNIT_UNITLESS,
    "ELightUnits::Unitless": UNIT_UNITLESS,
    "EV": UNIT_EV100,
    "EV100": UNIT_EV100,
    "ELightUnits::EV": UNIT_EV100,
    "ELightUnits::EV100": UNIT_EV100,
}


def matmul3(a, b):
    return [
        [sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)]
        for r in range(3)
    ]


def matmul4(a, b):
    return [
        sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4))
        for r in range(4)
        for c in range(4)
    ]


IDENTITY4 = [
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
]


def ue_rotation_xziel(rot):
    p = math.radians(float(rot["Pitch"]))
    y = math.radians(float(rot["Yaw"]))
    r = math.radians(float(rot["Roll"]))
    sp, sy, sr = math.sin(p), math.sin(y), math.sin(r)
    cp, cy, cr = math.cos(p), math.cos(y), math.cos(r)

    ue_rows = [
        [cp * cy, cp * sy, sp],
        [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp],
        [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp],
    ]
    ue_col = [[ue_rows[c][r] for c in range(3)] for r in range(3)]
    basis = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
    return matmul3(matmul3(basis, ue_col), basis)


def local_matrix(node):
    pos = node["locationUEcm"]
    rot = node["rotationUE"]
    scale = node["scale"]

    tx = float(pos["X"]) / 100.0
    ty = -float(pos["Y"]) / 100.0
    tz = float(pos["Z"]) / 100.0

    sx = float(scale["X"])
    sy = float(scale["Y"])
    sz = float(scale["Z"])

    r = ue_rotation_xziel(rot)
    return [
        r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx,
        r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty,
        r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz,
        0.0, 0.0, 0.0, 1.0,
    ]


def normalized_rotation(world):
    cols = [
        [world[0], world[4], world[8]],
        [world[1], world[5], world[9]],
        [world[2], world[6], world[10]],
    ]
    out = []
    for col in cols:
        length = math.sqrt(sum(v * v for v in col))
        if not math.isfinite(length) or length <= 1.0e-10:
            raise SystemExit("XZIEL XZEN rejected: singular light transform")
        out.append([v / length for v in col])
    return [
        [out[0][0], out[1][0], out[2][0]],
        [out[0][1], out[1][1], out[2][1]],
        [out[0][2], out[1][2], out[2][2]],
    ]


def xziel_rotation_to_ue_rotator(rot):
    basis = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
    ue = matmul3(matmul3(basis, rot), basis)

    sp = max(-1.0, min(1.0, ue[2][0]))
    pitch = math.asin(sp)
    cp = math.cos(pitch)
    if abs(cp) > 1.0e-7:
        yaw = math.atan2(ue[1][0], ue[0][0])
        roll = math.atan2(-ue[2][1], ue[2][2])
    else:
        yaw = math.atan2(-ue[0][1], ue[1][1])
        roll = 0.0

    return math.degrees(pitch), math.degrees(yaw), math.degrees(roll)


def world_transform(hierarchy):
    if not isinstance(hierarchy, list) or not hierarchy:
        raise SystemExit("XZIEL XZEN rejected: empty light hierarchy")

    world = IDENTITY4[:]
    for node in reversed(hierarchy):
        if not isinstance(node, dict):
            raise SystemExit("XZIEL XZEN rejected: malformed hierarchy row")
        world = matmul4(world, local_matrix(node))

    if not all(math.isfinite(v) for v in world):
        raise SystemExit("XZIEL XZEN rejected: non-finite world transform")

    return world, xziel_rotation_to_ue_rotator(normalized_rotation(world))


def optional_float(props, key):
    value = props.get(key)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return True, float(value)
    return False, 0.0


def optional_bool(props, key):
    value = props.get(key)
    if isinstance(value, bool):
        return True, value
    return False, False


def color3(value):
    if not isinstance(value, dict):
        return False, (0.0, 0.0, 0.0)
    try:
        rgb = tuple(
            max(0, min(255, int(value[k]))) / 255.0
            for k in ("R", "G", "B")
        )
    except (KeyError, TypeError, ValueError):
        return False, (0.0, 0.0, 0.0)
    return True, rgb


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    doc = json.loads(args.source.read_text(encoding="utf-8"))
    if doc.get("schemaVersion") != 1:
        raise SystemExit("XZIEL XZEN rejected: unsupported source schema")

    lights = doc.get("lights")
    if not isinstance(lights, list) or not lights:
        raise SystemExit("XZIEL XZEN rejected: no lights")

    rows = []
    report_rows = []
    counts = {
        TYPE_POINT: 0,
        TYPE_SPOT: 0,
        TYPE_DIRECTIONAL: 0,
        TYPE_SKY: 0,
    }

    for index, light in enumerate(lights):
        if not isinstance(light, dict):
            raise SystemExit("XZIEL XZEN rejected: malformed light row")

        kind = light.get("componentType")
        light_type = TYPE_MAP.get(kind)
        if light_type is None:
            raise SystemExit(f"XZIEL XZEN rejected: unknown type {kind!r}")

        world, world_rot = world_transform(light.get("hierarchy"))
        position = (world[3], world[7], world[11])

        props = light.get("properties")
        if not isinstance(props, dict):
            raise SystemExit("XZIEL XZEN rejected: missing properties")

        intensity_ok, intensity = optional_float(props, "intensity")
        if not intensity_ok or intensity < 0.0:
            raise SystemExit(f"XZIEL XZEN rejected: bad intensity at {index}")

        color_ok, color = color3(props.get("lightColor"))
        radius_ok, radius_cm = optional_float(props, "attenuationRadiusCm")
        inner_ok, inner = optional_float(props, "innerConeAngleDegrees")
        outer_ok, outer = optional_float(props, "outerConeAngleDegrees")
        falloff_ok, falloff = optional_float(props, "lightFalloffExponent")
        temp_ok, temperature = optional_float(props, "temperatureKelvin")
        source_radius_ok, source_radius_cm = optional_float(props, "sourceRadiusCm")
        soft_radius_ok, soft_radius_cm = optional_float(props, "softSourceRadiusCm")
        source_length_ok, source_length_cm = optional_float(props, "sourceLengthCm")

        units_name = props.get("intensityUnits")
        units_ok = isinstance(units_name, str) and bool(units_name)
        units = UNIT_MAP.get(units_name, UNIT_UNKNOWN)

        inverse_ok, inverse = optional_bool(props, "useInverseSquaredFalloff")
        use_temp_ok, use_temp = optional_bool(props, "useTemperature")
        shadows_ok, cast_shadows = optional_bool(props, "castShadows")
        visible_ok, visible = optional_bool(props, "visible")
        sun_ok, atmosphere_sun = optional_bool(props, "usedAsAtmosphereSunLight")

        if kind == "directional" and not color_ok:
            raise SystemExit(
                f"XZIEL XZEN rejected: directional color missing at {index}"
            )

        if kind in ("point", "spot"):
            if not (color_ok and radius_ok and units_ok and inverse_ok):
                raise SystemExit(
                    f"XZIEL XZEN rejected: local-light payload incomplete at {index}"
                )
            if units == UNIT_UNKNOWN:
                raise SystemExit(
                    f"XZIEL XZEN rejected: unsupported light units {units_name!r}"
                )
            if not inverse:
                raise SystemExit(
                    f"XZIEL XZEN rejected: non-inverse-square local light at {index}"
                )
            if radius_cm <= 0.0:
                raise SystemExit(
                    f"XZIEL XZEN rejected: local-light radius <= 0 at {index}"
                )

        if kind == "spot":
            if not (inner_ok and outer_ok) or inner < 0.0 or outer < inner:
                raise SystemExit(
                    f"XZIEL XZEN rejected: invalid spot cone at {index}"
                )

        flags = HAS_POSITION | HAS_ROTATION | HAS_INTENSITY
        if color_ok:
            flags |= HAS_COLOR
        if radius_ok:
            flags |= HAS_RADIUS
        if units_ok:
            flags |= HAS_UNITS
        if inner_ok:
            flags |= HAS_INNER_CONE
        if outer_ok:
            flags |= HAS_OUTER_CONE
        if falloff_ok:
            flags |= HAS_FALLOFF_EXPONENT
        if temp_ok:
            flags |= HAS_TEMPERATURE
        if source_radius_ok:
            flags |= HAS_SOURCE_RADIUS
        if soft_radius_ok:
            flags |= HAS_SOFT_SOURCE_RADIUS
        if source_length_ok:
            flags |= HAS_SOURCE_LENGTH
        if inverse_ok:
            flags |= HAS_INVERSE_SQUARED
        if use_temp_ok:
            flags |= HAS_USE_TEMPERATURE
        if shadows_ok:
            flags |= HAS_CAST_SHADOWS
        if visible_ok:
            flags |= HAS_VISIBLE
        if sun_ok:
            flags |= HAS_ATMOSPHERE_SUN

        behavior = 0
        if inverse:
            behavior |= BEHAVIOR_INVERSE_SQUARED
        if use_temp:
            behavior |= BEHAVIOR_USE_TEMPERATURE
        if cast_shadows:
            behavior |= BEHAVIOR_CAST_SHADOWS
        if visible:
            behavior |= BEHAVIOR_VISIBLE
        if atmosphere_sun:
            behavior |= BEHAVIOR_ATMOSPHERE_SUN

        row = (
            light_type,
            flags,
            *position,
            *world_rot,
            *color,
            intensity,
            radius_cm / 100.0 if radius_ok else 0.0,
            inner,
            outer,
            falloff,
            temperature,
            source_radius_cm / 100.0 if source_radius_ok else 0.0,
            soft_radius_cm / 100.0 if soft_radius_ok else 0.0,
            source_length_cm / 100.0 if source_length_ok else 0.0,
            units,
            behavior,
        )

        if not all(math.isfinite(float(v)) for v in row[2:-2]):
            raise SystemExit("XZIEL XZEN rejected: non-finite record")

        rows.append(row)
        counts[light_type] += 1
        report_rows.append({
            "id": light.get("id"),
            "packagePath": light.get("packagePath"),
            "sourcePath": light.get("sourcePath"),
            "componentType": kind,
            "flags": flags,
            "behaviorFlags": behavior,
            "worldPositionMeters": list(position),
            "worldRotationUE": {
                "Pitch": world_rot[0],
                "Yaw": world_rot[1],
                "Roll": world_rot[2],
            },
            "color": list(color) if color_ok else None,
            "intensity": intensity,
            "radiusMeters": radius_cm / 100.0 if radius_ok else None,
            "innerConeAngleDegrees": inner if inner_ok else None,
            "outerConeAngleDegrees": outer if outer_ok else None,
            "falloffExponent": falloff if falloff_ok else None,
            "temperatureKelvin": temperature if temp_ok else None,
            "useTemperature": use_temp if use_temp_ok else None,
            "sourceRadiusMeters": source_radius_cm / 100.0 if source_radius_ok else None,
            "softSourceRadiusMeters": soft_radius_cm / 100.0 if soft_radius_ok else None,
            "sourceLengthMeters": source_length_cm / 100.0 if source_length_ok else None,
            "units": units_name,
            "inverseSquared": inverse if inverse_ok else None,
            "castShadows": cast_shadows if shadows_ok else None,
            "visible": visible if visible_ok else None,
            "atmosphereSun": atmosphere_sun if sun_ok else None,
        })

    source_counts = doc.get("typeCounts") or {}
    compiled_counts = {
        "point": counts[TYPE_POINT],
        "spot": counts[TYPE_SPOT],
        "directional": counts[TYPE_DIRECTIONAL],
        "sky": counts[TYPE_SKY],
    }
    normalized_source = {
        k: int(source_counts.get(k, 0))
        for k in ("point", "spot", "directional", "sky")
    }
    if compiled_counts != normalized_source:
        raise SystemExit(
            f"XZIEL XZEN rejected: source count drift "
            f"{normalized_source!r} != {compiled_counts!r}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as handle:
        handle.write(HEADER.pack(
            MAGIC,
            VERSION,
            len(rows),
            counts[TYPE_POINT],
            counts[TYPE_SPOT],
            counts[TYPE_DIRECTIONAL],
            counts[TYPE_SKY],
        ))
        for row in rows:
            handle.write(LIGHT.pack(*row))

    report = {
        "format": "XZEN",
        "version": VERSION,
        "bytes": args.output.stat().st_size,
        "lightCount": len(rows),
        "pointCount": counts[TYPE_POINT],
        "spotCount": counts[TYPE_SPOT],
        "directionalCount": counts[TYPE_DIRECTIONAL],
        "skyCount": counts[TYPE_SKY],
        "lights": report_rows,
    }

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        "XZIEL_UE_XZEN_GREEN",
        json.dumps(
            {k: v for k, v in report.items() if k != "lights"},
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
