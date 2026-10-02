#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict,dataclass
from pathlib import Path

import numpy as np
from PIL import Image

@dataclass
class View:
    name:str
    bbox:list[int]
    width_fraction:float
    height_fraction:float
    fill_fraction:float

def _mask(path:Path):
    im=np.asarray(Image.open(path).convert("RGB"),dtype=np.float32)
    h,w=im.shape[:2]
    corners=np.concatenate([
        im[:max(8,h//20),:max(8,w//20)].reshape(-1,3),
        im[-max(8,h//20):,-max(8,w//20):].reshape(-1,3),
    ],axis=0)
    bg=np.median(corners,axis=0)
    dist=np.linalg.norm(im-bg,axis=2)
    m=dist>18.0
    ys,xs=np.where(m)
    if len(xs)<64:
        raise RuntimeError(f"no_subject:{path.name}")
    bbox=[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]
    wf=(bbox[2]-bbox[0]+1)/w
    hf=(bbox[3]-bbox[1]+1)/h
    fill=float(m.mean())
    return im,m,View(path.stem,bbox,round(wf,6),round(hf,6),round(fill,6))

def _crop_signature(im,m):
    ys,xs=np.where(m)
    crop=im[ys.min():ys.max()+1,xs.min():xs.max()+1]
    pil=Image.fromarray(np.clip(crop,0,255).astype(np.uint8)).convert("L").resize((64,64))
    arr=np.asarray(pil,dtype=np.float32)/255.0
    return arr

def main()->int:
    p=argparse.ArgumentParser(description="Eyes-open visual gate for HAYUYA preview packs.")
    p.add_argument("render_dir",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    required=["front","three_quarter","side","face"]
    reasons=[]
    views={}
    sig={}
    for name in required:
        path=a.render_dir/f"{name}.png"
        if not path.is_file():
            reasons.append(f"missing_render:{name}")
            continue
        try:
            im,m,v=_mask(path)
            views[name]=asdict(v)
            sig[name]=_crop_signature(im,m)
        except Exception as exc:
            reasons.append(f"{name}:{type(exc).__name__}:{exc}")

    for name in ("front","three_quarter","side"):
        v=views.get(name)
        if not v:
            continue
        if v["height_fraction"]<0.68:
            reasons.append(f"{name}_too_small:{v['height_fraction']:.3f}<0.68")
        if v["height_fraction"]>0.94:
            reasons.append(f"{name}_cropped:{v['height_fraction']:.3f}>0.94")

    face=views.get("face")
    if face:
        if face["height_fraction"]<0.58:
            reasons.append(f"face_not_close_enough:{face['height_fraction']:.3f}<0.58")
        if face["bbox"][1]<=2 or face["bbox"][3]>=1021:
            reasons.append("face_crop_touches_frame")

    if all(k in sig for k in ("front","three_quarter","side")):
        d13=float(np.mean(np.abs(sig["front"]-sig["three_quarter"])))
        d14=float(np.mean(np.abs(sig["front"]-sig["side"])))
        if d13<0.015:
            reasons.append(f"front_three_quarter_not_distinct:{d13:.4f}")
        if d14<0.035:
            reasons.append(f"front_side_not_distinct:{d14:.4f}")
    else:
        d13=d14=None

    payload={
        "schema":1,
        "render_dir":str(a.render_dir),
        "views":views,
        "front_three_quarter_delta":round(d13,6) if d13 is not None else None,
        "front_side_delta":round(d14,6) if d14 is not None else None,
        "passed":not reasons,
        "reasons":reasons,
    }
    print(json.dumps(payload,indent=2))
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True)
        a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    return 0 if not reasons else 5

if __name__=="__main__":
    raise SystemExit(main())
