#!/usr/bin/env python3
import json, math, os
from pathlib import Path

PACKAGE = Path(os.environ.get("CHURCH_PACKAGE", "church/out/SanctumOfAsh"))
PLAN = Path(os.environ.get("CHURCH_PLAN", "church/out/zombies_map_plan.json"))
OUT = Path(os.environ.get("NZP_MAP_OUT", "church/out/nzp_harness/sanctum_harness.map"))
FITTED = Path(os.environ.get("CHURCH_FITTED", "church/out/church_runtime_fitted_v2.json"))
NAV_SKELETON_ENV=os.environ.get("CHURCH_NAV_SKELETON","").strip()
NAV_SKELETON=Path(NAV_SKELETON_ENV) if NAV_SKELETON_ENV else None
OUT.parent.mkdir(parents=True, exist_ok=True)

zones_doc=json.loads((PACKAGE/"zones.json").read_text())
entities=json.loads((PACKAGE/"entities.json").read_text())["entities"]
spawns=json.loads((PACKAGE/"spawns.json").read_text())["spawns"]
plan=json.loads(PLAN.read_text())
fitted_doc=json.loads(FITTED.read_text()) if FITTED.exists() else {"barricades":[]}
fitted_by_spawn={x["spawn"]:x for x in fitted_doc.get("barricades",[])}
nav_doc=json.loads(NAV_SKELETON.read_text()) if NAV_SKELETON and NAV_SKELETON.exists() else None
if nav_doc and nav_doc.get("mode")!="floors_ramps_only":
    raise SystemExit(f"unsupported CHURCH_NAV_SKELETON mode: {nav_doc.get('mode')}")

SCALE=39.3700787402  # Blender meters -> Quake/Hammer-ish units
zone_raw=plan["zones"]

mins=[999999,999999,999999]; maxs=[-999999,-999999,-999999]
for z,info in zone_raw.items():
    if z=="other": continue
    for i,v in enumerate(info["min"]): mins[i]=min(mins[i],v)
    for i,v in enumerate(info["max"]): maxs[i]=max(maxs[i],v)
center=[(mins[i]+maxs[i])*0.5 for i in range(3)]

def qv(p):
    return tuple(int(round((p[i]-center[i])*SCALE)) for i in range(3))

def qraw(p):
    return tuple(int(round(p[i]*SCALE)) for i in range(3))

def quote(v):
    return str(v).replace("\\","/").replace('"',"'")

def kv(k,v):
    return f'"{quote(k)}" "{quote(v)}"\n'

def brush_box(mn,mx,texture="null"):
    x1,y1,z1=map(int,mn); x2,y2,z2=map(int,mx)
    if x2<=x1: x2=x1+1
    if y2<=y1: y2=y1+1
    if z2<=z1: z2=z1+1

    # Exact six-plane winding pattern used by NZ:P's official template.map.
    # Valve/GoldSrc MAP brushes are intersections of oriented half-spaces;
    # reversing these point orders turns finite boxes into effectively
    # infinite brushes, which HLCsg reports near +/-80000.
    planes=[
      # low X (+X normal)
      ((x1,y1,z1),(x1,y1+1,z1),(x1,y1,z1+1),texture,"[ 0 -1 0 0 ]","[ 0 0 -1 0 ]"),
      # low Y (+Y normal)
      ((x1,y1,z1),(x1,y1,z1+1),(x1+1,y1,z1),texture,"[ 1 0 0 0 ]","[ 0 0 -1 0 ]"),
      # low Z (+Z normal)
      ((x1,y1,z1),(x1+1,y1,z1),(x1,y1+1,z1),texture,"[ -1 0 0 0 ]","[ 0 -1 0 0 ]"),
      # high Z (-Z normal)
      ((x2,y2,z2),(x2,y2+1,z2),(x2+1,y2,z2),texture,"[ 1 0 0 0 ]","[ 0 -1 0 0 ]"),
      # high Y (-Y normal)
      ((x2,y2,z2),(x2+1,y2,z2),(x2,y2,z2+1),texture,"[ -1 0 0 0 ]","[ 0 0 -1 0 ]"),
      # high X (-X normal)
      ((x2,y2,z2),(x2,y2,z2+1),(x2,y2+1,z2),texture,"[ 0 1 0 0 ]","[ 0 0 -1 0 ]"),
    ]
    out="{\n"
    for p1,p2,p3,t,u,v in planes:
        out+=f"( {p1[0]} {p1[1]} {p1[2]} ) ( {p2[0]} {p2[1]} {p2[2]} ) ( {p3[0]} {p3[1]} {p3[2]} ) {t} {u} {v} 0 1 1\n"
    return out+"}\n"

