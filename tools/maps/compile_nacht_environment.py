#!/usr/bin/env python3
"""Compile exact Nacht UE4 light components into XZIEL XZEN v2.

The source must come from tools/maps/NachtLightExtractor and therefore contains
all 166 serialized light components from Nacht_de_Untoten.umap, including each
component's complete AttachParent transform chain.

XZEN v2 keeps the v1 header and expands each light record to preserve the
authored lighting parameters needed by later renderer stages. Missing serialized
values remain distinguishable through presence flags; this compiler never
invents Unreal defaults.

Header <4sIIIIII>:
  magic, version, lightCount, pointCount, spotCount, directionalCount, skyCount

Light <II3f3f3f9fII>:
  type, presenceFlags,
  worldPosition.xyz meters in XZIEL basis,
  worldRotation.pitch/yaw/roll in UE degrees,
  color.rgb normalized 0..1,
  intensity,
  attenuationRadiusMeters,
  innerConeDegrees,
  outerConeDegrees,
  falloffExponent,
  temperatureKelvin,
  sourceRadiusMeters,
  softSourceRadiusMeters,
  sourceLengthMeters,
  intensityUnits,
  behaviorFlags
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

BEHAVIOR_INVERSE_SQUARED = 1 << 0
BEHAVIOR_USE_TEMPERATURE = 1 << 1
BEHAVIOR_CAST_SHADOWS = 1 << 2
BEHAVIOR_VISIBLE = 1 << 3

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

EXPECTED_LIGHTS = 166
EXPECTED_POINT = 144
EXPECTED_SPOT = 19
EXPECTED_DIRECTIONAL = 2
EXPECTED_SKY = 1


def matmul3(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)]
        for r in range(3)
    ]


def matmul4(a: list[float], b: list[float]) -> list[float]:
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


def ue_rotation_xziel(rot: dict) -> list[list[float]]:
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


def local_matrix(node: dict) -> list[float]:
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


def normalized_rotation(world: list[float]) -> list[list[float]]:
    cols = [
        [world[0], world[4], world[8]],
        [world[1], world[5], world[9]],
        [world[2], world[6], world[10]],
    ]
    out_cols = []
    for col in cols:
        length = math.sqrt(sum(v * v for v in col))
        if not math.isfinite(length) or length <= 1.0e-10:
            raise SystemExit("XZIEL XZEN rejected: singular light transform")
        out_cols.append([v / length for v in col])

    # Return row-major 3x3.
    return [
        [out_cols[0][0], out_cols[1][0], out_cols[2][0]],
        [out_cols[0][1], out_cols[1][1], out_cols[2][1]],
        [out_cols[0][2], out_cols[1][2], out_cols[2][2]],
    ]


def xziel_rotation_to_ue_rotator(rot: list[list[float]]) -> tuple[float, float, float]:
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

    return (
        math.degrees(pitch),
        math.degrees(yaw),
        math.degrees(roll),
    )


def world_transform(hierarchy: object) -> tuple[list[float], tuple[float, float, float]]:
    if not isinstance(hierarchy, list) or not hierarchy:
        raise SystemExit("XZIEL XZEN rejected: empty light hierarchy")

    world = IDENTITY4[:]
    # Extractor stores child -> parent. Compose root -> child.
    for node in reversed(hierarchy):
        if not isinstance(node, dict):
            raise SystemExit("XZIEL XZEN rejected: malformed hierarchy row")
        world = matmul4(world, local_matrix(node))

    if not all(math.isfinite(v) for v in world):
        raise SystemExit("XZIEL XZEN rejected: non-finite world transform")

    rotation = normalized_rotation(world)
    euler = xziel_rotation_to_ue_rotator(rotation)
    return world, euler


def color3(value: object) -> tuple[float, float, float]:
    if not isinstance(value, dict):
        raise SystemExit("XZIEL XZEN rejected: missing light color")
    try:
        return (
            max(0, min(255, int(value["R"]))) / 255.0,
            max(0, min(255, int(value["G"]))) / 255.0,
            max(0, min(255, int(value["B"]))) / 255.0,
        )
    except (KeyError, TypeError, ValueError):
        raise SystemExit("XZIEL XZEN rejected: malformed light color")


def optional_float(props: dict, key: str) -> tuple[bool, float]:
    value = props.get(key)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return True, float(value)
    return False, 0.0


def optional_bool(props: dict, key: str) -> tuple[bool, bool]:
    value = props.get(key)
    if isinstance(value, bool):
        return True, value
    return False, False


def compile_environment(source: Path, output: Path, report_path: Path | None) -> dict:
    doc = json.loads(source.read_text(encoding="utf-8"))

    if doc.get("schemaVersion") != 1:
        raise SystemExit("XZIEL XZEN rejected: unsupported light source schema")

    lights = doc.get("lights")
    if not isinstance(lights, list) or len(lights) != EXPECTED_LIGHTS:
        raise SystemExit(
            f"XZIEL XZEN rejected: expected {EXPECTED_LIGHTS} light components"
        )

    expected_types = {
        "point": EXPECTED_POINT,
        "spot": EXPECTED_SPOT,
        "directional": EXPECTED_DIRECTIONAL,
        "sky": EXPECTED_SKY,
    }
    source_counts = doc.get("typeCounts")
    if source_counts != expected_types:
        raise SystemExit(
            f"XZIEL XZEN rejected: source light census drift {source_counts!r}"
        )

    rows: list[tuple] = []
    report_rows: list[dict] = []
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
            raise SystemExit(f"XZIEL XZEN rejected: unknown light type {kind!r}")

        world, world_rot = world_transform(light.get("hierarchy"))
        position = (world[3], world[7], world[11])

        props = light.get("properties")
        if not isinstance(props, dict):
            raise SystemExit("XZIEL XZEN rejected: missing properties")

        color = color3(props.get("lightColor"))

        intensity_ok, intensity = optional_float(props, "intensity")
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

        if not intensity_ok:
            raise SystemExit("XZIEL XZEN rejected: intensity missing")
        if kind in ("point", "spot") and not (
            radius_ok and units_ok and inverse_ok and falloff_ok
            and source_radius_ok and soft_radius_ok and source_length_ok
        ):
            raise SystemExit(
                f"XZIEL XZEN rejected: point/spot payload incomplete at {index}"
            )
        if kind == "spot" and not (inner_ok and outer_ok):
            raise SystemExit(f"XZIEL XZEN rejected: spot cone missing at {index}")
        if kind != "sky" and not (temp_ok and use_temp_ok):
            raise SystemExit(f"XZIEL XZEN rejected: temperature missing at {index}")
        if not shadows_ok:
            raise SystemExit(f"XZIEL XZEN rejected: CastShadows missing at {index}")

        flags = (
            HAS_POSITION |
            HAS_ROTATION |
            HAS_COLOR |
            HAS_INTENSITY
        )
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

        behavior = 0
        if inverse:
            behavior |= BEHAVIOR_INVERSE_SQUARED
        if use_temp:
            behavior |= BEHAVIOR_USE_TEMPERATURE
        if cast_shadows:
            behavior |= BEHAVIOR_CAST_SHADOWS
        if visible:
            behavior |= BEHAVIOR_VISIBLE

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

        if not all(
            math.isfinite(float(v))
            for v in row[2:-2]
        ):
            raise SystemExit("XZIEL XZEN rejected: non-finite light record")

        rows.append(row)
        counts[light_type] += 1
        report_rows.append({
            "id": light.get("id"),
            "actorName": light.get("actorName"),
            "componentName": light.get("componentName"),
            "componentType": kind,
            "sourcePath": light.get("sourcePath"),
            "flags": flags,
            "behaviorFlags": behavior,
            "worldPositionMeters": list(position),
            "worldRotationUE": {
                "Pitch": world_rot[0],
                "Yaw": world_rot[1],
                "Roll": world_rot[2],
            },
            "color": list(color),
            "intensity": intensity,
            "radiusMeters": radius_cm / 100.0 if radius_ok else None,
            "innerConeDegrees": inner if inner_ok else None,
            "outerConeDegrees": outer if outer_ok else None,
            "falloffExponent": falloff if falloff_ok else None,
            "temperatureKelvin": temperature if temp_ok else None,
            "sourceRadiusMeters": source_radius_cm / 100.0 if source_radius_ok else None,
            "softSourceRadiusMeters": soft_radius_cm / 100.0 if soft_radius_ok else None,
            "sourceLengthMeters": source_length_cm / 100.0 if source_length_ok else None,
            "intensityUnits": units_name,
            "intensityUnitsEnum": units,
            "sourceHierarchyDepth": len(light.get("hierarchy") or []),
        })

    expected_counts = {
        TYPE_POINT: EXPECTED_POINT,
        TYPE_SPOT: EXPECTED_SPOT,
        TYPE_DIRECTIONAL: EXPECTED_DIRECTIONAL,
        TYPE_SKY: EXPECTED_SKY,
    }
    if counts != expected_counts:
        raise SystemExit(
            f"XZIEL XZEN rejected: compiled census drift {counts!r}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
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
        "withCone": sum(
            bool(row[1] & HAS_INNER_CONE) and bool(row[1] & HAS_OUTER_CONE)
            for row in rows
        ),
        "withTemperature": sum(bool(row[1] & HAS_TEMPERATURE) for row in rows),
        "withCastShadows": sum(bool(row[1] & HAS_CAST_SHADOWS) for row in rows),
        "lights": report_rows,
    }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        "XZIEL_NACHT_XZEN_OK",
        json.dumps(
            {k: v for k, v in report.items() if k != "lights"},
            sort_keys=True,
        ),
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    compile_environment(args.source, args.output, args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
