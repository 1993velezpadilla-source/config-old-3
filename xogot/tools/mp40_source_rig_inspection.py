#!/usr/bin/env python3
"""Read original MP40 and T4 Marine hand GLB animation data, without Blender guesses."""
import json
import math
import struct
from pathlib import Path

ROOT = Path("xogot/assets/weapons")
FILES = [
    ROOT / "aether_waw_hands/t4_marine/mp40/viewhands.glb",
    ROOT / "aether_waw_real/mp40/viewmodel.glb",
]
PHASES = (0.0, 0.18, 0.34, 0.5, 0.68, 0.88, 1.0)
NAMES = ("tag_weapon", "tag_view", "tag_ads", "tag_torso",
         "l_hand", "r_hand", "j_clip", "j_gun", "j_bolt")
def load(path):
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    json_len, code = struct.unpack_from("<II", data, 12)
    assert code == 0x4e4f534a
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    return data, gltf, bin_start

def values(data, gltf, offset, idx):
    a = gltf["accessors"][idx]
    view = gltf["bufferViews"][a["bufferView"]]
    n = {"SCALAR":1, "VEC3":3, "VEC4":4}.get(a["type"])
    if not n or a["componentType"] != 5126:
        return []
    stride = view.get("byteStride", n * 4)
    start = offset + view.get("byteOffset", 0) + a.get("byteOffset", 0)
    return [list(struct.unpack_from("<" + "f"*n, data, start+i*stride))
            for i in range(a["count"])]

def inspect(path):
    data, g, off = load(path)
    nodes = g["nodes"]
    parents = {}
    for i, node in enumerate(nodes):
        for ch in node.get("children", []):
            parents[ch] = i
    print("MP40_GLTF_SOURCE",path,"nodes=",len(nodes),"meshes=",len(g.get("meshes", [])),
          "skins=",len(g.get("skins", [])),"anims=",len(g.get("animations", [])))
    print("MP40_SOURCE_ROOTS", [
        {"i":i,"name":n.get("name"),"translation":n.get("translation"),
         "scale":n.get("scale"),"rotation":n.get("rotation")}
        for i,n in enumerate(nodes) if i not in parents][:8])
    print("MP40_SOURCE_ANIMATIONS",[
        {"name":a.get("name"),"count":len(a["channels"])}
        for a in g.get("animations", [])])
    ids = []
    for i,n in enumerate(nodes):
        name = str(n.get("name",""))
        if any(w in name.lower() for w in NAMES):
            ids.append(i)
    for i in ids:
        n = nodes[i]
        lineage = []
        p = i
        while p in parents:
            lineage.append(nodes[p].get("name","")+"#"+str(p))
            p = parents[p]
        lineage.append(nodes[p].get("name", "")+"#"+str(p))
        print("MP40_SOURCE_BONE",i,n.get("name"),
              "rest_t=",n.get("translation", [0,0,0]),
              "rest_r=",n.get("rotation", [0,0,0,1]),
              "rest_s=",n.get("scale",[1,1,1]),
              "lineage=", " <- ".join(lineage))
    for anim in g.get("animations", []):
        name = anim.get("name", "")
        if "reload" not in name.lower():
            continue
        print("MP40_SOURCE_RELOAD",name)
        for ch in anim["channels"]:
            node = ch["target"]["node"]
            if node not in ids:
                continue
            sampler=anim["samplers"][ch["sampler"]]
            times=values(data,g,off,sampler["input"])
            output=values(data,g,off,sampler["output"])
            if not times or not output:
                continue
            tmin=times[0][0]
            tmax=times[-1][0]
            samples=[]
            for f in PHASES:
                t=tmin + (tmax-tmin)*f
                index=min(range(len(times)),key=lambda k:abs(times[k][0]-t))
                samples.append([round(times[index][0],2),[round(v,5) for v in output[index]]])
            name_node=nodes[node].get("name","")
            print("MP40_SOURCE_TRACK",name,"bone=",name_node,
                  "type=",ch["target"]["path"],
                  "keys=",len(times),"sample=",json.dumps(samples))
    print("MP40_SOURCE_GLB_FINISHED",path)

for file in FILES:
    inspect(file)
print("MP40_SOURCE_RIG_AUDIT_FINISHED")
