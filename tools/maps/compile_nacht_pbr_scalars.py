#!/usr/bin/env python3
"""Compile safe authored PBR scalar bindings for BO3 Nacht.

XZPB v1 is intentionally a sidecar to XZMT v1. It preserves the proven
base-color material ABI while carrying one fixed scalar record per static-scene
submesh. Only exact, physically meaningful scalar parameter names are accepted.
Out-of-range graph controls are rejected rather than clamped into misleading
PBR values.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import struct

MAGIC = b"XZPB"
VERSION = 1
EXPECTED_BINDINGS = 1063
HEADER = struct.Struct("<4sIIII")
RECORD = struct.Struct("<Iffff")

FLAG_ROUGHNESS = 1 << 0
FLAG_METALLIC = 1 << 1
FLAG_SPECULAR = 1 << 2
FLAG_EMISSIVE = 1 << 3
KNOWN_FLAGS = (
    FLAG_ROUGHNESS
    | FLAG_METALLIC
    | FLAG_SPECULAR
    | FLAG_EMISSIVE
)

DEFAULT_ROUGHNESS = 0.75
DEFAULT_METALLIC = 0.0
DEFAULT_SPECULAR = 0.5
DEFAULT_EMISSIVE = 0.0


def canonical_parameter(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def parse_scalar(row: dict) -> float | None:
    try:
        value = float(str(row.get("value", "")).strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--materials-report", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    material_report = json.loads(
        args.materials_report.read_text(encoding="utf-8")
    )

    scalar_rows = manifest.get("materialScalars", [])
    binding_materials = material_report.get("bindingMaterials", [])

    if len(binding_materials) != EXPECTED_BINDINGS:
        raise SystemExit(
            f"expected {EXPECTED_BINDINGS} binding materials, "
            f"got {len(binding_materials)}"
        )

    scalars_by_material: dict[str, dict[str, dict]] = {}
    for row in scalar_rows:
        material_path = str(row.get("materialPath", "")).strip().lower()
        parameter = canonical_parameter(str(row.get("parameter", "")))
        if not material_path or not parameter:
            continue
        scalars_by_material.setdefault(material_path, {}).setdefault(
            parameter,
            row,
        )

    specs = (
        (
            "roughness",
            FLAG_ROUGHNESS,
            ("roughness",),
            0.0,
            1.0,
            DEFAULT_ROUGHNESS,
        ),
        (
            "metallic",
            FLAG_METALLIC,
            ("metallic",),
            0.0,
            1.0,
            DEFAULT_METALLIC,
        ),
        (
            "specular",
            FLAG_SPECULAR,
            ("specularamount",),
            0.0,
            1.0,
            DEFAULT_SPECULAR,
        ),
        (
            "emissive",
            FLAG_EMISSIVE,
            ("emissive",),
            0.0,
            16.0,
            DEFAULT_EMISSIVE,
        ),
    )

    valid_counts = {name: 0 for name, *_ in specs}
    invalid_counts = {name: 0 for name, *_ in specs}
    alias_counts = {name: 0 for name, *_ in specs}
    records: list[tuple[int, float, float, float, float]] = []
    report_rows = []

    for binding_index, binding in enumerate(binding_materials):
        primary = str(binding.get("materialPath", "")).strip().lower()
        alias = str(binding.get("aliasMaterialPath", "")).strip().lower()

        values = {
            "roughness": DEFAULT_ROUGHNESS,
            "metallic": DEFAULT_METALLIC,
            "specular": DEFAULT_SPECULAR,
            "emissive": DEFAULT_EMISSIVE,
        }
        flags = 0
        sources = {}

        for (
            name,
            bit,
            accepted_names,
            min_value,
            max_value,
            default_value,
        ) in specs:
            selected = None
            selected_path = ""
            used_alias = False

            for material_path, is_alias in ((primary, False), (alias, True)):
                if not material_path:
                    continue
                rows = scalars_by_material.get(material_path, {})
                for parameter in accepted_names:
                    if parameter in rows:
                        selected = rows[parameter]
                        selected_path = material_path
                        used_alias = is_alias
                        break
                if selected is not None:
                    break

            if selected is None:
                values[name] = default_value
                continue

            value = parse_scalar(selected)
            if value is None or value < min_value or value > max_value:
                invalid_counts[name] += 1
                values[name] = default_value
                continue

            values[name] = value
            flags |= bit
            valid_counts[name] += 1
            if used_alias:
                alias_counts[name] += 1
            sources[name] = {
                "materialPath": selected_path,
                "parameter": str(selected.get("parameter", "")),
                "value": value,
                "alias": used_alias,
            }

        if flags & ~KNOWN_FLAGS:
            raise SystemExit("internal XZPB flag overflow")

        records.append((
            flags,
            values["roughness"],
            values["metallic"],
            values["specular"],
            values["emissive"],
        ))

        if flags:
            report_rows.append({
                "bindingIndex": binding_index,
                "materialPath": primary,
                "aliasMaterialPath": alias,
                "flags": flags,
                "roughness": values["roughness"],
                "metallic": values["metallic"],
                "specular": values["specular"],
                "emissive": values["emissive"],
                "sources": sources,
            })

    if len(records) != EXPECTED_BINDINGS:
        raise SystemExit("XZPB record count mismatch")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as out:
        out.write(HEADER.pack(
            MAGIC,
            VERSION,
            EXPECTED_BINDINGS,
            RECORD.size,
            0,
        ))
        for record in records:
            out.write(RECORD.pack(*record))

    expected_bytes = HEADER.size + EXPECTED_BINDINGS * RECORD.size
    actual_bytes = args.output.stat().st_size
    if actual_bytes != expected_bytes:
        raise SystemExit(
            f"XZPB size mismatch: expected {expected_bytes}, got {actual_bytes}"
        )

    authored_bindings = sum(1 for flags, *_ in records if flags != 0)
    report = {
        "schemaVersion": 1,
        "format": "XZPB",
        "version": VERSION,
        "bindingCount": EXPECTED_BINDINGS,
        "recordBytes": RECORD.size,
        "bytes": actual_bytes,
        "authoredBindingCount": authored_bindings,
        "validCounts": valid_counts,
        "invalidRejectedCounts": invalid_counts,
        "aliasResolvedCounts": alias_counts,
        "defaults": {
            "roughness": DEFAULT_ROUGHNESS,
            "metallic": DEFAULT_METALLIC,
            "specular": DEFAULT_SPECULAR,
            "emissive": DEFAULT_EMISSIVE,
        },
        "authoredBindings": report_rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "XZIEL_NACHT_XZPB_OK"
        f" bindings={EXPECTED_BINDINGS}"
        f" authored={authored_bindings}"
        f" roughness={valid_counts['roughness']}"
        f" metallic={valid_counts['metallic']}"
        f" specular={valid_counts['specular']}"
        f" emissive={valid_counts['emissive']}"
        f" rejectedMetallic={invalid_counts['metallic']}"
        f" rejectedSpecular={invalid_counts['specular']}"
        f" bytes={actual_bytes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
