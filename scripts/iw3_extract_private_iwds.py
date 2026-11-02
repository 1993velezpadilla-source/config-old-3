#!/usr/bin/env python3
"""Resolve real ORIGINAL COD4 viewmodel material IWI in player's multipart ZIP.

Scans original main/iw_00..iw_13.iwd nested ZIP files one at a time.
Only matching IWI textures are extracted into a *temporary private runner*.
The output report excludes image contents and original filename lists.
Never commit, redistribute or upload original COD4 image bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil,tempfile
import zipfile

from iw3_collect_original_fastfiles import PREFIX,SplitReader
from iw3_iwd_texture_inventory import dds_links

MAX_IWD_BYTES=2*1024*1024*1024
MAX_IMAGE_BYTES=64*1024*1024


def extract_from_iwd(package:Path,wanted:set[str],dest:Path):
    found=set()
    with zipfile.ZipFile(package) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name=entry.filename.lower().replace("\\","/")
            if name not in wanted or ".." in PurePosixPath(name).parts:
                continue
            if entry.file_size<12 or entry.file_size>MAX_IMAGE_BYTES:
                raise ValueError("Invalid source COD4 IWI size")
            dest_path=dest/name
            dest_path.parent.mkdir(parents=True,exist_ok=True)
            if dest_path.exists():
                found.add(name)
                continue
            with archive.open(entry) as source,dest_path.open("wb") as target:
                shutil.copyfileobj(source,target,length=512*1024)
            if dest_path.stat().st_size!=entry.file_size:
                raise ValueError("Original IWI extraction truncated")
            found.add(name)
    return found


def collect(parts:list[Path],viewmodel:Path,dest:Path):
    wanted=dds_links(viewmodel)
    if not wanted or len(wanted)>512:
        raise ValueError("Expected 1..512 original CoD4 GLB DDS image references")
    dest.mkdir(parents=True,exist_ok=True)
    source=SplitReader(parts)
    found=set()
    scanned=0
    try:
        with zipfile.ZipFile(source,allowZip64=True) as outer:
            for i in range(14):
                key=PREFIX+f"main/iw_{i:02d}.iwd"
                try:
                    part=outer.getinfo(key)
                except KeyError:
                    continue
                if part.file_size<1000 or part.file_size>MAX_IWD_BYTES:
                    raise ValueError("Unexpected original COD4 IWD container size")
                scanned+=1
                with tempfile.TemporaryDirectory(prefix="iw3-private-archive-") as tmp:
                    temp=Path(tmp)/f"iw_{i:02d}.iwd"
                    with outer.open(part) as inp,temp.open("wb") as out:
                        shutil.copyfileobj(inp,out,length=2*1024*1024)
                    if temp.stat().st_size!=part.file_size:
                        raise ValueError("Original COD4 IWD container incomplete")
                    found|=extract_from_iwd(temp,wanted-found,dest)
                if len(found)==len(wanted):
                    break
    finally:
        source.close()
    return {"original_iwd_archives_scanned":scanned,
            "original_material_iwi_wanted":len(wanted),
            "original_material_iwi_found":len(found),
            "original_material_iwi_missing":len(wanted-found),
            "original_iwi_bytes_committed":False,
            "original_iwi_bytes_published":False,
            "first_color_candidates_in_temp":bool(found)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--parts-dir",type=Path,required=True)
    p.add_argument("--selected-glb",type=Path,required=True)
    p.add_argument("--temporary-output",type=Path,required=True)
    a=p.parse_args()
    parts=[a.parts_dir/f"C4-Mocs.zip.part-{i:03d}" for i in range(4)]
    result=collect(parts,a.selected_glb,a.temporary_output)
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