def point_entity(classname, origin, props=None):
    s="{\n"+kv("classname",classname)
    if props:
        for k,v in props.items():
            if v is not None: s+=kv(k,v)
    s+=kv("origin",f"{origin[0]} {origin[1]} {origin[2]}")
    return s+"}\n"

# World shell.
qmins=qv(mins); qmaxs=qv(maxs)
pad=int(5*SCALE)
wall=16
wx1=qmins[0]-pad; wy1=qmins[1]-pad; wz1=qmins[2]-pad
wx2=qmaxs[0]+pad; wy2=qmaxs[1]+pad; wz2=qmaxs[2]+pad
parts=[]
parts.append("// Xziel SANCTUM OF ASH NZ:P smoke harness\n// Generated automatically; visual source remains the CC-BY GLB/Blend pipeline.\n")
parts.append("{\n")
parts.append(kv("mapversion","220"))
parts.append(kv("classname","worldspawn"))
parts.append(kv("message","SANCTUM OF ASH - Xziel runtime harness"))
parts.append(kv("chaptertitle","SANCTUM OF ASH"))
parts.append(kv("location","Ruined Sanctuary"))
parts.append(kv("person","Xziel"))
parts.append(kv("wad","../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad"))
# floor, ceiling, four walls
parts.append(brush_box((wx1,wy1,wz1-wall),(wx2,wy2,wz1),"tiles_me"))
parts.append(brush_box((wx1,wy1,wz2),(wx2,wy2,wz2+wall),"ceilings_64"))
parts.append(brush_box((wx1-wall,wy1,wz1),(wx1,wy2,wz2),"facility_wall_l"))
parts.append(brush_box((wx2,wy1,wz1),(wx2+wall,wy2,wz2),"facility_wall_l"))
parts.append(brush_box((wx1,wy1-wall,wz1),(wx2,wy1,wz2),"facility_wall_l"))
parts.append(brush_box((wx1,wy2,wz1),(wx2,wy2+wall,wz2),"facility_wall_l"))

# Collision/navigation authority.
# Normal map builds retain the broad zone decks. Snapshot navigation tests can
# instead supply a surgical floors+ramp skeleton so we can walk all three
# levels without spending time on interior wall/prop collision yet.
floor_pad=max(48,int(1.75*SCALE))
floor_thickness=16
floor_count=0
nav_ramp_count=0
nav_step_count=0
nav_step_height_max=0.0

if nav_doc:
    for floor in nav_doc.get("floors",[]):
        mnq=qv(floor["min"])
        mxq=qv(floor["max"])
        lo=tuple(min(mnq[i],mxq[i]) for i in range(3))
        hi=tuple(max(mnq[i],mxq[i]) for i in range(3))
        parts.append(brush_box(lo,hi,"null"))
        floor_count += 1

    for ramp in nav_doc.get("ramps",[]):
        low=qv(ramp["low"])
        high=qv(ramp["high"])
        # Manifest endpoints are ordered by height, but keep this robust.
        if high[2] < low[2]:
            low,high=high,low
        dx=high[0]-low[0]
        dy=high[1]-low[1]
        dz=high[2]-low[2]
        requested=max(1,int(ramp.get("steps",12)))
        # GoldSrc/Quake step-up is happiest below ~18u. Target <=14u.
        steps=max(requested,int(math.ceil(abs(dz)/14.0)))
        half_w=max(12,int(round(float(ramp["width_m"])*SCALE*0.5)))
        overlap=2
        zbase=low[2]-8
        step_h=abs(dz)/steps if steps else abs(dz)
        nav_step_height_max=max(nav_step_height_max,step_h)
        for si in range(steps):
            t0=si/steps
            t1=(si+1)/steps
            xa=int(round(low[0]+dx*t0)); xb=int(round(low[0]+dx*t1))
            ya=int(round(low[1]+dy*t0)); yb=int(round(low[1]+dy*t1))
            ztop=int(round(low[2]+dz*t1))
            x0=min(xa,xb)-half_w-overlap
            x1=max(xa,xb)+half_w+overlap
            y0=min(ya,yb)-overlap
            y1=max(ya,yb)+overlap
            parts.append(brush_box((x0,y0,zbase),(x1,y1,ztop),"null"))
            nav_step_count += 1
        nav_ramp_count += 1
