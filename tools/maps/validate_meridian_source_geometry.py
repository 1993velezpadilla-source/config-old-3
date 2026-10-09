#!/usr/bin/env python3
"""Independent ORIGINAL UE-XZIEL/GLB versus Meridian-exported GLB GPU geometry audit.

No assumptions about Unreal import axes. Compare every actual source POSITION
vertex mapped through its existing authoritative XZIEL->Godot scene transform
against every translated/exported vertex, per exact source actor ID.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import struct
import sys

def load_glb(path):
    payload=path.read_bytes()
    if payload[:4] != b"glTF" or len(payload)<32:
        raise ValueError("invalid source GLB "+str(path))
    size, typ=struct.unpack_from("<II",payload,12)
    if typ != 0x4E4F534A:
        raise ValueError("GLB JSON missing")
    doc=json.loads(payload[20:20+size])
    off=20+size
    bsize,btype=struct.unpack_from("<II",payload,off)
    if btype != 0x004E4942:
        raise ValueError("GLB BIN missing")
    return doc, memoryview(payload)[off+8:off+8+bsize]

def vpositions(doc, binary, idx):
    a=doc["accessors"][idx]
    if a["componentType"]!=5126 or a["type"]!="VEC3" or a.get("sparse"):
        raise ValueError("unproven POSITION layout: FLOAT VEC3 only")
    v=doc["bufferViews"][a["bufferView"]]
    start=v.get("byteOffset",0)+a.get("byteOffset",0)
    step=v.get("byteStride",12)
    if step<12 or step%4:
        raise ValueError("invalid POSITION byteStride")
    for i in range(a["count"]):
        point=struct.unpack_from("<3f",binary,start+i*step)
        if not all(math.isfinite(t) for t in point):
            raise ValueError("nonfinite GLB source vertex")
        yield point

def positions_for_mesh(doc,bin_bytes,idx):
    for primitive in doc["meshes"][idx]["primitives"]:
        if primitive.get("mode",4)!=4:
            raise ValueError("expected original triangle primitives")
        yield from vpositions(doc,bin_bytes,primitive["attributes"]["POSITION"])

def mul(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)]for i in range(4)]

def identity():
    return [[float(i==j) for j in range(4)]for i in range(4)]

def local(node):
    if "matrix" in node:
        vals=node["matrix"]
        return [[vals[4*j+i] for j in range(4)]for i in range(4)]
    tx,ty,tz=node.get("translation",[0,0,0])
    x,y,z,w=node.get("rotation",[0,0,0,1])
    length=math.sqrt(x*x+y*y+z*z+w*w)
    if length<1e-8:raise ValueError("invalid source quaternion")
    x,y,z,w=[q/length for q in (x,y,z,w)]
    sx,sy,sz=node.get("scale",[1,1,1])
    return [
        [(1-2*(y*y+z*z))*sx,2*(x*y-z*w)*sy,2*(x*z+y*w)*sz,tx],
        [2*(x*y+z*w)*sx,(1-2*(x*x+z*z))*sy,2*(y*z-x*w)*sz,ty],
        [2*(x*z-y*w)*sx,2*(y*z+x*w)*sy,(1-2*(x*x+y*y))*sz,tz],
        [0,0,0,1]
    ]

def xform(m,point):
    x,y,z=point
    return [m[i][0]*x+m[i][1]*y+m[i][2]*z+m[i][3] for i in range(3)]

def box(points):
    points=iter(points)
    first=next(points,None)
    if first is None:
        raise ValueError("mesh POSITION list empty")
    lo=list(first);hi=list(first)
    for p in points:
        for i in range(3):
            lo[i]=min(lo[i],p[i]);hi[i]=max(hi[i],p[i])
    return {"min":lo,"max":hi}

def source_actor_boxes(scene,source_glb_dir,ids):
    # Existing shipped XZIELSceneRoot transform:
    # XZIEL+X => Godot-Z, +Y => Godot-X, +Z => Godot+Y
    basis=[[0,-1,0,0],[0,0,1,0],[-1,0,0,0],[0,0,0,1]]
    mesh_rows={int(r["index"]):r for r in scene["meshes"]}
    cache={}
    result={}
    for row in scene["instances"]:
        iid=row["instanceId"]
        if iid not in ids:continue
        mesh=int(row["meshIndex"])
        if mesh not in cache:
            file=source_glb_dir/(Path(mesh_rows[mesh]["runtimeFile"]).stem+".glb")
            doc,b=load_glb(file)
            # All GLB root meshes from native XZMS must have node identity.
            if any("translation" in node or "rotation" in node or "scale" in node or
                   ("matrix" in node and local(node)!=identity())
                   for node in doc["nodes"]):
                raise ValueError("source GLB additional node transform unproven "+file.name)
            cache[mesh]=[
                point for i in range(len(doc["meshes"]))
                for point in positions_for_mesh(doc,b,i)
            ]
        raw=row["matrixRowMajor"]
        if len(raw)!=16:raise ValueError("invalid source matrix "+iid)
        src=[list(map(float,raw[4*i:4*i+4])) for i in range(4)]
        w=mul(basis,src)
        result[iid]=box(xform(w,v) for v in cache[mesh])
    return result

def meridian_actor_boxes(path,ids):
    doc,b=load_glb(path)
    mesh_cache={}
    results=defaultdict(list)
    def rec(i,parent,actor=None):
        node=doc["nodes"][i]
        m=mul(parent,local(node))
        name=node.get("name","")
        if name in ids:
            actor=name
        if "mesh" in node:
            if actor is None:
                raise ValueError("output mesh was detached from original actor "+name)
            j=node["mesh"]
            if j not in mesh_cache:
                mesh_cache[j]=list(positions_for_mesh(doc,b,j))
            results[actor].extend(xform(m,v)for v in mesh_cache[j])
        for child in node.get("children",[]):
            rec(child,m,actor)
    for i in doc["scenes"][doc.get("scene",0)]["nodes"]:
        rec(i,identity())
    return {k:box(v)for k,v in results.items()}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scene",type=Path,required=True)
    p.add_argument("--native-glb-dir",type=Path,required=True)
    p.add_argument("--meridian-glb",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    opt=p.parse_args()
    scene=json.loads(opt.scene.read_text())
    report=json.loads(opt.report.read_text())
    if report["made_up_source_objects"] or report["original_bo3_t7_map_proven"]:
        raise ValueError("this A/B is for real PAVLOV UE source only")
    ids=set(report["source_world_positions"])
    inp=source_actor_boxes(scene,opt.native_glb_dir,ids)
    out=meridian_actor_boxes(opt.meridian_glb,ids)
    errors=[]
    result={}
    for k in sorted(ids):
        if k not in inp or k not in out:
            errors.append(k+":source_actor_or_exported_mesh_missing")
            continue
        error=max(abs(inp[k][axis][i]-out[k][axis][i])
                  for axis in ("min","max")for i in range(3))
        result[k]={"source_world_aabb":inp[k],"exported_world_aabb":out[k],"error_m":error}
        print("XZOGOT_PAVLOV_MERIDIAN_REAL_SOURCE_BOUNDS",k,"max_abs_m",error)
        if error>0.002:
            errors.append(k+":original_source_mesh_bounds_mismatch_m="+str(error))
    payload={"source":"actual_archived_Pavlov_UE421_NOT_original_BO3_T7",
             "actors":result,"errors":errors,
             "source_mesh_bounds_equal":not errors}
    opt.output.write_text(json.dumps(payload,indent=2)+"\n")
    if errors:
        print("XZOGOT_NACHT_REAL_SOURCE_GEOMETRY_PARITY_RED",errors)
        return 6
    print("XZOGOT_NACHT_REAL_SOURCE_GEOMETRY_PARITY_GREEN",
          "actors",len(ids),"tolerance_m",0.002)
    return 0

if __name__=="__main__":
    sys.exit(main())
