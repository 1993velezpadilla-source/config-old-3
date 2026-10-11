#!/usr/bin/env python3
"""Fail-closed single-map package optimizer for Xziel v0.26 DEV Dead Cell.

Removes OTHER map files only. Does not touch shared weapon models, weapon HUD,
sound, scripts, progs.dat, engines, or the original (source-pinned) branches.
Run after prepare_android.sh, before Gradle assembles APK.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import os
import hashlib
from zipfile import ZipFile

KEEP_MAP = "xziel_proto"
KEEP_SUFFIXES = (".bsp", ".nsz", ".txt")
NEEDED_FILES = (
    "nzp/progs.dat", "nzp/maps/xziel_proto.bsp",
    "nzp/maps/xziel_proto.nsz", "nzp/maps/xziel_proto.txt",
    "nzp/models/xziel/godot_altar/altar.xzsm",
    "nzp/gfx/xziel/fire.png", "nzp/gfx/xziel/ads.png",
    "nzp/gfx/xziel/reload.png", "nzp/gfx/xziel/knife.png",
)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("data_zip",type=Path)
    parser.add_argument("--report",type=Path,default=None)
    args=parser.parse_args()
    archive=args.data_zip
    if not archive.is_file():
        parser.error(f"Missing {archive}")
    temp=archive.with_suffix(".deadcell.tmp")
    removed=[]
    before=archive.stat().st_size
    try:
        with ZipFile(archive,"r") as src, ZipFile(temp,"w") as dest:
            source_names=set(src.namelist())
            if len(source_names)!=len(src.namelist()):
                raise RuntimeError("Duplicate zip entries; will not prune ambiguous package")
            for path in NEEDED_FILES:
                if path not in source_names:
                    raise RuntimeError(f"Required source package entry missing: {path}")
            if not src.read("nzp/maps/xziel_proto.txt").startswith(b"XZIEL: DEAD CELL"):
                raise RuntimeError("Dead Cell map metadata missing expected display title")
            for entry in src.infolist():
                name=entry.filename
                if name.startswith("nzp/maps/") and name != "nzp/maps/":
                    if name not in {"nzp/maps/"+KEEP_MAP+ext for ext in KEEP_SUFFIXES}:
                        removed.append((name,entry.file_size))
                        continue
                dest.writestr(entry,src.read(name))
        with ZipFile(temp) as z:
            names=set(z.namelist())
            maps=sorted(n for n in names if n.startswith("nzp/maps/") and n.endswith(".bsp"))
            assert maps==["nzp/maps/xziel_proto.bsp"], maps
            assert all(n in names for n in NEEDED_FILES)
            assert sum(n.startswith("nzp/gfx/xziel/") and n.endswith(".png") for n in names)>=12
            assert len(z.read("nzp/progs.dat"))>50000
            assert len(z.read("nzp/models/xziel/godot_altar/altar.xzsm"))>1000
            pngs=[n for n in names if n.startswith("nzp/textures/xziel/godot_altar/") and n.endswith(".png")]
            assert len(pngs)==5, pngs
            assert z.testzip() is None
            if any(name.startswith("nzp/maps/") and
                   name not in {"nzp/maps/","nzp/maps/xziel_proto.bsp","nzp/maps/xziel_proto.nsz","nzp/maps/xziel_proto.txt"}
                   for name in names):
                raise RuntimeError("A non-Dead-Cell map file survived pruning")
        os.replace(temp,archive)
    finally:
        if temp.exists():
            temp.unlink()
    version=archive.with_name("nzp-data.version")
    if version.exists():
        version.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+"\n",encoding="utf-8")
    report={
        "mode":"single-map-only","kept_map":KEEP_MAP,
        "remaining_bsp":1,"removed_map_entries":len(removed),
        "removed_map_file_bytes":sum(size for _,size in removed),
        "nzp_data_bytes_before":before,"nzp_data_bytes_after":archive.stat().st_size,
        "removed_map_names":[name for name,_ in removed],
        "retains_all_shared_weapon_assets":True,
        "material_textures_retained":5,
    }
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("XZIEL_SINGLE_DEAD_CELL_PACKAGE_GREEN",json.dumps({k:v for k,v in report.items() if k!="removed_map_names"}))

if __name__=="__main__":
    main()