else:
    # Legacy broad decks used by the generic smoke harness.
    for z,info in zone_raw.items():
        if z=="other": continue
        mn=qv(info["min"]); mx=qv(info["max"])
        floorz=mn[2]
        parts.append(brush_box(
            (mn[0]-floor_pad,mn[1]-floor_pad,floorz-floor_thickness),
            (mx[0]+floor_pad,mx[1]+floor_pad,floorz),
            "null"
        ))
        floor_count += 1

# Last-resort catch deck beneath the lowest authored collision floor.
catch_drop=max(96,int(2.5*SCALE))
if nav_doc and nav_doc.get("floors"):
    nav_low=min(qv(f["min"])[2] for f in nav_doc["floors"])
    catch_z=nav_low-catch_drop
else:
    catch_z=wz1-catch_drop
parts.append(brush_box(
    (wx1,wy1,catch_z-floor_thickness),
    (wx2,wy2,catch_z),
    "null"
))
parts.append("}\n")

# Player spawns: preserve exact scan-derived start but make 4 nearby co-op slots.
p_ent=next(e for e in entities if e["type"]=="player_spawn")
pp=list(p_ent["transform"]["position"].values())
base=qv(pp)
main_target=qv(plan["zones"]["main_church"]["center"])
look_dx=main_target[0]-base[0]
look_dy=main_target[1]-base[1]
spawn_angle=str(int(round(math.degrees(math.atan2(look_dy,look_dx))))%360)
offsets=[(-24,-24,40),(24,-24,40),(-24,24,40),(24,24,40)]
for i,off in enumerate(offsets,1):
    p=(base[0]+off[0],base[1]+off[1],base[2]+off[2])
    parts.append(point_entity(f"info_player_{i}_spawn",p,{
        "weapon":"0","currentmag":"0","currentammo":"0","angle":spawn_angle
    }))

# Group spawns by zone target name.
zone_spawn_groups={}
for s in spawns:
    z=s["zone"].replace("zone_","")
    zone_spawn_groups.setdefault(z,[]).append(s)

# Zombie spawns + approach path + barricade.
for zi,(z,items) in enumerate(sorted(zone_spawn_groups.items())):
    group=f"soa_{z}"[:31]
    for i,s in enumerate(items):
        pos=list(s["transform"]["position"].values())
        p=qv(pos)
        dx=base[0]-p[0]; dy=base[1]-p[1]
        length=max(math.hypot(dx,dy),1.0)
        ux,uy=dx/length,dy/length
        fit=fitted_by_spawn.get(s.get("name",""))
        if fit:
            inside=qv(fit["inside"])
            win=qv(fit["location"])
            path=inside
            normal=fit.get("normal",[ux,uy,0])
            angle=str(int(round(math.degrees(math.atan2(normal[1],normal[0]))))%360)
        else:
            path=(int(p[0]+ux*48),int(p[1]+uy*48),p[2]+32)
            win=(int(p[0]+ux*96),int(p[1]+uy*96),p[2]+32)
            angle=str(int(round(math.degrees(math.atan2(uy,ux))))%360)
        sid=f"{group}_{i+1}"
        pathid=f"path_{z}_{i+1}"[:31]
        winid=f"win_{z}_{i+1}"[:31]
        parts.append(point_entity("spawn_zombie",p,{
            "spawnflags":"0","targetname":group,"target":pathid,
        }))
        parts.append(point_entity("path_corner",path,{
            "wait":"0","spawnflags":"0","targetname":pathid,"target":winid,
        }))
        parts.append(point_entity("item_barricade",win,{
            "model":"models/misc/window.mdl","skin":"0","health":"6","health_delay":"6",
            "oldmodel":"sounds/misc/barricade.wav",
            "aistatus":"sounds/misc/barricade_destroy.wav",
            "spawnflags":"0","targetname":winid,
            "angle":angle,
        }))

