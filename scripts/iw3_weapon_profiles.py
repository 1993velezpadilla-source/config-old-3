#!/usr/bin/env python3
"""Translate authentic KisakCOD/CoD4 .weapon position fields to a Vril C table.

Geometry/material/rig and XAnim are NOT transferred by this metadata adapter.
Model map names MUST refer to independently converted Vril model assets.
Does not bundle any proprietary .weapon files or game assets.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import re

FIELDS = {
    "stand_move": ("standMoveF", "standMoveR", "standMoveU"),
    "stand_rot": ("standRotP", "standRotY", "standRotR"),
    "ducked_ofs": ("duckedOfsF", "duckedOfsR", "duckedOfsU"),
    "prone_ofs": ("proneOfsF", "proneOfsR", "proneOfsU"),
}
SCALARS = ("adsAimPitch", "posMoveRate")
NUMBERS = {x for group in FIELDS.values() for x in group} | set(SCALARS)
ASCII_NAME = re.compile(r"^models/weapons/iw3/[a-zA-Z0-9_./-]+\.mdl$")


def parse_weapon_file(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8-sig")
    result: dict[str, float] = {}
    # CoD weapon files often use 'WEAPONFILE\\key\\value\\key\\value'.
    # Also allow one field per line for exported text fixtures.
    tokens = text.split("\\")
    if len(tokens) > 2:
        for i in range(len(tokens) - 1):
            key = tokens[i].strip()
            value = tokens[i + 1].strip()
            if key not in NUMBERS:
                continue
            if not value or "\n" in value or "\r" in value:
                raise ValueError(f"Malformed {key} in {path.name}")
            num = float(value)
            if not math.isfinite(num) or abs(num) > 100000:
                raise ValueError(f"Bad numeric {key} in {path.name}")
            result[key] = num
    else:
        for line in text.splitlines():
            parts = re.split(r"\s*=\s*|\s+", line.strip(), maxsplit=1)
            if len(parts) != 2 or parts[0] not in NUMBERS:
                continue
            value = float(parts[1].strip())
            if not math.isfinite(value) or abs(value) > 100000:
                raise ValueError(f"Bad numeric field {parts[0]}")
            result[parts[0]] = value
    if not result:
        raise ValueError(f"No valid IW3 weapon pose fields: {path}")
    return result


def render_header(rows: list[tuple[str, dict[str, float]]]) -> str:
    lines = [
        "/* IW3 pose metadata only; exported from caller-supplied .weapon files. */",
        "#ifndef VIRIL_IW3_GENERATED_PROFILES_H",
        "#define VIRIL_IW3_GENERATED_PROFILES_H",
        "static const iw3_weapon_pose_t iw3_pose_table[] = {",
    ]
    for mdl, fields in rows:
        parts = []
        for key in FIELDS:
            xyz = (fields.get(v, 0.0) for v in FIELDS[key])
            parts.append("{" + ", ".join(f"{x:.9g}f" if x else "0.0f" for x in xyz) + "}")
        parts.extend(
            (f"{fields.get(k, 0.0):.9g}f" if fields.get(k, 0.0) else "0.0f")
            for k in SCALARS
        )
        lines.append("    {" + json.dumps(mdl) + ", " + ", ".join(parts) + "},")
    if not rows:
        lines.append("    {0, {0,0,0}, {0,0,0}, {0,0,0}, {0,0,0}, 0, 0},")
    lines.extend(["};", f"#define IW3_POSE_TABLE_SIZE {len(rows)}u", "#endif", ""])
    return "\n".join(lines)


def generate(definitions: Path, mapping: Path) -> str:
    data = json.loads(mapping.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Mapping must be a JSON array of {definition, viewmodel}")
    rows = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Invalid weapon mapping")
        definition = item.get("definition", "")
        viewmodel = item.get("viewmodel", "")
        if not isinstance(definition, str) or not re.fullmatch(
                r"[A-Za-z0-9_/-]+\.weapon", definition):
            raise ValueError("Invalid .weapon definition path")
        if ".." in Path(definition).parts:
            raise ValueError("Path traversal in weapon mapping")
        if not isinstance(viewmodel, str) or not ASCII_NAME.fullmatch(viewmodel):
            raise ValueError("Require .mdl converted path under models/weapons/iw3/")
        if viewmodel in seen:
            raise ValueError("Duplicate converted weapon model path")
        seen.add(viewmodel)
        fields = parse_weapon_file(definitions / definition)
        rows.append((viewmodel, fields))
    return render_header(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--definitions", type=Path, required=True)
    ap.add_argument("--mapping", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    header = generate(args.definitions, args.mapping)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(header, encoding="utf-8")
    print(f"Converted IW3 weapon profile source: {header.count('models/weapons/iw3/')} models")


if __name__ == "__main__":
    main()
