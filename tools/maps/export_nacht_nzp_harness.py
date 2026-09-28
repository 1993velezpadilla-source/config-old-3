#!/usr/bin/env python3
"""
Generate a clean-room NZ:P gameplay harness for the XZIEL BO3 Nacht reference.

This map contains no Treyarch/Pavlov mesh or texture payload. It converts only
validated gameplay metadata into stock NZ:P server entities so XZIEL can test
rounds, doors, barricades, spawns and the one currently-native wall purchase
(Frag Grenades) before replacement visual geometry is mounted.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = Path(
    os.environ.get(
        "XZIEL_NACHT_REFERENCE",
        ROOT / "assets/nacht_reference/runtime_reference_v1.json",
    )
)
SYSTEM_PLACEMENTS = ROOT / "assets/nacht_reference/bo3_system_placements_v1.json"
OUT = Path(
    os.environ.get(
        "XZIEL_NACHT_MAP_OUT",
        ROOT / "build/nacht_harness/xziel_nacht_bo3.map",
    )
)
SUMMARY = Path(
    os.environ.get(
        "XZIEL_NACHT_HARNESS_SUMMARY",
        ROOT / "build/nacht_harness/xziel_nacht_bo3_harness.json",
    )
)

SCALE = 39.3700787402  # XZIEL shared meters -> Vril/Quake units.
W_GRENADE = 26
WORLD_PAD_M = 6.0
WORLD_WALL_UNITS = 16

# The Pavlov port exposes ten generic player-spawn candidates.  The first
# candidate sits directly inside a tall-grass card in the BO3 static scene,
# which is useful evidence but a terrible Android smoke-test camera.  Keep all
# ten candidates in the persisted reference; the gameplay harness selects four
# exact source positions with measured static-geometry clearance so first-frame
# visual validation starts inside the playable structure instead of foliage.
HARNESS_PLAYER_SPAWN_IDS = (
    "player_spawn_pavlov_spawn4",
    "player_spawn_pavlov_spawn5",
    "player_spawn_pavlov_spawn6",
    "player_spawn_pavlov_spawn7",
)


def quote(value: object) -> str:
    return str(value).replace("\\", "/").replace('"', "'")


def kv(key: str, value: object) -> str:
    return f'"{quote(key)}" "{quote(value)}"\n'


def qv(position_m: list[float] | tuple[float, float, float]) -> tuple[int, int, int]:
    return tuple(int(round(float(v) * SCALE)) for v in position_m)


def brush_box(
    mn: tuple[int, int, int],
    mx: tuple[int, int, int],
    texture: str = "null",
) -> str:
    x1, y1, z1 = map(int, mn)
    x2, y2, z2 = map(int, mx)
    if x2 <= x1:
        x2 = x1 + 1
    if y2 <= y1:
        y2 = y1 + 1
    if z2 <= z1:
        z2 = z1 + 1

    planes = [
        ((x1, y1, z1), (x1, y1 + 1, z1), (x1, y1, z1 + 1), "[ 0 -1 0 0 ]", "[ 0 0 -1 0 ]"),
        ((x1, y1, z1), (x1, y1, z1 + 1), (x1 + 1, y1, z1), "[ 1 0 0 0 ]", "[ 0 0 -1 0 ]"),
        ((x1, y1, z1), (x1 + 1, y1, z1), (x1, y1 + 1, z1), "[ -1 0 0 0 ]", "[ 0 -1 0 0 ]"),
        ((x2, y2, z2), (x2, y2 + 1, z2), (x2 + 1, y2, z2), "[ 1 0 0 0 ]", "[ 0 -1 0 0 ]"),
        ((x2, y2, z2), (x2 + 1, y2, z2), (x2, y2, z2 + 1), "[ -1 0 0 0 ]", "[ 0 0 -1 0 ]"),
        ((x2, y2, z2), (x2, y2, z2 + 1), (x2, y2 + 1, z2), "[ 0 1 0 0 ]", "[ 0 0 -1 0 ]"),
    ]
    out = "{\n"
    for p1, p2, p3, u, v in planes:
        out += (
            f"( {p1[0]} {p1[1]} {p1[2]} ) "
            f"( {p2[0]} {p2[1]} {p2[2]} ) "
            f"( {p3[0]} {p3[1]} {p3[2]} ) "
            f"{texture} {u} {v} 0 1 1\n"
        )
    return out + "}\n"


def point_entity(
    classname: str,
    origin: tuple[int, int, int],
    props: dict[str, object] | None = None,
) -> str:
    out = "{\n" + kv("classname", classname)
    if props:
        for key, value in props.items():
            if value is not None:
                out += kv(key, value)
    out += kv("origin", f"{origin[0]} {origin[1]} {origin[2]}")
    return out + "}\n"


def brush_entity(
    classname: str,
    mn: tuple[int, int, int],
    mx: tuple[int, int, int],
    props: dict[str, object] | None = None,
    texture: str = "trigger",
) -> str:
    out = "{\n" + kv("classname", classname)
    if props:
        for key, value in props.items():
            if value is not None:
                out += kv(key, value)
    out += brush_box(mn, mx, texture)
    return out + "}\n"


reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
system_placements = json.loads(SYSTEM_PLACEMENTS.read_text(encoding="utf-8"))

box_placements = [
    row for row in system_placements.get("entities", [])
    if row.get("type") == "mystery_box"
]
assert len(box_placements) == 1
mystery_box_placement = box_placements[0]
mystery_box_transform = mystery_box_placement["transform"]
mystery_box_position_m = [
    mystery_box_transform["position"]["x"],
    mystery_box_transform["position"]["y"],
    mystery_box_transform["position"]["z"],
]
mystery_box_yaw = float(
    (mystery_box_transform.get("rotationDegrees") or {}).get("yaw", 0.0)
)

assert reference["runtimePolicy"]["serverAuthoritative"] is True
assert reference["runtimePolicy"]["maximumPlayers"] == 4
assert reference["runtimePolicy"]["maximumActiveZombies"] == 24
assert reference["runtimePolicy"]["startingPoints"] == 500
assert len(reference["purchases"]) == 9
assert len(reference["doors"]) == 3
assert len(reference["barricades"]) == 12
assert len(reference["zombieSpawns"]) == 21
assert len(reference["playerSpawns"]) >= 4

player_spawns_by_id = {
    spawn["id"]: spawn
    for spawn in reference["playerSpawns"]
}
missing_harness_spawns = [
    spawn_id
    for spawn_id in HARNESS_PLAYER_SPAWN_IDS
    if spawn_id not in player_spawns_by_id
]
if missing_harness_spawns:
    raise SystemExit(
        "missing harness player spawns: "
        + ", ".join(missing_harness_spawns)
    )
harness_player_spawns = [
    player_spawns_by_id[spawn_id]
    for spawn_id in HARNESS_PLAYER_SPAWN_IDS
]

native_purchases = [
    p for p in reference["purchases"]
    if p["logicalItemId"] == "frag_grenade"
]
blocked_purchases = [
    p for p in reference["purchases"]
    if p["logicalItemId"] != "frag_grenade"
]
assert len(native_purchases) == 1
assert len(blocked_purchases) == 8

all_positions: list[list[float]] = []
for group in ("purchases", "doors", "barricades", "zombieSpawns", "playerSpawns"):
    all_positions.extend(item["positionMeters"] for item in reference[group])
all_positions.append(mystery_box_position_m)

mins_m = [min(p[i] for p in all_positions) for i in range(3)]
maxs_m = [max(p[i] for p in all_positions) for i in range(3)]

world_min = qv((
    mins_m[0] - WORLD_PAD_M,
    mins_m[1] - WORLD_PAD_M,
    min(-1.25, mins_m[2] - 0.5),
))
world_max = qv((
    maxs_m[0] + WORLD_PAD_M,
    maxs_m[1] + WORLD_PAD_M,
    max(8.0, maxs_m[2] + 2.0),
))

wx1, wy1, wz1 = world_min
wx2, wy2, wz2 = world_max

parts: list[str] = []
parts.append(
    "// XZIEL Engine BO3 Nacht gameplay harness\n"
    "// Metadata-only clean-room validation map; no third-party BO3/Pavlov asset payload.\n"
    f"// Shared scale: {SCALE:.10f} Vril/Quake units per meter.\n"
)

# Sealed test shell. This is NOT final Nacht architecture/collision.
parts.append("{\n")
parts.append(kv("mapversion", "220"))
parts.append(kv("classname", "worldspawn"))
parts.append(kv("message", "XZIEL NACHT BO3 GAMEPLAY HARNESS"))
parts.append(kv("chaptertitle", "XZIEL NACHT BO3"))
parts.append(kv("location", "Reference Gameplay Harness"))
parts.append(kv("person", "XZIEL Engine"))
parts.append(kv("wad", "../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad"))
parts.append(brush_box((wx1, wy1, wz1 - WORLD_WALL_UNITS), (wx2, wy2, wz1), "tiles_me"))
parts.append(brush_box((wx1, wy1, wz2), (wx2, wy2, wz2 + WORLD_WALL_UNITS), "ceilings_64"))
parts.append(brush_box((wx1 - WORLD_WALL_UNITS, wy1, wz1), (wx1, wy2, wz2), "facility_wall_l"))
parts.append(brush_box((wx2, wy1, wz1), (wx2 + WORLD_WALL_UNITS, wy2, wz2), "facility_wall_l"))
parts.append(brush_box((wx1, wy1 - WORLD_WALL_UNITS, wz1), (wx2, wy1, wz2), "facility_wall_l"))
parts.append(brush_box((wx1, wy2, wz1), (wx2, wy2 + WORLD_WALL_UNITS, wz2), "facility_wall_l"))

# Broad upper validation deck so upstairs spawns/barricades exist on a stable
# collision layer during CI. Final geometry will replace this harness proxy.
upper_z = int(round(3.35 * SCALE))
parts.append(
    brush_box(
        (wx1 + 64, wy1 + 64, upper_z - 12),
        (wx2 - 64, wy2 - 64, upper_z),
        "null",
    )
)
parts.append("}\n")

# Four exact reference spawn candidates. They remain Pavlov-port spatial
# references, not claimed as Treyarch-authored canonical player-start
# identities.  Selection is explicit instead of extraction-order-dependent.
for index, spawn in enumerate(harness_player_spawns, start=1):
    parts.append(
        point_entity(
            f"info_player_{index}_spawn",
            qv(spawn["positionMeters"]),
            {"weapon": "0", "currentmag": "0", "currentammo": "0", "angle": "0"},
        )
    )

# Real NZ:P barricade entities: six boards, server-side repair/damage behavior.
for index, barricade in enumerate(reference["barricades"]):
    parts.append(
        point_entity(
            "item_barricade",
            qv(barricade["positionMeters"]),
            {
                "model": "models/misc/window.mdl",
                "skin": "0",
                "health": str(barricade["maximumBoards"]),
                "health_delay": str(barricade["maximumBoards"]),
                "oldmodel": "sounds/misc/barricade.wav",
                "aistatus": "sounds/misc/barricade_destroy.wav",
                "spawnflags": "0",
                "targetname": f"xz_win_{index:02d}",
                "angle": "0",
            },
        )
    )

# Native NZ:P zombie spawns. Start-zone spawns are active immediately; the two
# locked zones start as spawn_zombie_in via spawnflag INACTIVE and are activated
# by door target chains. Riser bit matches the validated reference metadata.
zone_groups = {
    "start_zone": "xz_start_spawns",
    "box_zone": "xz_box_spawns",
    "upstairs_zone": "xz_upstairs_spawns",
}
zone_counts = {key: 0 for key in zone_groups}

for spawn in reference["zombieSpawns"]:
    zone = spawn["zone"]
    zone_counts[zone] += 1
    spawnflags = 0
    if not spawn["activeDefault"]:
        spawnflags |= 1  # INACTIVE
    if spawn["riser"]:
        spawnflags |= 2  # native NZ:P riser bit

    linked = int(spawn["linkedBarricadeIndex"])
    assert 0 <= linked < len(reference["barricades"])

    parts.append(
        point_entity(
            "spawn_zombie",
            qv(spawn["positionMeters"]),
            {
                "spawnflags": str(spawnflags),
                "targetname": zone_groups[zone],
                "target": f"xz_win_{linked:02d}",
            },
        )
    )

assert zone_counts == {
    "start_zone": 10,
    "box_zone": 5,
    "upstairs_zone": 6,
}

# Door target relays fan one server-authoritative door purchase into all
# gameplay state that belongs to that newly accessible zone.
parts.append(
    point_entity(
        "trigger_relay",
        (0, 0, 0),
        {"targetname": "xz_unlock_box", "target": "xz_box_spawns"},
    )
)
parts.append(
    point_entity(
        "trigger_relay",
        (0, 0, 0),
        {
            "targetname": "xz_unlock_upstairs",
            "target": "xz_upstairs_spawns",
            "target2": "xz_upstairs_purchases",
        },
    )
)

# Native cost doors. Brush shape/orientation are harness placeholders centered
# on the validated exact door positions; final collision comes with final world
# geometry. Cost and topology are canonical runtime contracts.
door_target = {
    "door_start_to_box": "xz_unlock_box",
    "door_start_to_upstairs": "xz_unlock_upstairs",
    "door_box_to_upstairs": "xz_unlock_upstairs",
}

for door in reference["doors"]:
    x, y, z = qv(door["positionMeters"])
    parts.append(
        brush_entity(
            "func_door_nzp",
            (x - 24, y - 8, z - 40),
            (x + 24, y + 8, z + 48),
            {
                "cost": str(door["cost"]),
                "speed": "100",
                "sounds": "2",
                "wait": "4",
                "lip": "8",
                "distance": "64",
                "dmg": "0",
                "health": "0",
                "spawnflags": "0",
                "target": door_target[door["id"]],
            },
            "mechanical_door",
        )
    )

# The only purchase that is truly native today. NZ:P's W_GRENADE purchase path
# uses cost2 and restores primary grenades to four; keep cost too for explicit
# metadata symmetry. Starts inactive because this location is upstairs.
frag = native_purchases[0]
fx, fy, fz = qv(frag["positionMeters"])
radius_units = int(round(1.5 * SCALE))
parts.append(
    brush_entity(
        "buy_weapon",
        (fx - radius_units, fy - radius_units, fz - 40),
        (fx + radius_units, fy + radius_units, fz + 40),
        {
            "weapon": str(W_GRENADE),
            "cost": str(frag["cost"]),
            "cost2": str(frag["cost"]),
            "pap_cost": "4500",
            "spawnflags": "1",
            "targetname": "xz_upstairs_purchases",
            "useprint_string_1": "Hold %b to buy Frag Grenades",
            "useprint_string_2": "Hold %b to buy Frag Grenades",
        },
        "trigger",
    )
)

# Native NZ:P Mystery Box at the persisted BO3 Nacht reference anchor.
# Weapon rewards are controlled by the generated maps/xziel_nacht_bo3.mb2
# readiness allow-list. The QuakeC patch refuses purchases when that list has
# zero ready weapons, so development builds cannot charge the player for an
# invisible/incomplete reward.
box_props = mystery_box_placement.get("properties", {})
parts.append(
    point_entity(
        "mystery_box",
        qv(mystery_box_position_m),
        {
            "angles": f"0 {mystery_box_yaw:.6f} 0",
            "cost": str(int(box_props.get("cost", 950))),
            "model": "models/machines/mystery.mdl",
            "weapon2model": "models/machines/mglow$.mdl",
            "oldmodel": "sounds/machines/mbox_open.wav",
            "powerup_vo": "sounds/machines/mbox_close.wav",
            "spawnflags": "0",
            "useprint_string_1": "Hold %b for Mystery Box",
            "useprint_string_2": "Hold %b for %s",
        },
    )
)

# Lighting only exists to make Android smoke screenshots non-flat.
center_x = (wx1 + wx2) // 2
center_y = (wy1 + wy2) // 2
parts.append(point_entity("light", (center_x, center_y, wz1 + 180), {"_light": "350", "style": "0"}))
parts.append(point_entity("light", (center_x, center_y, upper_z + 120), {"_light": "300", "style": "0"}))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("".join(parts), encoding="utf-8")

summary = {
    "schemaVersion": 1,
    "map": str(OUT),
    "mapId": "xziel_nacht_bo3",
    "serverAuthoritative": True,
    "scaleUnitsPerMeter": SCALE,
    "harnessGeometryOnly": True,
    "finalGeometryIncluded": False,
    "playerSpawnSelection": {
        "source": "pavlov_port_spatial_reference",
        "reason": "first_frame_static_geometry_clearance",
        "ids": list(HARNESS_PLAYER_SPAWN_IDS),
    },
    "counts": {
        "playerSpawns": 4,
        "zombieSpawns": len(reference["zombieSpawns"]),
        "startZombieSpawns": zone_counts["start_zone"],
        "boxZombieSpawns": zone_counts["box_zone"],
        "upstairsZombieSpawns": zone_counts["upstairs_zone"],
        "barricades": len(reference["barricades"]),
        "doors": len(reference["doors"]),
        "nativePurchases": len(native_purchases),
        "blockedBo3WeaponPurchases": len(blocked_purchases),
        "mysteryBoxes": 1,
    },
    "mysteryBox": {
        "id": mystery_box_placement["id"],
        "positionMeters": mystery_box_position_m,
        "yawDegrees": mystery_box_yaw,
        "cost": int(box_props.get("cost", 950)),
        "runtimePoolSidecar": "maps/xziel_nacht_bo3.mb2",
        "rewardPolicy": "runtime_ready_only",
        "emptyPoolBehavior": "deny_without_charge",
    },
    "nativePurchase": {
        "id": frag["id"],
        "displayName": frag["displayName"],
        "weapon": "W_GRENADE",
        "weaponId": W_GRENADE,
        "cost": frag["cost"],
        "startsInactive": True,
        "unlockRelay": "xz_unlock_upstairs",
    },
    "blockedBo3Weapons": [
        {
            "id": p["id"],
            "displayName": p["displayName"],
            "logicalItemId": p["logicalItemId"],
            "cost": p["cost"],
            "reason": "awaiting_native_weapon_definition",
        }
        for p in blocked_purchases
    ],
    "doorActivation": {
        "door_start_to_box": ["xz_box_spawns"],
        "door_start_to_upstairs": ["xz_upstairs_spawns", "xz_upstairs_purchases"],
        "door_box_to_upstairs": ["xz_upstairs_spawns", "xz_upstairs_purchases"],
    },
    "worldBoundsUnits": {"min": list(world_min), "max": list(world_max)},
}

SUMMARY.parent.mkdir(parents=True, exist_ok=True)
SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

print(json.dumps(summary, indent=2))
