#!/usr/bin/env python3
"""Export a GREEN Quake/NZ:P graybox of SANCTUM OF ASH from the real St Giles scan plan.

The Blender pass remains the geometric authority. This exporter converts the scan-derived
zone bounds/floor levels into simple GoldSrc/Quake brushes so XZIEL can validate the
church layout on Android before final art is restored.
"""
import json, math, os
from pathlib import Path

PLAN = Path(os.environ.get("CHURCH_PLAN", "church/out/zombies_map_plan.json"))
OUT = Path(os.environ.get("NZP_MAP_OUT", "church/out/nzp_green/sanctum_green.map"))
OUT.parent.mkdir(parents=True, exist_ok=True)

plan = json.loads(PLAN.read_text(encoding="utf-8"))
zones = plan["zones"]
floors = plan.get("floor_levels", {})
interactives = plan["interactives"]

SCALE = 39.3700787402  # Blender metres -> Quake/Hammer-ish units
usable = {k:v for k,v in zones.items() if k != "other"}

mins = [min(v["min"][i] for v in usable.values()) for i in range(3)]
maxs = [max(v["max"][i] for v in usable.values()) for i in range(3)]
center = [(mins[i]+maxs[i])*0.5 for i in range(3)]

def qv(p):
    return tuple(int(round((float(p[i])-center[i])*SCALE)) for i in range(3))

def qfloor(zone_name):
    z = float(floors.get(zone_name, zones[zone_name]["min"][2]))
    return int(round((z-center[2])*SCALE))

def kv(k,v):
    return f'"{str(k).replace(chr(34), chr(39))}" "{str(v).replace(chr(34), chr(39))}"\n'

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
    out="{\n"
    for p1,p2,p3,t,u,v in planes:
        out+=f"( {p1[0]} {p1[1]} {p1[2]} ) ( {p2[0]} {p2[1]} {p2[2]} ) ( {p3[0]} {p3[1]} {p3[2]} ) {t} {u} {v} 0 1 1\n"
    return out+"}\n"

def point_entity(classname, origin, props=None):
    s="{\n"+kv("classname",classname)
    for k,v in (props or {}).items():
        if v is not None: s+=kv(k,v)
    s+=kv("origin",f"{int(origin[0])} {int(origin[1])} {int(origin[2])}")
    return s+"}\n"

# Exact scan-derived horizontal bounds.
zone_q={}
for name,info in usable.items():
    mn=qv(info["min"]); mx=qv(info["max"])
    zone_q[name]={"mn":mn,"mx":mx,"center":qv(info["center"]),"floor":qfloor(name)}

qmins=qv(mins); qmaxs=qv(maxs)
pad=192
wall=16
wx1=qmins[0]-pad; wy1=qmins[1]-pad
wx2=qmaxs[0]+pad; wy2=qmaxs[1]+pad
lowest=min(z["floor"] for z in zone_q.values())
highest=max(max(z["mx"][2],z["floor"]+128) for z in zone_q.values())
wz1=lowest-160; wz2=highest+160

parts=[]
parts.append("// XZIEL SANCTUM OF ASH // GREEN Quake graybox\n")
parts.append("// Scan-derived from St Giles Cripplegate (artfletch, CC BY).\n")
parts.append("{\n")
parts.append(kv("mapversion","220"))
parts.append(kv("classname","worldspawn"))
parts.append(kv("message","XZIEL: SANCTUM OF ASH"))
parts.append(kv("chaptertitle","SANCTUM OF ASH"))
parts.append(kv("location","Fallen Sanctuary"))
parts.append(kv("person","XZIEL"))
parts.append(kv("wad","../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad"))

# World safety shell.
parts.append(brush_box((wx1,wy1,wz1-16),(wx2,wy2,wz1),"tiles_me"))
parts.append(brush_box((wx1,wy1,wz2),(wx2,wy2,wz2+16),"ceilings_64"))
parts.append(brush_box((wx1-16,wy1,wz1),(wx1,wy2,wz2),"facility_wall_l"))
parts.append(brush_box((wx2,wy1,wz1),(wx2+16,wy2,wz2),"facility_wall_l"))
parts.append(brush_box((wx1,wy1-16,wz1),(wx2,wy1,wz2),"facility_wall_l"))
parts.append(brush_box((wx1,wy2,wz1),(wx2,wy2+16,wz2),"facility_wall_l"))

# Scan-derived zone decks + low outlines. These preserve actual room/tower extents
# while staying forgiving for mobile movement.
floor_thick=16
curb_h=10
curb_w=10
zone_colors={name:"tiles_me" for name in zone_q}
for name,z in zone_q.items():
    mn,mx,fz=z["mn"],z["mx"],z["floor"]
    # clamp degenerate scan groups to a useful playable footprint
    x1,x2=mn[0],mx[0]; y1,y2=mn[1],mx[1]
    if x2-x1 < 96:
        c=(x1+x2)//2; x1,x2=c-48,c+48
    if y2-y1 < 96:
        c=(y1+y2)//2; y1,y2=c-48,c+48
    tex=zone_colors.get(name,"tiles_me")
    parts.append(brush_box((x1,y1,fz-floor_thick),(x2,y2,fz),tex))
    # low visible perimeter: preserves room silhouette without blocking navigation
    parts.append(brush_box((x1,y1,fz),(x2,y1+curb_w,fz+curb_h),"facility_wall_l"))
    parts.append(brush_box((x1,y2-curb_w,fz),(x2,y2,fz+curb_h),"facility_wall_l"))
    parts.append(brush_box((x1,y1,fz),(x1+curb_w,y2,fz+curb_h),"facility_wall_l"))
    parts.append(brush_box((x2-curb_w,y1,fz),(x2,y2,fz+curb_h),"facility_wall_l"))

