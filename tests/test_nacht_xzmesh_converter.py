#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"assets/nacht_reference/pavlov_scene_reference/assets.json"
CONVERT=ROOT/"tools/maps/convert_glb_to_xzmesh.py"
BATCH=ROOT/"tools/maps/compile_nacht_xzmesh_bundle.py"
HEADER=struct.Struct("<4sIIIIIII6f")
VERTEX=struct.Struct("<8f")


def pad4(data:bytes,pad=b" ")->bytes:
    return data + pad*((4-len(data)%4)%4)


def make_glb(path:Path)->None:
    pos=struct.pack("<9f",0,0,0,1,0,0,0,1,0)
    nrm=struct.pack("<9f",0,0,1,0,0,1,0,0,1)
    uv=struct.pack("<6f",0,0,1,0,0,1)
    idx=struct.pack("<3H",0,1,2)
    chunks=[]
    offset=0
    for payload in (pos,nrm,uv,idx):
        start=offset
        chunks.append((start,len(payload)))
        offset += len(payload)
        offset = (offset+3)&~3
    binary=bytearray(offset)
    for payload,(start,length) in zip((pos,nrm,uv,idx),chunks):
        binary[start:start+length]=payload

    views=[
        {"buffer":0,"byteOffset":chunks[0][0],"byteLength":chunks[0][1]},
        {"buffer":0,"byteOffset":chunks[1][0],"byteLength":chunks[1][1]},
        {"buffer":0,"byteOffset":chunks[2][0],"byteLength":chunks[2][1]},
        {"buffer":0,"byteOffset":chunks[3][0],"byteLength":chunks[3][1]},
    ]
    doc={
        "asset":{"version":"2.0"},
        "buffers":[{"byteLength":len(binary)}],
        "bufferViews":views,
        "accessors":[
            {"bufferView":0,"componentType":5126,"count":3,"type":"VEC3"},
            {"bufferView":1,"componentType":5126,"count":3,"type":"VEC3"},
            {"bufferView":2,"componentType":5126,"count":3,"type":"VEC2"},
            {"bufferView":3,"componentType":5123,"count":3,"type":"SCALAR"},
        ],
        "materials":[{}],
        "meshes":[{"primitives":[{
            "attributes":{"POSITION":0,"NORMAL":1,"TEXCOORD_0":2},
            "indices":3,
            "material":0,
            "mode":4,
        }]}],
        "nodes":[{"mesh":0,"translation":[1,2,3],"scale":[2,2,2]}],
        "scenes":[{"nodes":[0]}],
        "scene":0,
    }
    j=pad4(json.dumps(doc,separators=(",",":")).encode("utf-8"),b" ")
    b=pad4(bytes(binary),b"\x00")
    total=12+8+len(j)+8+len(b)
    raw=(
        struct.pack("<III",0x46546C67,2,total)
        +struct.pack("<II",len(j),0x4E4F534A)+j
        +struct.pack("<II",len(b),0x004E4942)+b
    )
    path.write_bytes(raw)


with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    one=td/"one.glb"
    out=td/"one.xzm"
    make_glb(one)
    p=subprocess.run(["python3",str(CONVERT),str(one),str(out)],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    assert p.returncode==0,p.stdout
    raw=out.read_bytes()
    head=HEADER.unpack_from(raw,0)
    assert head[0]==b"XZMS" and head[1]==1
    assert head[2:5]==(3,3,1),head
    v0=VERTEX.unpack_from(raw,HEADER.size)
    assert abs(v0[0]-1)<1e-6 and abs(v0[1]+3)<1e-6 and abs(v0[2]-2)<1e-6,v0

    assets=json.loads(ASSETS.read_text())
    glbs=td/"glbs"; glbs.mkdir()
    for row in assets["meshes"]:
        name=row["sourcePath"].replace("\\","/").rstrip("/").rsplit("/",1)[-1]
        make_glb(glbs/f"{name}.glb")
    xzroot=td/"xzmesh"
    manifest=td/"bundle.json"
    bproc=subprocess.run([
        "python3",str(BATCH),
        "--glb-root",str(glbs),
        "--output-root",str(xzroot),
        "--manifest",str(manifest),
    ],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    assert bproc.returncode==0,bproc.stdout
    payload=json.loads(manifest.read_text())
    s=payload["summary"]
    assert s["meshCount"]==492,s
    assert s["vertexCount"]==492*3,s
    assert s["indexCount"]==492*3,s
    assert s["triangleCount"]==492,s
    assert s["submeshCount"]==492,s
    assert s["submeshesWithoutNormals"]==0,s
    assert s["submeshesWithoutUv0"]==0,s
    assert s["geometryRuntimeFormatReady"] is True
    assert s["materialBindingReady"] is False

    files=sorted(p.name for p in xzroot.glob("*.xzm"))
    assert len(files)==492
    assert files[0]=="m0000.xzm",files[:3]
    assert files[-1]=="m0491.xzm",files[-3:]
    assert payload["meshes"][0]["runtimeFile"]=="m0000.xzm"
    assert payload["meshes"][-1]["runtimeFile"]=="m0491.xzm"
    assert payload["runtimeNaming"]["scheme"]=="compact_ordinal_v1"

print("XZIEL_NACHT_XZMS_TEST_OK meshes=492 compact_qpath=PASS basis_conversion=PASS binary_format=PASS")
