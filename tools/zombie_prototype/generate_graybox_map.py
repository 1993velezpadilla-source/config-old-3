#!/usr/bin/env python3
"""Generate a tiny ugly-but-functional Zombies graybox for XZIEL/NZ:P.

The point of this map is systems validation, not art. It intentionally uses
only stock NZ:P textures/models and standard gameplay entities so geometry and
assets can later be swapped without rewriting the Zombies loop.
"""
from pathlib import Path
import json

OUT = Path("build/prototype/xziel_proto.map")
OUT.parent.mkdir(parents=True, exist_ok=True)

def kv(k, v):
    return f'"{k}" "{v}"\n'

def brush_box(mn, mx, texture="null"):
    x1,y1,z1=map(int,mn); x2,y2,z2=map(int,mx)
    planes=[
      ((x1,y1,z1),(x1,y1+1,z1),(x1,y1,z1+1),texture,"[ 0 -1 0 0 ]","[ 0 0 -1 0 ]"),
      ((x1,y1,z1),(x1,y1,z1+1),(x1+1,y1,z1),texture,"[ 1 0 0 0 ]","[ 0 0 -1 0 ]"),
      ((x1,y1,z1),(x1+1,y1,z1),(x1,y1+1,z1),texture,"[ -1 0 0 0 ]","[ 0 -1 0 0 ]"),
      ((x2,y2,z2),(x2,y2+1,z2),(x2+1,y2,z2),texture,"[ 1 0 0 0 ]","[ 0 -1 0 0 ]"),
      ((x2,y2,z2),(x2+1,y2,z2),(x2,y2,z2+1),texture,"[ -1 0 0 0 ]","[ 0 0 -1 0 ]"),
      ((x2,y2,z2),(x2,y2,z2+1),(x2,y2+1,z2),texture,"[ 0 1 0 0 ]","[ 0 0 -1 0 ]"),
    ]
    s="{\n"
    for p1,p2,p3,t,u,v in planes:
        s += f"( {p1[0]} {p1[1]} {p1[2]} ) ( {p2[0]} {p2[1]} {p2[2]} ) ( {p3[0]} {p3[1]} {p3[2]} ) {t} {u} {v} 0 1 1\n"
    return s+"}\n"

def point(classname, origin, props=None):
    s="{\n"+kv("classname",classname)+kv("origin",f"{origin[0]} {origin[1]} {origin[2]}")
    for k,v in (props or {}).items():
        s += kv(k,v)
    return s+"}\n"

def brush_entity(classname, mn, mx, texture="trigger", props=None):
    s="{\n"+kv("classname",classname)
    for k,v in (props or {}).items():
        s += kv(k,v)
    s += brush_box(mn,mx,texture)
    return s+"}\n"

parts=[]
parts.append("// XZIEL Zombies Prototype - functionality-first graybox\n")
parts.append("{\n")
parts.append(kv("mapversion","220"))
parts.append(kv("classname","worldspawn"))
parts.append(kv("message","XZIEL ZOMBIES PROTOTYPE"))
parts.append(kv("chaptertitle","FUNCTIONALITY FIRST"))
parts.append(kv("location","Graybox Bunker"))
parts.append(kv("person","XZIEL"))
parts.append(kv("wad","../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad"))
# Large sealed shell.
parts.append(brush_box((-1250,-950,-32),(1250,950,0),"tiles_me"))
parts.append(brush_box((-1250,-950,320),(1250,950,352),"ceilings_64"))
parts.append(brush_box((-1282,-950,0),(-1250,950,320),"facility_wall_l"))
parts.append(brush_box((1250,-950,0),(1282,950,320),"facility_wall_l"))
parts.append(brush_box((-1250,-982,0),(1250,-950,320),"facility_wall_l"))
parts.append(brush_box((-1250,950,0),(1250,982,320),"facility_wall_l"))
# Simple divider walls; leave a central doorway gap at each divider.
for x in (-350,350):
    parts.append(brush_box((x-16,-950,0),(x+16,-120,240),"facility_wall_l"))
    parts.append(brush_box((x-16,120,0),(x+16,950,240),"facility_wall_l"))
parts.append("}\n")

# Four co-op spawns.
for i,(x,y) in enumerate([(-760,-60),(-760,60),(-650,-60),(-650,60)],1):
    parts.append(point(f"info_player_{i}_spawn",(x,y,40),{"weapon":"0","currentmag":"0","currentammo":"0","angle":"0"}))

# Cost doors separating the three rooms.
for x,cost in [(-350,1000),(350,1250)]:
    parts.append(brush_entity("func_door_nzp",(x-18,-118,0),(x+18,118,112),"mechanical_door",{
        "speed":"100","sounds":"1","wait":"-1","lip":"8","distance":"96","dmg":"0",
        "health":"0","cost":str(cost),"spawnflags":"0"
    }))

# Zones and their spawn groups.
zones=[
    ("spawn",(-1180,-880,4),(-365,880,280),"power","proto_spawn"),
    ("power",(-335,-880,4),(335,880,280),"spawn, upgrade","proto_power"),
    ("upgrade",(365,-880,4),(1180,880,280),"power","proto_upgrade"),
]
for name,mn,mx,adj,target in zones:
    parts.append(brush_entity("spawn_zone",mn,mx,"trigger",{
        "zone_name":name,"adjacent_zones":adj,"zone_target":target
    }))

