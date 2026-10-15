#!/usr/bin/env python3
"""Read the actual generated XZIEL Dead Cell .map and preserve its layout.

Dead Cell is deliberately made from axis-aligned Quake 220 brushes. Output
includes ALL brush bounds and ALL point-entity parameters, including zombie
spawn paths, perks, doors, barricades, Mystery Box and wall buys. This is a
visual/collision migration preview, not a recreation of QuakeC gameplay.
"""
import argparse
import json
import re
from pathlib import Path

KEY_VALUE = re.compile(r'^"([^"]+)"\s+"([^"]*)"')
POINT = re.compile(r'\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)')


def to_godot(xyz):
    x, y, z = map(float, xyz)
    return [-y / 64.0, z / 64.0, -x / 64.0]


def parse_map(path):
    entities = []
    current = None
    brush_faces = []
    depth = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if line == "{":
            depth += 1
            if depth == 1:
                current = {"properties": {}, "brushes": []}
            elif depth == 2:
                brush_faces = []
            elif depth > 2:
                raise ValueError(f"unexpected nested brush at line {line_number}")
        elif line == "}":
            if depth == 2:
                vertices = [p for face in brush_faces for p in face]
                if not vertices:
                    raise ValueError(f"empty brush at line {line_number}")
                mins = [min(p[axis] for p in vertices) for axis in range(3)]
                maxs = [max(p[axis] for p in vertices) for axis in range(3)]
                # Quake220 box brush source describes six planes using points
                # that can extend +1 unit off a face in other coordinates.
                # The normalized AABB is the graybox migration baseline.
                current["brushes"].append({"min_quake": mins, "max_quake": maxs})
            elif depth == 1:
                entities.append(current)
                current = None
            else:
                raise ValueError(f"unbalanced closing brace at line {line_number}")
            depth -= 1
        elif depth == 1:
            match = KEY_VALUE.match(line)
            if match:
                current["properties"][match.group(1)] = match.group(2)
        elif depth == 2:
            triplets = [tuple(map(float, p)) for p in POINT.findall(line)]
            if triplets:
                if len(triplets) != 3:
                    raise ValueError(f"unexpected brush face at line {line_number}")
                brush_faces.append(triplets)
    if depth != 0:
        raise ValueError("unclosed .map entity")
    result = {"map": "XZIEL: DEAD CELL", "units_per_meter": 64,
              "source": str(path), "brushes": [], "entities": []}
    for entry in entities:
        properties = entry["properties"]
        classname = properties.get("classname", "unknown")
        record = {"classname": classname, "properties": properties}
        origin = properties.get("origin", "")
        if origin:
            coords = origin.split()
            if len(coords) == 3:
                record["position"] = to_godot(coords)
        result["entities"].append(record)
        for brush in entry["brushes"]:
            mn = brush["min_quake"]
            mx = brush["max_quake"]
            center = [(mn[i] + mx[i]) / 2 for i in range(3)]
            dims = [(mx[i] - mn[i]) / 64 for i in range(3)]
            result["brushes"].append({
                "classname": classname,
                "position": to_godot(center),
                "size": [dims[1], dims[2], dims[0]],
                "visible": classname not in ("spawn_zone", "buy_weapon", "trigger_multiple"),
                "solid": classname in ("worldspawn", "func_door_nzp"),
                "properties": properties,
            })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = parse_map(args.map)
    if not data["brushes"] or not any(x["classname"] == "info_player_1_spawn" for x in data["entities"]):
        raise SystemExit("RED: map is missing world geometry or player spawn")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("DEAD_CELL_IMPORT_OK", len(data["brushes"]), "brushes",
          len(data["entities"]), "entities")


if __name__ == "__main__":
    main()
