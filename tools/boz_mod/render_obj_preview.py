#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def load_obj(path: Path):
    verts=[]
    faces=[]
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            parts=line.split()
            if len(parts) >= 4:
                verts.append(tuple(float(v) for v in parts[1:4]))
        elif line.startswith("f "):
            idx=[]
            for tok in line.split()[1:]:
                raw=tok.split("/")[0]
                if raw:
                    i=int(raw)
                    idx.append(i-1 if i>0 else len(verts)+i)
            if len(idx)>=3:
                for j in range(1,len(idx)-1):
                    faces.append((idx[0],idx[j],idx[j+1]))
    if not verts:
        raise SystemExit("OBJ has no vertices")
    return verts,faces

def rotate(v, yaw, pitch):
    x,y,z=v
    cy,sy=math.cos(yaw),math.sin(yaw)
    x,z=x*cy+z*sy,-x*sy+z*cy
    cp,sp=math.cos(pitch),math.sin(pitch)
    y,z=y*cp-z*sp,y*sp+z*cp
    return x,y,z

def render(obj: Path, out: Path, yaw_deg: float, pitch_deg: float, title: str):
    verts,faces=load_obj(obj)
    cx=sum(v[0] for v in verts)/len(verts)
    cy=sum(v[1] for v in verts)/len(verts)
    cz=sum(v[2] for v in verts)/len(verts)
    centered=[(x-cx,y-cy,z-cz) for x,y,z in verts]
    yaw=math.radians(yaw_deg); pitch=math.radians(pitch_deg)
    rv=[rotate(v,yaw,pitch) for v in centered]

    xs=[v[0] for v in rv]; ys=[v[1] for v in rv]
    span=max(max(xs)-min(xs),max(ys)-min(ys),1.0)
    W,H=1600,900
    scale=0.72*min(W,H)/span

    def pt(v):
        return (W/2+v[0]*scale, H/2-v[1]*scale)

    img=Image.new("RGB",(W,H),(15,16,18))
    draw=ImageDraw.Draw(img)

    depth=[]
    for f in faces:
        z=sum(rv[i][2] for i in f)/3.0
        depth.append((z,f))
    depth.sort(reverse=True)

    if depth:
        for z,f in depth:
            p=[pt(rv[i]) for i in f]
            # depth-only grayscale shading so the geometry itself remains the evidence.
            shade=int(max(50,min(190,120+z/span*90)))
            draw.polygon(p,fill=(shade,shade,shade))
            draw.line(p+[p[0]],fill=(28,28,30),width=1)
    else:
        # Some BOZ CIwModel variants expose vertex blocks but the current
        # decoder cannot recover the triangle-list block. Show the real
        # projected vertex cloud instead of returning a misleading blank frame.
        order=sorted(range(len(rv)), key=lambda i: rv[i][2], reverse=True)
        for i in order:
            x,y=pt(rv[i])
            z=rv[i][2]
            shade=int(max(80,min(235,155+z/span*100)))
            r=2
            draw.ellipse((x-r,y-r,x+r,y+r),fill=(shade,shade,shade))

    draw.rectangle((0,0,W,72),fill=(7,8,10))
    draw.text((28,18),title,fill=(240,240,240))
    draw.text((28,47),f"{obj.name} | verts={len(verts)} tris={len(faces)} | yaw={yaw_deg:g} pitch={pitch_deg:g}",fill=(190,190,190))
    out.parent.mkdir(parents=True,exist_ok=True)
    img.save(out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--obj",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    args=ap.parse_args()
    render(args.obj,args.outdir/"xchurch_model_front.png",25,-12,"XChurch — modified BOZ theatre model (front 3/4)")
    render(args.obj,args.outdir/"xchurch_model_back.png",205,-12,"XChurch — modified BOZ theatre model (reverse 3/4)")
    print("XZIEL_XCHURCH_MODEL_PREVIEW_OK")

if __name__=="__main__":
    main()
