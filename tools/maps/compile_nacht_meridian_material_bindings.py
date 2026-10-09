#!/usr/bin/env python3
"""Compile exact original Pavlov UE4.21 authored material-to-surface map for Meridian.

Input authority is the same CUE4Parse material-binding-manifest, XZMI/XZML,
complete XZTX catalog and original native geometry already used by the
existing Xogot benchmark runtime. No materials or associations are guessed.

Produces reproducible per-original-actor, per-GLB primitive material paths
and source texture references. This is NOT a full pixel/render parity test,
nor original BO3 T7 content.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def canonical(p):
    p = str(p or "").strip().replace("\\", "/")
    if "'" in p and p.endswith("'"):
        p = p[p.find("'")+1:-1]
    low = p.lower()
    at = low.find("/content/")
    if at >= 0 and not low.startswith("/game/"):
        p = "/Game/" + p[at+len("/content/"):]
    elif low.startswith("content/"):
        p = "/Game/" + p[len("Content/"):]
    elif low.startswith("game/"):
        p = "/" + p
    elif not p.startswith("/") and "/" in p:
        p = "/Game/" + p
    return p.lower()

def glb_primitive_count(path):
    with path.open("rb") as fh:
        raw = fh.read(20)
        if len(raw) != 20:
            raise ValueError("truncated GLB: "+str(path))
        magic, ver, total, njson, kind = struct.unpack("<IIIII", raw)
        if (magic,ver,kind)!=(0x46546C67,2,0x4E4F534A):
            raise ValueError("non GLB 2.0 original native mesh "+str(path))
        if total != path.stat().st_size or njson+28 > total:
            raise ValueError("bad GLB size "+str(path))
        doc=json.loads(fh.read(njson))
    if doc.get("extras",{}).get("xziel_basis_preserved") is not True:
        raise ValueError("unproven native GLB axis "+str(path))
    return sum(len(mesh["primitives"]) for mesh in doc["meshes"])

def parse_override(row):
    out={}
    for entry in row.get("slotOverrides", []):
        idx=int(entry.get("slotIndex",-1))
        if idx in out or idx < 0:
            raise ValueError("duplicate/invalid overridden authored slot")
        out[idx]=str(entry.get("materialPath",""))
    return out

def compile_authority(opt):
    source=load(opt.scene)
    bindings=load(opt.bindings)
    effective=load(opt.xzmi)
    xzml=load(opt.xzml)
    complete=load(opt.complete)
    if (source.get("format") != "xziel_visual_scene_v1"
        or not source.get("summary",{}).get("ready")
        or len(source.get("instances",[])) != 10793
        or len(source.get("meshes",[])) != 493):
        raise ValueError("full original archived Pavlov UE4.21 scene authority absent")
    if (len(bindings.get("meshes",[])) != 493
        or len(bindings.get("materials",[])) != 635
        or len(bindings.get("instanceOverrides",[])) != 1231
        or not effective.get("ready")
        or len(effective.get("materialPaths",[])) != 574
        or not xzml.get("ready")
        or len(xzml.get("textureAssets",[])) != 718
        or not complete.get("ready")
        or len(complete.get("textureAssets",[])) != 1581):
        raise ValueError("original 493/635/1231/574/718/1581 manifest authority contract violated")
    if int(effective.get("instanceCount", -1)) != 10793 or int(effective.get("bindingCount",-1)) != 16595:
        raise ValueError("native XZMI 10793 actors/16595 surface bindings contract violated")
    source_meshes={int(x["index"]):x for x in source["meshes"]}
    bm={}
    surfaces_per_type={}
    for entry in bindings["meshes"]:
        idx=int(entry["sceneMeshIndex"])
        if idx in bm or idx not in source_meshes:
            raise ValueError("duplicate/unknown authored native mesh type")
        sections=entry.get("sections",[])
        if len(sections) != int(entry.get("submeshCount",-1)):
            raise ValueError("authored section/submesh count disagrees")
        for n, row in enumerate(sections):
            if int(row.get("submeshIndex",-1)) != n:
                raise ValueError("noncontiguous authored source submesh identity")
        path = opt.native_glbs / (Path(source_meshes[idx]["runtimeFile"]).stem + ".glb")
        count = glb_primitive_count(path)
        if count != len(sections):
            raise ValueError(f"exact native model surface count mismatch type={idx} glb={count} source={len(sections)}")
        bm[idx]=sections
        surfaces_per_type[idx]=count
    if set(bm) != set(source_meshes):
        raise ValueError("material manifest is missing source model types")
    overrides={}
    for o in bindings["instanceOverrides"]:
        iid=str(o["instanceId"])
        if iid in overrides:
            raise ValueError("duplicate source instance material overrides")
        overrides[iid]=parse_override(o)
    source_actors={str(x["instanceId"]):x for x in source["instances"]}
    if len(source_actors)!=10793 or not set(overrides).issubset(source_actors):
        raise ValueError("duplicate/orphaned original actor overrides")
    records={}
    for m in bindings["materials"]:
        path=str(m["materialPath"])
        canon=canonical(path)
        if canon in records and records[canon].get("materialPath")!=path:
            raise ValueError("source authored material canonical collision "+canon)
        records[canon]=m
    valid_effective={canonical(s) for s in effective["materialPaths"]}
    if len(valid_effective)!=574:
        raise ValueError("duplicate original effective material identities")
    texture_paths={}
    for catalog in (xzml,complete):
        for t in catalog["textureAssets"]:
            src=str(t["sourcePath"])
            key=canonical(src)
            runtime=str(t.get("runtimeFile",""))
            if key in texture_paths and texture_paths[key]["runtimeFile"]!=runtime:
                raise ValueError("conflicting original source texture identities")
            if not runtime:
                raise ValueError("original texture runtimeFile missing")
            texture_paths[key]=t
    if len(texture_paths)!=1581:
        raise ValueError(f"actual full source texture catalog distinct count={len(texture_paths)}")
    not_on_disk=[]
    for t in texture_paths.values():
        path=opt.dds / (Path(t["runtimeFile"]).stem + ".dds")
        if not path.is_file():
            not_on_disk.append(str(path))
    if not_on_disk:
        raise ValueError("missing original DDS: "+repr(not_on_disk[:8]))

    paths_used=Counter()
    total=0
    overridden=0
    actors_out=[]
    missing_mats=[]
    for iid, actor in source_actors.items():
        idx=int(actor["meshIndex"])
        ov=overrides.get(iid,{})
        by_surface=[]
        for section in bm[idx]:
            slot=int(section["slotIndex"])
            src_path=str(section.get("baseMaterialPath",""))
            if slot in ov:
                src_path=ov[slot]
                overridden+=1
            key=canonical(src_path)
            if key not in valid_effective:
                missing_mats.append((iid,idx,slot,src_path))
            paths_used[key]+=1
            by_surface.append(src_path)
            total+=1
        actors_out.append({"actorId":iid,"meshIndex":idx,"sourceMaterialPaths":by_surface})
    if total!=16595 or missing_mats:
        raise ValueError(f"expected 16595 actual authored slots, total={total}, missing={missing_mats[:12]}")
    if set(paths_used)!=valid_effective:
        raise ValueError(f"original XZMI effective material mismatch missing={sorted(valid_effective-set(paths_used))[:8]} unexpected={sorted(set(paths_used)-valid_effective)[:8]}")
    material_records=[]
    for eff in effective["materialPaths"]:
        name=canonical(eff)
        row=records.get(name)
        if row is None and name!="xziel://ue/default-surface":
            raise ValueError("original effective material missing exact authored record "+str(eff))
        material_records.append(row if row else {
            "materialPath":eff,
            "exportType":"SyntheticDefaultSurface",
            "sourceFallback":True,
            "canonicalTextures":{},
        })
    return {
        "authority":"existing Pavlov UE4.21 CUE4Parse/XZMI/XZML/XYZ TX - NOT original BO3 T7",
        "sourceActorCount":10793,
        "sourceMeshTypeCount":493,
        "originalSourceSurfaceBindings":total,
        "sourceOverrideActors":len(overrides),
        "sourceOverriddenSurfaceBindings":overridden,
        "distinctSourceEffectiveMaterials":len(paths_used),
        "sourceTextureAssetsAvailable":len(texture_paths),
        "sourceDDSFilesVerified":len(texture_paths),
        "originalUE401MaterialAssignment":True,
        "originalBO3T7Proven":False,
        "fullPixelMaterialEquivalenceProven":False,
        "renderedGodotTexturesChecked":False,
        "actors":actors_out,
        "materials":material_records,
        "textureAssets":list(texture_paths.values()),
        "nativeSurfaceCountByMeshType":surfaces_per_type,
        "source_sha256":{
          "scene":hashlib.sha256(opt.scene.read_bytes()).hexdigest(),
          "bindings":hashlib.sha256(opt.bindings.read_bytes()).hexdigest(),
          "xzmi":hashlib.sha256(opt.xzmi.read_bytes()).hexdigest(),
          "xzml":hashlib.sha256(opt.xzml.read_bytes()).hexdigest(),
        }
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scene",type=Path,required=True)
    p.add_argument("--bindings",type=Path,required=True)
    p.add_argument("--xzmi",type=Path,required=True)
    p.add_argument("--xzml",type=Path,required=True)
    p.add_argument("--complete",type=Path,required=True)
    p.add_argument("--native-glbs",type=Path,required=True)
    p.add_argument("--dds",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=compile_authority(a)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,separators=(",",":"),ensure_ascii=False)+"\n",encoding="utf-8")
    print("XZOGOT_NACHT_SOURCE_MATERIAL_ASSIGNMENT_GREEN",
          "actors",result["sourceActorCount"],
          "native_mesh_types",result["sourceMeshTypeCount"],
          "surfaces",result["originalSourceSurfaceBindings"],
          "effective_materials",result["distinctSourceEffectiveMaterials"],
          "overridden_surface_bindings",result["sourceOverriddenSurfaceBindings"],
          "source_DDS",result["sourceDDSFilesVerified"])

if __name__=="__main__":
    main()
