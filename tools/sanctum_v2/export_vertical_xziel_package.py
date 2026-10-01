#!/usr/bin/env python3
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT=Path(os.environ.get("SANCTUM_VERTICAL_OUT","sanctum-vertical-probe"))
OUT=Path(os.environ.get("SANCTUM_XZIEL_PACKAGE",str(ROOT/"xziel-package")))
OUT.mkdir(parents=True,exist_ok=True)
(OUT/"geometry").mkdir(exist_ok=True)
(OUT/"runtime").mkdir(exist_ok=True)

report=json.loads((ROOT/"vertical-report.json").read_text(encoding="utf-8"))
gameplay=json.loads((ROOT/"sanctum-gameplay-entities.json").read_text(encoding="utf-8"))
ads=json.loads((ROOT/"sanctum-ad-surfaces.json").read_text(encoding="utf-8"))

def uid(text):
    return hashlib.sha1(("sanctum-vertical:"+text).encode("utf-8")).hexdigest()[:16]

def vec(v):
    return {"x":round(float(v[0]),5),"y":round(float(v[1]),5),"z":round(float(v[2]),5)}

def copy_if(src,dst):
    src=Path(src)
    dst=Path(dst)
    if src.is_file():
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        return True
    return False

floor_heights=report["floor_heights_m"]
main_min,main_max=report["main_floor_bounds"]
under_min,under_max=report["undercroft_bounds"]
gallery=report["gallery"]

zones=[
    {
        "id":"zone_undercroft",
        "type":"zone",
        "displayName":"Service Undercroft",
        "bounds":{"min":vec(under_min),"max":vec(under_max)},
        "neighbors":["zone_nave"],
        "environmentProfile":"boiler_undercroft",
        "pressureVectors":3,
    },
    {
        "id":"zone_nave",
        "type":"zone",
        "displayName":"Nave",
        "bounds":{
            "min":vec([main_min[0],main_min[1],floor_heights["nave"]-0.5]),
            "max":vec([main_max[0],main_max[1],floor_heights["gallery"]-0.2]),
        },
        "neighbors":["zone_undercroft","zone_gallery"],
        "environmentProfile":"church_nave",
        "pressureVectors":3,
    },
    {
        "id":"zone_gallery",
        "type":"zone",
        "displayName":"Choir Gallery",
        "bounds":{
            "min":vec([
                (main_min[0]+main_max[0])*0.5-gallery["x_offset"]-gallery["width"],
                gallery["y0"],
                floor_heights["gallery"]-0.5,
            ]),
            "max":vec([
                (main_min[0]+main_max[0])*0.5+gallery["x_offset"]+gallery["width"],
                gallery["y1"],
                floor_heights["gallery"]+2.5,
            ]),
        },
        "neighbors":["zone_nave"],
        "environmentProfile":"choir_gallery",
        "pressureVectors":2,
    },
]

zone_lookup={
    "floor_minus_1":"zone_undercroft",
    "floor_0":"zone_nave",
    "floor_1":"zone_gallery",
}

entities=[]
for item in gameplay.get("entities",[]):
    entities.append({
        "id":uid(item["id"]),
        "name":item["id"],
        "type":item["kind"],
        "zone":zone_lookup[item["floor"]],
        "transform":{"position":vec(item["world_position"]),"rotation":{"pitch":0,"yaw":0,"roll":0}},
        "properties":{"source":"sanctum-vertical-layout.v1","floor":item["floor"]},
        "enabled":True,
        "replicationPolicy":"server_authoritative",
    })

# Connections are server-authoritative progression links. Geometry already
# contains both routes; runtime state controls whether a gated link is enabled.
connections=[]
for item in gameplay.get("connections",[]):
    connections.append({
        "id":uid(item["id"]),
        "name":item["id"],
        "type":"zone_connection",
        "fromZone":zone_lookup[item["from"]],
        "toZone":zone_lookup[item["to"]],
        "kind":item["kind"],
        "cost":int(item.get("door_cost",0)),
        "requires":item.get("requires"),
        "alwaysEscapeAfterOpen":bool(item.get("always_escape_after_open",False)),
        "replicationPolicy":"server_authoritative",
    })

ad_entities=[]
for item in ads.get("placements",[]):
    p={
        "id":uid(item["id"]),
        "name":item["id"],
        "type":"diegetic_ad_surface",
        "zone":zone_lookup[item["floor"]],
        "transform":{"position":vec(item["world_position"]),"rotation":{"pitch":0,"yaw":0,"roll":0}},
        "surfaceType":item["type"],
        "allowedMedia":item["allowed_media"],
        "properties":{
            "pausesGameplay":False,
            "hudOverlay":False,
            "forcedFullscreen":False,
            "providerPolicyGateRequired":True,
        },
        "enabled":True,
        "replicationPolicy":"client_visual_server_campaign_state",
    }
    if item.get("audio"):
        p["audio"]=item["audio"]
    ad_entities.append(p)

