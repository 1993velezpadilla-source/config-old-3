#!/usr/bin/env python3
"""Audit original-source Nacht materials; never mislabel bound DDS as shader parity.

The archived scene comes from a Pavlov UE4.21 reconstruction, NOT official BO3.
A non-null Godot albedo texture is NOT enough evidence for accurate source
Masked/Unlit/opacity/world-position-offset shader behavior or lighting.
"""
import argparse
import collections
import json
import re
from pathlib import Path

BLACK_RISK_PATTERN = re.compile(r"wall|concrete|plaster|ceiling|roof|floor|tile|brick|window|glass|stone|door|plywood|wood|board",re.I)
def audit(data, godot=None):
    if data.get("sourceActorCount")!=10793 or data.get("distinctSourceEffectiveMaterials")!=574 or data.get("originalSourceSurfaceBindings")!=16595:
        raise ValueError("RED: source authority is not the original 10793 actors / 574 materials / 16595 surfaces")
    materials={row["materialPath"]:row for row in data["materials"]}
    if len(materials)!=574:
        raise ValueError("RED: missing or duplicated effective source material definition")
    actor_counts=collections.Counter()
    per_actor_material={}
    fallback_ids=[]
    for actor in data["actors"]:
        iid=actor["actorId"]
        if iid in per_actor_material:
            raise ValueError("RED: source actor reused " + iid)
        paths=actor["sourceMaterialPaths"]
        if not paths:
            raise ValueError("RED: source actor with no material bindings: "+iid)
        for path in paths:
            if path not in materials:
                raise ValueError("RED: missing effective source material "+path)
            actor_counts[path]+=1
        per_actor_material[iid]=paths
        if "xziel://ue/default-surface" in paths:
            fallback_ids.append(iid)
    if sum(actor_counts.values())!=16595:
        raise ValueError("RED: original source material-bound surface authority lost")
    statuses=collections.Counter(str(x.get("sourceGraphStatus") or "not_applicable") for x in materials.values())
    blend=collections.Counter(str(x.get("blendMode")) for x in materials.values())
    shading=collections.Counter(str(x.get("shadingModel")) for x in materials.values())
    affected=sorted((
        {
            "sourceMaterialPath":path,
            "sourceActorSurfaceInstances":actor_counts[path],
            "cookedMaterialGraphStatus":str(row.get("sourceGraphStatus") or "not_applicable"),
            "sourceBlendMode":row.get("blendMode"),
            "sourceShadingModel":row.get("shadingModel"),
            "sourceTwoSided":bool(row.get("twoSided",False)),
            "sourceGraphUnresolvedOutputs":list((row.get("sourceGraphUnresolvedOutputs") or {}).keys()),
            "hasSourceAuthoredTextureParameter":bool(row.get("textures")),
            "sourceTextureParameterCount":len(row.get("textures") or []),
            "authoritativeSourceColorCount":len(row.get("colors") or []),
        }
        for path,row in materials.items() if BLACK_RISK_PATTERN.search(path)
    ),key=lambda x:-x["sourceActorSurfaceInstances"])
    default_rows={id:{"meshIndex":next(a["meshIndex"] for a in data["actors"] if a["actorId"]==id),
                      "sourceMaterialPaths":per_actor_material[id]} for id in fallback_ids}
    out={
      "source":"Pavlov UE4.21 archival authored scene (NOT BO3 T7)",
      "fullNativeSourceActors":len(per_actor_material),
      "sourceSurfaceBindings":sum(actor_counts.values()),
      "sourceEffectiveMaterials":len(materials),
      "effectiveCookedMaterialGraphStatuses":dict(statuses),
      "effectiveCookedBlendModes":dict(blend),
      "effectiveCookedShadingModels":dict(shading),
      "flatDefaultEngineCubeSourceActors":default_rows,
      "topPotentialInteriorArchitecturalSourceMaterialRows":affected[:120],
      "architecturalSourceDistinctMaterials":len(affected),
      "architecturalSourceSurfaceBindings":sum(x["sourceActorSurfaceInstances"] for x in affected),
      "allMaterialsWithDDSLoadedProofOnly":None if godot is None else {
          "totalTexturedSourceSurfaces":godot["actual_godot_textured_surfaces"],
          "totalSourceSurfaceBindings":godot["actual_godot_source_surface_bindings"],
          "distinctMaterialPathsWithTexture":godot["unique_original_effective_materials_with_loaded_albedo"],
          "DDSLoadedIsNOTSourceShaderParity":True,
      },
      "blackRegionsExplainedByTextureAbsence":False,
      "allUnrealMaterialGraphOutputsReconstructed":False,
      "allBlackScreenshotsCertifiedIntendedHoles":False,
      "colorAndAlphaShaderInterpretationNeedsSceneLevelPixelDiagnostics":True,
      "shippingApproved":False,
      "sourceMeshGeometryDeleted":0,
    }
    if len(fallback_ids)!=2 or set(fallback_ids)!={"ue_instance_000004","ue_instance_000005"}:
        raise ValueError("RED: unexpected default-surface source actor identity")
    if godot is not None and not (godot["actual_godot_source_surface_bindings"]==16595 and godot["actual_godot_textured_surfaces"]==16593 and godot["unique_original_effective_materials_with_loaded_albedo"]==573):
        raise ValueError("RED: original Godot source material provenance changed")
    return out

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--actor-material-authority",type=Path,required=True)
    p.add_argument("--godot-binding-report",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    report=audit(json.loads(a.actor_material_authority.read_text()),
                 json.loads(a.godot_binding_report.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+"\n")
    print("XZOGOT_NACHT_ARCHIVED_10793_ACTORS_574_MATERIAL_BLACK_VISUAL_TRIAGE_GREEN",
          "partial_materials",report["effectiveCookedMaterialGraphStatuses"].get("partial",0),
          "default_gray_meshes",list(report["flatDefaultEngineCubeSourceActors"]),
          "material_bindings",report["sourceSurfaceBindings"],
          "BLACK_HOLES_NOT_YET_PROVEN_FIXED")
