import bpy, json, os
from pathlib import Path
from mathutils import Vector

SOURCE=os.environ.get("CHURCH_SOURCE","church/source/st-giles-cripplegate.glb")
OUT=Path(os.environ.get("CHURCH_PLAN","church/out/zombies_map_plan_fast.json"))
OUT.parent.mkdir(parents=True,exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=SOURCE)
objs=[o for o in bpy.context.scene.objects if o.type=="MESH"]
if not objs:
    raise RuntimeError("No mesh objects in St Giles source")

def bbox(items):
    pts=[]
    for o in items:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def mats(o):
    return " ".join(m.name.lower() for m in o.data.materials if m)

def classify(o):
    m=mats(o)
    if "boiler" in m: return "boiler"
    if "clockchamber" in m: return "clock_chamber"
    if "officecorridor" in m: return "office_corridor"
    if "office" in m: return "office"
    if "ringingchamber" in m: return "ringing_chamber"
    if "roofchamber" in m: return "roof_chamber"
    if "towerstairs" in m: return "tower_stairs"
    if "towertop" in m: return "tower_top"
    if "turret" in m: return "turret"
    if "exterior" in m: return "exterior"
    if "stgilescripplegate11" in m: return "main_church"
    return "other"

groups={}
for o in objs:
    groups.setdefault(classify(o),[]).append(o)

zones={}
for name,items in groups.items():
    mn,mx=bbox(items)
    zones[name]={
        "center":list((mn+mx)*0.5),
        "min":list(mn),"max":list(mx),"size":list(mx-mn),
        "mesh_count":len(items),
    }

def dominant_floor(zone):
    items=groups.get(zone,[])
    info=zones[zone]
    buckets={}
    for o in items:
        mesh=o.data
        if not mesh.polygons: continue
        stride=max(1,len(mesh.polygons)//12000)
        world=o.matrix_world
        normal_matrix=world.to_3x3().inverted().transposed()
        for i in range(0,len(mesh.polygons),stride):
            poly=mesh.polygons[i]
            n=normal_matrix @ poly.normal
            if n.length<=1e-8: continue
            n.normalize()
            if n.z<0.58: continue
            p=world @ poly.center
            zbin=round(float(p.z)*4.0)/4.0
            buckets[zbin]=buckets.get(zbin,0.0)+float(poly.area)*stride
    if buckets:
        return max(buckets.items(),key=lambda kv:kv[1])[0]
    return float(info["min"][2])

floor_levels={k:dominant_floor(k) for k in zones if k!="other"}

main=zones.get("main_church")
ext=zones.get("exterior")
if not main:
    raise RuntimeError("main_church group missing from St Giles materials")
if not ext:
    raise RuntimeError("exterior group missing from St Giles materials")

mmn=Vector(main["min"]); mmx=Vector(main["max"]); mc=Vector(main["center"])
emn=Vector(ext["min"]); emx=Vector(ext["max"])
sides=[
 ("west",max(0.0,mmn.x-emn.x),Vector((-1,0,0)),Vector((mmn.x,mc.y,0))),
 ("east",max(0.0,emx.x-mmx.x),Vector((1,0,0)),Vector((mmx.x,mc.y,0))),
 ("south",max(0.0,mmn.y-emn.y),Vector((0,-1,0)),Vector((mc.x,mmn.y,0))),
 ("north",max(0.0,emx.y-mmx.y),Vector((0,1,0)),Vector((mc.x,mmx.y,0))),
]
_,clearance,outward,edge=max(sides,key=lambda x:x[1])
distance=min(10.0,max(4.5,clearance*0.45))
player=edge+outward*distance
player.x=min(max(player.x,emn.x+1.0),emx.x-1.0)
player.y=min(max(player.y,emn.y+1.0),emx.y-1.0)
player.z=floor_levels["exterior"]+1.05

interactives=[{
    "name":"P1_START_COURTYARD","kind":"player_spawn","location":list(player),
    "properties":{"zone":"exterior","phase":"start","look_at":"main_church"}
}]

spawn_zones=["exterior","main_church","office","office_corridor","boiler","tower_stairs","ringing_chamber"]
for zone in spawn_zones:
    if zone not in zones: continue
    info=zones[zone]
    mn=Vector(info["min"]); mx=Vector(info["max"]); c=Vector(info["center"])
    z=floor_levels.get(zone,float(mn.z))+0.45
    candidates=[
        Vector((mn.x+(mx.x-mn.x)*0.12,c.y,z)),
        Vector((mx.x-(mx.x-mn.x)*0.12,c.y,z)),
        Vector((c.x,mn.y+(mx.y-mn.y)*0.12,z)),
        Vector((c.x,mx.y-(mx.y-mn.y)*0.12,z)),
    ]
    for i,p in enumerate(candidates,1):
        interactives.append({
            "name":f"ZSP_{zone.upper()}_{i:02d}","kind":"zombie_spawn","location":list(p),
            "properties":{"zone":zone,"candidate":True}
        })

overall_min,overall_max=bbox(objs)
plan={
    "working_title":"SANCTUM OF ASH",
    "source_building":"St Giles-without-Cripplegate scan by artfletch (CC BY)",
    "design_pass":"fast-scan-measurement-for-quake-green",
    "overall":{"min":list(overall_min),"max":list(overall_max),"size":list(overall_max-overall_min)},
    "floor_levels":floor_levels,
    "zones":zones,
    "progression":["courtyard","nave","office_corridor","boiler_power","tower_stairs","ringing_chamber","clock_chamber","roof_chamber","tower_top"],
    "interactives":interactives,
}
OUT.write_text(json.dumps(plan,indent=2)+"\n",encoding="utf-8")
print("FAST_SANCTUM_MEASURE_OK")
print("OVERALL",json.dumps(plan["overall"]))
print("FLOORS",json.dumps(floor_levels,sort_keys=True))
print("ZONES",sorted(k for k in zones if k!="other"))
print("INTERACTIVES",len(interactives))