logic={
    "schemaVersion":1,
    "nodes":[
        {
            "nodeId":"power_on",
            "type":"PowerOn",
            "settings":{"circuit":"church_main"},
            "persistentState":True,
            "authority":"server",
        },
        {
            "nodeId":"unlock_undercroft_shortcut",
            "type":"SetConnectionEnabled",
            "settings":{"connection":"undercroft_ramp_east_shortcut","enabled":True},
            "persistentState":True,
            "authority":"server",
        },
        {
            "nodeId":"diegetic_ad_scheduler",
            "type":"DiegeticAdScheduler",
            "settings":{
                "worldSpaceOnly":True,
                "maxSimultaneousAudioAds":1,
                "combatAndQuestAudioPriority":True,
                "offlineFallback":"authored_art",
                "providerMode":"house_or_direct_sponsor_until_adapter_approved",
            },
            "persistentState":False,
            "authority":"server_campaign_selection_client_render",
        },
    ],
    "edges":[
        {"sourceNode":"power_on","sourcePort":"activated","targetNode":"unlock_undercroft_shortcut","targetPort":"activate"}
    ],
}

geometry_src=ROOT/report["glb"]
geometry_dst=OUT/"geometry"/"sanctum-vertical-blockout.glb"
if not copy_if(geometry_src,geometry_dst):
    raise SystemExit(f"missing geometry {geometry_src}")

runtime_files={}
for name,rel in [
    ("navmesh","runtime/sanctum.navbin"),
    ("collision","runtime/sanctum-collision-hulls.glb"),
    ("navmeshReport","runtime/navmesh-report.json"),
    ("collisionReport","runtime/collision-report.json"),
]:
    src=ROOT/rel
    dst=OUT/rel
    if copy_if(src,dst):
        runtime_files[name]=rel

for name in ("sanctum-ad-surfaces.json","sanctum-gameplay-entities.json","vertical-report.json"):
    copy_if(ROOT/name,OUT/name)

manifest={
    "id":"sanctum_of_ash",
    "displayName":"SANCTUM OF ASH",
    "version":"0.2.0-vertical-blockout",
    "schemaVersion":1,
    "geometry":"geometry/sanctum-vertical-blockout.glb",
    "runtime":runtime_files,
    "zones":"zones.json",
    "entities":"entities.json",
    "connections":"connections.json",
    "ads":"ads.json",
    "logic":"logic.json",
    "renderPolicy":{
        "nativeVulkan":True,
        "mobileKtx2Preferred":True,
        "roomPortalCullingRequired":True,
        "rawGeometryPreserved":True,
    },
    "monetizationPolicy":{
        "diegeticOnlyDuringGameplay":True,
        "pauseGameplay":False,
        "hudOverlay":False,
        "providerPolicyGateRequired":True,
    },
    "sourcePolicy":{
        "outer":"MIT",
        "interior":"CC0",
        "gothicDressing":"CC0",
        "props":"CC0",
        "layout":"original_xziel",
    },
}

files={
    "map.json":manifest,
    "zones.json":{"schemaVersion":1,"zones":zones},
    "entities.json":{"schemaVersion":1,"entities":entities},
    "connections.json":{"schemaVersion":1,"connections":connections},
    "ads.json":{"schemaVersion":1,"policy":ads["policy"],"placements":ad_entities},
    "logic.json":logic,
}
for name,data in files.items():
    (OUT/name).write_text(json.dumps(data,indent=2),encoding="utf-8")

errors=[]
if len(zones)!=3:
    errors.append("expected 3 gameplay zones")
if len(connections)!=4:
    errors.append("expected 4 vertical connections")
if len(ad_entities)!=3:
    errors.append("expected 3 diegetic ad placements")
if not any(e["type"]=="power" for e in entities):
    errors.append("missing power entity")
if report.get("vertical_span_m",0)<7.0:
    errors.append("vertical span below design target")
if not runtime_files.get("navmesh"):
    errors.append("runtime navmesh missing")
if not runtime_files.get("collision"):
    errors.append("runtime collision missing")

preflight={
    "ok":not errors,
    "errors":errors,
    "counts":{
        "zones":len(zones),
        "entities":len(entities),
        "connections":len(connections),
        "ads":len(ad_entities),
    },
    "verticalSpanM":report.get("vertical_span_m"),
}
(OUT/"preflight.json").write_text(json.dumps(preflight,indent=2),encoding="utf-8")
if errors:
    raise SystemExit("SANCTUM_XZIEL_PACKAGE_FAIL: "+"; ".join(errors))
print("SANCTUM_XZIEL_PACKAGE_PASS")
print(json.dumps(preflight,indent=2))
