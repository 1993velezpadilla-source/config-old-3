#!/usr/bin/env python3
"""Research-only mobile static renderer grouping plan, NOT implemented batching.

Groups only genuinely identical SOURCE geometry type AND source-authored,
per-surface ordered effective materials inside separately cullable spatial
cells. No source actor/world transform or material identity can be lost.
Outputs evidence, not an edited Godot scene or a claim of actual FPS.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def xyz_from_source_matrix(row):
    raw = row["matrixRowMajor"]
    if not isinstance(raw, list) or len(raw) != 16:
        raise ValueError("missing original 4x4 actor transform")
    vals = list(map(float, raw))
    if not all(math.isfinite(n) for n in vals):
        raise ValueError("non-finite original transform")
    # Original archived native basis verified by source_world_bounds gauntlet.
    # Basis XZIEL(+X,+Y,+Z) -> Godot(-Z,-X,+Y).
    return (-vals[7], vals[11], -vals[3])


def calculate(scene, report, cell_width, floor_height):
    original = scene["instances"]
    author = report["actors"]
    if (len(original) != 10793 or len(author) != 10793
            or len(scene.get("meshes", [])) != 493
            or report.get("originalSourceSurfaceBindings") != 16595
            or report.get("distinctSourceEffectiveMaterials") != 574):
        raise ValueError("authoritative 10793/493/16595/574 source dataset missing")
    indexed={}
    for row in author:
        actor = str(row["actorId"])
        if actor in indexed:
            raise ValueError("duplicate actor in material authority")
        indexed[actor]=row
    actors=set()
    groups=defaultdict(list)
    original_surfaces=0
    original_materials=set()
    actor_sha=hashlib.sha256()
    for row in original:
        iid=str(row["instanceId"])
        if iid in actors or iid not in indexed:
            raise ValueError("duplicate/orphan original scene actor "+iid)
        actors.add(iid)
        material=indexed[iid]
        mesh=int(row["meshIndex"])
        if mesh != int(material["meshIndex"]) or mesh not in range(493):
            raise ValueError("mesh type changed from original material report")
        paths=material["sourceMaterialPaths"]
        if not paths or not isinstance(paths,list):
            raise ValueError("empty original mesh sections "+iid)
        assert all(isinstance(v,str) and v for v in paths),iid
        original_surfaces+=len(paths)
        original_materials.update(paths)
        location=xyz_from_source_matrix(row)
        cell=(math.floor(location[0]/cell_width),
              math.floor(location[2]/cell_width),
              math.floor(location[1]/floor_height))
        signature=(mesh,tuple(paths),cell)
        groups[signature].append(iid)
        actor_sha.update(iid.encode()+b"\0")
        actor_sha.update(json.dumps(row["matrixRowMajor"],separators=(",",":")).encode()+b"\0")
        actor_sha.update(json.dumps(paths,separators=(",",":")).encode()+b"\n")
    if actors!=set(indexed):
        raise ValueError("authoritative actor ID mismatch")
    if original_surfaces!=16595 or len(original_materials)!=574:
        raise ValueError("source surface/material count mismatch")
    groups_multi=[(key, ids) for key,ids in groups.items() if len(ids)>=2]
    single_groups=[(key, ids) for key,ids in groups.items() if len(ids)==1]
    grouped_actors=sum(len(ids) for _,ids in groups_multi)
    potential_submits=sum(len(key[1]) for key in groups)
    base_submits=original_surfaces
    if sum(len(v) for v in groups.values())!=10793:
        raise ValueError("source actor lost from exact group partition")
    if not (0<potential_submits<=16595):
        raise ValueError("invalid projected surface draw count")
    if sum(len(k[1])*len(v) for k,v in groups.items())!=16595:
        raise ValueError("source material surface instances not preserved")
    # Preserve exact transforms in a plan so downstream real Godot MultiMesh
    # compiler is required to revalidate before mutating production.
    sample=[]
    for key,ids in sorted(groups_multi,key=lambda pair:len(pair[1]),reverse=True)[:12]:
        sample.append({"sourceNativeMeshIndex":key[0],
                       "sourceMaterialPaths":list(key[1]),
                       "spatialCellXYZ":list(key[2]),
                       "actorCount":len(ids),
                       "sourceActorIDsFirst12":ids[:12]})
    result={
        "authority":"archived Pavlov UE4.21 static source (NOT BO3 T7)",
        "status":"read-only renderer grouping optimization feasibility, not applied",
        "actor_count":len(actors),
        "native_mesh_types":493,
        "original_source_surfaces":original_surfaces,
        "source_effective_materials":len(original_materials),
        "cell_width_m":cell_width,
        "height_slice_m":floor_height,
        "unique_spatial_material_mesh_groups":len(groups),
        "potential_multimesh_groups":len(groups_multi),
        "individual_singleton_groups":len(single_groups),
        "actors_in_potential_multimesh":grouped_actors,
        "actors_retaining_individual_instance":len(single_groups),
        "current_mesh_surface_submissions_upper_bound":base_submits,
        "grouped_mesh_surface_submissions_estimate":potential_submits,
        "potential_surface_submit_reduction_pct":round(100*(1-potential_submits/base_submits),3),
        "triangles_removed":0,
        "actor_world_matrix_modifications":0,
        "actor_source_material_identity_changes":0,
        "rendered_Godot_multimesh_not_yet_built":True,
        "actual_GPU_draw_calls_or_FPS_proven":False,
        "interactive_actor_safety_passed":False,
        "original_transform_material_identity_sha256":actor_sha.hexdigest(),
        "largest_exact_match_clusters":sample,
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scene",type=Path,required=True)
    p.add_argument("--material-bridge",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    source=json.loads(a.scene.read_text())
    bridge=json.loads(a.material_bridge.read_text())
    if source.get("format")!="xziel_visual_scene_v1" or not source.get("summary",{}).get("ready"):
        raise ValueError("source XZIEL static scene not ready")
    results=[calculate(source,bridge,cell_width=w,floor_height=6.0) for w in (8.0,16.0,32.0)]
    checks=[item["original_transform_material_identity_sha256"] for item in results]
    if len(set(checks))!=1:
        raise ValueError("original source actor transform/material identities changed with cell width")
    for row in results:
        print("XZOGOT_NACHT_MOBILE_SOURCE_GROUPING_PLAN_CANDIDATE",
              "cell_m",row["cell_width_m"],
              "multi_actor_groups",row["potential_multimesh_groups"],
              "actors",row["actors_in_potential_multimesh"],
              "potential_surface_submits",row["grouped_mesh_surface_submissions_estimate"],
              "estimated_reduction_percent",row["potential_surface_submit_reduction_pct"])
    best=max(results,key=lambda r:r["potential_surface_submit_reduction_pct"])
    output={
        "authority":"Pavlov UE4.21 archival reconstruction, NOT original BO3 T7",
        "status":"VERIFIED READ-ONLY plan, no rendering runtime/FPS or Android APK",
        "important":"All numbers are conservative source MATERIAL/SURFACE submit estimates, not real driver drawcalls",
        "source_actor_matrix_material_sha256":checks[0],
        "candidates":results,
        "highest_estimated_reduction_cell_m":best["cell_width_m"],
        "interactive_actor_classification_required_before_applying_plan":True,
        "real_Godot_draw_call_and_Android_FPS_validation_required":True,
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(output,indent=2)+"\n")
    print("XZOGOT_NACHT_MOBILE_SOURCE_GROUPING_10793_ACTORS_16595_SURFACES_GREEN source_identity_unchanged 3_spatial_grouping_plans")
if __name__=="__main__":
    main()
