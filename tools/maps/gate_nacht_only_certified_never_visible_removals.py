#!/usr/bin/env python3
"""Nacht 'delete only if NEVER seen' conservative gate.

Do not call sampled 360-degree screenshots exhaustive. Deletion needs
continuous coverage for all *actual reachable* player camera/height/door/window
states and only permanent opaque non-interactive source blockers. This tool
generates non-destructive KEEP/LOD candidates and fail-closed deletion list.
It refuses any purported visual-invisibility certificate until a validated
complete playable-nav+view-volume evidence pipeline exists.
"""
import argparse
import json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vista",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    data=json.loads(args.vista.read_text())
    assert data["sourceModels"]==493 and data["originalSourceActors"]==10793
    assert data["sourceVistaDistantActorsOutside55mCANDIDATES"]==340
    assert not data["proofNeverVisibleOrReachable"]
    seen=set()
    records=[]
    for row in data["actorDetails"]:
        id=str(row["originalActorID"])
        assert id not in seen
        seen.add(id)
        assert row["sourceRootDistanceFromBuildingM"]>=55
        assert row["sourceClassification"]=="tree_silhouette"
        records.append({
            "actorId":id,
            "nativeOriginalType":int(row["sourceNativeMeshType"]),
            "verifiedFarBackgroundVistaAuthorTag":True,
            "allReachableWindows360LOSCompleted":False,
            "allGameplayCameraPositionsAndEyeHeightsVerified":False,
            "allGameplayDoorAndBarricadeStatesVerified":False,
            "allOutdoorNavigationVolumesCertified":False,
            "reversibleLowResolutionPerActorAllowed":True,
            "permanentlyRemoveOriginalGeometry":False,
            "removalBlockedBy":"no complete real playable camera/occlusion proof",
        })
    if len(records)!=340:raise ValueError("source vista actor identity mismatch")
    report={
        "source":"archived Pavlov UE4.21, not original BO3 T7",
        "originalWorldActors":10793,
        "authoredFarVistaSourceCandidates":len(records),
        "candidateLODArraysAreOnlyReversible":True,
        "certified100PercentNeverVisible":0,
        "actorIdsApprovedForPermanentDelete":[],
        "sourceBackdropActorCountKept":340,
        "nearAllWindowsCameraCompletenessCertified":False,
        "360DegreeReachableCameraVolumeCertified":False,
        "realShippingWalkableNavigationAndDoorStateCompletenessCertified":False,
        "opaqueOcclusionAllAnglesAllDoorStatesCertified":False,
        "sourceActorsGeometryPhysicallyDeleted":0,
        "doNotInferNeverVisibleFromDistanceAlone":True,
        "doNotInferNeverVisibleFromNighttimeDarknessFogOrCurrentFarClip":True,
        "provenances":"340 source-vista actors kept, pending full reachable camera 360-degree LOS evidence",
        "actors":records,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print("XZOGOT_NACHT_340_AUTHORED_FAR_VISTAS_SAFE_PERMANENT_DELETE_GUARD_GREEN",
          " original_actor_census=10793",
          " vista_keep_or_source_LOD=340",
          " deleted=0",
          " full_reachability_PROVEN=false")
if __name__=="__main__":main()
