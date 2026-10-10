#!/usr/bin/env python3
"""Research-only Nacht source-authored distant vista asset classification.

Uses ONLY metadata from previously GREEN provenance gates. 'vista' tags
indicate background-targeted source design, not proof that the player cannot
see them. Never mark unseen on distance alone. World GLB actor bounds and
actual playable navigation/line-of-sight still required before destructive LOD.

Does NOT modify meshes, DDS, any sources or the shipping game.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

SAFE_VISTA_MARKERS = ("_vista", "/vista/", "background", "_backdrop")
FORBIDDEN_GAMEPLAY = (
    "barricade","door","window","wall","roof","floor","stair","ladder",
    "interactive","portal","switch","machine","power","wallbuy",
    "mystery","perk","pack_a_punch","collision","spawn","weapon",
    "skybox","skysphere","landscape","terrain","floor","ground","bridge"
)

def inspect(inventory,far):
    assert inventory["mesh_count"]==493 and inventory["actor_count"]==10793
    assert far["sourceActorCount"]==10793 and far["sourceNativeMeshTypes"]==493
    assert far["largeGameplayRegionProtectionRadiusM"]>=55
    meshrows={int(x["index"]):x for x in inventory["mesh_by_frequency"]}
    assert set(meshrows)==set(range(493))
    all_vista=[]
    by_native_type=Counter()
    forbidden_overlap=[]
    rejected_incomplete=[]
    for row in far["actors"]:
        idx=int(row["nativeSourceMeshIndex"])
        record=meshrows[idx]
        label=record["sourceDescription"].lower()
        if not any(t in label for t in SAFE_VISTA_MARKERS):
            continue
        if any(t in label for t in FORBIDDEN_GAMEPLAY):
            forbidden_overlap.append(str(row["actorId"]))
            continue
        if row["buildingAnchorHorizontalDistanceM"]<55:
            rejected_incomplete.append(str(row["actorId"]))
            continue
        assert row["authoredAssetClass"] in ("tree_silhouette","small_foliage","small_decorative_ground")
        # Preserve exact asset source ID and actor world transform.
        all_vista.append({
            "originalActorID":row["actorId"],
            "sourceNativeMeshType":idx,
            "sourceOriginalAssetLabel":record["sourceDescription"],
            "sourceRootDistanceFromBuildingM":row["buildingAnchorHorizontalDistanceM"],
            "sourceClassification":row["authoredAssetClass"],
            "mayUseMoreAggressiveDistantMeshLODIfNativeLODExists":True,
            "mayReplaceWithLowResImpostorAfter360ReachableLOSProof":False,
            "sourceCollisionAndNavChanges":False,
            "sourceMeshMaterialReferencesChanges":False,
        })
        by_native_type[idx]+=1
    result={
        "authority":"source authored Pavlov UE4.21 reconstruction, NOT official BO3 T7",
        "sourceModels":493,"originalSourceActors":10793,
        "totalSourceVistaAssetTypes":sum(
            any(t in m["sourceDescription"].lower() for t in SAFE_VISTA_MARKERS)
            for m in meshrows.values()),
        "sourceVistaDistantActorsOutside55mCANDIDATES":len(all_vista),
        "sourceVistaDistantNativeModelTypes":len(by_native_type),
        "sourceVistaDistantActorsPerOriginalMeshType":dict(sorted(by_native_type.items())),
        "sourceVistaActorsWithUnverifiedGameplayRelevance":len(all_vista),
        "actorDetails":all_vista,
        "rejectedForPossibleGameplayOverlap":forbidden_overlap,
        "rejectedForProtectedBuilding":rejected_incomplete,
        "sourceOriginalsStillUntouched":True,
        "proofNeverVisibleOrReachable":False,
        "safeToPermanentlyDelete":False,
        "safeToShareOriginalNearDDSAsReducedGlobalTexture":False,
        "fullCharacterReachableNavAnd360LineOfSightProbeRequired":True,
        "GPUFPSNotBenchmarked":True,
        "recommendation":"First downsample ONLY explicitly backdrop-exclusive source assets with independent materials/geometry and reachable-LOS proof. For shared foliage use per-instance full-fidelity near/low-detail far resources, never global downscale.",
    }
    if not all_vista:
        raise ValueError("no source-authored actual vista/background distant candidates")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-source-inventory",type=Path,required=True)
    p.add_argument("--distant-actor-policy",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    obj=inspect(json.loads(args.original_source_inventory.read_text()),
                json.loads(args.distant_actor_policy.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(obj,indent=2)+"\n")
    print("XZOGOT_NACHT_ORIGINAL_SOURCE_VISTA_FAR_BACKDROP_RESEARCH_GREEN",
          " vista_native_asset_types",obj["totalSourceVistaAssetTypes"],
          " distant_vista_instances",obj["sourceVistaDistantActorsOutside55mCANDIDATES"],
          " distant_native_vista_types",obj["sourceVistaDistantNativeModelTypes"],
          " never_visible_claim",obj["proofNeverVisibleOrReachable"],
          " original_geometry_and_textures_untouched",obj["sourceOriginalsStillUntouched"])
if __name__=="__main__":
    main()
