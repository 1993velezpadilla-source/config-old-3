#!/usr/bin/env python3
"""Provenance audit of original Oct-02 Sanctum V2 GLB.
Do not confuse procedural Blender nodes with authored bitmap textures.
Outputs per-material triangle coverage / UV range / node family for baking.
"""
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import trimesh
import argparse

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("source",type=Path)
    ap.add_argument("--out",type=Path,default=Path("sanctum-material-audit.json"))
    args=ap.parse_args()
    scene=trimesh.load(str(args.source),force="scene",process=False)
    stats=defaultdict(lambda:dict(triangles=0,nodes=0,uv_nodes=0,colors_nodes=0,images_nodes=0,examples=[]))
    for node in scene.graph.nodes_geometry:
        _,name=scene.graph[node]
        mesh=scene.geometry[name]
        mat=getattr(mesh.visual,"material",None)
        key=str(getattr(mat,"name","<none>")) if mat is not None else "<none>"
        rec=stats[key]
        rec['triangles']+=len(mesh.faces)
        rec['nodes']+=1
        if len(rec['examples'])<5:rec['examples'].append(node)
        uv=getattr(mesh.visual,"uv",None)
        if uv is not None and np.asarray(uv).size and np.ptp(uv,axis=0).max()>1e-6:
            rec['uv_nodes']+=1
        if getattr(mesh.visual,"kind",None) in ("vertex","face"):rec['colors_nodes']+=1
        if mat is not None and any(getattr(mat,atr,None) is not None for atr in ("baseColorTexture","image")):rec["images_nodes"]+=1
    ordered={k:v for k,v in sorted(stats.items(),key=lambda x:-x[1]["triangles"])}
    totals=dict(materials=len(stats),triangles=sum(x['triangles'] for x in stats.values()),nodes=sum(x['nodes'] for x in stats.values()))
    outcome={"source":str(args.source),"totals":totals,"materials":ordered}
    args.out.write_text(json.dumps(outcome,indent=2)+"\n")
    print("SANCTUM_MATERIAL_PROVENANCE",json.dumps(totals))
    for key,v in ordered.items():
        print(f"MAT {key!r} tris={v['triangles']} nodes={v['nodes']} UV={v['uv_nodes']} IMAGE={v['images_nodes']} COLOR={v['colors_nodes']} examples={v['examples'][:2]}")
    assert totals["triangles"]>=350000
if __name__=="__main__":main()
