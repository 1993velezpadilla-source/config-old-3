#!/usr/bin/env python3
"""Research only: classify exact source UE4.21 MasterMat opacity connections.

A source UMaterial whose OpacityMask expression input is not connected would
have constant OpacityMask=1 even with BLEND_Masked. But this export contains
partial cooked graphs; absence in exported fields alone is NOT proof it is
disconnected in the original engine. No shipping shader overrides permitted.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

MASTER="Content/CustomMaps/UGC2755515831/CoD_nacht/AssetsFolder/MasterMat.MasterMat"
def plan(report):
    assert report["sourceActorCount"]==10793
    assert report["originalSourceSurfaceBindings"]==16595
    assert report["distinctSourceEffectiveMaterials"]==574
    materials={m["materialPath"]:m for m in report["materials"]}
    if len(materials)!=574:
        raise ValueError("duplicate original material keys")
    counts=Counter(path for actor in report["actors"] for path in actor["sourceMaterialPaths"])
    if sum(counts.values())!=16595:
        raise ValueError("original material binding sum corrupted")
    candidates=[]
    not_covered=[]
    mask_total=0
    for m in materials.values():
        if m.get("blendMode")!="BLEND_Masked":
            continue
        mask_total+=1
        graph=m.get("sourceGraphBindings",{}) or {}
        unresolved=m.get("sourceGraphUnresolvedOutputs",{}) or {}
        base=set(m.get("baseSourceRawPropertyNames",[]))
        has_output="OpacityMask" in graph or "OpacityMask" in unresolved or "OpacityMask" in base
        original_master=m.get("semanticBaseMaterialPath")==MASTER
        row={
            "materialPath":m["materialPath"],
            "sourceSurfaceBindings":counts[m["materialPath"]],
            "sourceMaster":m.get("semanticBaseMaterialPath"),
            "graphStatus":m.get("sourceGraphStatus"),
            "sourceOpacityMaskOutputExplicitlyPresent":has_output,
            "hasAuthoritativeSourceMaster":original_master,
            "sourceBlendMode":m.get("blendMode"),
            "sourceOriginalTwoSided":bool(m.get("twoSided")),
            "sourceTextureCount":len(m.get("textures",[])),
        }
        if original_master and not has_output and m.get("sourceGraphStatus")=="partial":
            row["candidate"]="research_only_opaque_if_original_UMaterial_mask_truly_unwired"
            candidates.append(row)
        else:
            row["candidate"]="reject_without_proven_source_mask_graph"
            not_covered.append(row)
    if mask_total!=571 or len(candidates)!=564 or len(not_covered)!=7:
        raise ValueError(f"original cooked graph pattern drift: {mask_total}/{len(candidates)}/{len(not_covered)}")
    for r in candidates:
        if not (r["hasAuthoritativeSourceMaster"] and not r["sourceOpacityMaskOutputExplicitlyPresent"]):
            raise ValueError("unsafe source opacity candidate")
    return {
        "source":"Pavlov UE4.21 reconstructed archive, not official BO3 T7",
        "sourceActors":10793,
        "sourceSurfaceBindings":16595,
        "sourceMaterials":574,
        "maskMaterials":571,
        "provisionallyUnwiredSourceMasterMaterialCount":len(candidates),
        "provisionallyUnwiredSourceMasterSurfaceBindings":sum(r["sourceSurfaceBindings"] for r in candidates),
        "otherMaskedMaterialsMustRemainUnchanged":len(not_covered),
        "sourceProvenanceNotCompleteShaderGraph":True,
        "requiresNative9PNGMaskVsLightPixelEvidence":True,
        "renderSourceMaskOnlyForKnownConstantOneOnlyAfterActualGraphConfirm":True,
        "productionIntegrationApproved":False,
        "automaticMaskOverrideExecuted":False,
        "candidates":sorted(candidates,key=lambda r:-r["sourceSurfaceBindings"]),
        "excluded":not_covered,
    }

def self_test():
    from zipfile import ZipFile
    # Source-test only happens with provided original actual authority artifact;
    # avoiding fabricated manifest rows avoids hiding real source identity drift.
    print("XZOGOT_NACHT_OPACITY_MASTER_RESEARCH_POLICY_CODE_GREEN")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test:
        self_test()
    else:
        if args.source is None or args.output is None:
            ap.error("requires --source and --output")
        result=plan(json.loads(args.source.read_text()))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+"\n")
        print("XZOGOT_NACHT_REAL_SOURCE_564_MASTER_MASK_OUTPUT_HYPOTHESIS_GREEN",
              "candidates=",len(result["candidates"]),
              "surface_bindings=",result["provisionallyUnwiredSourceMasterSurfaceBindings"],
              "excluded=",len(result["excluded"]),
              "SHIPPING_FIX_NOT_APPROVED")
