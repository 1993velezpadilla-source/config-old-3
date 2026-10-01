#!/usr/bin/env python3
"""Build the deterministic SANCTUM GREEN Quake map from the measured St Giles snapshot."""
import json, math, os
from pathlib import Path

SNAP=Path(os.environ.get("SANCTUM_SNAPSHOT","tools/church_map/sanctum_st_giles_measurement.v1.json"))
OUT=Path(os.environ.get("NZP_MAP_OUT","church/out/nzp_green/sanctum_green.map"))
OUT.parent.mkdir(parents=True,exist_ok=True)
doc=json.loads(SNAP.read_text(encoding="utf-8"))
zones=doc["zones"]
qb=doc["quake_bounds"]

def kv(k,v):
    return f'"{k}" "{v}"\n'

def brush_box(mn,mx,texture="null"):
    x1,y1,z1=map(int,mn); x2,y2,z2=map(int,mx)
    if x2<=x1: x2=x1+1
    if y2<=y1: y2=y1+1
    if z2<=z1: z2=z1+1
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
        s+=f"( {p1[0]} {p1[1]} {p1[2]} ) ( {p2[0]} {p2[1]} {p2[2]} ) ( {p3[0]} {p3[1]} {p3[2]} ) {t} {u} {v} 0 1 1\n"
    return s+"}\n"

def point(classname,origin,props=None):
    s="{\n"+kv("classname",classname)
    for k,v in (props or {}).items():
        s+=kv(k,v)
    s+=kv("origin",f"{int(origin[0])} {int(origin[1])} {int(origin[2])}")
    return s+"}\n"

wx1,wy1,wz1=qb["min"]; wx2,wy2,wz2=qb["max"]
parts=["// XZIEL SANCTUM OF ASH - deterministic GREEN scan snapshot\n"]
parts.append("{\n")
for k,v in [
    ("mapversion","220"),("classname","worldspawn"),
    ("message","XZIEL: SANCTUM OF ASH"),
    ("chaptertitle","SANCTUM OF ASH"),
    ("location","Fallen Sanctuary"),("person","XZIEL"),
    ("wad","../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad")
]:
    parts.append(kv(k,v))

# Safety shell from exact measured Quake bounds.
wall=16
parts.append(brush_box((wx1,wy1,wz1-wall),(wx2,wy2,wz1),"tiles_me"))
parts.append(brush_box((wx1,wy1,wz2),(wx2,wy2,wz2+wall),"ceilings_64"))
parts.append(brush_box((wx1-wall,wy1,wz1),(wx1,wy2,wz2),"facility_wall_l"))
parts.append(brush_box((wx2,wy1,wz1),(wx2+wall,wy2,wz2),"facility_wall_l"))
parts.append(brush_box((wx1,wy1-wall,wz1),(wx2,wy1,wz2),"facility_wall_l"))
parts.append(brush_box((wx1,wy2,wz1),(wx2,wy2+wall,wz2),"facility_wall_l"))

# Real zone footprints/floors from the scan.
floor_thick=16; curb=10; curb_h=10
for name,z in zones.items():
    x1,y1,_=z["min"]; x2,y2,_=z["max"]; fz=z["floor"]
    if x2-x1<96:
        c=(x1+x2)//2; x1,x2=c-48,c+48
    if y2-y1<96:
        c=(y1+y2)//2; y1,y2=c-48,c+48
    parts.append(brush_box((x1,y1,fz-floor_thick),(x2,y2,fz),"tiles_me"))
    parts.append(brush_box((x1,y1,fz),(x2,y1+curb,fz+curb_h),"facility_wall_l"))
    parts.append(brush_box((x1,y2-curb,fz),(x2,y2,fz+curb_h),"facility_wall_l"))
    parts.append(brush_box((x1,y1,fz),(x1+curb,y2,fz+curb_h),"facility_wall_l"))
    parts.append(brush_box((x2-curb,y1,fz),(x2,y2,fz+curb_h),"facility_wall_l"))

