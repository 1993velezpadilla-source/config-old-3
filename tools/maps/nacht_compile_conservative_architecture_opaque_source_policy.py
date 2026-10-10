#!/usr/bin/env python3
"""Conservative original UE4.21 hard-architecture source material alpha policy.

Choose *only* explicit masonry/structural material families. Exclude trees,
foliage, transparent glass, cables, wires, grills, decals, invisible VFX
and EVERY other MasterMat alpha texture. This is a REVERSIBLE proposal,
not certified UE shader graph reconstruction or shipping alpha fix.
"""
import argparse
from collections import Counter
import json
import re
from pathlib import Path

STRUCTURE = re.compile(
    r"^(?:t7_concrete|t7_plaster|t7_linoleum|concrete_wall|"
    r"mtl_p7_zm_gen_proto_column|t7_metal_rust_ceiling)",re.I)
NO_CARD = re.compile(
    r"(foliage|tree|grass|leaves?|branches?|decal|glass|window|"
    r"chain|fence|wire|invisible|alpha|sprite|particle|billboard|"
    r"barbed|poster|grate|cloth|curtain|sign)",re.I)
MASTER = "Content/CustomMaps/UGC2755515831/CoD_nacht/AssetsFolder/MasterMat.MasterMat"

def compile_safe(data):
    if (data.get("sourceActorCount")!=10793 or
        data.get("distinctSourceEffectiveMaterials")!=574 or
        data.get("originalSourceSurfaceBindings")!=16595):
        raise ValueError("RED: native source actor/material authority mismatch")
    material_map={r["materialPath"]:r for r in data["materials"]}
    if len(material_map)!=574:
        raise ValueError("RED: original material records are duplicated")
    bindings=Counter(p for actor in data["actors"] for p in actor["sourceMaterialPaths"])
    if sum(bindings.values())!=16595:
        raise ValueError("RED: original source material binding total changed")
    candidates=[]
    excluded=[]
    for source_path, m in material_map.items():
        name=source_path.rsplit("/",1)[-1].split(".",1)[0]
        mask=m.get("blendMode")=="BLEND_Masked"
        source_master=m.get("semanticBaseMaterialPath")==MASTER
        linked=(
            "OpacityMask" in (m.get("sourceGraphBindings") or {})
            or "OpacityMask" in (m.get("sourceGraphUnresolvedOutputs") or {})
            or "OpacityMask" in (m.get("baseSourceRawPropertyNames") or []))
        safe=(
            mask and source_master and not linked
            and m.get("sourceGraphStatus")=="partial"
            and bool(STRUCTURE.search(name))
            and not bool(NO_CARD.search(name)))
        entry={"materialPath":source_path,"sourceMaterialShortName":name,
               "originalSourceBindings":bindings[source_path],
               "sourceMasked":mask,"sourceMasterMat":source_master,
               "opacityLinkUnproven":not linked,
               "sourceGraphPartial":m.get("sourceGraphStatus")=="partial"}
        (candidates if safe else excluded).append(entry)
    count=sum(x["originalSourceBindings"] for x in candidates)
    if len(candidates)!=26 or count!=1262:
        raise ValueError(f"RED: source hard-surface policy cannot silently drift {len(candidates)}, {count}")
    if any(NO_CARD.search(c["sourceMaterialShortName"]) for c in candidates):
        raise ValueError("RED: glass/foliage/decals became opaque")
    # Specifically prove representative source foliage and glass are NOT selected.
    terms=("foliage_tree","foliage_grass","glass_dirty","chainlink_fence")
    for term in terms:
        if not any(term in x["materialPath"].lower() for x in excluded):
            raise ValueError("RED: no original excluded transparency category: "+term)
    return {
      "source":"archived Pavlov UE4.21 source reconstruction, NOT BO3 T7",
      "originalActorCount":10793,
      "originalEffectiveMaterials":574,
      "originalSourceMaterialBindings":16595,
      "hardArchitecturalCandidateMaterials":len(candidates),
      "hardArchitecturalSourceBindings":count,
      "allOtherOriginalMaterialsUntouched":574-len(candidates),
      "candidates":sorted(candidates,key=lambda x:-x["originalSourceBindings"]),
      "excludedMaterialsSourceCount":len(excluded),
      "excludedTransparentCategoryGuards":list(terms),
      "partialSourceGraphsAreNotOriginalGraphCompletion":True,
      "originalSourceDDSAndLightingUnmodified":True,
      "noPermanentMeshTransformOrCollisionEdits":True,
      "architectureOnlyAlphaExperimentReversible":True,
      "doNotForceTreesGlassVFXOrOtherMasterMatsOpaque":True,
      "productionEnabled":False,
      "allPlayableWindowCameraVisualParityApproved":False
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    d=compile_safe(json.loads(a.source.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(d,indent=2)+"\n")
    print("XZOGOT_NACHT_ARCHIVE_EXACT_26_ARCHITECTURE_ONLY_ALPHA_SCISSOR_CANDIDATES_GREEN",
          "actors",d["originalActorCount"],
          "safe_materials",len(d["candidates"]),
          "source_bindings",d["hardArchitecturalSourceBindings"],
          "NOT_SHIPPING")
