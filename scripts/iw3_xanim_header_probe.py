#!/usr/bin/env python3
"""Validate real ORIGINAL IW3 (CoD4) compiled XAnim v17 headers.

Based on OpenAssetTools' CompiledXAnimWriter.cpp and CompiledXAnimLoader.cpp:
  uint16 version, uint16 frame_count, uint16 bone_count, uint8 flags,
  uint8 asset_type, uint16 frames_per_second.
No animation playback or bone solving is claimed by this header probe.
Only anonymized aggregate counts may leave the disposable runner.
"""
from __future__ import annotations
from collections import Counter
import argparse
import json
from pathlib import Path
import struct

HEADER = struct.Struct("<HHHBBH")
IW3_VERSION=17

def header(path:Path) -> dict:
    with path.open("rb") as stream:
        raw=stream.read(HEADER.size)
    if len(raw)!=HEADER.size:
        raise ValueError("IW3 XAnim compiled header truncated")
    version,frames,bones,flags,asset_type,fps=HEADER.unpack(raw)
    if version!=IW3_VERSION:
        raise ValueError(f"Expected IW3 compiled XAnim version 17, got {version}")
    if not (1<=frames<=65535) or not (0<=bones<=1024):
        raise ValueError("Unreasonable IW3 original animation shape")
    if flags & ~0x03:
        raise ValueError("Unexpected CoD4 XAnim flags")
    if fps >1000:
        raise ValueError("Unexpected original animation frame rate")
    return dict(version=version,frames=frames,bones=bones,loop=bool(flags&1),
                root_delta=bool(flags&2),asset_type=asset_type,fps=fps)

def census(root:Path):
    files=[p for p in root.rglob("*") if p.is_file() and p.parent.name=="xanim"]
    count=Counter()
    categories=Counter()
    examples=[]
    for path in files:
        try:
            h=header(path)
            count["valid_compiled_iw3_v17"]+=1
            count["root_delta"]+=h["root_delta"]
            count["looped"]+=h["loop"]
            count["bones_total"]+=h["bones"]
            count["frames_total"]+=h["frames"]
            count["max_bones"]=max(count["max_bones"],h["bones"])
            count["max_frames"]=max(count["max_frames"],h["frames"])
            count["fps_0"]+=h["fps"]==0
            lower=path.name.lower()
            for typ in ("reload","fire","ads","idle","sprint","raise","melee"):
                if typ in lower:
                    categories[typ]+=1
                    break
            if len(examples)<10:
                examples.append({"frames":h["frames"],"bones":h["bones"],
                                 "fps":h["fps"],"loop":h["loop"],
                                 "root_delta":h["root_delta"]})
        except (OSError,ValueError,struct.error):
            count["invalid_or_not_v17"]+=1
    return dict(source="user-owned original COD4 IW3 OAT transient extraction",
                files_examined=len(files),totals=dict(count),
                name_categories=dict(categories),safe_anonymized_samples=examples,
                decoded_keyframes=False,played_by_vril=False,
                proprietary_animation_files_uploaded=False)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("private_oat_output",type=Path)
    args=parser.parse_args()
    print(json.dumps(census(args.private_oat_output),indent=2))