# Connect the real scan zones with broad graybox step paths.
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
bridge_count=0
for a,b in links:
    if a not in zone_q or b not in zone_q: continue
    za,zb=zone_q[a],zone_q[b]
    ax,ay=za["center"][0],za["center"][1]
    bx,by=zb["center"][0],zb["center"][1]
    az,bz=za["floor"],zb["floor"]
    dist=math.hypot(bx-ax,by-ay)
    n=max(1,int(math.ceil(max(dist/48.0,abs(bz-az)/10.0))))
    n=min(n,120)
    for i in range(n+1):
        t=i/max(n,1)
        x=int(round(ax+(bx-ax)*t)); y=int(round(ay+(by-ay)*t)); z=int(round(az+(bz-az)*t))
        parts.append(brush_box((x-36,y-36,z-12),(x+36,y+36,z),"tiles_me"))
        bridge_count+=1

# Nave columns from the real main-church bounds to make the graybox read as a church.
if "main_church" in zone_q:
    z=zone_q["main_church"]; mn,mx,fz=z["mn"],z["mx"],z["floor"]
    sx,sy=mx[0]-mn[0],mx[1]-mn[1]
    long_x=sx>=sy
    for i in range(1,7):
        t=i/7.0
        if long_x:
            x=int(mn[0]+sx*t)
            ys=[int(mn[1]+sy*0.28),int(mn[1]+sy*0.72)]
            for y in ys:
                parts.append(brush_box((x-12,y-12,fz),(x+12,y+12,fz+144),"facility_wall_l"))
        else:
            y=int(mn[1]+sy*t)
            xs=[int(mn[0]+sx*0.28),int(mn[0]+sx*0.72)]
            for x in xs:
                parts.append(brush_box((x-12,y-12,fz),(x+12,y+12,fz+144),"facility_wall_l"))

parts.append("}\n")

def interactive(kind,name=None):
    xs=[o for o in interactives if o.get("kind")==kind]
    if name is not None:
        xs=[o for o in xs if o.get("name")==name]
    return xs

# Four co-op slots around the exact scan-derived courtyard start.
p=interactive("player_spawn","P1_START_COURTYARD")
if not p:
    p=interactive("player_spawn")
if not p:
    raise SystemExit("No scan-derived player spawn in church plan")
base=qv(p[0]["location"])
target=zone_q.get("main_church",{"center":(base[0]+1,base[1],base[2])})["center"]
angle=int(round(math.degrees(math.atan2(target[1]-base[1],target[0]-base[0]))))%360
for i,(ox,oy) in enumerate([(-24,-24),(24,-24),(-24,24),(24,24)],1):
    parts.append(point_entity(f"info_player_{i}_spawn",(base[0]+ox,base[1]+oy,base[2]+40),{
        "weapon":"0","currentmag":"0","currentammo":"0","angle":str(angle)
    }))

# GREEN combat pool: scan-derived exterior + nave spawn candidates, direct inside spawns.
# No window/path dependency yet; those are restored after this church geometry gate is stable.
safe_spawns=[]
for o in interactive("zombie_spawn"):
    zone=str((o.get("properties") or {}).get("zone",""))
    if zone in {"exterior","main_church"}:
        safe_spawns.append((o,zone))
for o,zone in safe_spawns:
    pos=qv(o["location"])
    parts.append(point_entity("spawn_zombie",(pos[0],pos[1],pos[2]+36),{
        "targetname":"sanctum_core","spawnflags":"4"
    }))

# One broad spawn zone is intentionally used for the GREEN gate.
parts.append("{\n"+kv("classname","spawn_zone")+kv("zone_name","sanctum_core")+kv("adjacent_zones","")+kv("zone_target","sanctum_core")+
             brush_box((wx1+32,wy1+32,wz1+16),(wx2-32,wy2-32,wz2-16),"trigger")+"}\n")

# Readable lighting across real zone centers.
for name,z in zone_q.items():
    cx,cy,_=z["center"]; fz=z["floor"]
    parts.append(point_entity("light",(cx,cy,fz+160),{"_light":"300","wait":"1","style":"0"}))

OUT.write_text("".join(parts),encoding="utf-8")
report={
    "map":str(OUT),
    "source":plan.get("source_building"),
    "scale":SCALE,
    "scan_bounds_m":{"min":mins,"max":maxs,"size":[maxs[i]-mins[i] for i in range(3)]},
    "quake_bounds":{"min":[wx1,wy1,wz1],"max":[wx2,wy2,wz2]},
    "zones":{k:{
        "floor":v["floor"],"min":list(v["mn"]),"max":list(v["mx"]),"center":list(v["center"])
    } for k,v in zone_q.items()},
    "player_spawns":4,
    "zombie_spawns":len(safe_spawns),
    "bridge_steps":bridge_count,
    "mode":"sanctum-green-scan-derived",
}
(OUT.parent/"sanctum_green_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
