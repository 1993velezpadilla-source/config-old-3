"""Engine-agnostic ORIGINAL Black Pines layout contract.

Godot meters use (x, up=y, z). Unreal coordinates are (x, -z, y) in cm.
No commercial map or gameplay sources are imported.
"""
import json
from pathlib import Path


def read_layout(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data["schemaVersion"] == 1
    assert data["worldUnits"] == "meters"
    assert len(data["cells"]) == 9
    assert len(data["portals"]) == 12
    assert len(data["windows"]) == 12
    assert len(data["heroCollisionProxies"]) == 9
    assert len(data["perks"]) == 6
    assert len(data["mysterySpots"]) == 4
    assert data["endlessSurvival"] is True
    assert data["technicalGates"]["originalChurchFilesMayChange"] is False
    assert data["technicalGates"]["testSkeletonAssetsNotSafeForPublicRedistribution"] is True
    return data


def box(name, category, xyz, dimensions):
    if not all(float(n) > 0 for n in dimensions):
        raise ValueError((name, dimensions))
    return {
        "name": name,
        "category": category,
        "center": tuple(float(n) for n in xyz),
        "dimensions": tuple(float(n) for n in dimensions),
    }


def rooms(data):
    xs = data["cellBoundaries"]["x"]
    zs = data["cellBoundaries"]["z"]
    assert len(xs) == len(zs) == 4
    for room in data["cells"]:
        col, row = room["col"], room["row"]
        x0, x1 = xs[col], xs[col + 1]
        z0, z1 = zs[row], zs[row + 1]
        yield box(
            "BP_Floor_" + room["id"],
            "Floor",
            ((x0 + x1) / 2, data["floorY"] - 0.12, (z0 + z1) / 2),
            (x1 - x0, 0.24, z1 - z0),
        )


def wall_piece(axis, fixed, a, b, lower, upper, name):
    if not b > a or not upper > lower:
        raise ValueError((axis, fixed, a, b, lower, upper))
    h = upper - lower
    if axis == "x":
        return box(name, "Wall", (fixed, (lower + upper) / 2, (a + b) / 2),
                   (0.35, h, b - a))
    return box(name, "Wall", ((a + b) / 2, (lower + upper) / 2, fixed),
               (b - a, h, 0.35))


def walls(data):
    """Split original grid walls at every actual door and window opening."""
    xs = data["cellBoundaries"]["x"]
    zs = data["cellBoundaries"]["z"]
    height = float(data["wallHeight"])
    consumed = {"portal": set(), "window": set()}
    index = 0
    for axis, fixed_values, intervals in (("x", xs, zs), ("z", zs, xs)):
        for fixed in fixed_values:
            for low, high in zip(intervals[:-1], intervals[1:]):
                cuts = []
                for kind, rows in (("portal", data["portals"]), ("window", data["windows"])):
                    for n, entry in enumerate(rows):
                        if entry["axis"] != axis or abs(entry["coord"] - fixed) > 0.001:
                            continue
                        if not low <= entry["at"] < high:
                            continue
                        width = (3.0 if entry.get("type") == "rolling" else
                                 2.4 if entry.get("type") == "double" else
                                 1.65 if kind == "window" else 2.0)
                        cut_a, cut_b = entry["at"] - width / 2, entry["at"] + width / 2
                        if cut_a < low or cut_b > high:
                            raise ValueError("Opening extends wall segment: " + str(entry))
                        cuts.append((cut_a, cut_b, kind, n))
                cuts.sort(key=lambda e: e[0])
                cursor = low
                for a, b, kind, n in cuts:
                    if a < cursor - 0.001:
                        raise ValueError("Overlapping openings: " + str((axis, fixed, low, high)))
                    if a > cursor + 0.001:
                        yield wall_piece(axis, fixed, cursor, a, 0, height,
                                         "BP_Wall_%03d" % index)
                        index += 1
                    if kind == "portal":
                        yield wall_piece(axis, fixed, a, b, 2.7, height,
                                         "BP_PortalLintel_%02d" % n)
                    else:
                        yield wall_piece(axis, fixed, a, b, 0, 1.0,
                                         "BP_WindowSill_%02d" % n)
                        yield wall_piece(axis, fixed, a, b, 2.4, height,
                                         "BP_WindowLintel_%02d" % n)
                    consumed[kind].add(n)
                    cursor = b
                if high > cursor + 0.001:
                    yield wall_piece(axis, fixed, cursor, high, 0, height,
                                     "BP_Wall_%03d" % index)
                    index += 1
    if len(consumed["portal"]) != len(data["portals"]):
        raise ValueError("Not all portals placed: " + str(consumed["portal"]))
    if len(consumed["window"]) != len(data["windows"]):
        raise ValueError("Not all windows placed: " + str(consumed["window"]))


def hero_blockouts(data):
    for entry in data["heroCollisionProxies"]:
        yield box("BP_Hero_" + entry["id"], "HeroProxy",
                  entry["center"], entry["size"])


def markers(data):
    for i, entry in enumerate(data["portals"]):
        pos = ((entry["coord"], 0.1, entry["at"]) if entry["axis"] == "x"
               else (entry["at"], 0.1, entry["coord"]))
        yield ("Portal_%02d_%s" % (i, entry["type"]), pos)
    for i, entry in enumerate(data["windows"]):
        pos = ((entry["coord"], 1.4, entry["at"]) if entry["axis"] == "x"
               else (entry["at"], 1.4, entry["coord"]))
        yield ("Barricade_%02d" % i, pos)
    for entry in data["perks"]:
        yield ("Perk_" + entry["id"], entry["pos"])
    for entry in data["wallbuys"]:
        yield ("WallBuy_" + entry["id"], entry["pos"])
    for i, pos in enumerate(data["mysterySpots"]):
        yield ("MysteryBox_%02d" % i, pos)
    yield ("PowerSwitch", data["powerSwitch"])
    yield ("PackAPunch", data["packAPunch"])
    yield ("PlayerStartData", data["playerSpawn"])
    for i, pos in enumerate(data["outsideDirectSpawns"]):
        yield ("ZombieOutsideSpawn_%02d" % i, pos)
