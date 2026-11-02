#!/usr/bin/env python3
"""Preserve REAL CoD4 GLB skeleton joint names, bind matrices and skin weights.

IWSK v1 companion for optional IWVM v1. No generated fake keyframes;
skeletal playback is not claimed. Source meshes come only from an owner's
OAT-extracted GLB, never committed, bundled or uploaded publicly.

Format little-endian:
  header <4sIIII> = b'IWSK',1,vertex_count,joint_count,flags(0)
  bones joint_count times <64si16f16f>:
     null-terminated original joint name, parent joint index (-1 root),
     local bind matrix and inverse-bind matrix (both Quake Z-up basis)
  vertices vertex_count times <4B4f>: four joint indices and weights.
Triangles/UVs are carried by companion IWVM. Vertex order *must* match
the existing scripts/iw3_glb_to_iwvm.py exporter exactly.
"""
from __future__ import annotations
import argparse,json,math,struct
from pathlib import Path
from iw3_glb_to_iwvm import (
    load_glb, read_accessor, IDENT, mat_trs, mmul, convert
)

HEADER=struct.Struct("<4sIIII")
BONE=struct.Struct("<64si16f16f")
VERTEX=struct.Struct("<4B4f")
BASIS=(0.,-1.,0.,0., 0.,0.,1.,0., -1.,0.,0.,0., 0.,0.,0.,1.)
# Orthogonal basis inverse: transpose the upper-left 3x3, preserve W.
INVERSE_BASIS=tuple(
    (BASIS[r*4+c] if r<3 and c<3 else 1. if r==c else 0.)
    for c in range(4) for r in range(4)
)


def basis_convert(m,axis):
    if axis=="original":return tuple(m)
    if axis!="gltf_yup_to_quake_zup":raise ValueError("Unknown GLB axis")
    return mmul(mmul(BASIS,m),INVERSE_BASIS)


def matrix_accessor(doc,blob,index):
    entries=doc.get("accessors",[])
    if not isinstance(index,int) or not 0<=index<len(entries):
        raise ValueError("No inverse bind matrix accessor")
    if entries[index].get("type")!="MAT4" or entries[index].get("componentType")!=5126:
        raise ValueError("OAT glTF inverse bind matrix must be float MAT4")
    return read_accessor(doc,blob,index,16)


def export(path:Path,scale:float=1.,axis:str="gltf_yup_to_quake_zup"):
    doc,blob=load_glb(path)
    skins=doc.get("skins",[])
    if len(skins)!=1:raise ValueError("This IWSK v1 requires one original glTF skin")
    skin=skins[0]
    nodes=doc.get("nodes",[])
    joints=skin.get("joints",[])
    if not (1<=len(joints)<=255) or len(set(joints))!=len(joints):
        raise ValueError("Invalid OAT gun joint range")
    if any(not isinstance(i,int) or not 0<=i<len(nodes) for i in joints):
        raise ValueError("Original skin joint outside GLB nodes")
    inverse=matrix_accessor(doc,blob,skin.get("inverseBindMatrices"))
    if len(inverse)!=len(joints):
        raise ValueError("Inverse bind count does not match original joint count")
    indices={n:i for i,n in enumerate(joints)}
    parents={}
    for n,node in enumerate(nodes):
        for child in node.get("children",[]):
            if child in parents:raise ValueError("Multiple glTF joint parents")
            parents[child]=n
    bone_bytes=bytearray()
    for index,node_index in enumerate(joints):
        node=nodes[node_index]
        name=node.get("name","")
        if not isinstance(name,str):raise ValueError("Invalid joint name")
        encoded=name.encode("utf-8")
        if not encoded or len(encoded)>=64 or b"\0" in encoded:
            raise ValueError("Unsupported original joint name")
        parent=parents.get(node_index)
        if parent is not None and parent not in indices:
            raise ValueError("Joint's parent missing from skin")
        bind=basis_convert(mat_trs(node),axis)
        inv=basis_convert(inverse[index],axis)
        if not all(math.isfinite(v) for v in bind+inv):
            raise ValueError("Corrupt IW3 bind matrices")
        bone_bytes+=BONE.pack(encoded.ljust(64,b"\0"),
                              indices[parent] if parent is not None else -1,
                              *bind,*inv)
    meshes=doc.get("meshes",[])
    if not nodes:nodes=[{"mesh":i,"skin":0} for i in range(len(meshes))]
    scenes=doc.get("scenes",[])
    roots=(scenes[doc.get("scene",0)].get("nodes",[])
           if scenes else list(range(len(nodes))))
    influences=bytearray()
    active=0
    def visit(ni,ancestors):
        nonlocal active
        if ni in ancestors:raise ValueError("Cyclic original GLB nodes")
        if not 0<=ni<len(nodes):raise ValueError("Invalid glTF scene graph")
        node=nodes[ni]
        if "mesh" in node:
            if node.get("skin")!=0:
                raise ValueError("Mesh references different original skeleton")
            mesh=meshes[node["mesh"]]
            for prim in mesh.get("primitives",[]):
                if prim.get("mode",4)!=4:continue
                attributes=prim.get("attributes",{})
                positions=read_accessor(doc,blob,attributes["POSITION"],3)
                a=attributes.get("JOINTS_0")
                b=attributes.get("WEIGHTS_0")
                if a is None or b is None:
                    raise ValueError("Original CoD4 vertex lacks skin weights")
                ja=doc["accessors"][a]
                wa=doc["accessors"][b]
                if ja["componentType"]!=5121 or wa["componentType"]!=5126:
                    raise ValueError("Expected official OAT u8 joints/float weights")
                js=read_accessor(doc,blob,a,4)
                ws=read_accessor(doc,blob,b,4)
                if len(positions)!=len(js) or len(js)!=len(ws):
                    raise ValueError("Original bone weight / vertex order mismatch")
                for bones,weights in zip(js,ws):
                    if any(v>=len(joints) for v in bones):
                        raise ValueError("Vertex bone index beyond skeleton")
                    if not all(math.isfinite(v) and v>=0 for v in weights):
                        raise ValueError("Invalid joint weight")
                    total=sum(weights)
                    if total<=0 or abs(total-1.)>.02:
                        raise ValueError("Original vertex bone weights not normalized")
                    influences.extend(VERTEX.pack(*bones,*(v/total for v in weights)))
                    active+=1
        for child in node.get("children",[]):
            visit(child,ancestors|{ni})
    for n in roots:visit(n,set())
    reference,meta=convert(path,scale,axis)
    expected=struct.unpack_from("<I",reference,8)[0]
    if active!=expected:
        raise ValueError(f"Original mesh + skin vertex index order mismatch: {active}/{expected}")
    binary=HEADER.pack(b"IWSK",1,active,len(joints),0)+bone_bytes+influences
    assert len(binary)==HEADER.size+len(joints)*BONE.size+active*VERTEX.size
    return binary,{
        "original_glb_joints":len(joints),
        "original_rigged_vertices":active,
        "source_original_joints_and_weights_retained":True,
        "original_reload_skeletal_playback":False,
        "original_game_bytes_to_public_artifact":False,
        "output_private_bytes":len(binary),
        "native_viewmodel_vertex_count":expected,
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    encoded,counts=export(a.input)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(encoded)
    print(json.dumps(counts,indent=2))
