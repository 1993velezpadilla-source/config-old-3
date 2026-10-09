#!/usr/bin/env python3
"""Source-preserving Nacht exterior-only visual LOD policy (research).

The camera refs are from the actual approved Godot source-spawn screenshot
gauntlet, NOT a derived gameplay blocker. Radius 55m is deliberately large:
all building, door/windows, source interactive/reachable outdoor region inside
that ring are immutable. Exact original GLB world AABB is independently
checked by Godot at runtime BEFORE any visual-only LOD is applied.

Does not touch source transforms/meshes, source material names, collisions or
BO3 T7 assets. This is a renderer policy candidate, not proven Android FPS.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

# Source screenshot #37951843624's exact, already recorded overview
# target is the broken Nacht building, verified with user's provided image.
RESEARCH_BUILDING_ANCHOR_XZ = (-2.494789, -7.258049)
SOURCE_INTERIOR_SPAWN_XZ = ((-10.51,-1.924322), (7.530912,-0.335323),(11.61863,-0.325515))
PROTECT_BUILDING_RADIUS_M = 55.0
MIN_TREE_RADIUS_M = 55.0
MIN_SMALL_PROP_RADIUS_M = 65.0
MIN_SHADOW_RADIUS_M = 85.0

BLOCKED = ("door","window","barricade","wall","floor","roof","ceiling",
    "house","building","stair","ladder","ramp","power","perks","mystery",
    "pack_a_punch","machine","purchase","switch","portal","spawn","sky",
    "terrain","landscape","water","weapon","collision","blocking","fence",
    "gate","traverse","bridge","path","walkway","foundation","column")
def labels(row):
    fields=[]
    for name, value in row.items():
        if name in ("runtimeFile","index"): continue
        if isinstance(value,str): fields.append(value)
    return " ".join(fields).lower()

def classify(row):
    t=labels(row)
    if any(term in t for term in BLOCKED):return None
    # Only AUTHORITATIVELY named asset classes. Never infer "background"
    # from material color, distance alone, or one actor's geometry size.
    if ("foliage_grass" in t or "foliage_weed" in t
        or "foliage_bush" in t or "foliage_shrub" in t):
        return "small_foliage"
    if "foliage_tree" in t or "/trees/" in t:
        return "tree_silhouette"
    if ("debris_rocks_loose" in t or "debris_asphalt_chunks_sm" in t
        or "debris_gravel_sm" in t or "foliage_plant_" in t):
        return "small_decorative_ground"
    return None

def point(row):
    m=row["matrixRowMajor"]
    if len(m)!=16:raise ValueError("missing actual source transform")
    x,y,z=-float(m[7]),float(m[11]),-float(m[3])
    if not all(map(math.isfinite,(x,y,z))):raise ValueError("invalid original actor world location")
    return x,y,z

def create(src):
    if src.get("format")!="xziel_visual_scene_v1" or len(src["meshes"])!=493 or len(src["instances"])!=10793:
        raise ValueError("wrong original Pavlov UE4.21 source authority")
    type_map={int(m["index"]):m for m in src["meshes"]}
    if set(type_map)!=set(range(493)):
        raise ValueError("source 493 types do not preserve exact meshIndex identity")
    original_count=0
    results=[]
    categories=Counter()
    near_categories=Counter()
    unselected=Counter()
    seen=set()
    sha=hashlib.sha256()
    for actor in src["instances"]:
        iid=str(actor["instanceId"])
        if iid in seen:
            raise ValueError("duplicate authoritative source actor")
        seen.add(iid)
        idx=int(actor["meshIndex"])
        if idx not in type_map:raise ValueError("original source mesh index missing")
        x,y,z=point(actor)
        matrix=actor["matrixRowMajor"]
        sha.update(iid.encode()+b"\0")
        sha.update(json.dumps(matrix,separators=(",",":")).encode()+b"\n")
        original_count+=1
        category=classify(type_map[idx])
        if category is None:
            unselected["no_unambiguous_source_asset_class"]+=1
            continue
        distance=math.hypot(x-RESEARCH_BUILDING_ANCHOR_XZ[0],z-RESEARCH_BUILDING_ANCHOR_XZ[1])
        if distance<PROTECT_BUILDING_RADIUS_M:
            near_categories[category]+=1
            continue
        if category in ("small_foliage","small_decorative_ground") and distance<MIN_SMALL_PROP_RADIUS_M:
            near_categories[category]+=1
            continue
        item={"actorId":iid, "nativeSourceMeshIndex":idx,
              "authoredAssetClass":category,
              "originalOriginXZ":[round(x,6),round(z,6)],
              "buildingAnchorHorizontalDistanceM":round(distance,4),
              "preserveWorldMatrixAndMaterials":True,
              "collisionAndNavNotModified":True}
        if category=="tree_silhouette":
            item["lodBiasTarget"]=0.48
            item["maxCameraVisibilityM"]=0  # 0: never distance-cull skyline trees.
            item["canDisableLongRangeShadow"]=distance>MIN_SHADOW_RADIUS_M
        elif category=="small_foliage":
            item["lodBiasTarget"]=0.35
            item["maxCameraVisibilityM"]=90
            item["canDisableLongRangeShadow"]=distance>MIN_SHADOW_RADIUS_M
        else:
            item["lodBiasTarget"]=0.58
            item["maxCameraVisibilityM"]=115
            item["canDisableLongRangeShadow"]=distance>MIN_SHADOW_RADIUS_M
        results.append(item)
        categories[category]+=1
    if original_count!=10793 or len(seen)!=10793:
        raise ValueError("original source actor world records changed")
    if any(row["buildingAnchorHorizontalDistanceM"]<55 for row in results):
        raise ValueError("near-source protection contract violated")
    output={
        "authority":"actual archived Pavlov UE4.21 source static mesh path, NOT original BO3 T7",
        "stage":"research-only, actual Godot runtime world-bounds verification required",
        "sourceActorCount":10793,"sourceNativeMeshTypes":493,
        "sourceMatrixIdentitySHA256":sha.hexdigest(),
        "buildingCameraTargetXZ":list(RESEARCH_BUILDING_ANCHOR_XZ),
        "originalSourceSpawnXZ":[list(x) for x in SOURCE_INTERIOR_SPAWN_XZ],
        "largeGameplayRegionProtectionRadiusM":PROTECT_BUILDING_RADIUS_M,
        "outdoorPlayabilityBeyondProtectedRadiusNotProven":True,
        "safeAssetClassCounts":dict(categories),
        "sourceNearProtectedFoliageCounts":dict(near_categories),
        "sourceUnclassifiedExcludedActors":dict(unselected),
        "eligibleOriginalVisualActors":len(results),
        "actors":results,
        "sourceOriginalActorTransformsChanged":0,
        "originalGLBGeometryDecimated":False,
        "collisionsAndNavigationModified":False,
        "realGodotScreenPixelBeforeAfterNotYetMeasured":True,
        "mobileGpuDrawCallsFPSNotYetMeasured":True,
        "notes":"Runtime must exclude any source-world AABB overlapping 55m protected disk and any unusually large source mesh. Visibility range is relative to player camera, not an invented level boundary.",
    }
    if len(results)<50:raise ValueError("no meaningful safe exterior-only original actor candidates")
    return output

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--scene",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    o=ap.parse_args()
    result=create(json.loads(o.scene.read_text()))
    o.output.parent.mkdir(parents=True,exist_ok=True)
    o.output.write_text(json.dumps(result,indent=2)+"\n")
    print("XZOGOT_NACHT_ORIGINAL_SAFE_EXTERIOR_ASSET_LOD_PLAN_GREEN",
          " eligible_original_actors",result["eligibleOriginalVisualActors"],
          " classes",result["safeAssetClassCounts"],
          " protected_near_origins",result["sourceNearProtectedFoliageCounts"],
          " source_actors",result["sourceActorCount"])
if __name__=="__main__": main()
