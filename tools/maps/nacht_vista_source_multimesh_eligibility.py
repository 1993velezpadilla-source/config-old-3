#!/usr/bin/env python3
"""Read-only Vista MultiMesh eligibility: no deletions, geometry changes or FPS claims."""
import argparse
import json
from collections import defaultdict
from hashlib import sha256
from math import floor
from pathlib import Path

WIDTHS = (16, 24, 32, 48, 64)

def audit(material, policy, vista):
    if material.get("sourceActorCount") != 10793 or material.get("originalSourceSurfaceBindings") != 16595:
        raise ValueError("RED: invalid original actor/material authority")
    if policy.get("sourceActorCount") != 10793 or policy.get("largeGameplayRegionProtectionRadiusM", 0) < 55:
        raise ValueError("RED: source actor 55m protection ring missing")
    if vista.get("originalSourceActors") != 10793 or len(vista.get("actorDetails", [])) != 340:
        raise ValueError("RED: exactly 340 original Vista candidates required")
    if len(material["actors"]) != 10793:
        raise ValueError("RED: source actor material manifest truncated")
    by_id = {r["actorId"]: r for r in material["actors"]}
    if len(by_id) != 10793:
        raise ValueError("RED: duplicate actor IDs")
    policy_by_id = {r["actorId"]: r for r in policy["actors"]}
    if len(policy_by_id) != len(policy["actors"]):
        raise ValueError("RED: duplicate source visual policy IDs")
    seen = set()
    rows = []
    for v in vista["actorDetails"]:
        uid = v["originalActorID"]
        if uid in seen or uid not in by_id or uid not in policy_by_id:
            raise ValueError("RED: unknown or repeated source Vista actor")
        seen.add(uid)
        p, a = policy_by_id[uid], by_id[uid]
        if (v["sourceClassification"] != "tree_silhouette"
                or p["authoredAssetClass"] != "tree_silhouette"
                or int(v["sourceNativeMeshType"]) != int(a["meshIndex"])
                or int(a["meshIndex"]) != int(p["nativeSourceMeshIndex"])):
            raise ValueError("RED: source Vista original model/classification mismatch " + uid)
        if not p.get("preserveWorldMatrixAndMaterials") or not p.get("collisionAndNavNotModified"):
            raise ValueError("RED: original source actor protection missing " + uid)
        if float(p["buildingAnchorHorizontalDistanceM"]) <= 55.0:
            raise ValueError("RED: Vista candidate overlaps protected building radius " + uid)
        xz, mats = p.get("originalOriginXZ"), a["sourceMaterialPaths"]
        if not isinstance(xz, list) or len(xz) != 2 or not mats:
            raise ValueError("RED: original root position/material unavailable " + uid)
        if not all(isinstance(m, str) and m for m in mats):
            raise ValueError("RED: invalid source material " + uid)
        rows.append((uid, int(a["meshIndex"]), tuple(mats), tuple(map(float, xz))))
    if len(rows) != 340:
        raise ValueError("RED: incomplete Vista source identity audit")
    raw_slots = sum(len(r[2]) for r in rows)
    grids = {}
    for size in WIDTHS:
        groups = defaultdict(list)
        for uid, mesh_id, paths, (x, z) in rows:
            groups[(mesh_id, paths, (floor(x / size), floor(z / size)))].append(uid)
        clustered = {key: ids for key, ids in groups.items() if len(ids) >= 2}
        n_clustered = sum(map(len, clustered.values()))
        proposed_slots = sum(len(key[1]) for key in groups)
        grids[str(size)] = {
            "groupsIncludingSingletons": len(groups),
            "groupsWithMultipleOriginalActors": len(clustered),
            "originalActorsInMultiGroups": n_clustered,
            "originalActorsLeftIndividual": 340 - n_clustered,
            "maxInstancesPerSpatialGroup": max(map(len, groups.values())),
            "originalSourceMaterialSurfaceSlots": raw_slots,
            "theoreticalSurfaceSlotsAfterGroupingIfAllActorsVisible": proposed_slots,
            "theoreticalMaximumSurfaceSlotReductionNOTMeasuredDrawCalls": raw_slots - proposed_slots,
            "actualDrawCallReductionProven": False,
            "multiMeshCullingMayIncreaseDrawnTriangles": True,
        }
    return {
        "source": "Pavlov UE4.21 archived source, NOT official BO3 T7",
        "sourceActors": 10793,
        "vistaSourceActorsIdentified": 340,
        "vistaSourceMaterialSlots": raw_slots,
        "originalMeshTypes": sorted({r[1] for r in rows}),
        "sourceActorIDsSHA256": sha256("\n".join(sorted(seen)).encode()).hexdigest(),
        "researchSpatialBatchGroups": grids,
        "originalActorsDeleted": 0,
        "collisionAndNavigationMutated": False,
        "geometryAndTexturesMutated": False,
        "originalWorldMatricesAppliedOrModified": False,
        "actualMultimeshGodotDrawCallsMeasured": False,
        "androidFPSVRAMMeasured": False,
        "360ExteriorWindowReachabilityProven": False,
        "approvedForShipping": False,
        "caveats": [
            "Actual renderer material overrides, culling, shadows and winding still require runtime checks.",
            "Per-cell MultiMesh can reduce draw calls but worsen per-instance culling and triangle work.",
            "Root distance 55m is NOT proof of full player outside navigation or 360-window visibility.",
            "This gate only ranks candidates; no mesh instances or source data are altered."
        ]
    }

def main():
    p = argparse.ArgumentParser()
    for name in ("material", "policy", "vista", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    args = p.parse_args()
    data = audit(*(json.loads(v.read_text(encoding="utf-8")) for v in
                   (args.material, args.policy, args.vista)))
    assert data["vistaSourceActorsIdentified"] == 340
    assert data["originalActorsDeleted"] == 0 and not data["approvedForShipping"]
    for size, row in data["researchSpatialBatchGroups"].items():
        assert row["originalActorsInMultiGroups"] + row["originalActorsLeftIndividual"] == 340
        assert row["theoreticalSurfaceSlotsAfterGroupingIfAllActorsVisible"] <= 680
        print("XZOGOT_NACHT_AUTHORED_VISTA_GRID_SOURCE_CANDIDATES",
              size, row["groupsIncludingSingletons"],
              row["theoreticalSurfaceSlotsAfterGroupingIfAllActorsVisible"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("XZOGOT_NACHT_340_VISTA_SOURCE_BATCH_ELIGIBILITY_GREEN_NONSHIPPING")

if __name__ == "__main__":
    main()