# Broad step paths following the church progression graph.
links=[
 ("exterior","main_church"),
 ("main_church","office_corridor"),
 ("office_corridor","office"),
 ("office_corridor","boiler"),
 ("main_church","tower_stairs"),
 ("tower_stairs","ringing_chamber"),
 ("ringing_chamber","clock_chamber"),
 ("clock_chamber","roof_chamber"),
 ("roof_chamber","tower_top"),
]
bridge_steps=0
for a,b in links:
    if a not in zones or b not in zones: continue
    za,zb=zones[a],zones[b]
    ax,ay,_=za["center"]; bx,by,_=zb["center"]
    az,bz=za["floor"],zb["floor"]
    dist=math.hypot(bx-ax,by-ay)
    n=max(1,int(math.ceil(max(dist/48.0,abs(bz-az)/10.0))))
    n=min(n,120)
    for i in range(n+1):
        t=i/max(n,1)
        x=round(ax+(bx-ax)*t); y=round(ay+(by-ay)*t); z=round(az+(bz-az)*t)
        parts.append(brush_box((x-36,y-36,z-12),(x+36,y+36,z),"tiles_me"))
        bridge_steps+=1

# Nave columns so the blockout reads as church architecture.
m=zones["main_church"]; x1,y1,_=m["min"]; x2,y2,_=m["max"]; fz=m["floor"]
sx,sy=x2-x1,y2-y1
if sx>=sy:
    for i in range(1,7):
        x=int(x1+sx*(i/7))
        for y in (int(y1+sy*0.28),int(y1+sy*0.72)):
            parts.append(brush_box((x-12,y-12,fz),(x+12,y+12,fz+144),"facility_wall_l"))
else:
    for i in range(1,7):
        y=int(y1+sy*(i/7))
        for x in (int(x1+sx*0.28),int(x1+sx*0.72)):
            parts.append(brush_box((x-12,y-12,fz),(x+12,y+12,fz+144),"facility_wall_l"))

parts.append("}\n")

# Spawn in the exterior on the side with the biggest clearance from the nave.
e=zones["exterior"]; m=zones["main_church"]
emn=e["min"]; emx=e["max"]; mmn=m["min"]; mmx=m["max"]; mc=m["center"]
choices=[
    (mmn[0]-emn[0],(mmn[0]-180,mc[1])),
    (emx[0]-mmx[0],(mmx[0]+180,mc[1])),
    (mmn[1]-emn[1],(mc[0],mmn[1]-180)),
    (emx[1]-mmx[1],(mc[0],mmx[1]+180)),
]
_,(px,py)=max(choices,key=lambda v:v[0])
px=max(emn[0]+64,min(emx[0]-64,px)); py=max(emn[1]+64,min(emx[1]-64,py))
pz=e["floor"]+40
angle=int(round(math.degrees(math.atan2(mc[1]-py,mc[0]-px))))%360
for i,(ox,oy) in enumerate([(-24,-24),(24,-24),(-24,24),(24,24)],1):
    parts.append(point(f"info_player_{i}_spawn",(px+ox,py+oy,pz),{
        "weapon":"0","currentmag":"0","currentammo":"0","angle":str(angle)
    }))

# Eight GREEN zombie spawns derived from the measured exterior+nave bounds.
def zone_candidates(name):
    z=zones[name]; mn=z["min"]; mx=z["max"]; c=z["center"]; zz=z["floor"]+36
    return [
        (int(mn[0]+(mx[0]-mn[0])*0.12),c[1],zz),
        (int(mx[0]-(mx[0]-mn[0])*0.12),c[1],zz),
        (c[0],int(mn[1]+(mx[1]-mn[1])*0.12),zz),
        (c[0],int(mx[1]-(mx[1]-mn[1])*0.12),zz),
    ]
spawns=zone_candidates("exterior")+zone_candidates("main_church")
for p in spawns:
    parts.append(point("spawn_zombie",p,{"targetname":"sanctum_core","spawnflags":"4"}))

parts.append("{\n"+kv("classname","spawn_zone")+kv("zone_name","sanctum_core")+kv("adjacent_zones","")+kv("zone_target","sanctum_core")+
             brush_box((wx1+32,wy1+32,wz1+16),(wx2-32,wy2-32,wz2-16),"trigger")+"}\n")

for name,z in zones.items():
    cx,cy,_=z["center"]
    parts.append(point("light",(cx,cy,z["floor"]+160),{"_light":"300","wait":"1","style":"0"}))

OUT.write_text("".join(parts),encoding="utf-8")
report={
    "map":str(OUT),
    "source":doc["source"],
    "source_uid":doc["source_uid"],
    "scan_bounds_m":doc["scan_bounds_m"],
    "quake_bounds":doc["quake_bounds"],
    "zones":doc["zones"],
    "player_spawns":4,
    "zombie_spawns":len(spawns),
    "bridge_steps":bridge_steps,
    "mode":"sanctum-green-frozen-scan-snapshot",
}
(OUT.parent/"sanctum_green_report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,indent=2))