# Spawn zones as trigger brushes.
zone_docs={z["id"].replace("zone_",""):z for z in zones_doc["zones"]}
for z,zd in zone_docs.items():
    if z=="other" or z not in zone_raw: continue
    info=zone_raw[z]
    mn=qv(info["min"]); mx=qv(info["max"])
    # Keep trigger volume inside shell and at least 32u thick.
    mn2=(mn[0]+4,mn[1]+4,mn[2]+4)
    mx2=(max(mn2[0]+32,mx[0]-4),max(mn2[1]+32,mx[1]-4),max(mn2[2]+32,mx[2]-4))
    neighbors=", ".join(n.replace("zone_","") for n in zd.get("neighbors",[]))
    target=f"soa_{z}"[:31] if z in zone_spawn_groups else ""
    parts.append("{\n"+kv("classname","spawn_zone")+kv("zone_name",z)+kv("adjacent_zones",neighbors)+kv("zone_target",target)+brush_box(mn2,mx2,"trigger")+"}\n")

# Stock runtime adapters for portable testing; the canonical package keeps the
# original Xziel perk/quest names and semantics.
perk_adapter={
 "Second Wind":"perk_revive",
 "Iron Veins":"perk_juggernog",
 "Rapid Hands":"perk_speed",
 "Deadeye":"perk_deadshot",
 "Sprint Surge":"perk_staminup",
}
for e in entities:
    pos=list(e["transform"]["position"].values())
    p=qv(pos)
    typ=e["type"]
    props=e.get("properties",{})
    if typ=="power_source":
        parts.append(point_entity("power_switch",p,{"model":"models/machines/hl_scale/power_switch.mdl","oldmodel":"sounds/machines/power.wav"}))
    elif typ=="box_anchor":
        parts.append(point_entity("mystery_box",p,{"model":"models/machines/mystery.mdl","cost":"950","spawnflags":"0"}))
    elif typ=="upgrade_machine":
        parts.append(point_entity("perk_pap",p,{"model":"models/machines/hl_scale/pap/p_machine.mdl","cost":"5000","spawnflags":"0"}))
    elif typ=="perk_machine":
        classname=perk_adapter.get(props.get("perk"))
        if classname:
            parts.append(point_entity(classname,p,{"cost":"2000","spawnflags":"0"}))
    elif typ=="door":
        # Small interaction/test door brush near the marker. It validates the
        # NZ:P door entity contract without pretending this is final collision.
        cost=str(props.get("cost",750))
        x,y,z=p
        parts.append("{\n"+kv("classname","func_door_nzp")+kv("speed","100")+kv("sounds","1")+kv("wait","4")+kv("lip","8")+kv("distance","64")+kv("dmg","0")+kv("health","0")+kv("cost",cost)+kv("spawnflags","0")+brush_box((x-20,y-4,z),(x+20,y+4,z+80),"mechanical_door")+"}\n")

# Lights for a visible smoke environment.
parts.append(point_entity("light",(0,0,wz1+192),{"_light":"350","wait":"1","style":"0"}))
parts.append(point_entity("light",(0,0,wz2-192),{"_light":"250","wait":"1","style":"0"}))

OUT.write_text("".join(parts),encoding="utf-8")
summary={
 "map":str(OUT),"scale":SCALE,"bounds":{"min":[wx1,wy1,wz1],"max":[wx2,wy2,wz2]},
 "zones":len([z for z in zone_docs if z!="other"]),"spawns":len(spawns),
 "players":4,"entities":len(entities),
 "collisionSafety":{
   "mode":"floors_ramps_only" if nav_doc else "legacy_zone_decks",
   "zoneFloorDecks":floor_count,
   "floorPadUnits":0 if nav_doc else floor_pad,
   "rampCount":nav_ramp_count,
   "rampStepBrushes":nav_step_count,
   "maxRampStepHeightUnits":round(nav_step_height_max,3),
   "interiorWallCollision":False if nav_doc else None,
   "catchDeckDropUnits":catch_drop
 }
}
(OUT.parent/"sanctum_harness_export.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))
