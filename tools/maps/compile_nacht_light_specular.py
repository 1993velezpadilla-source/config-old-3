#!/usr/bin/env python3
"""Compile authored UE light specular metadata for BO3 Nacht.

XZLS v1 is deliberately a sidecar to XZEN v2 so the proven 166-light
environment ABI remains untouched. Record order is exactly the source light
order used by compile_nacht_environment.py.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct

MAGIC = b"XZLS"
VERSION = 1
EXPECTED_LIGHTS = 166
HEADER = struct.Struct("<4sIII")
RECORD = struct.Struct("<Iff")

HAS_SPECULAR_SCALE = 1 << 0
HAS_INDIRECT_LIGHTING_INTENSITY = 1 << 1


def authored_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    if not math.isfinite(result):
        return None
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    doc = json.loads(args.source.read_text(encoding="utf-8"))
    lights = doc.get("lights")
    if not isinstance(lights, list) or len(lights) != EXPECTED_LIGHTS:
        raise SystemExit(
            f"expected {EXPECTED_LIGHTS} source lights, got "
            f"{len(lights) if isinstance(lights, list) else 'invalid'}"
        )

    records: list[tuple[int, float, float]] = []
    details: list[dict] = []
    specular_count = 0
    indirect_count = 0
    non_unity_specular_count = 0

    for index, light in enumerate(lights):
        if not isinstance(light, dict):
            raise SystemExit(f"malformed light row {index}")

        props = light.get("properties")
        if not isinstance(props, dict):
            raise SystemExit(f"missing light properties {index}")

        optional = props.get("optional")
        if not isinstance(optional, dict):
            optional = {}

        flags = 0
        specular = authored_float(optional.get("specularScale"))
        indirect = authored_float(
            optional.get("indirectLightingIntensity")
        )

        if specular is not None:
            if specular < 0.0 or specular > 64.0:
                raise SystemExit(
                    f"invalid specularScale at light {index}: {specular}"
                )
            flags |= HAS_SPECULAR_SCALE
            specular_count += 1
            if abs(specular - 1.0) > 1.0e-6:
                non_unity_specular_count += 1
        else:
            specular = 0.0

        if indirect is not None:
            if indirect < 0.0 or indirect > 64.0:
                raise SystemExit(
                    "invalid indirectLightingIntensity at "
                    f"light {index}: {indirect}"
                )
            flags |= HAS_INDIRECT_LIGHTING_INTENSITY
            indirect_count += 1
        else:
            indirect = 0.0

        records.append((flags, specular, indirect))
        details.append({
            "index": index,
            "id": light.get("id"),
            "componentType": light.get("componentType"),
            "sourcePath": light.get("sourcePath"),
            "flags": flags,
            "specularScale":
                specular if flags & HAS_SPECULAR_SCALE else None,
            "indirectLightingIntensity":
                indirect
                if flags & HAS_INDIRECT_LIGHTING_INTENSITY
                else None,
        })

    if specular_count == 0:
        raise SystemExit("no authored SpecularScale values found")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as out:
        out.write(HEADER.pack(
            MAGIC,
            VERSION,
            len(records),
            RECORD.size,
        ))
        for record in records:
            out.write(RECORD.pack(*record))

    report = {
        "format": "XZLS",
        "version": VERSION,
        "lightCount": len(records),
        "recordBytes": RECORD.size,
        "bytes": args.output.stat().st_size,
        "authoredSpecularCount": specular_count,
        "nonUnitySpecularCount": non_unity_specular_count,
        "authoredIndirectLightingCount": indirect_count,
        "records": details,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "XZIEL_NACHT_XZLS_OK",
        f"lights={len(records)}",
        f"specularAuthored={specular_count}",
        f"specularNonUnity={non_unity_specular_count}",
        f"indirectAuthored={indirect_count}",
        f"bytes={args.output.stat().st_size}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
