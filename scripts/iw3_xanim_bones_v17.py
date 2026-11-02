#!/usr/bin/env python3
"""Strict partial decoder for ORIGINAL CoD4 IW3 XAnim v17 bone tracks.

Supports full per-bone rotation/translation tracks when root-delta is absent.
Records frame timing/notify indices. Root-delta v17 tracks are deliberately
rejected until their two-track layout is implemented (rather than invented).
No original CoD4 animation bytes may be committed or published by this tool.

Ported from the documented data layout in OpenAssetTools
src/ObjLoading/XAnim/CompiledXAnimLoader.cpp, license GPL-3.0.
"""
from __future__ import annotations
import math
from pathlib import Path
import struct

from iw3_xanim_header_probe import HEADER,header
HALF_SCALE=0.003921568859368563
FULL_SCALE=0.00001525902189314365

class BrokenXAnim(ValueError):
    pass

class Cursor:
    def __init__(self,data:bytes):
        self.data=data
        self.pos=0
    def raw(self,n:int)->bytes:
        if n<0 or n>len(self.data)-self.pos:
            raise BrokenXAnim("Truncated CoD4 XAnim v17 bone track")
        value=self.data[self.pos:self.pos+n]
        self.pos+=n
        return value
    def unpack(self,fmt:str):
        x=struct.Struct("<"+fmt)
        return x.unpack(self.raw(x.size))
    def u8(self):
        return self.unpack("B")[0]
    def u16(self):
        return self.unpack("H")[0]
    def float3(self):
        return self.unpack("fff")
    def cstring(self):
        rest=self.data.find(b"\0",self.pos)
        if rest<0 or rest-self.pos>256:
            raise BrokenXAnim("Unterminated or oversized original bone name")
        txt=self.raw(rest-self.pos).decode("utf-8",errors="strict")
        self.raw(1)
        return txt


def get_indices(cursor:Cursor,n:int,num_loop_frames:int,use_byte:bool):
    if n<2 or n>num_loop_frames:
        raise BrokenXAnim("Invalid original keyed bone-track count")
    if n>=num_loop_frames:
        return list(range(n))
    if use_byte:
        return list(cursor.raw(n))
    return list(cursor.unpack(str(n)+"H"))


def read_quat(c:Cursor,nframes:int,use_byte:bool,half:bool,flip:bool):
    n=c.u16()
    if n>nframes:
        raise BrokenXAnim("IW3 quat track beyond frame count")
    if n==0:
        if not half:
            raise BrokenXAnim("No quaternion requires half-quat flag")
        return dict(kind="identity",frame_indices=[],raw_values=[])
    indices=[] if n<=1 else get_indices(c,n,nframes,use_byte)
    components=1 if half else 3
    raw_values=[]
    for k in range(n):
        fields=c.unpack(str(components)+"h")
        raw_values.append(list(fields))
    # Preserve source quantized bone values and signed continuity semantics
    # without pretending half-quat is a full 4D pose.
    return dict(kind="half" if half else "full",
                frame_indices=indices,raw_values=raw_values,flip_first=flip)


def read_trans(c:Cursor,nframes:int,use_byte:bool):
    n=c.u16()
    if n>nframes:
        raise BrokenXAnim("IW3 position track beyond frame count")
    if n==0:
        return dict(kind="none",frame_indices=[],xyz=[])
    if n==1:
        xyz=c.float3()
        if not all(math.isfinite(v) for v in xyz):
            raise BrokenXAnim("Nonfinite original position track")
        return dict(kind="constant",frame_indices=[],xyz=[list(xyz)])
    indices=get_indices(c,n,nframes,use_byte)
    small=c.u8()
    if small not in (0,1):
        raise BrokenXAnim("Original quantization flag invalid")
    minimum=c.float3()
    raw_size=c.float3()
    if not all(math.isfinite(v) for v in minimum+raw_size):
        raise BrokenXAnim("Original quantized position has invalid values")
    factor=HALF_SCALE if small else FULL_SCALE
    scale=[v*factor for v in raw_size]
    xyz=[]
    for _ in range(n):
        values=c.unpack("BBB" if small else "HHH")
        xyz.append([minimum[i]+values[i]*scale[i] for i in range(3)])
    return dict(kind="quantized_u8" if small else "quantized_u16",
                frame_indices=indices,xyz=xyz)


def decode(path:Path):
    h=header(path)
    if h["root_delta"]:
        raise BrokenXAnim("IW3 root-delta XAnim requires separate decoder")
    data=path.read_bytes()
    if len(data)>64*1024*1024:
        raise BrokenXAnim("Original animation too large for bounded decoder")
    cursor=Cursor(data)
    assert HEADER.unpack(cursor.raw(HEADER.size))[0]==17
    count=h["bones"]
    nframes=h["frames"]+1 if h["loop"] else h["frames"]
    use_byte=(nframes-1)<256
    mask_bytes=(count+7)//8
    flip=cursor.raw(mask_bytes)
    half=cursor.raw(mask_bytes)
    names=[cursor.cstring() for _ in range(count)]
    bones=[]
    for i,name in enumerate(names):
        flip_i=bool((flip[i//8]>>(i%8))&1)
        half_i=bool((half[i//8]>>(i%8))&1)
        rotation=read_quat(cursor,nframes,use_byte,half_i,flip_i)
        position=read_trans(cursor,nframes,use_byte)
        bones.append(dict(name=name,rotation=rotation,position=position))
    notify_count=cursor.u8()
    notes=[]
    for i in range(notify_count):
        name=cursor.cstring()
        frame=cursor.u16()
        if frame>nframes:
            raise BrokenXAnim("XAnim notify outside animation duration")
        notes.append(dict(name=name,frame=frame))
    if cursor.pos!=len(data):
        raise BrokenXAnim("Unexpected trailing XAnim data (wrong stream layout)")
    return dict(frames=nframes,bones=bones,looped=h["loop"],
                fps=h["fps"],notifications=notes)


def census(root:Path):
    inspected=0
    decoded=0
    failed=0
    rootdelta=0
    samples=[]
    for p in root.rglob("*"):
        if not p.is_file() or p.parent.name!="xanim":
            continue
        inspected+=1
        try:
            h=header(p)
            if h["root_delta"]:
                rootdelta+=1
                continue
            a=decode(p)
            decoded+=1
            if len(samples)<8:
                samples.append(dict(frames=a["frames"],
                                    bones=len(a["bones"]),
                                    notes=len(a["notifications"])))
        except (ValueError,OSError,struct.error,UnicodeError):
            failed+=1
    return dict(original_iw3_v17_files=inspected,
                decoded_full_bones_without_rootdelta=decoded,
                delta_tracks_waiting_implementation=rootdelta,
                rejected_due_to_schema=failed,
                anonymized_decoded_samples=samples,
                native_android_playback=False)

if __name__=="__main__":
    import argparse,json
    ap=argparse.ArgumentParser()
    ap.add_argument("private_oat_output",type=Path)
    args=ap.parse_args()
    print(json.dumps(census(args.private_oat_output),indent=2))
