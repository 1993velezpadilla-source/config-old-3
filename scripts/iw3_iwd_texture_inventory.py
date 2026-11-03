#!/usr/bin/env python3
"""Count original COD4 .iwd ZIP references for GLB DDS material images.

CoD4 .iwd are ZIP archives containing original images/*.iwi.
This tool cross-checks their names against OpenAssetTools glTF material
image URIs. DOES NOT extract, copy, convert or distribute IWI content.
"""
from __future__ import annotations
from collections import Counter
import argparse,json
from pathlib import Path,PurePosixPath
import zipfile

from iw3_glb_to_iwvm import load_glb


def dds_links(glb:Path):
    desc,_=load_glb(glb)
    images=desc.get("images",[])
    found=set()
    for i in images:
        uri=i.get("uri","")
        if not isinstance(uri,str) or not uri.lower().endswith(".dds"):
            continue
        name=PurePosixPath(uri.replace("\\","/")).name
        if name and name not in {".",".."} and "/" not in name:
            found.add("images/"+name[:-4].lower()+".iwi")
    return found


def scan_iwds(paths):
    indexed={}
    corrupt=[]
    count=0
    for package in paths:
        with zipfile.ZipFile(package,"r") as z:
            for info in z.infolist():
                if info.is_dir():continue
                name=info.filename.replace("\\","/").lower().lstrip("/")
                if not name.startswith("images/") or not name.endswith(".iwi"):
                    continue
                if ".." in PurePosixPath(name).parts:continue
                count+=1
                indexed.setdefault(name,[]).append(package.name)
    return indexed,count


def match(glb_paths,archives):
    referenced=set()
    for glb in glb_paths:referenced.update(dds_links(glb))
    inventory,entries=scan_iwds(archives)
    present=referenced.intersection(inventory.keys())
    missing=referenced.difference(inventory.keys())
    return dict(original_glbs_examined=len(glb_paths),
                original_iwd_archives_scanned=len(archives),
                iwi_files_indexed=entries,
                unique_material_iwi_references=len(referenced),
                iwi_references_found=len(present),
                iwi_references_missing=len(missing),
                iwi_payloads_copied=False,
                textures_currently_rendered_by_vril=False,
                original_game_content_published=False)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--glb-dir",type=Path,required=True)
    p.add_argument("--iwd-dir",type=Path,required=True)
    a=p.parse_args()
    models=sorted(a.glb_dir.rglob("*_lod0.glb"))
    iwds=sorted(a.iwd_dir.rglob("*.iwd"))
    if not models or not iwds:raise SystemExit("Need user-owned extracted GLBs and original IWD archives")
    print(json.dumps(match(models,iwds),indent=2))
