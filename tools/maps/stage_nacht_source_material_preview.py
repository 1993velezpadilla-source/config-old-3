#!/usr/bin/env python3
"""Stage exact original authored material/texture sample for Godot 4.6.

Uses the authoritative complete 10,793-actor XZMI per-surface compiler report,
copies only selected original DDS texture files and original manifest JSONs;
does not fabricate textures or assign materials from filenames.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

def canonical(p):
    p=str(p or "").strip().replace("\\","/")
    if "'" in p and p.endswith("'"):
        p=p[p.find("'")+1:-1]
    low=p.lower()
    if low.startswith("game/"):
        p="/"+p
    elif low.startswith("content/"):
        p="/Game/"+p[8:]
    elif not p.startswith("/") and "/" in p:
        p="/Game/"+p
    return p.lower()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bridge",type=Path,required=True)
    p.add_argument("--source-stage",type=Path,required=True)
    p.add_argument("--dds",type=Path,required=True)
    p.add_argument("--godot-project",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--max-actors",type=int,default=32)
    a=p.parse_args()
    source=json.loads(a.bridge.read_text())
    if (source.get("sourceActorCount")!=10793
            or source.get("originalSourceSurfaceBindings")!=16595
            or source.get("distinctSourceEffectiveMaterials")!=574):
        raise ValueError("input source authority lacks complete exact XZMI assignments")
    texture_files={
        canonical(t["sourcePath"]): str(t["runtimeFile"])
        for t in source["textureAssets"]
    }
    by_material={}
    for m in source["materials"]:
        key=canonical(m["materialPath"])
        direct=m.get("canonicalTextures",{})
        graph=m.get("sourceGraphBindings",{})
        possible=[direct.get("diffuse"), graph.get("diffuse")]
        tex=next((canonical(x) for x in possible if x and canonical(x) in texture_files),None)
        if tex:
            by_material[key]=tex
    selected=[]
    used_materials=set()
    copied_paths={}
    for actor in source["actors"]:
        found=None
        for n,material in enumerate(actor["sourceMaterialPaths"]):
            key=canonical(material)
            tex=by_material.get(key)
            if tex and key not in used_materials:
                found=(n,material,key,tex)
                break
        if not found:
            continue
        n,material,key,tex=found
        runtime=texture_files[tex]
        src=a.dds / (Path(runtime).stem+".dds")
        if not src.is_file() or src.stat().st_size<128:
            raise ValueError("real source DDS missing for authored material "+str(src))
        used_materials.add(key)
        selected.append({"actorId":actor["actorId"],
                         "meshIndex":actor["meshIndex"],
                         "targetSurface":n,
                         "sourceMaterialPath":material,
                         "originalDiffuseTextureSourcePath":tex,
                         "sourceDDS":Path(runtime).stem+".dds",
                         "sourceSurfaceCount":len(actor["sourceMaterialPaths"])})
        copied_paths[tex]=src
        if len(selected)>=a.max_actors:
            break
    if len(selected)<8:
        raise ValueError(f"too few source-authored uniquely textured material actor samples: {len(selected)}")
    dest=a.godot_project/"nacht-authority"
    dest.mkdir(parents=True,exist_ok=True)
    for name in ("material-binding-manifest.json","xzml-report.json",
                 "xzmi-report.json","complete-xztx-report.json"):
        file=a.source_stage/name
        if not file.is_file():
            raise ValueError("missing original archived material manifest "+name)
        shutil.copy2(file,dest/name)
    texdest=dest/"vfs/xziel/maps/xziel_nacht_chronicles/textures_dds"
    texdest.mkdir(parents=True,exist_ok=True)
    for item in copied_paths.values():
        shutil.copy2(item,texdest/item.name)
    out={"authority":"Pavlov UE4.21 original material + source DDS. NOT BO3 T7",
         "samples":selected,
         "sampleActorCount":len(selected),
         "uniqueAuthoredDiffuseMaterials":len(used_materials),
         "originalDDSCopied":len(copied_paths),
         "noSynthesizedImages":True,
         "all10793MaterialsApplied":False}
    dest.joinpath("material-preview-samples.json").write_text(json.dumps(out,indent=2)+"\n")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2)+"\n")
    print("XZOGOT_NACHT_AUTHORED_MATERIAL_TEXTURE_PREVIEW_STAGE_GREEN",
          "sample_actors",len(selected),"distinct_original_diffuses",len(copied_paths),
          "dds_dir",texdest)

if __name__=="__main__":
    main()
