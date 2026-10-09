#!/usr/bin/env python3
"""Full archived Nacht exact bunker concrete actor/material provenance.

The two actors have similarly named but DIFFERENT source UE4 material
assets, DIFFERENT authored source DDS, and DIFFERENT mesh surface slots.
Never consolidate by basename in the renderer. Source is Pavlov UE4.21
reconstruction, not BO3 T7; no geometry/material modifications here.
"""
import argparse
import json
from pathlib import Path
from collections import Counter

ROOT="Content/CustomMaps/UGC2755515831/CoD_nacht/"
NAME="t7_concrete_poured_bunker_dirty_01.t7_concrete_poured_bunker_dirty_01"
EXPECTED={
    "ue_instance_010576":{"meshIndex":470,"sourceMaterialPath":ROOT+"materials/"+NAME,"materialSlot":2,"albedoDDSNativeIndex":635},
    "ue_instance_010730":{"meshIndex":17,"sourceMaterialPath":ROOT+"MAP_FILES/"+NAME,"materialSlot":0,"albedoDDSNativeIndex":152},
}

def run(authority):
    actors=authority.get("actors")
    materials=authority.get("materials")
    assert authority.get("sourceActorCount")==10793
    assert authority.get("originalSourceSurfaceBindings")==16595
    assert authority.get("distinctSourceEffectiveMaterials")==574
    assert len(actors)==10793 and len(materials)==574
    by_actor={a["actorId"]:a for a in actors}
    by_material={m["materialPath"]:m for m in materials}
    if len(by_actor)!=10793 or len(by_material)!=574:
        raise ValueError("RED duplicate exact source actor or material")
    if sum(len(a["sourceMaterialPaths"]) for a in actors)!=16595:
        raise ValueError("RED source original surface assignment count changed")
    observed={}
    for actor_id,required in EXPECTED.items():
        row=by_actor[actor_id]
        assert row["meshIndex"]==required["meshIndex"]
        source_path=required["sourceMaterialPath"]
        matches=[i for i,p in enumerate(row["sourceMaterialPaths"]) if p==source_path]
        if matches!=[required["materialSlot"]]:
            raise ValueError("RED exact concrete actor SOURCE path or surface slot mismatch")
        material=by_material[source_path]
        if material.get("blendMode")!="BLEND_Masked":
            raise ValueError("RED original bunker source opacity blend changed")
        orig=next((p["native"]["nativeIndex"] for p in material.get("textures",[])
                   if p.get("parameter")=="AlbedoTexture"),None)
        if orig!=required["albedoDDSNativeIndex"]:
            raise ValueError("RED native texture palette assignment changed")
        if material.get("sourceGraphStatus")!="partial":
            raise ValueError("RED original cooked UE shader graph completeness assumption changed")
        observed[actor_id]={
            **required,
            "actualSourceOriginalMaterialBlendMode":material["blendMode"],
            "sourceCookedGraphIncomplete":True,
            "sourceAlbedoDDSSourceType":"Original authored UE texture, NOT cloned or generated",
        }
    if len({v["sourceMaterialPath"] for v in observed.values()})!=2:
        raise ValueError("RED source material paths collapsed accidentally")
    if len({v["albedoDDSNativeIndex"] for v in observed.values()})!=2:
        raise ValueError("RED two original DDS textures erroneously combined")
    all_bindings=Counter(p for row in actors for p in row["sourceMaterialPaths"])
    for record in observed.values():
        if all_bindings[record["sourceMaterialPath"]]!=1:
            raise ValueError("RED bunker target source material bound more than once")
    return {
        "source":"Original archival Pavlov UE4.21 reconstruction not official BO3 T7",
        "totalSourceActorNodes":10793,
        "originalSurfaceBindings":16595,
        "sourceMaterialCount":574,
        "exactTwoActorOriginalSourceMaterials":observed,
        "originalSourceDDSAlbedoDifferent":True,
        "originalSurfaceIndexDifferent":True,
        "researchAlphaScissorHypothesisNotProven":True,
        "retargetingBaseNameAcrossMaterialFoldersForbidden":True,
        "0OriginalSourceActorNodesDeleted":True,
        "productionFixNotApproved":True,
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    r=run(json.loads(args.source.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(r,indent=2)+"\n")
    print("XZOGOT_NACHT_TWO_DIFFERENT_NATIVE_BUNKER_SOURCE_DDS_AND_ACTOR_SLOTS_GREEN",
          json.dumps(r["exactTwoActorOriginalSourceMaterials"]))
