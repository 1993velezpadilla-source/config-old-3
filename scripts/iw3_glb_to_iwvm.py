#!/usr/bin/env python3
"""Convert one glTF 2.0 GLB into VIRIL IW3's small GLES2 viewmodel mesh.

IWVM v1 = <4sIII header> + vertices <5f> + triangle indices <H>.
This is a GEOMETRY transport only: it preserves vertex placement, the scene
node transformations and UVs, but not skeletal XAnim, materials or weights.
Never publish converted proprietary COD4 meshes in an open APK/repository.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import struct

MAX_VERTICES = 65535
MAX_INDICES = 360000
IDENT = (1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)


def mmul(a,b):
    return tuple(sum(a[k*4+r]*b[c*4+k] for k in range(4))
                 for c in range(4) for r in range(4))


def mat_trs(node):
    if "matrix" in node:
        result=tuple(float(v) for v in node["matrix"])
        if len(result)!=16: raise ValueError("GLB node matrix should have 16 floats")
        return result
    t=node.get("translation",[0,0,0])
    q=node.get("rotation",[0,0,0,1])
    s=node.get("scale",[1,1,1])
    if len(t)!=3 or len(q)!=4 or len(s)!=3:
        raise ValueError("Malformed node transform")
    x,y,z,w=(float(v) for v in q)
    n=x*x+y*y+z*z+w*w
    if n<1e-12: raise ValueError("Zero-length node quaternion")
    x,y,z,w=(v/math.sqrt(n) for v in (x,y,z,w))
    sx,sy,sz=map(float,s)
    rotation=(1-2*(y*y+z*z),2*(x*y+z*w),2*(x*z-y*w),0,
              2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w),0,
              2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y),0,
              0,0,0,1)
    # Column-major matrix: scale first, translate last.
    v=list(rotation)
    for c,sc in enumerate((sx,sy,sz)):
        for r in range(3):v[c*4+r]*=sc
    v[12:15]=list(map(float,t))
    return tuple(v)


def transform(m,p):
    return tuple(sum(m[c*4+r]*p[c] for c in range(3))+m[12+r]
                 for r in range(3))


def load_glb(path):
    data=Path(path).read_bytes()
    if len(data)<20:raise ValueError("GLB truncated")
    magic,version,total=struct.unpack_from("<4sII",data)
    if magic!=b"glTF" or version!=2 or total!=len(data):
        raise ValueError("Expected complete glTF 2.0 binary GLB")
    pos=12
    descriptor=None
    buffer=None
    while pos+8<=len(data):
        length,kind=struct.unpack_from("<I4s",data,pos)
        pos+=8
        if length>len(data)-pos or length%4:raise ValueError("Malformed GLB chunk")
        chunk=data[pos:pos+length]
        pos+=length
        if kind==b"JSON":
            if descriptor is not None:raise ValueError("Duplicate JSON chunk")
            descriptor=json.loads(chunk.decode("utf-8").strip(" \x00"))
        if kind==b"BIN\x00":
            if buffer is not None:raise ValueError("Duplicate BIN chunk")
            buffer=chunk
    if descriptor is None or buffer is None or pos!=len(data):
        raise ValueError("GLB must have JSON and BIN chunks")
    return descriptor,buffer


def read_accessor(doc,blob,idx,components):
    accessors=doc.get("accessors",[])
    views=doc.get("bufferViews",[])
    if not isinstance(idx,int) or not 0<=idx<len(accessors):
        raise ValueError("Missing accessor")
    a=accessors[idx]
    if "sparse" in a:raise ValueError("Sparse glTF accessors unsupported")
    vt={"SCALAR":1,"VEC2":2,"VEC3":3}
    if vt.get(a["type"])!=components:raise ValueError("Unexpected accessor dimension")
    formats={5121:("B",1),5123:("H",2),5125:("I",4),5126:("f",4)}
    field= a["componentType"]
    if field not in formats:raise ValueError("Unsupported glTF component type")
    code,size=formats[field]
    count=int(a.get("count",0))
    if count<1 or count>MAX_INDICES:raise ValueError("Invalid accessor element count")
    v=views[a["bufferView"]]
    if v.get("buffer",0)!=0:raise ValueError("External glTF buffer unsupported")
    stride=v.get("byteStride",size*components)
    if stride<size*components or stride>256:raise ValueError("Invalid GLB stride")
    base=int(v.get("byteOffset",0))+int(a.get("byteOffset",0))
    view_end=int(v.get("byteOffset",0))+int(v["byteLength"])
    end=base+stride*(count-1)+size*components
    if base<0 or end>min(view_end,len(blob)):raise ValueError("Out-of-range GLB accessor")
    pattern="<"+code*components
    return [struct.unpack_from(pattern,blob,base+i*stride) for i in range(count)]


def convert(path,scale=1.0,axis="gltf_yup_to_quake_zup"):
    if not math.isfinite(scale) or not 0<scale<=10000:
        raise ValueError("Bad scale")
    doc,blob=load_glb(path)
    nodes=doc.get("nodes",[])
    meshes=doc.get("meshes",[])
    if not meshes: raise ValueError("GLB has no mesh")
    if not nodes: nodes=[{"mesh":i} for i in range(len(meshes))]
    scenes=doc.get("scenes",[])
    roots=scenes[doc.get("scene",0)].get("nodes",[]) if scenes else list(range(len(nodes)))
    vertices=[]
    indices=[]
    seen=set()
    skin_meshes=0

    def visit(ni,parent,ancestors):
        nonlocal skin_meshes
        if ni in ancestors:raise ValueError("Cyclic GLB node scene")
        if not 0<=ni<len(nodes):raise ValueError("Invalid scene node")
        node=nodes[ni]
        mat=mmul(parent,mat_trs(node))
        if "mesh" in node:
            mid=node["mesh"]
            if not 0<=mid<len(meshes):raise ValueError("Invalid mesh index")
            if "skin" in node:skin_meshes+=1
            for prim in meshes[mid].get("primitives",[]):
                if prim.get("mode",4)!=4:continue
                attrib=prim["attributes"]
                if "POSITION" not in attrib:raise ValueError("GLB mesh without POSITION")
                xyz=read_accessor(doc,blob,attrib["POSITION"],3)
                uv=(read_accessor(doc,blob,attrib["TEXCOORD_0"],2)
                    if "TEXCOORD_0" in attrib else [(0.,0.) for _ in xyz])
                if len(xyz)!=len(uv):raise ValueError("GLB UV count mismatch")
                if len(vertices)+len(xyz)>MAX_VERTICES:raise ValueError("IWVM v1 vertex limit")
                if "indices" in prim:
                    face_indices=read_accessor(doc,blob,prim["indices"],1)
                    local=[int(t[0]) for t in face_indices]
                else:
                    local=list(range(len(xyz)))
                if len(local)%3:raise ValueError("Nontriangular GLB index list")
                if len(indices)+len(local)>MAX_INDICES:raise ValueError("IWVM v1 triangle limit")
                if any(i<0 or i>=len(xyz) for i in local):
                    raise ValueError("GLB primitive index outside vertex array")
                offset=len(vertices)
                for v,t in zip(xyz,uv):
                    x,y,z=transform(mat,v)
                    # Quake world: X forward, Y left, Z up. glTF convention is Y up.
                    if axis=="gltf_yup_to_quake_zup":
                        x,y,z=-z,-x,y
                    elif axis!="original":
                        raise ValueError("Unknown coordinate conversion")
                    values=[x*scale,y*scale,z*scale,float(t[0]),float(t[1])]
                    if not all(math.isfinite(v) and abs(v)<1e7 for v in values):
                        raise ValueError("Non-finite or extreme vertex in GLB")
                    vertices.append(values)
                indices.extend(offset+i for i in local)
        for kid in node.get("children",[]):visit(kid,mat,ancestors|{ni})

    for root in roots:visit(root,IDENT,set())
    if not vertices or not indices:raise ValueError("No drawable glTF triangle meshes")
    if max(indices)>=len(vertices):raise ValueError("GLB broken index")
    header=struct.pack("<4sIII",b"IWVM",1,len(vertices),len(indices))
    payload=b"".join(struct.pack("<5f",*v) for v in vertices)
    faces=struct.pack("<"+"H"*len(indices),*indices)
    evidence={"vertices":len(vertices),"triangles":len(indices)//3,
              "skin_meshes_not_animated":skin_meshes,
              "output_bytes":len(header)+len(payload)+len(faces),
              "axis":axis,"scale":scale,
              "skeleton_animation_supported":False,"texture_mapping_supported":False}
    return header+payload+faces,evidence


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--scale",type=float,default=1.0)
    ap.add_argument("--axis",choices=("original","gltf_yup_to_quake_zup"),
                    default="gltf_yup_to_quake_zup")
    args=ap.parse_args()
    binary,ev=convert(args.input,args.scale,args.axis)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(binary)
    print(json.dumps(ev,sort_keys=True))


if __name__=="__main__":
    main()
