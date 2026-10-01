#!/usr/bin/env python3
from pathlib import Path
import json

MAP_NAME="sanctum_authored"
TITLE="XZIEL: SANCTUM OF ASH"
OUT=Path(f"build/sanctum_authored/{MAP_NAME}.map")
REPORT=Path(f"build/sanctum_authored/{MAP_NAME}_report.json")
PLAN=Path(f"build/sanctum_authored/{MAP_NAME}_plan.svg")
OUT.parent.mkdir(parents=True,exist_ok=True)

ART={
 "floor":"tiles_me","ceiling":"ceilings_64","wall":"facility_wall_l","door":"mechanical_door",
 "wood":"tiles_me","trigger":"trigger","glass":"facility_wall_l",
 "barricade_model":"models/misc/window.mdl",
 "barricade_rebuild_sfx":"sounds/misc/barricade.wav",
 "barricade_break_sfx":"sounds/misc/barricade_destroy.wav",
}

def kv(k,v):
    return f'"{k}" "{v}"\n'

def brush_box(mn,mx,texture="null"):
    x1,y1,z1=map(int,mn); x2,y2,z2=map(int,mx)
    if not (x2>x1 and y2>y1 and z2>z1):
        raise ValueError((mn,mx))
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

def point(cls,origin,props=None):
    s="{\n"+kv("classname",cls)+kv("origin",f"{origin[0]} {origin[1]} {origin[2]}")
    for k,v in (props or {}).items(): s+=kv(k,v)
    return s+"}\n"

def brush_entity(cls,mn,mx,texture="trigger",props=None):
    s="{\n"+kv("classname",cls)
    for k,v in (props or {}).items(): s+=kv(k,v)
    s+=brush_box(mn,mx,texture)
    return s+"}\n"

parts=[]
parts += [
    "// Authored SANCTUM OF ASH church -- not a bbox harness\n",
    "{\n",kv("mapversion","220"),kv("classname","worldspawn"),
    kv("message",TITLE),kv("chaptertitle","SANCTUM OF ASH"),
    kv("location","Ruined Parish"),kv("person","XZIEL"),
    kv("wad","../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad"),
]

# FLOOR PLATES — church proportions are intentionally authored rather than
# generated from zone AABBs.
parts.append(brush_box((-980,-440,-24),(560,440,0),ART["floor"]))
parts.append(brush_box((560,-300,-24),(940,300,0),ART["floor"]))
parts.append(brush_box((-1180,-240,-24),(-980,240,0),ART["floor"]))
parts.append(brush_box((-920,440,-24),(-620,690,0),ART["floor"]))
parts.append(brush_box((420,440,-24),(760,690,0),ART["floor"]))
parts.append(brush_box((680,-700,-24),(1020,-300,0),ART["floor"]))

# CEILINGS.
parts.append(brush_box((-980,-440,320),(560,440,336),ART["ceiling"]))
parts.append(brush_box((560,-300,360),(940,300,376),ART["ceiling"]))
parts.append(brush_box((-1180,-240,240),(-980,240,256),ART["ceiling"]))
parts.append(brush_box((-920,440,220),(-620,690,236),ART["ceiling"]))
parts.append(brush_box((420,440,220),(760,690,236),ART["ceiling"]))
parts.append(brush_box((680,-700,520),(1020,-300,536),ART["ceiling"]))

# WEST FACADE + NARTHEX.
parts.append(brush_box((-1004,-440,0),(-980,-90,320),ART["wall"]))
parts.append(brush_box((-1004,90,0),(-980,440,320),ART["wall"]))
parts.append(brush_box((-1004,-90,192),(-980,90,320),ART["wall"]))
parts.append(brush_box((-1204,-240,0),(-1180,240,240),ART["wall"]))
parts.append(brush_box((-1180,-264,0),(-980,-240,240),ART["wall"]))
parts.append(brush_box((-1180,240,0),(-980,264,240),ART["wall"]))

