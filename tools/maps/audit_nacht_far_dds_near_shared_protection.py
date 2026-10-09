#!/usr/bin/env python3
"""Exact-source original Pavlov Nacht far-only texture sharing audit (NO rewriting).

Distant foliage source actors often SHARE original material/DDS with trees
near the player's building. A global downscale would blur the near scenery:
prove exclusive usage before ever considering Android low-res texture assets.
Original GLB, texture binaries, UE4.21 materials, and gameplay unchanged.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-materials",type=Path,required=True)
    parser.add_argument("--exterior-policy",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    opt=parser.parse_args()
    data=json.loads(opt.source_materials.read_text())
    policy=json.loads(opt.exterior_policy.read_text())
    require(data.get("sourceActorCount")==10793 and data.get("sourceMeshTypeCount")==493
            and data.get("originalSourceSurfaceBindings")==16595
            and data.get("distinctSourceEffectiveMaterials")==574,
            "not validated complete original UE4.21 source material authority")
    require(policy.get("sourceActorCount")==10793 and policy.get("sourceNativeMeshTypes")==493
            and policy.get("largeGameplayRegionProtectionRadiusM",0)>=55,
            "near playable Nacht building safeguard missing")
    far_ids={str(a["actorId"]) for a in policy["actors"]}
    require(len(far_ids)==policy["eligibleOriginalVisualActors"]==440,
            "duplicate or altered far source foliage actor classification")
    require(all(a.get("authoredAssetClass") in ("tree_silhouette","small_foliage","small_decorative_ground")
                and a.get("buildingAnchorHorizontalDistanceM",0)>=55
                for a in policy["actors"]),
            "far actor not verified outside protected source building")
    source_far=Counter()
    source_near=Counter()
    actors=set()
    slots=0
    for row in data["actors"]:
        actor=str(row["actorId"])
        require(actor not in actors, "source actor duplicate")
        actors.add(actor)
        mats=row["sourceMaterialPaths"]
        require(isinstance(mats,list) and bool(mats),"source actor without material sections")
        slots+=len(mats)
        target=source_far if actor in far_ids else source_near
        target.update(str(m) for m in mats)
    require(len(actors)==10793 and far_ids.issubset(actors) and slots==16595,
            "original actors or material surfaces lost")
    all_materials=set(source_far)|set(source_near)
    require(len(all_materials)==574,"original effective source materials missing")
    near_only=set(source_near)-set(source_far)
    shared=set(source_near)&set(source_far)
    far_only=set(source_far)-set(source_near)

    records={str(r["materialPath"]):r for r in data["materials"]}
    require(len(data["materials"])==574, "source authored material rows incomplete")
    def dependences(material):
        row=records.get(material)
        if row is None:
            # synthetic default sentinel has no DDS; don't invent one.
            require(material.lower()=="xziel://ue/default-surface",
                    "actual authored source material record missing: "+material)
            return set()
        values=set()
        for t in row.get("textures",[]):
            native=t.get("native",{})
            name=str(native.get("runtimeFile",""))
            if name:
                values.add(name)
        return values

    far_tex=set()
    near_tex=set()
    far_only_mat_tex=set()
    for material in source_far:
        far_tex|=dependences(material)
    for material in source_near:
        near_tex|=dependences(material)
    for material in far_only:
        far_only_mat_tex|=dependences(material)
    shared_dds=far_tex & near_tex
    far_only_dds=far_tex - near_tex
    original_textures={str(t["runtimeFile"]):t for t in data["textureAssets"]}
    require(len(original_textures)==1581, "missing original native DDS catalog")
    require((near_tex|far_tex).issubset(original_textures),
            "source material references unverified DDS")
    saved_bytes=sum(int(original_textures[x]["fileBytes"]) for x in far_only_dds)

    result={
        "source":"complete original Pavlov UE4.21 source XZMI/GLB material bindings, not BO3 T7",
        "original_actor_count":10793,
        "original_native_source_mesh_types":493,
        "original_indexed_material_surface_bindings":16595,
        "original_effective_materials":574,
        "far_exterior_source_actor_candidates":len(far_ids),
        "near_actors_with_unaltered_source_materials":10793-len(far_ids),
        "source_materials_only_on_far_candidate_actors":len(far_only),
        "source_materials_shared_between_far_and_near_actors":len(shared),
        "materials_used_only_near_or_on_other_actors":len(near_only),
        "far_only_material_source_paths":sorted(far_only),
        "far_materials_used_on_close_original_geometry":sorted(shared),
        "far_source_material_dependent_DDS_count":len(far_tex),
        "far_source_DDS_shared_with_near_geometry_count":len(shared_dds),
        "far_only_unshared_original_DDS_count":len(far_only_dds),
        "far_only_original_DDS_paths":sorted(far_only_dds),
        "original_DDS_disk_bytes_possible_upper_limit_on_far_only":saved_bytes,
        "warning":"Texture references enumerated from authored UE4.21 material parameter table only; engine graph closure and final Godot runtime dependency inventory not yet proven. ZERO texture downscaling applied.",
        "source_texture_binary_rewritten":False,
        "shared_original_close_texture_resolution_changed":False,
        "source_actor_materials_reassigned":False,
        "actual_mobile_GPU_memory_or_FPS_measured":False,
    }
    opt.output.parent.mkdir(parents=True,exist_ok=True)
    opt.output.write_text(json.dumps(result,indent=2)+"\n")
    print("XZOGOT_NACHT_FAR_EXTERIOR_SOURCE_TEXTURE_SHARING_AUDIT_GREEN",
          " source_far_actors",len(far_ids),
          " far_only_materials",len(far_only),
          " far_near_shared_materials",len(shared),
          " source_exclusive_DDS",len(far_only_dds),
          " original_unshared_DDS_bytes_upper_bound",saved_bytes,
          " no_upclose_quality_loss_possible_by_global_downscale")
    if len(shared)==0:
        raise ValueError("unexpected all far foliage materials exclusive; inspect authored atlas coupling")
if __name__=="__main__":
    main()
