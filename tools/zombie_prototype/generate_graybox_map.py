#!/usr/bin/env python3
"""Generate the minimal GREEN XZIEL: DEAD CELL arena.

Purpose: prove the native XZIEL/NZ:P round -> spawn -> combat loop on Android
with the smallest possible entity set. Art is intentionally graybox and all
geometry is replaceable later.
"""
from pathlib import Path
import json

MAP_NAME = "xziel_proto"
TITLE = "XZIEL: DEAD CELL // CORE"
OUT = Path(f"build/prototype/{MAP_NAME}.map")
REPORT = Path(f"build/prototype/{MAP_NAME}_report.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

ART = {
    "floor": "tiles_me",
    "ceiling": "ceilings_64",
    "wall": "facility_wall_l",
    "trigger": "trigger",
}

def kv(k, v):
    return f'"{k}" "{v}"\n'

def brush_box(mn, mx, texture="null"):
    x1, y1, z1 = map(int, mn)
    x2, y2, z2 = map(int, mx)
    planes = [
        ((x1,y1,z1),(x1,y1+1,z1),(x1,y1,z1+1),texture,"[ 0 -1 0 0 ]","[ 0 0 -1 0 ]"),
        ((x1,y1,z1),(x1,y1,z1+1),(x1+1,y1,z1),texture,"[ 1 0 0 0 ]","[ 0 0 -1 0 ]"),
        ((x1,y1,z1),(x1+1,y1,z1),(x1,y1+1,z1),texture,"[ -1 0 0 0 ]","[ 0 -1 0 0 ]"),
        ((x2,y2,z2),(x2,y2+1,z2),(x2+1,y2,z2),texture,"[ 1 0 0 0 ]","[ 0 -1 0 0 ]"),
        ((x2,y2,z2),(x2+1,y2,z2),(x2,y2,z2+1),texture,"[ -1 0 0 0 ]","[ 0 0 -1 0 ]"),
        ((x2,y2,z2),(x2,y2,z2+1),(x2,y2+1,z2),texture,"[ 0 1 0 0 ]","[ 0 0 -1 0 ]"),
    ]
    s = "{\n"
    for p1, p2, p3, t, u, v in planes:
        s += (
            f"( {p1[0]} {p1[1]} {p1[2]} ) "
            f"( {p2[0]} {p2[1]} {p2[2]} ) "
            f"( {p3[0]} {p3[1]} {p3[2]} ) "
            f"{t} {u} {v} 0 1 1\n"
        )
    return s + "}\n"

def point(classname, origin, props=None):
    s = "{\n" + kv("classname", classname) + kv("origin", f"{origin[0]} {origin[1]} {origin[2]}")
    for k, v in (props or {}).items():
        s += kv(k, v)
    return s + "}\n"

def brush_entity(classname, mn, mx, texture="trigger", props=None):
    s = "{\n" + kv("classname", classname)
    for k, v in (props or {}).items():
        s += kv(k, v)
    s += brush_box(mn, mx, texture)
    return s + "}\n"

parts = ["// XZIEL: DEAD CELL // CORE - minimum playable zombies arena\n"]
parts.append("{\n")
parts.append(kv("mapversion", "220"))
parts.append(kv("classname", "worldspawn"))
parts.append(kv("message", TITLE))
parts.append(kv("chaptertitle", "SURVIVE"))
parts.append(kv("location", "Dead Cell Core"))
parts.append(kv("person", "XZIEL"))
parts.append(kv("wad", "../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad"))

# 1280 x 960 sealed arena; geometry can be swapped without touching gameplay.
parts.append(brush_box((-640,-480,-32),(640,480,0), ART["floor"]))
parts.append(brush_box((-640,-480,256),(640,480,288), ART["ceiling"]))
parts.append(brush_box((-672,-480,0),(-640,480,256), ART["wall"]))
parts.append(brush_box((640,-480,0),(672,480,256), ART["wall"]))
parts.append(brush_box((-640,-512,0),(640,-480,256), ART["wall"]))
parts.append(brush_box((-640,480,0),(640,512,256), ART["wall"]))
# Simple central cover.
parts.append(brush_box((-72,-72,0),(72,72,64), ART["wall"]))
parts.append("}\n")

# Four co-op starts.
for i, (x, y, a) in enumerate([
    (-220,-100,0),(-220,100,0),(-100,-100,0),(-100,100,0)
], 1):
    parts.append(point(
        f"info_player_{i}_spawn", (x,y,40),
        {"weapon":"0","currentmag":"0","currentammo":"0","angle":str(a)},
    ))

# One active zone controls all four direct-combat zombie spawns.
parts.append(brush_entity(
    "spawn_zone", (-600,-440,4),(600,440,220), ART["trigger"],
    {"zone_name":"core","adjacent_zones":"","zone_target":"deadcell_core"},
))

# No window/path dependency in this GREEN core. spawnflags=4 means Start inside.
# This tests the authoritative round/spawn/combat loop directly.
for x, y, ang in [
    (500,-330,180),(500,330,180),(-500,-330,0),(-500,330,0)
]:
    parts.append(point("spawn_zombie",(x,y,40),{
        "targetname":"deadcell_core","spawnflags":"4","angle":str(ang),
    }))

# Lighting only; no optional machines or scripted progression in this gate.
for x, y in [(-320,-240),(320,-240),(-320,240),(320,240)]:
    parts.append(point("light",(x,y,180),{
        "_light":"320","wait":"1","style":"0","spawnflags":"0",
    }))

OUT.write_text("".join(parts), encoding="utf-8")
report = {
    "title": TITLE,
    "map": MAP_NAME,
    "mode": "minimal-green-core",
    "player_spawns": 4,
    "zones": 1,
    "zombie_spawns": 4,
    "barricades": 0,
    "doors": 0,
    "wall_buys": 0,
    "mystery_box_locations": 0,
    "perks": 0,
    "pack_a_punch": 0,
    "power_switch": 0,
    "purpose": "Prove native round/spawn/combat loop before restoring progression entities.",
}
REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(OUT)
print(REPORT)