# NAVE SIDE WALLS WITH ACTUAL BARRICADE OPENINGS.
window_x=[-820,-460,-100,260]
win_half=54
for side in (-1,1):
    y0=-440 if side==-1 else 416
    y1=-416 if side==-1 else 440
    cuts=[(x-win_half,x+win_half) for x in window_x]
    cursor=-980
    for a,b in cuts:
        if a>cursor:
            parts.append(brush_box((cursor,y0,0),(a,y1,320),ART["wall"]))
        parts.append(brush_box((a,y0,0),(b,y1,32),ART["wall"]))
        parts.append(brush_box((a,y0,176),(b,y1,320),ART["wall"]))
        cursor=b
    if cursor<560:
        parts.append(brush_box((cursor,y0,0),(560,y1,320),ART["wall"]))

# CHANCEL / APSE.
parts.append(brush_box((560,-324,0),(940,-300,360),ART["wall"]))
parts.append(brush_box((560,300,0),(940,324,360),ART["wall"]))
parts.append(brush_box((916,-300,0),(940,-110,360),ART["wall"]))
parts.append(brush_box((916,110,0),(940,300,360),ART["wall"]))
parts.append(brush_box((916,-110,0),(940,110,70),ART["wall"]))
parts.append(brush_box((916,-110,270),(940,110,360),ART["wall"]))

# OFFICE WING, real doorway in south wall.
parts.append(brush_box((-944,440,0),(-920,690,220),ART["wall"]))
parts.append(brush_box((-620,440,0),(-596,690,220),ART["wall"]))
parts.append(brush_box((-920,666,0),(-620,690,220),ART["wall"]))
parts.append(brush_box((-920,416,0),(-840,440,220),ART["wall"]))
parts.append(brush_box((-700,416,0),(-620,440,220),ART["wall"]))
parts.append(brush_box((-840,416,128),(-700,440,220),ART["wall"]))

# BOILER / SERVICE WING.
parts.append(brush_box((396,440,0),(420,690,220),ART["wall"]))
parts.append(brush_box((760,440,0),(784,690,220),ART["wall"]))
parts.append(brush_box((420,666,0),(760,690,220),ART["wall"]))
parts.append(brush_box((420,416,0),(510,440,220),ART["wall"]))
parts.append(brush_box((650,416,0),(760,440,220),ART["wall"]))
parts.append(brush_box((510,416,128),(650,440,220),ART["wall"]))

# TOWER SHELL WITH REAL WALKABLE ACCESS.
parts.append(brush_box((656,-700,0),(680,-300,520),ART["wall"]))
parts.append(brush_box((1020,-700,0),(1044,-300,520),ART["wall"]))
parts.append(brush_box((680,-724,0),(1020,-700,520),ART["wall"]))
parts.append(brush_box((680,-324,0),(790,-300,520),ART["wall"]))
parts.append(brush_box((930,-324,0),(1020,-300,520),ART["wall"]))
parts.append(brush_box((790,-324,144),(930,-300,520),ART["wall"]))

# NAVE COLUMNS AND BAYS.
columns=[]
for x in (-640,-280,80,440):
    for y in (-250,250):
        parts.append(brush_box((x-22,y-22,0),(x+22,y+22,260),ART["wall"]))
        parts.append(brush_box((x-30,y-30,252),(x+30,y+30,278),ART["wall"]))
        columns.append((x,y))
for x in (-640,-280,80,440):
    parts.append(brush_box((x-22,-416,244),(x+22,-272,272),ART["wall"]))
    parts.append(brush_box((x-22,272,244),(x+22,416,272),ART["wall"]))

# THREE BROAD CHANCEL STEPS + ALTAR.
for i in range(3):
    x1=500+i*24
    parts.append(brush_box((x1,-250,0),(x1+24,250,(i+1)*8),ART["floor"]))
