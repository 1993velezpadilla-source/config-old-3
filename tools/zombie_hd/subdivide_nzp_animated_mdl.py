#!/usr/bin/env python3
"""XZIEL Dead Cell: non-destructive geometry refinement of Quake MDL v6 enemies.

The algorithm subdivides every source triangle into four while maintaining:
 - the original 211/127 animated poses and immutable source vertices,
 - all original PCX skins and UV coordinates, including Quake back-face seams,
 - separate head/left-arm/right-arm meshes used by breakable body parts,
 - every original frame name, bbox and QuakeC index.
New edge vertices are sampled from the *same* source frame via Loop-style
neighbor weighting, which gently rounds silhouettes rather than only upscaling
the original painted texture.

All models remain below Vril's 2048 alias vertices/tris and 256 frame limits.
This is an experimental cosmetic remesh, NOT a new skeletal/PBR renderer.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile
import argparse
import hashlib
import json
import re
import struct
import numpy as np

MODELS = [
    "zfull.mdl","zb%.mdl","zh^.mdl","zal(.mdl","zar(.mdl",
    "zcfull.mdl","zbc%.mdl","zhc^.mdl","zalc(.mdl","zarc(.mdl",
]
MAX_ALIAS_VERTS=2048
MAX_ALIAS_TRIS=2048
MAX_ALIAS_FRAMES=256

def read_four(raw, where):
    if where+4>len(raw):raise ValueError(f"Unexpected EOF at {where}")
    return struct.unpack_from("<i", raw, where)[0]

def parse_normals(path):
    text=path.read_text(encoding="utf8")
    matches=re.findall(r"\{\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\}",text)
    a=np.asarray(matches,dtype=np.float32)
    if a.shape!=(162,3):raise ValueError(f"Expected 162 pinned Quake vertex normals: {a.shape}")
    return a

def parse_mdl(data):
    if len(data)<84 or data[:4]!=b"IDPO" or read_four(data,4)!=6:
        raise ValueError("Source must be Quake IDPO version 6")
    skins,w,h,nverts,ntris,nframes,synctype,flags=struct.unpack_from("<8i",data,48)
    if not (0<skins<=32 and 0<w<=2048 and 0<h<=2048 and
            0<nverts<=2048 and 0<ntris<=2048 and 0<nframes<=256):
        raise ValueError(f"Unexpected stock MDL dimensions {(skins,w,h,nverts,ntris,nframes)}")
    off=84
    for skin in range(skins):
        t=read_four(data,off)
        off+=4
        if t==0:
            off+=w*h
        elif t==1:
            n=read_four(data,off);off+=4
            if n<=0 or n>256:raise ValueError("Invalid skin group count")
            off+=n*4 + n*w*h
        else:raise ValueError(f"Unrecognized skin group: {t}")
        if off>len(data):raise ValueError("Skin bytes truncated")
    skin_data=data[84:off]
    uv=[]
    for i in range(nverts):
        uv.append(struct.unpack_from("<3i",data,off+i*12))
    off+=nverts*12
    tris=[]
    for i in range(ntris):
        front,a,b,c=struct.unpack_from("<4i",data,off+i*16)
        if front not in (0,1) or max(a,b,c)>=nverts or min(a,b,c)<0 or len({a,b,c})<3:
            raise ValueError(f"Triangle {i} invalid: {(front,a,b,c)}")
        tris.append((front,a,b,c))
    off+=ntris*16
    # Most NZ:P MDLs are simple (type 0). Preserve group frames too.
    frames=[]
    total_poses=0
    for frame in range(nframes):
        t=read_four(data,off)
        if t==0:
            frame_header=data[off:off+28]
            payload=data[off+28:off+28+4*nverts]
            if len(frame_header)!=28 or len(payload)!=4*nverts:raise ValueError("Simple frame truncated")
            frames.append((0,frame_header,[payload]))
            off+=28+4*nverts
            total_poses+=1
        elif t==1:
            poses=read_four(data,off+4)
            if not (0<poses<=256):raise ValueError("Invalid group frame count")
            head_end=off+16+4*poses
            frame_header=data[off:head_end]
            if len(frame_header)!=16+4*poses:raise ValueError("Frame group header truncated")
            pos=head_end
            items=[]
            for j in range(poses):
                header=data[pos:pos+24]
                raw=data[pos+24:pos+24+4*nverts]
                if len(header)!=24 or len(raw)!=4*nverts:raise ValueError("Grouped subframe truncated")
                items.append(header+raw)
                pos+=24+4*nverts
            frames.append((1,frame_header,items))
            off=pos
            total_poses+=poses
        else:raise ValueError(f"Unknown Quake frame type {t}")
    if off>len(data):raise ValueError("Frame data truncated")
    return {
        "nverts":nverts,"ntris":ntris,"nframes":nframes,"nposes":total_poses,
        "uv":uv,"tris":tris,"frames":frames,"skins":skins,
        "w":w,"h":h,"skin_data":skin_data,"tail":data[off:],
        "original_size":len(data),"header":data[:84]}

def make_topology(meta):
    uv=meta["uv"]; tris=meta["tris"]; w=meta["w"]
    n=meta["nverts"]
    all_tri=[]
    extra_st=[]
    edges=defaultdict(list)
    ordered_edges=[]
    for front,a,b,c in tris:
        for x,y,opposite in ((a,b,c),(b,c,a),(c,a,b)):
            k=(min(x,y),max(x,y))
            edges[k].append(opposite)
            ordered_edges.append(k)
        idx=len(all_tri)//4
        ab=n+3*idx
        bc=ab+1
        ca=ab+2
        all_tri.extend([(front,a,ab,ca),
                        (front,ab,b,bc),
                        (front,ca,bc,c),
                        (front,ab,bc,ca)])
        for x,y in ((a,b),(b,c),(c,a)):
            seam_offset=lambda z: (w//2 if (not front and uv[z][0]) else 0)
            s=round((uv[x][1]+seam_offset(x)+uv[y][1]+seam_offset(y))/2)
            t=round((uv[x][2]+uv[y][2])/2)
            extra_st.append((0,s,t))
    new_verts=n+3*meta["ntris"]
    new_tris=len(all_tri)
    if not (new_verts<=MAX_ALIAS_VERTS and new_tris<=MAX_ALIAS_TRIS):
        raise ValueError(f"Refined mesh exceeds pinned Vril MDL cap: {new_verts} verts, {new_tris} triangles")
    assert len(extra_st)==3*meta["ntris"] and new_tris==4*meta["ntris"]
    edge_unique=list(dict.fromkeys(ordered_edges))
    edge_ref={edge:i for i,edge in enumerate(edge_unique)}
    edge_ids=np.asarray([edge_ref[e] for e in ordered_edges],dtype=np.int32)
    # For edges shared by 2 faces Loop subdivision uses both opposite vertices;
    # preserve boundary and non-manifold edges with safe halfway sampling.
    edge_ab=np.asarray(edge_unique,dtype=np.int32)
    opp=np.asarray([edges[e][:2] if len(edges[e])==2 else [-1,-1] for e in edge_unique],dtype=np.int32)
    return new_verts,all_tri,extra_st,edge_ab,opp,edge_ids

def extend_frame(body,nverts,edge_ab,opp,edge_ids,normals):
    original=np.frombuffer(body,dtype=np.uint8).reshape(nverts,4)
    old=original[:,:3].astype(np.float32)
    mid=(old[edge_ab[:,0]]+old[edge_ab[:,1]])*0.5
    interior=np.flatnonzero(opp[:,0]>=0)
    if len(interior):
        ids=interior
        a,b=edge_ab[ids].T
        c,d=opp[ids].T
        mid[ids]=.375*(old[a]+old[b])+.125*(old[c]+old[d])
    mids=np.rint(np.clip(mid[edge_ids],0,255)).astype(np.uint8)
    na=normals[original[edge_ab[:,0],3]]
    nb=normals[original[edge_ab[:,1],3]]
    normals_blend=na+nb
    nr=np.linalg.norm(normals_blend,axis=1,keepdims=True)
    normals_blend/=np.maximum(nr,0.001)
    matches=normals_blend@normals.T
    normidx=matches.argmax(axis=1).astype(np.uint8)
    enriched=np.empty((len(edge_ids),4),dtype=np.uint8)
    enriched[:,:3]=mids
    enriched[:,3]=normidx[edge_ids]
    return body+enriched.tobytes()

def transform(original,normals):
    m=parse_mdl(original)
    nv,newtris,extra_st,edge_ab,opp,edge_ids=make_topology(m)
    hd=bytearray(m["header"])
    struct.pack_into("<2i",hd,60,nv,len(newtris))
    out=bytearray(hd)
    out.extend(m["skin_data"])
    for u in m["uv"]+extra_st:out.extend(struct.pack("<3i",*u))
    for face in newtris:out.extend(struct.pack("<4i",*face))
    for t,header,poses in m["frames"]:
        out.extend(header)
        if t==0:
            out.extend(extend_frame(poses[0],m["nverts"],edge_ab,opp,edge_ids,normals))
        else:
            for item in poses:
                out.extend(item[:24])
                out.extend(extend_frame(item[24:],m["nverts"],edge_ab,opp,edge_ids,normals))
    out.extend(m["tail"])
    check=parse_mdl(bytes(out))
    assert check["nframes"]==m["nframes"] and check["nposes"]==m["nposes"]
    assert check["nverts"]==nv and check["ntris"]==len(newtris)
    assert check["skins"]==m["skins"] and check["w"]==m["w"] and check["h"]==m["h"]
    assert check["skin_data"]==m["skin_data"],"Original embedded skins changed"
    assert check["uv"][:m["nverts"]]==m["uv"],"Original UVs changed"
    for (t,header,_),(t2,h2,_) in zip(m["frames"],check["frames"]):
        assert t==t2 and header==h2,"Original frame headers/names changed"
    return bytes(out),{
        "old_triangles":m["ntris"],"new_triangles":check["ntris"],
        "old_vertices":m["nverts"],"new_vertices":nv,
        "frames":m["nframes"],"poses":m["nposes"],"skin_dimensions":[m["w"],m["h"]],
        "old_bytes":len(original),"new_bytes":len(out),
        "frame_names_and_original_vertices_preserved":True,
        "UV_source_preserved":True,"within_native_Vril_limits":True,
        "sha256":hashlib.sha256(out).hexdigest()}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--pack",type=Path,required=True)
    parser.add_argument("--anorms",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    normals=parse_normals(args.anorms)
    args.out.mkdir(parents=True,exist_ok=True)
    reports={}
    with ZipFile(args.pack) as archive:
        paths=archive.namelist()
        for name in MODELS:
            path="nzp/models/ai/"+name
            if path not in paths:raise ValueError(f"Required model missing: {path}")
            raw=archive.read(path)
            hd,metadata=transform(raw,normals)
            (args.out/name).write_bytes(hd)
            reports[name]=metadata
            print("XZIEL_ZOMBIE_GEOMETRY_UPGRADE",name,json.dumps(metadata,sort_keys=True))
    manifest={"status":"QUAKE_MDL_1LEVEL_FACE_SUBDIVISION",
              "preserves":"Source frame names, 211/127 frame animation indices, source UVs, embedded skins, dismemberment model paths and QuakeC",
              "scope":"Dead Cell pilot only; stock UV-safe HD texture maps also used; fidelity on Android not yet tested",
              "source_pack_sha256":hashlib.sha256(args.pack.read_bytes()).hexdigest(),
              "models":reports}
    (args.out.parent.parent/"zombie-geo-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    assert all(v["within_native_Vril_limits"] for v in reports.values())
    print("XZIEL_ZOMBIE_GEO_10_MDLS_ANIMATIONS_UV_BOUNDS_GREEN")

if __name__=="__main__":
    main()
