#!/usr/bin/env python3
"""Forensic UE4 Masked OpacityMask authority vs Godot alpha-scissor emulation.

Do NOT infer all BLEND_Masked materials require texture-alpha cutouts.
A UE MasterMat may be Blend_Masked yet have no wired OpacityMask property.
The parsed archive has many partial graphs; a missing link is suggestive,
NOT a proven complete shader graph. No real material is modified here.
"""
import argparse
import collections
import json
from pathlib import Path

SOURCE_EXPECTED=10793
MASKED_EXPECTED=571
def classify(bridge):
    if bridge.get("sourceActorCount")!=SOURCE_EXPECTED or bridge.get("distinctSourceEffectiveMaterials")!=574:
        raise ValueError("RED: original archived source manifest no longer matches")
    paths={x["materialPath"]:x for x in bridge["materials"]}
    counts=collections.Counter(path for a in bridge["actors"] for path in a["sourceMaterialPaths"])
    masked=[x for x in paths.values() if x.get("blendMode")=="BLEND_Masked"]
    if len(masked)!=MASKED_EXPECTED:
        raise ValueError("RED: changed archive blend mode inventory")
    relevant=[]
    for m in masked:
        graph=m.get("sourceGraphBindings") or {}
        unknown=m.get("sourceGraphUnresolvedOutputs") or {}
        texture_candidates=m.get("sourceGraphTextureParameterCandidates") or []
        raw=m.get("baseSourceRawPropertyNames") or []
        # Absence of a graph link in PARTIAL reconstruction is not proof.
        declared=(
            "OpacityMask" in raw
            or "OpacityMask" in graph
            or "opacity_mask" in graph
            or "OpacityMask" in unknown
        )
        relevant.append({
            "sourceMaterialPath":m["materialPath"],
            "originalSurfaceInstances":counts[m["materialPath"]],
            "sourceGraphStatus":m.get("sourceGraphStatus"),
            "sourceMaskParameterDeclared":declared,
            "originalBlendMode":m["blendMode"],
            "originalOpacityMaskClipValue":m.get("opacityMaskClipValue"),
            "originalSourceBaseRawPropertyHasOpacityMask":"OpacityMask" in raw,
            "sourcePartialGraphOpacityLinkMustNotBeAssumedAbsent":m.get("sourceGraphStatus")!="exact",
            "sourceTextureParameterNames":[x.get("parameter") for x in m.get("textures") or []],
            "sourceGraphTextureParameterCandidates":texture_candidates,
            "sourceMasterMaterialPath":m.get("semanticBaseMaterialPath"),
            "materialShaderRiskHypothesis":"Potential false Godot texture-alpha scissor on material whose source OpacityMask is unwired or missing from cook. Requires 3-stage rendering evidence.",
        })
    linked=sum(x["sourceMaskParameterDeclared"] for x in relevant)
    source_nolink=sum(not x["sourceMaskParameterDeclared"] for x in relevant)
    ranked=sorted(relevant,key=lambda r:r["originalSurfaceInstances"],reverse=True)
    out={
        "source":"Pavlov UE4.21 archived reconstructed original source, NOT authentic BO3 T7",
        "sourceActors":bridge["sourceActorCount"],
        "effectiveOriginalMaterials":574,
        "maskedSourceMaterials":len(masked),
        "maskedSourceSurfaceBindings":sum(x["originalSurfaceInstances"] for x in relevant),
        "maskedMaterialsWithSourceOpacityMaskDeclared":linked,
        "maskedMaterialsWithoutExplicitOpacityMaskInRecoveredPartialGraph":source_nolink,
        "sourceShaderGraphMayBeIncomplete":True,
        "GodotBindingBehavior":"xziel_benchmark_loader._material_for_path enables TRANSPARENCY_ALPHA_SCISSOR for ALL mask flags and samples diffuse texture alpha",
        "unverifiedPotentialError":"Unreal Masked mode with no material-output OpacityMask must render opaque for BaseColor; currently Godot may cut by unrelated diffuse alpha",
        "diagnosticOnlyCandidateMaterials":ranked,
        "doNotAutomaticallyForceAllSourceMaskedSurfacesOpaque":True,
        "noPermanentMaterialOrGeometryChange":True,
        "actual9ImageForensicsIsRequiredBeforeFix":True,
        "mobileFrameRateProven":False,
        "readyToMerge":False,
    }
    if sum(counts.values())!=16595 or len(relevant)!=571:
        raise ValueError("RED: exact effective source bindings lost")
    return out

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--bridge",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=classify(json.loads(a.bridge.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print("XZOGOT_NACHT_MASKED_OPACITY_GRAPH_PARTIAL_SOURCE_AUTHORITY_AUDIT_GREEN",
        "masked_source_materials=",result["maskedSourceMaterials"],
        "recovered_mask_links=",result["maskedMaterialsWithSourceOpacityMaskDeclared"],
        "real_Godot_pixel_retest_required=YES")