parts.append(brush_box((572,-250,0),(900,250,24),ART["floor"]))
parts.append(brush_box((790,-80,24),(865,80,84),ART["wall"]))
parts.append(brush_box((900,-18,84),(916,18,230),ART["wall"]))
parts.append(brush_box((900,-72,155),(916,72,185),ART["wall"]))

# PASSABLE PEWS — visible but explicitly noclip so AI has clean lanes.
# Keep brush entities outside worldspawn; nesting an entity inside worldspawn is invalid MAP syntax.
pew_entities=[]
for x in (-520,-380,-240,-100,40,180):
    for y1,y2 in [(-210,-72),(72,210)]:
        pew_entities.append(brush_entity(
            "func_detail",(x-44,y1,0),(x+44,y2,28),ART["wood"],
            {"zhlt_noclip":"1","zhlt_detaillevel":"2"}
        ))

# Doorway framing.
parts.append(brush_box((-1000,-105,0),(-960,-90,205),ART["wall"]))
parts.append(brush_box((-1000,90,0),(-960,105,205),ART["wall"]))

# TOWER SWITCHBACK — forty 8-unit steps, deliberately under normal step height.
for i in range(20):
    y2=-330-i*13; y1=y2-13; h=(i+1)*8
    parts.append(brush_box((700,y1,0),(840,y2,h),ART["floor"]))
parts.append(brush_box((700,-620,0),(1000,-590,160),ART["floor"]))
for i in range(20):
    y1=-590+i*13; y2=y1+13; h=160+(i+1)*8
    parts.append(brush_box((860,y1,0),(1000,y2,h),ART["floor"]))
parts.append(brush_box((680,-700,304),(850,-300,320),ART["floor"]))
parts.append(brush_box((850,-700,304),(1020,-590,320),ART["floor"]))
parts.append(brush_box((850,-330,304),(1020,-300,320),ART["floor"]))
parts.append(brush_box((842,-590,320),(858,-330,356),ART["wall"]))
parts.append(brush_box((850,-606,320),(1020,-590,356),ART["wall"]))
parts.append(brush_box((735,-625,320),(805,-555,390),ART["wall"]))

parts.append("}\n")
parts.extend(pew_entities)

# TRANSLUCENT GLASS / CLERESTORY.
parts.append(brush_entity(
    "func_wall",(920,-100,74),(936,100,266),ART["glass"],
    {"alpha":"0.42","rendermode":"4","renderamt":"150","spawnflags":"4"}
))
for side in (-1,1):
    yy=(-436,-420) if side==-1 else (420,436)
    for x in window_x:
        parts.append(brush_entity(
            "func_wall",(x-46,yy[0],190),(x+46,yy[1],258),ART["glass"],
            {"alpha":"0.32","rendermode":"4","renderamt":"130","spawnflags":"4"}
        ))

# PAID SIDE-ROOM / TOWER DOORS.
parts.append(brush_entity("func_door_nzp",(-840,420,0),(-700,436,128),ART["door"],{
    "speed":"100","sounds":"2","wait":"-1","lip":"8","distance":"112","dmg":"0","health":"0","cost":"750","spawnflags":"0"
}))
parts.append(brush_entity("func_door_nzp",(510,420,0),(650,436,128),ART["door"],{
    "speed":"100","sounds":"2","wait":"-1","lip":"8","distance":"112","dmg":"0","health":"0","cost":"1000","spawnflags":"0"
}))
parts.append(brush_entity("func_door_nzp",(790,-316,0),(930,-300,144),ART["door"],{
    "speed":"100","sounds":"2","wait":"-1","lip":"8","distance":"128","dmg":"0","health":"0","cost":"1250","spawnflags":"0"
}))

