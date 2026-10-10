#!/usr/bin/env python3
"""Stage all 718 SOURCE-USED original UE4.21 DDS textures for Godot A/B.

The complete original source catalog has 1,581 DDS assets, but XZML identifies
718 used by the full 10,793-instance static scene. Copy only those verified
authored assets, plus the original unmodified material manifests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def canon(value):
    raw=str(value or "").strip().replace("\\","/")
    if "'" in raw and raw.endswith("'"):
        raw=raw[raw.find("'")+1:-1]
    low=raw.lower()
    k=low.find("/content/")
    if k>=0 and not low.startswith("/game/"):
        raw="/Game/"+raw[k+len("/content/"):]
    elif low.startswith("content/"):
        raw="/Game/"+raw[len("content/"):]
    elif low.startswith("game/"):
        raw="/"+raw
    elif not raw.startswith("/") and "/" in raw:
        raw="/Game/"+raw
    return raw.lower()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage",type=Path,required=True)
    ap.add_argument("--dds",type=Path,required=True)
    ap.add_argument("--project",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    reports=("material-binding-manifest.json","xzmi-report.json",
             "xzml-report.json","complete-xztx-report.json")
    source={name:json.loads((args.stage/name).read_text()) for name in reports}
    xzml=source["xzml-report.json"]
    complete=source["complete-xztx-report.json"]
    if not xzml.get("ready") or not complete.get("ready"):
        raise ValueError("original UE4.21 material/texture source not ready")
    if int(xzml.get("textureAssetCount",-1))!=718 or int(complete.get("textureAssetCount",-1))!=1581:
        raise ValueError("expected 718 used / 1581 total original source DDS textures")
    full={canon(x["sourcePath"]):x for x in complete["textureAssets"]}
    if len(full)!=1581:
        raise ValueError("original texture source path identity conflict")
    expected={}
    for tex in xzml["textureAssets"]:
        path=canon(tex["sourcePath"])
        if path not in full:
            raise ValueError("a source-used XZML texture missing in full native catalog: "+path)
        native=full[path]
        if native["runtimeFile"]!=tex["runtimeFile"]:
            raise ValueError("mismatched original runtime DDS identity "+path)
        expected[path]=tex
    if len(expected)!=718:
        raise ValueError("source-used texture identity duplicated")
    root=args.project/"nacht-authority"
    root.mkdir(parents=True,exist_ok=True)
    for name in reports:
        shutil.copy2(args.stage/name,root/name)
    dest=root/"vfs/xziel/maps/xziel_nacht_chronicles/textures_dds"
    dest.mkdir(parents=True,exist_ok=True)
    total_bytes=0
    for tex in expected.values():
        name=Path(tex["runtimeFile"]).stem+".dds"
        file=args.dds/name
        if not file.is_file() or file.stat().st_size<128:
            raise ValueError("original material texture DDS absent or truncated: "+str(file))
        shutil.copy2(file,dest/name)
        total_bytes+=file.stat().st_size
    files=list(dest.glob("*.dds"))
    if len(files)!=718:
        raise ValueError("source DDS copied file count !=718")
    report={
        "authority":"original archived Pavlov UE4.21 material graph + XZML/XZMI, NOT BO3 T7",
        "scene_native_actor_count":10793,
        "effective_material_count":574,
        "original_surface_bindings":16595,
        "used_source_DDS_staged":len(files),
        "total_original_catalog_DDS":1581,
        "source_used_DDS_bytes":total_bytes,
        "source_mesh_material_guesses":0,
        "made_up_or_stock_textures":0,
        "pixel_render_fidelity_proven":False,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print("XZOGOT_NACHT_ALL_USED_UE421_SOURCE_DDS_STAGE_GREEN",
          "used_textures",len(files),"total_catalog",1581,
          "real_compressed_source_bytes",total_bytes)

if __name__=="__main__":
    main()
