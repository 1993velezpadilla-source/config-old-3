#!/usr/bin/env python3
"""ENGINE-ONLY 8,284 triangle MDL stress asset, built from stock NZ:P zfull.

Never commit the generated model, or label it as the Hotstrike original:
it is a procedural geometry/animation stress specimen preserving stock poses.
Supported original source: 484 or 1,936 triangles (last level subdivided
selectively to get an exactly 8,284-triangle diagnostic asset).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from zipfile import ZipFile
import numpy as np


def parse_mdl(raw):
    if raw[:4] != b"IDPO" or struct.unpack_from("<i", raw, 4)[0] != 6:
        raise ValueError("Expected Quake MDL version 6")
    skins,w,h,nv,nt,nf,_,_=struct.unpack_from("<8i",raw,48)
    if not(1<=skins<=4 and 1<=w<=2048 and 1<=h<=2048 and 1<=nv<=16384
            and 1<=nt<=16384 and 1<=nf<=256):
        raise ValueError("Unsafe MDL header")
    off=84
    for _ in range(skins):
        typ=struct.unpack_from("<i",raw,off)[0]
        off+=4
        if typ==0: off+=w*h
        elif typ==1:
            n=struct.unpack_from("<i",raw,off)[0];off+=4
            if not 1<=n<=64: raise ValueError("Unsafe grouped skins")
            off+=4*n+w*h*n
        else: raise ValueError("Unexpected skin type")
    skin=raw[84:off]
    uv=np.frombuffer(raw,dtype="<i4",count=nv*3,offset=off).copy().reshape(nv,3)
    off+=12*nv
    tris=np.frombuffer(raw,dtype="<i4",count=nt*4,offset=off).copy().reshape(nt,4)
    off+=16*nt
    if (tris[:,0].min()<0 or tris[:,0].max()>1 or tris[:,1:].min()<0
        or tris[:,1:].max()>=nv):
        raise ValueError("Unsafe triangle indices")
    frames=[]
    poses=[]
    for _ in range(nf):
        if struct.unpack_from("<i",raw,off)[0] != 0:
            raise ValueError("Test fixture requires single, not grouped, frames")
        hdr=raw[off:off+28];off+=28
        verts=np.frombuffer(raw,dtype=np.uint8,count=nv*4,offset=off).copy().reshape(nv,4)
        frames.append(hdr);poses.append(verts);off+=4*nv
    if len(poses)!=nf or off>len(raw): raise ValueError("Truncated model")
    return dict(header=raw[:84],skin=skin,uv=uv,tris=tris,
                poses=np.stack(poses),frames=frames,tail=raw[off:],w=w,h=h,
                original_sha=hashlib.sha256(raw).hexdigest())


def subdivide(m, select):
    tris=m["tris"]
    selected=np.arange(len(tris)) if select is None else np.arange(select)
    if not 0<len(selected)<=len(tris): raise ValueError("Unsafe selection")
    # Per-face edge vertices preserve mirrored and back-face Quake UV seams.
    three=tris[selected,1:]
    edges=np.stack([three[:,[0,1]],three[:,[1,2]],three[:,[2,0]]],axis=1).reshape(-1,2)
    nold=len(m["uv"])
    new_indices=(np.arange(len(selected)*3,dtype=np.int32)+nold).reshape(-1,3)
    src_uv=m["uv"]
    texw=m["w"]
    uvnew=[]
    for f,(ia,ib) in zip(np.repeat(tris[selected,0],3),edges):
        a,b=map(int,(ia,ib))
        # Original seam vertex is shifted by half the skin ONLY on a back face.
        sa=int(src_uv[a,1])+(texw//2 if f==0 and src_uv[a,0]!=0 else 0)
        sb=int(src_uv[b,1])+(texw//2 if f==0 and src_uv[b,0]!=0 else 0)
        uvnew.append((0,round((sa+sb)/2),round((int(src_uv[a,2])+int(src_uv[b,2]))/2)))
    out=np.concatenate([src_uv,np.asarray(uvnew,dtype=np.int32)])
    pa=m["poses"][:,edges[:,0],:].astype(np.uint16)
    pb=m["poses"][:,edges[:,1],:].astype(np.uint16)
    middle=np.empty_like(pa,dtype=np.uint8)
    middle[:,:,:3]=((pa[:,:,:3]+pb[:,:,:3]+1)//2).astype(np.uint8)
    middle[:,:,3]=pa[:,:,3].astype(np.uint8)
    updated=np.concatenate([m["poses"],middle],axis=1)
    # For stable ordering, keep nonselected triangles and add four for each selected.
    selected_mask=np.zeros(len(tris),dtype=bool)
    selected_mask[selected]=True
    untouched=tris[~selected_mask]
    front=tris[selected,0].astype(np.int32)
    a,b,c=three.T
    ab,bc,ca=new_indices.T
    quad=np.stack([
        np.stack([front,a,ab,ca],axis=1),
        np.stack([front,ab,b,bc],axis=1),
        np.stack([front,ca,bc,c],axis=1),
        np.stack([front,ab,bc,ca],axis=1),
    ],axis=1).reshape(-1,4)
    m["uv"]=out;m["tris"]=np.concatenate([untouched,quad]);m["poses"]=updated
    assert updated.shape[1]==len(out)
    if len(out)>16384 or len(m["tris"])>16384:
        raise ValueError("Engine limit exceeded")
    return m


def serialize(m):
    nverts=len(m["uv"]);ntri=len(m["tris"])
    assert ntri==8284 and nverts<=16384 and m["poses"].shape[0]<=256
    header=bytearray(m["header"])
    struct.pack_into("<ii",header,60,nverts,ntri)
    out=bytearray(header)
    out.extend(m["skin"])
    out.extend(m["uv"].astype("<i4").tobytes())
    out.extend(m["tris"].astype("<i4").tobytes())
    for frame,pose in zip(m["frames"],m["poses"]):
        out.extend(frame)
        out.extend(pose.astype("uint8").tobytes())
    out.extend(m["tail"])
    result=bytes(out)
    again=parse_mdl(result)
    assert len(again["tris"])==8284 and len(again["uv"])==nverts
    assert again["frames"]==m["frames"]
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asset",type=Path,required=True)
    p.add_argument("--package",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    source=args.asset.read_bytes()
    m=parse_mdl(source)
    old_tris=len(m["tris"]);old_verts=len(m["uv"]);old_frames=len(m["frames"])
    if old_tris not in (484,1936):
        raise ValueError(f"Pinned stock mesh changed unexpectedly: {old_tris}")
    while len(m["tris"])<7744:
        m=subdivide(m,None)
    if len(m["tris"])!=7744: raise ValueError("Unexpected refinement level")
    m=subdivide(m,180) # 7744+3*180 = 8284
    built=serialize(m)
    with tempfile.NamedTemporaryFile(dir=args.package.parent,suffix=".zip",delete=False) as tmp:
        temporary=Path(tmp.name)
    try:
        target="nzp/models/ai/zfull.mdl"
        with ZipFile(args.package) as old,ZipFile(temporary,"w",allowZip64=True) as out:
            paths=old.namelist()
            if paths.count(target)!=1:
                raise ValueError("Expected one stock zombie in NZ:P ZIP")
            for info in old.infolist():
                if info.filename==target:
                    out.writestr(info,built)
                elif info.is_dir():
                    out.writestr(info,b"")
                else:
                    with old.open(info) as src,out.open(info,"w") as dst:
                        shutil.copyfileobj(src,dst,1024*1024)
        with ZipFile(temporary) as verify:
            assert verify.namelist().count(target)==1
            assert verify.read(target)==built
            assert verify.testzip() is None
        os.replace(temporary,args.package)
    finally:
        temporary.unlink(missing_ok=True)
    version=args.package.parent/"nzp-data.version"
    version.write_text(hashlib.sha256(args.package.read_bytes()).hexdigest()+"\n")
    args.report.parent.mkdir(parents=True,exist_ok=True)
    record={"type":"SYNTHETIC_ENGINE_GEOMETRY_BENCHMARK_NOT_HOTSTRIKE",
            "original_triangle_count":old_tris,"original_vertices":old_verts,
            "new_triangles":8284,"new_vertices":len(m["uv"]),
            "frames":old_frames,"new_sha256":hashlib.sha256(built).hexdigest(),
            "preserved_stock_animation_frames":True,
            "note":"Proves packaging and model size, not Android runtime FPS, actual Hotstrike mesh, or material fidelity"}
    args.report.write_text(json.dumps(record,indent=2)+"\n")
    print("XZIEL_ENGINE_8284_TRIANGLE_ALIAS_PROBE_GREEN",json.dumps(record))


if __name__=="__main__":
    main()