# FOUR CO-OP STARTS IN THE NAVE FACING EAST TOWARD THE ALTAR.
for i,(x,y) in enumerate([(-430,-42),(-430,42),(-350,-42),(-350,42)],1):
    parts.append(point(f"info_player_{i}_spawn",(x,y,40),{
        "weapon":"0","currentmag":"0","currentammo":"0","angle":"0"
    }))

# ZONES.
zones=[
 ("nave",(-960,-410,4),(920,410,300),"office, boiler, tower","sanctum_nave"),
 ("office",(-900,450,4),(-640,670,200),"nave","sanctum_office"),
 ("boiler",(440,450,4),(740,670,200),"nave","sanctum_boiler"),
 ("tower",(690,-680,4),(1010,-310,500),"nave","sanctum_tower"),
]
for name,mn,mx,adj,target in zones:
    parts.append(brush_entity("spawn_zone",mn,mx,ART["trigger"],{
        "zone_name":name,"adjacent_zones":adj,"zone_target":target
    }))

# OFFICIAL NZ:P WINDOW CHAIN: spawn -> path_corner -> six-board barricade.
spawn_defs=[]
for x in window_x:
    spawn_defs.append(("nave",(x,-610,40),(x,-500,40),(x,-425,48),90))
for x in window_x:
    spawn_defs.append(("nave",(x,610,40),(x,500,40),(x,425,48),270))
for i,(zone,sp,approach,win,angle) in enumerate(spawn_defs,1):
    path=f"sanctum_path_{i}"; window=f"sanctum_window_{i}"
    parts.append(point("spawn_zombie",sp,{
        "targetname":"sanctum_nave","target":path,"spawnflags":"0"
    }))
    parts.append(point("path_corner",approach,{
        "targetname":path,"target":window,"wait":"0","spawnflags":"0"
    }))
    parts.append(point("item_barricade",win,{
        "targetname":window,"model":ART["barricade_model"],"skin":"0",
        "health":"6","health_delay":"6",
        "oldmodel":ART["barricade_rebuild_sfx"],
        "aistatus":ART["barricade_break_sfx"],
        "spawnflags":"0","angle":str(angle)
    }))

# Side-room pressure only becomes relevant when the zone is active.
for p,group in [
    ((-780,560,40),"sanctum_office"),
    ((590,560,40),"sanctum_boiler"),
    ((760,-520,40),"sanctum_tower"),
]:
    parts.append(point("spawn_zombie",p,{"targetname":group,"spawnflags":"4"}))

# POWER / BOX / PAP / PERKS.
parts.append(point("power_switch",(590,585,40),{"angle":"270","oldmodel":"sounds/machines/power.wav"}))
parts.append(point("mystery_box",(-720,535,40),{"cost":"950","spawnflags":"0","angle":"270"}))
parts.append(point("mystery_box_tp_spot",(700,160,48),{"angle":"180"}))
parts.append(point("mystery_box_tp_spot",(-1080,0,40),{"angle":"0"}))
parts.append(point("perk_pap",(840,0,64),{"cost":"5000","angle":"180"}))
for cls,pos,cost in [
    ("perk_revive",(-820,-315,40),500),
    ("perk_juggernog",(420,330,40),2500),
    ("perk_speed",(665,575,40),3000),
    ("perk_double",(735,-610,360),2000),
]:
    parts.append(point(cls,pos,{
        "cost":str(cost),"cost2":str(cost),
        "perk_requires_power_solo":"1","perk_requires_power_coop":"1","angle":"180"
    }))

# WALL BUYS.
for name,wid,cost,ammo,pos,ang in [
    ("m1",13,600,300,(-890,300,48),0),
    ("mp40",15,1000,500,(-300,395,48),270),
    ("trench",23,1500,750,(350,-395,48),90),
]:
    chalk=f"sanctum_chalk_{name}"
    parts.append(point("weapon_wall",pos,{
        "targetname":chalk,"sequence":str(wid-1),"weapon":str(wid),
        "cost":str(cost),"angle":str(ang)
    }))
    x,y,z=pos
    parts.append(brush_entity("buy_weapon",(x-42,y-42,z-42),(x+42,y+42,z+42),ART["trigger"],{
        "weapon":str(wid),"cost":str(cost),"cost2":str(ammo),
        "pap_cost":"4500","target":chalk
    }))

