#!/usr/bin/env python3
"""Build XZIEL: DEAD CELL, a functionality-first Zombies map for XZIEL/NZ:P.

This deliberately uses simple stock brush geometry and standard NZ:P gameplay
entities. The art layer is replaceable: walls, doors, barricades, props,
weapons, sounds and zombie presentation can be swapped later without changing
the round/economy/AI loop.

Gameplay authority remains in the XZIEL/NZ:P QuakeC runtime:
- server-authoritative rounds and zombie health/count scaling
- spawn zoning and barricade traversal
- points, purchases and power-up drops
- Mystery Box, perks and Pack-a-Punch
- mobile inventory/touch/gyro patches applied by prepare_android.sh
"""
from pathlib import Path
import json

MAP_NAME = "xziel_proto"
TITLE = "XZIEL: DEAD CELL"
OUT = Path(f"build/prototype/{MAP_NAME}.map")
REPORT = Path(f"build/prototype/{MAP_NAME}_report.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

# Replaceable art seam. Keep gameplay wiring intact and swap these paths later.
ART = {
    "floor": "tiles_me",
    "ceiling": "ceilings_64",
    "wall": "facility_wall_l",
    "door": "mechanical_door",
    "trigger": "trigger",
    "barricade_model": "models/misc/window.mdl",
    "barricade_rebuild_sfx": "sounds/misc/barricade.wav",
    "barricade_break_sfx": "sounds/misc/barricade_destroy.wav",
    "power_sfx": "sounds/machines/power.wav",
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

parts = []
parts.append("// XZIEL: DEAD CELL - gameplay-complete graybox\n")
parts.append("{\n")
parts.append(kv("mapversion", "220"))
parts.append(kv("classname", "worldspawn"))
parts.append(kv("message", TITLE))
parts.append(kv("chaptertitle", "SURVIVE THE CELL"))
parts.append(kv("location", "Dead Cell Bunker"))
parts.append(kv("person", "XZIEL"))
parts.append(kv("wad", "../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad"))

# Sealed three-room bunker. Exact geometry can later be replaced with authored art.
parts.append(brush_box((-1250,-950,-32),(1250,950,0), ART["floor"]))
parts.append(brush_box((-1250,-950,320),(1250,950,352), ART["ceiling"]))
parts.append(brush_box((-1282,-950,0),(-1250,950,320), ART["wall"]))
parts.append(brush_box((1250,-950,0),(1282,950,320), ART["wall"]))
parts.append(brush_box((-1250,-982,0),(1250,-950,320), ART["wall"]))
parts.append(brush_box((-1250,950,0),(1250,982,320), ART["wall"]))

# Paid progression gates.
for x in (-350, 350):
    parts.append(brush_box((x-16,-950,0),(x+16,-122,250), ART["wall"]))
    parts.append(brush_box((x-16,122,0),(x+16,950,250), ART["wall"]))

# Low cover to make the blockout readable as an FPS arena.
for mn, mx in [
    ((-980,-120,0),(-820,120,64)),
    ((-160,-110,0),(20,110,56)),
    ((650,-130,0),(820,130,72)),
]:
    parts.append(brush_box(mn, mx, ART["wall"]))
parts.append("}\n")

# Four co-op starts. NZ:P owns starting score/loadout policy.
for i, (x, y) in enumerate([(-760,-80),(-760,80),(-640,-80),(-640,80)], 1):
    parts.append(point(
        f"info_player_{i}_spawn",
        (x,y,40),
        {"weapon":"0","currentmag":"0","currentammo":"0","angle":"0"},
    ))

# Earn -> open -> expose new zombie pressure.
for x, cost in [(-350,1000),(350,1250)]:
    parts.append(brush_entity(
        "func_door_nzp",
        (x-18,-120,0),(x+18,120,112),
        ART["door"],
        {
            "speed":"100","sounds":"1","wait":"-1","lip":"8","distance":"96",
            "dmg":"0","health":"0","cost":str(cost),"spawnflags":"0",
        },
    ))

# Zone graph controls which spawn pool is eligible as doors open.
zones = [
    ("cell",(-1180,-880,4),(-365,880,280),"generator","deadcell_cell"),
    ("generator",(-335,-880,4),(335,880,280),"cell, armory","deadcell_generator"),
    ("armory",(365,-880,4),(1180,880,280),"generator","deadcell_armory"),
]
for name, mn, mx, adj, target in zones:
    parts.append(brush_entity(
        "spawn_zone", mn, mx, ART["trigger"],
        {"zone_name":name,"adjacent_zones":adj,"zone_target":target},
    ))

# Twelve zombie entry vectors, each routed through a six-board barricade.
spawn_defs = [
    ("cell",(-1100,-720,40),(-960,-620,40),(-850,-560,48),0),
    ("cell",(-1100,720,40),(-960,620,40),(-850,560,48),180),
    ("cell",(-540,-830,40),(-540,-690,40),(-540,-560,48),90),
    ("cell",(-540,830,40),(-540,690,40),(-540,560,48),270),
    ("generator",(-250,-830,40),(-250,-690,40),(-250,-560,48),90),
    ("generator",(-250,830,40),(-250,690,40),(-250,560,48),270),
    ("generator",(250,-830,40),(250,-690,40),(250,-560,48),90),
    ("generator",(250,830,40),(250,690,40),(250,560,48),270),
    ("armory",(540,-830,40),(540,-690,40),(540,-560,48),90),
    ("armory",(540,830,40),(540,690,40),(540,560,48),270),
    ("armory",(1100,-720,40),(960,-620,40),(850,-560,48),180),
    ("armory",(1100,720,40),(960,620,40),(850,560,48),0),
]
for i, (zone, sp, approach, win, angle) in enumerate(spawn_defs, 1):
    group = f"deadcell_{zone}"
    path = f"deadcell_path_{i}"
    window = f"deadcell_window_{i}"
    parts.append(point("spawn_zombie", sp, {
        "targetname":group,"target":path,"spawnflags":"0",
    }))
    parts.append(point("path_corner", approach, {
        "targetname":path,"target":window,"wait":"0","spawnflags":"0",
    }))
    parts.append(point("item_barricade", win, {
        "targetname":window,
        "model":ART["barricade_model"],
        "skin":"0","health":"6","health_delay":"6",
        "oldmodel":ART["barricade_rebuild_sfx"],
        "aistatus":ART["barricade_break_sfx"],
        "spawnflags":"0","angle":str(angle),
    }))

# Power and economy loop.
parts.append(point("power_switch",(0,-210,40),{
    "angle":"90","oldmodel":ART["power_sfx"],
}))
# One live Mystery Box plus relocation anchors. NZ:P's relocation path expects
# alternate locations to be mystery_box_tp_spot so the teddy model is
# precached before findboxspot() can use it.
parts.append(point("mystery_box",(-80,275,40),{
    "cost":"950","spawnflags":"0","angle":"90",
}))
parts.append(point("mystery_box_tp_spot",(655,270,40),{
    "angle":"180",
}))
parts.append(point("mystery_box_tp_spot",(980,-265,40),{
    "angle":"0",
}))
parts.append(point("perk_pap",(900,0,40),{
    "cost":"5000","angle":"180",
}))

# Match the mapper-facing NZ:P perk contract instead of writing the transient
# runtime requirespower field directly.
perk_defs = [
    ("perk_revive",(-900,270,40),500,1500,-1,1),
    ("perk_juggernog",(70,310,40),2500,2500,1,1),
    ("perk_speed",(620,-315,40),3000,3000,1,1),
    ("perk_double",(980,310,40),2000,2000,1,1),
]
for cls, pos, solo_cost, coop_cost, solo_power, coop_power in perk_defs:
    parts.append(point(cls, pos, {
        "cost":str(solo_cost),
        "cost2":str(coop_cost),
        "perk_requires_power_solo":str(solo_power),
        "perk_requires_power_coop":str(coop_power),
        "angle":"180",
    }))

# Wall-buy ladder. sequence is weapon id - 1 in NZ:P weapon_wall().
wall_buys = [
    ("m1",12,600,300,(-930,-315,48),0),
    ("mp40",15,1000,500,(-120,-315,48),0),
    ("trench",23,1500,750,(620,-315,48),0),
    ("thompson",3,1200,600,(1000,-315,48),0),
]
for name, weapon_id, cost, ammo, pos, angle in wall_buys:
    chalk = f"chalk_{name}"
    parts.append(point("weapon_wall", pos, {
        "targetname":chalk,"sequence":str(weapon_id - 1),
        "weapon":str(weapon_id),"cost":str(cost),"angle":str(angle),
    }))
    x,y,z = pos
    parts.append(brush_entity(
        "buy_weapon",(x-42,y-42,z-42),(x+42,y+42,z+42),ART["trigger"],
        {
            "weapon":str(weapon_id),"cost":str(cost),"cost2":str(ammo),
            "pap_cost":"4500","target":chalk,
        },
    ))

# Cheap grenade refill.
parts.append(brush_entity(
    "buy_weapon",(-40,500,16),(40,580,96),ART["trigger"],
    {"weapon":"26","cost":"250","cost2":"250","pap_cost":"250"},
))

# Readable lighting for mobile first-frame validation.
for p, val in [
    ((-760,0,220),300),((0,0,220),350),((760,0,220),320),((0,620,180),180),
]:
    parts.append(point("light", p, {"_light":str(val),"wait":"1","style":"0"}))

OUT.write_text("".join(parts), encoding="utf-8")
report = {
    "gameTitle": TITLE,
    "runtimeId": MAP_NAME,
    "map": str(OUT),
    "gameplayAuthority": "XZIEL/NZ:P QuakeC",
    "zones": len(zones),
    "playerSpawns": 4,
    "zombieSpawns": len(spawn_defs),
    "barricades": len(spawn_defs),
    "doors": 2,
    "wallBuys": len(wall_buys) + 1,
    "mysteryBoxLocations": 3,
    "mysteryBoxActive": 1,
    "mysteryBoxTeleportSpots": 2,
    "perks": 4,
    "packAPunch": 1,
    "powerSwitches": 1,
    "replaceableArt": ART,
    "goal": "complete playable Zombies loop with replaceable graybox art",
}
REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
