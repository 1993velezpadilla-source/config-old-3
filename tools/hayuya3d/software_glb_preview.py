#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
import trimesh


def _vertex_colors(mesh):
    vertices=np.asarray(mesh.vertices,dtype=np.float64)
    visual=getattr(mesh,"visual",None)
    uv=np.asarray(getattr(visual,"uv",None),dtype=np.float64) if getattr(visual,"uv",None) is not None else None
    material=getattr(visual,"material",None)
    texture=getattr(material,"baseColorTexture",None) if material is not None else None
    if uv is not None and texture is not None and len(uv)==len(vertices):
        arr=np.asarray(texture.convert("RGB"),dtype=np.uint8)
        tx=np.clip(np.rint(uv[:,0]*(arr.shape[1]-1)),0,arr.shape[1]-1).astype(np.int64)
        ty=np.clip(np.rint((1.0-uv[:,1])*(arr.shape[0]-1)),0,arr.shape[0]-1).astype(np.int64)
        return arr[ty,tx]

    colors=getattr(visual,"vertex_colors",None)
    if colors is not None and len(colors)==len(vertices):
        arr=np.asarray(colors,dtype=np.uint8)
        if arr.shape[1]>=3:
            return arr[:,:3]

    # Neutral evidence color for geometry-only meshes.
    return np.tile(np.array([[165,165,165]],dtype=np.uint8),(len(vertices),1))


def _collect(path:Path):
    loaded=trimesh.load(path,force="scene",process=False)
    parts=[]
    for geometry in loaded.geometry.values():
        if not hasattr(geometry,"vertices") or len(geometry.vertices)==0:
            continue
        vv=np.asarray(geometry.vertices,dtype=np.float64)
        cc=_vertex_colors(geometry)
        parts.append((vv,cc))
    if not parts:
        raise RuntimeError(f"no renderable mesh geometry in {path}")
    return (
        np.concatenate([p[0] for p in parts],axis=0),
        np.concatenate([p[1] for p in parts],axis=0),
    )


def _render_front(vertices,colors,size:int):
    lo=vertices.min(axis=0)
    hi=vertices.max(axis=0)

    # Raw Hunyuan GLBs are Y-up with +Z facing the source image.
    width=height=int(size)
    pad=0.06
    xmin,xmax=float(lo[0]),float(hi[0])
    ymin,ymax=float(lo[1]),float(hi[1])
    sx=(1.0-2.0*pad)*(width-1)/max(xmax-xmin,1e-9)
    sy=(1.0-2.0*pad)*(height-1)/max(ymax-ymin,1e-9)
    scale=min(sx,sy)
    cx=(xmin+xmax)*0.5
    cy=(ymin+ymax)*0.5

    px=np.rint((vertices[:,0]-cx)*scale+(width-1)*0.5).astype(np.int32)
    py=np.rint((cy-vertices[:,1])*scale+(height-1)*0.5).astype(np.int32)
    valid=(px>=0)&(px<width)&(py>=0)&(py<height)
    px=px[valid]
    py=py[valid]
    depth=vertices[valid,2]
    color=colors[valid]

    zbuf=np.full((height,width),-np.inf,dtype=np.float64)
    rgb=np.zeros((height,width,3),dtype=np.uint8)

    # Dense point splat with a front-depth z-buffer. This is intentionally
    # independent of OpenGL/Blender so CI can always emit factual previews.
    for oy in (-2,-1,0,1,2):
        for ox in (-2,-1,0,1,2):
            xx=px+ox
            yy=py+oy
            keep=(xx>=0)&(xx<width)&(yy>=0)&(yy<height)
            xx=xx[keep]
            yy=yy[keep]
            zz=depth[keep]
            cc=color[keep]
            flat=yy*width+xx
            order=np.argsort(zz)
            flat_sorted=flat[order]
            last=np.r_[flat_sorted[1:]!=flat_sorted[:-1],True]
            ids=order[last]
            xf=xx[ids]
            yf=yy[ids]
            zf=zz[ids]
            cf=cc[ids]
            better=zf>zbuf[yf,xf]
            zbuf[yf[better],xf[better]]=zf[better]
            rgb[yf[better],xf[better]]=cf[better]

    occupied=np.isfinite(zbuf)
    missing=~occupied
    distance,indices=distance_transform_edt(missing,return_indices=True)
    fill=missing & (distance<=3.0)
    rgb[fill]=rgb[indices[0][fill],indices[1][fill]]
    silhouette=occupied|fill

    background=np.full_like(rgb,18)
    final=np.where(silhouette[...,None],rgb,background)
    return Image.fromarray(final,"RGB"),silhouette,lo,hi


def _face_crop(image:Image.Image,mask:np.ndarray,edge:int):
    ys,xs=np.where(mask)
    if len(xs)==0:
        raise RuntimeError("software renderer produced empty silhouette")
    y0,y1=int(ys.min()),int(ys.max())
    x0,x1=int(xs.min()),int(xs.max())
    head_y1=int(y0+(y1-y0)*0.38)
    margin=int((x1-x0)*0.12)
    hx0=max(0,x0+margin)
    hx1=min(image.width,x1-margin)
    hy0=max(0,y0)
    hy1=min(image.height,head_y1)
    crop=image.crop((hx0,hy0,hx1,hy1))
    cw,ch=crop.size
    square=max(cw,ch)
    canvas=Image.new("RGB",(square,square),(18,18,18))
    canvas.paste(crop,((square-cw)//2,(square-ch)//2))
    if square!=int(edge):
        canvas=canvas.resize((int(edge),int(edge)),Image.Resampling.LANCZOS)
    return canvas


def render_preview(input_glb:Path,output_dir:Path,size:int=768,face_size:int=768):
    vertices,colors=_collect(input_glb)
    image,mask,lo,hi=_render_front(vertices,colors,int(size))
    turntable=output_dir/"turntable"
    faces=output_dir/"faces"
    turntable.mkdir(parents=True,exist_ok=True)
    faces.mkdir(parents=True,exist_ok=True)
    full_path=turntable/"12_180.png"
    face_path=faces/"12_180.png"
    image.save(full_path)
    _face_crop(image,mask,int(face_size)).save(face_path)
    payload={
        "schema":1,
        "renderer":"hayuya-cpu-zbuffer-source-texture-v1",
        "source":str(input_glb),
        "front_convention":"+Z raw Hunyuan coordinates; filename retained as 12_180 for Judge compatibility",
        "vertices":int(len(vertices)),
        "occupied_pixels":int(np.count_nonzero(mask)),
        "bounds":{"min":[float(x) for x in lo],"max":[float(x) for x in hi]},
        "turntable":[str(full_path)],
        "faces":[str(face_path)],
        "preflight_only":True,
    }
    (output_dir/"software_manifest.json").write_text(
        json.dumps(payload,indent=2)+"\n",encoding="utf-8"
    )
    print("HAYUYA_SOFTWARE_FRONT_PASS",json.dumps(payload,separators=(",",":")))
    return payload


def main():
    p=argparse.ArgumentParser(description="Dependency-light HAYUYA factual GLB front preview.")
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--size",type=int,default=768)
    p.add_argument("--face-size",type=int,default=768)
    a=p.parse_args()
    render_preview(a.input,a.output_dir,a.size,a.face_size)


if __name__=="__main__":
    main()