# LIGHTS.
for p,val in [
    ((-650,0,270),280),((-250,0,280),320),((150,0,280),320),
    ((500,0,300),340),((800,0,320),360),
    ((-780,555,180),180),((590,555,180),180),
    ((850,-500,180),220),((850,-500,450),180),
]:
    parts.append(point("light",p,{"_light":str(val),"wait":"1","style":"0"}))
parts.append(point("light",(860,-120,170),{"_light":"180 80 60 180","wait":"1","style":"0"}))
parts.append(point("light",(860,120,170),{"_light":"60 80 180 180","wait":"1","style":"0"}))

OUT.write_text("".join(parts),encoding="utf-8")

report={
 "title":TITLE,"map":str(OUT),
 "design":"authored church, no bbox rooms/no auto bridges",
 "footprint":{"nave":[1540,880],"chancel":[380,600],"tower":[340,400]},
 "columns":len(columns),"functional_stair_steps":40,"stair_rise":8,
 "zombie_windows":len(spawn_defs),"glass_panels":1+len(window_x)*2,
 "paid_doors":3,"zones":len(zones),"player_spawns":4,
 "zombie_spawns":len(spawn_defs)+3,"perks":4,"pap":1,
 "mystery_box_locations":3,"power":1,
 "ai_design":[
    "wide center aisle",
    "window lanes aligned between columns",
    "pews are noclip detail",
    "8-unit stair risers"
 ],
 "acceptance":[
    "first-person view reads as church",
    "zombies traverse barricade windows",
    "no giant bbox walls",
    "no autogenerated bridge blocks"
 ]
}
REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8")

# Floor-plan artifact for human review before APK installation.
scale=0.42; ox=540; oy=360
def sx(x): return ox+x*scale
def sy(y): return oy-y*scale
svg=[
 '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="760" viewBox="0 0 1100 760">',
 '<rect width="100%" height="100%" fill="#111"/>'
]
def rect(x1,y1,x2,y2,label,fill="#333"):
    X=sx(x1); Y=sy(y2); W=(x2-x1)*scale; H=(y2-y1)*scale
    svg.append(f'<rect x="{X:.1f}" y="{Y:.1f}" width="{W:.1f}" height="{H:.1f}" fill="{fill}" stroke="#ddd" stroke-width="2"/>')
    svg.append(f'<text x="{X+W/2:.1f}" y="{Y+H/2:.1f}" fill="white" font-family="sans-serif" font-size="16" text-anchor="middle">{label}</text>')
rect(-980,-440,560,440,"NAVE + AISLES")
rect(560,-300,940,300,"CHANCEL / ALTAR","#3b3333")
rect(-1180,-240,-980,240,"NARTHEX","#2d333a")
rect(-920,440,-620,690,"OFFICE","#303a30")
rect(420,440,760,690,"BOILER","#3a3030")
rect(680,-700,1020,-300,"TOWER / STAIRS","#38303a")
for x,y in columns:
    X=sx(x);Y=sy(y)
    svg.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="7" fill="#ddd"/>')
for x in window_x:
    for y in (-440,440):
        X=sx(x);Y=sy(y)
        svg.append(f'<rect x="{X-10:.1f}" y="{Y-3:.1f}" width="20" height="6" fill="#55cfff"/>')
svg.append('<text x="550" y="32" fill="white" font-family="sans-serif" font-size="24" text-anchor="middle">XZIEL SANCTUM — AUTHORED FLOOR PLAN</text>')
svg.append('</svg>')
PLAN.write_text("\n".join(svg),encoding="utf-8")
print(json.dumps(report,indent=2))