# Zombie entries. Each spawn is chained through an approach node to a real
# barricade entity. The geometry is intentionally crude.
spawn_defs=[
    ("spawn",(-1080,-720,40),(-950,-620,40),(-850,-560,48),0),
    ("spawn",(-1080,720,40),(-950,620,40),(-850,560,48),180),
    ("spawn",(-520,-820,40),(-520,-680,40),(-520,-560,48),90),
    ("spawn",(-520,820,40),(-520,680,40),(-520,560,48),270),
    ("power",(-250,-820,40),(-250,-680,40),(-250,-560,48),90),
    ("power",(-250,820,40),(-250,680,40),(-250,560,48),270),
    ("power",(250,-820,40),(250,-680,40),(250,-560,48),90),
    ("power",(250,820,40),(250,680,40),(250,560,48),270),
    ("upgrade",(520,-820,40),(520,-680,40),(520,-560,48),90),
    ("upgrade",(520,820,40),(520,680,40),(520,560,48),270),
    ("upgrade",(1080,-720,40),(950,-620,40),(850,-560,48),180),
    ("upgrade",(1080,720,40),(950,620,40),(850,560,48),0),
]
for i,(zone,sp,approach,win,angle) in enumerate(spawn_defs,1):
    group=f"proto_{zone}"
    path=f"proto_path_{i}"
    window=f"proto_win_{i}"
    parts.append(point("spawn_zombie",sp,{"targetname":group,"target":path,"spawnflags":"0"}))
    parts.append(point("path_corner",approach,{"targetname":path,"target":window,"wait":"0","spawnflags":"0"}))
    parts.append(point("item_barricade",win,{
        "targetname":window,"model":"models/misc/window.mdl","skin":"0",
        "health":"6","health_delay":"6","oldmodel":"sounds/misc/barricade.wav",
        "aistatus":"sounds/misc/barricade_destroy.wav","spawnflags":"0","angle":str(angle)
    }))

# Power and core machines.
parts.append(point("power_switch",(0,-180,40),{"angle":"90","oldmodel":"sounds/machines/power.wav"}))
parts.append(point("mystery_box",(-80,260,40),{"cost":"950","spawnflags":"0","angle":"90"}))
# Two alternate box locations.
parts.append(point("mystery_box",(650,260,40),{"cost":"950","spawnflags":"1","angle":"180"}))
parts.append(point("mystery_box",(920,-260,40),{"cost":"950","spawnflags":"1","angle":"0"}))
parts.append(point("perk_pap",(850,0,40),{"cost":"5000","requirespower":"1","angle":"180"}))

# Perks.
for cls,pos,cost in [
    ("perk_revive",(-900,250,40),1500),
    ("perk_juggernog",(50,300,40),2500),
    ("perk_speed",(620,-300,40),3000),
    ("perk_double",(950,300,40),2000),
]:
    parts.append(point(cls,pos,{"cost":str(cost),"requirespower":"1","angle":"180"}))

# Wall buys: M1 Garand (12), MP40 (15), Trench Gun (23), Thompson (3).
wall_buys=[
    ("m1",12,600,300,(-900,-300,48),0),
    ("mp40",15,1000,500,(-80,-300,48),0),
    ("trench",23,1500,750,(650,-300,48),0),
    ("thompson",3,1200,600,(980,-300,48),0),
]
for name,wep,cost,ammo,pos,angle in wall_buys:
    chalk=f"chalk_{name}"
    # sequence is weapon id - 1 in weapon_wall().
    parts.append(point("weapon_wall",pos,{"targetname":chalk,"sequence":str(wep-1),"weapon":str(wep),"cost":str(cost),"angle":str(angle)}))
    x,y,z=pos
    parts.append(brush_entity("buy_weapon",(x-42,y-42,z-42),(x+42,y+42,z+42),"trigger",{
        "weapon":str(wep),"cost":str(cost),"cost2":str(ammo),"pap_cost":"4500","target":chalk
    }))

# Cheap grenade refill.
parts.append(brush_entity("buy_weapon",(-40,500,16),(40,580,96),"trigger",{
    "weapon":"26","cost":"250","cost2":"250","pap_cost":"250"
}))

# Lighting.
for p,val in [((-760,0,220),300),((0,0,220),350),((760,0,220),320)]:
    parts.append(point("light",p,{"_light":str(val),"wait":"1","style":"0"}))

OUT.write_text("".join(parts),encoding="utf-8")
report={
    "map":str(OUT),
    "zones":3,
    "playerSpawns":4,
    "zombieSpawns":len(spawn_defs),
    "doors":2,
    "wallBuys":len(wall_buys)+1,
    "mysteryBoxLocations":3,
    "perks":4,
    "packAPunch":1,
    "powerSwitches":1,
    "goal":"functional Zombies loop before final art",
}
Path("build/prototype/xziel_proto_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
