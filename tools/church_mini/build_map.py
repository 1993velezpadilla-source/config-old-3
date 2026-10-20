#!/usr/bin/env python3
"""XZIEL native Quake/NZ:P church V1: short nave, authentic Tripo furniture overlay."""
from pathlib import Path
import json

OUT = Path("build/church_mini/sanctum_mini.map")
OUT.parent.mkdir(parents=True, exist_ok=True)

def kv(key, value):
    return '"%s" "%s"\n' % (key, value)

def box(a, b, texture="bricks_temple_l"):
    x1,y1,z1=map(int,a)
    x2,y2,z2=map(int,b)
    assert x1<x2 and y1<y2 and z1<z2, (a,b)
    faces=[
        ((x1,y1,z1),(x1,y1+1,z1),(x1,y1,z1+1),"[ 0 -1 0 0 ]","[ 0 0 -1 0 ]"),
        ((x1,y1,z1),(x1,y1,z1+1),(x1+1,y1,z1),"[ 1 0 0 0 ]","[ 0 0 -1 0 ]"),
        ((x1,y1,z1),(x1+1,y1,z1),(x1,y1+1,z1),"[ -1 0 0 0 ]","[ 0 -1 0 0 ]"),
        ((x2,y2,z2),(x2,y2+1,z2),(x2+1,y2,z2),"[ 1 0 0 0 ]","[ 0 -1 0 0 ]"),
        ((x2,y2,z2),(x2+1,y2,z2),(x2,y2,z2+1),"[ -1 0 0 0 ]","[ 0 0 -1 0 ]"),
        ((x2,y2,z2),(x2,y2,z2+1),(x2,y2+1,z2),"[ 0 1 0 0 ]","[ 0 0 -1 0 ]")
    ]
    return "{\n"+"".join("( %d %d %d ) ( %d %d %d ) ( %d %d %d ) %s %s %s 0 1 1\n" %
        (*p,*q,*r,texture,u,v) for p,q,r,u,v in faces)+"}\n"

def point(name,xyz,**props):
    s="{\n"+kv("classname",name)
    for k,v in props.items():
        s+=kv(k,v)
    return s+kv("origin","%d %d %d"%xyz)+"}\n"

parts=['// XZIEL CHURCH MINI — original NZ:P gameplay, Tripo PBR furniture visual overlay\n',
       "{\n",kv("mapversion","220"),kv("classname","worldspawn"),
       kv("message","XZIEL CHURCH MINI"),kv("chaptertitle","THE CHAPEL"),
       kv("wad","../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad")]

# Sealed playable nave. Central aisle runs toward +Y (north).
parts.extend([
    box((-340,-520,-16),(340,520,0),"w_wood_floor_dr"),
    box((-340,-520,312),(340,520,328),"ceilings_y_di2"),
    box((-356,-520,0),(-340,520,328)),
    box((340,-520,0),(356,520,328)),
    box((-340,-536,0),(340,-520,328)),
    box((-340,520,0),(340,536,328)),
    # raised chancel platform beneath the authentic Tripo altar
    box((-180,320,0),(180,520,18),"w_wood_floor_dr"),
    # stone supports, placed away from the center combat aisle
    box((-306,-340,0),(-278,-312,300)),
    box((278,-340,0),(306,-312,300)),
    box((-306,260,0),(-278,288,300)),
    box((278,260,0),(306,288,300)),
])

# Real furniture meshes are loaded through XZSM. BSP uses hidden/simplified
# collision boxes (CLIP texture); never 1.9M-triangle collision mesh on Android.
for y in (-220,-80,60,200):
    for x in (-171,171):
        parts.append(box((x-93,y-28,0),(x+93,y+28,52),"CLIP"))
parts.append(box((-75,375,18),(75,460,108),"CLIP"))
parts.append("}\n")

for i,(x,y) in enumerate(((-42,-395),(42,-395),(-42,-450),(42,-450)),1):
    parts.append(point("info_player_%d_spawn"%i,(x,y,44),
        weapon="0",currentmag="0",currentammo="0",angle="90"))

for i,(x,y) in enumerate(((-250,390),(250,390),(-250,-35),(250,-35)),1):
    parts.append(point("spawn_zombie",(x,y,43),
        targetname="chapel_core",spawnflags="4"))

# One zone, deterministic combat gate; sprite conversion is separate.
parts.append("{\n"+kv("classname","spawn_zone")+kv("zone_name","chapel_core")+
    kv("adjacent_zones","")+kv("zone_target","chapel_core")+
    box((-320,-500,5),(320,500,300),"trigger")+"}\n")
for pos in ((0,-220,268),(0,75,268),(0,390,268),(-275,0,220),(275,0,220)):
    parts.append(point("light",pos,_light="300",wait="1",style="0"))

OUT.write_text("".join(parts),encoding="utf-8")
report={"map":str(OUT),"name":"sanctum_mini","geometry":"small sealed nave",
        "tripo_furniture":{"benches":8,"altars":1},
        "player_spawns":4,"zombie_spawns":4,
        "weapon_policy":"UNMODIFIED original NZ:P/Vril arsenal",
        "nun_sprite":"not yet mounted; do not mislabel stock zombie as PNG nun"}
(OUT.parent/"map_report.json").write_text(json.dumps(report,indent=2)+"\n")
print("XZIEL_CHURCH_MINI_MAP_GENERATED",json.dumps(report))
