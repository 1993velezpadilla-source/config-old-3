#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from numba import njit
from PIL import Image
import trimesh


@njit(cache=False)
def _raster_textured(
    vertices,
    faces,
    uv,
    texture,
    zbuf,
    rgb,
    xmin,
    xmax,
    ymin,
    ymax,
):
    height,width=zbuf.shape
    sx=(width-1)/max(xmax-xmin,1e-9)
    sy=(height-1)/max(ymax-ymin,1e-9)
    tex_h,tex_w,_=texture.shape

    for face_index in range(faces.shape[0]):
        i0=faces[face_index,0]
        i1=faces[face_index,1]
        i2=faces[face_index,2]

        x0=(vertices[i0,0]-xmin)*sx
        y0=(ymax-vertices[i0,1])*sy
        x1=(vertices[i1,0]-xmin)*sx
        y1=(ymax-vertices[i1,1])*sy
        x2=(vertices[i2,0]-xmin)*sx
        y2=(ymax-vertices[i2,1])*sy

        min_x=max(0,int(math.floor(min(x0,x1,x2))))
        max_x=min(width-1,int(math.ceil(max(x0,x1,x2))))
        min_y=max(0,int(math.floor(min(y0,y1,y2))))
        max_y=min(height-1,int(math.ceil(max(y0,y1,y2))))
        if max_x<min_x or max_y<min_y:
            continue

        denom=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(denom)<1e-10:
            continue

        z0=vertices[i0,2]
        z1=vertices[i1,2]
        z2=vertices[i2,2]
        u0=uv[i0,0]
        v0=uv[i0,1]
        u1=uv[i1,0]
        v1=uv[i1,1]
        u2=uv[i2,0]
        v2=uv[i2,1]

        for yy in range(min_y,max_y+1):
            py=yy+0.5
            for xx in range(min_x,max_x+1):
                px=xx+0.5
                a=((y1-y2)*(px-x2)+(x2-x1)*(py-y2))/denom
                b=((y2-y0)*(px-x2)+(x0-x2)*(py-y2))/denom
                c=1.0-a-b
                if a < -1e-5 or b < -1e-5 or c < -1e-5:
                    continue

                depth=a*z0+b*z1+c*z2
                if depth <= zbuf[yy,xx]:
                    continue

                uu=a*u0+b*u1+c*u2
                vv=a*v0+b*v1+c*v2
                tx=uu*(tex_w-1)
                ty=(1.0-vv)*(tex_h-1)

                if tx<0.0:
                    tx=0.0
                elif tx>tex_w-1:
                    tx=tex_w-1.0
                if ty<0.0:
                    ty=0.0
                elif ty>tex_h-1:
                    ty=tex_h-1.0

                xlo=int(tx)
                ylo=int(ty)
                xhi=min(xlo+1,tex_w-1)
                yhi=min(ylo+1,tex_h-1)
                fx=tx-xlo
                fy=ty-ylo

                for channel in range(3):
                    top=(1.0-fx)*texture[ylo,xlo,channel]+fx*texture[ylo,xhi,channel]
                    bottom=(1.0-fx)*texture[yhi,xlo,channel]+fx*texture[yhi,xhi,channel]
                    value=(1.0-fy)*top+fy*bottom
                    rgb[yy,xx,channel]=np.uint8(
                        min(255,max(0,int(value+0.5)))
                    )
                zbuf[yy,xx]=depth


def _texture_payload(geometry):
    visual=getattr(geometry,"visual",None)
    uv=getattr(visual,"uv",None)
    material=getattr(visual,"material",None)
    texture=getattr(material,"baseColorTexture",None) if material is not None else None
    if uv is None or texture is None:
        return None
    uv=np.asarray(uv,dtype=np.float32)
    vertices=np.asarray(geometry.vertices,dtype=np.float32)
    if len(uv)!=len(vertices):
        return None
    return (
        vertices,
        np.asarray(geometry.faces,dtype=np.int32),
        uv,
        np.asarray(texture.convert("RGB"),dtype=np.uint8),
    )


def _load_scene(path:Path):
    scene=trimesh.load(path,force="scene",process=False)
    geometries=[
        geometry
        for geometry in scene.geometry.values()
        if hasattr(geometry,"vertices")
        and hasattr(geometry,"faces")
        and len(geometry.vertices)
        and len(geometry.faces)
    ]
    if not geometries:
        raise RuntimeError(f"no renderable geometry in {path}")
    vertices=np.concatenate(
        [np.asarray(g.vertices,dtype=np.float32) for g in geometries],
        axis=0,
    )
    return geometries,vertices


def _render_point_fallback(geometries,size:int):
    chunks=[]
    colors=[]
    for geometry in geometries:
        vertices=np.asarray(geometry.vertices,dtype=np.float64)
        visual=getattr(geometry,"visual",None)
        vertex_colors=getattr(visual,"vertex_colors",None)
        if vertex_colors is not None and len(vertex_colors)==len(vertices):
            color=np.asarray(vertex_colors,dtype=np.uint8)[:,:3]
        else:
            color=np.tile(
                np.array([[165,165,165]],dtype=np.uint8),
                (len(vertices),1),
            )
        chunks.append(vertices)
        colors.append(color)

    vertices=np.concatenate(chunks,axis=0)
    colors=np.concatenate(colors,axis=0)
    lo=vertices.min(axis=0)
    hi=vertices.max(axis=0)

    edge=int(size)
    span=max(float(hi[0]-lo[0]),float(hi[1]-lo[1]))*1.08
    cx=float((lo[0]+hi[0])*0.5)
    cy=float((lo[1]+hi[1])*0.5)
    xmin=cx-span*0.5
    xmax=cx+span*0.5
    ymin=cy-span*0.5
    ymax=cy+span*0.5

    px=np.rint((vertices[:,0]-xmin)/max(xmax-xmin,1e-9)*(edge-1)).astype(np.int32)
    py=np.rint((ymax-vertices[:,1])/max(ymax-ymin,1e-9)*(edge-1)).astype(np.int32)
    valid=(px>=0)&(px<edge)&(py>=0)&(py<edge)
    px=px[valid]
    py=py[valid]
    depth=vertices[valid,2]
    color=colors[valid]

    zbuf=np.full((edge,edge),-np.inf,dtype=np.float64)
    rgb=np.full((edge,edge,3),18,dtype=np.uint8)
    for oy in (-2,-1,0,1,2):
        for ox in (-2,-1,0,1,2):
            xx=px+ox
            yy=py+oy
            keep=(xx>=0)&(xx<edge)&(yy>=0)&(yy<edge)
            xx=xx[keep]
            yy=yy[keep]
            zz=depth[keep]
            cc=color[keep]
            flat=yy*edge+xx
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

    return Image.fromarray(rgb,"RGB"),lo,hi


def _render_uv_region(
    geometries,
    bounds,
    output_size:int,
    supersample:int,
):
    render_size=max(int(output_size),int(output_size)*max(1,int(supersample)))
    zbuf=np.full((render_size,render_size),-1e9,dtype=np.float32)
    rgb=np.full((render_size,render_size,3),18,dtype=np.uint8)
    xmin,xmax,ymin,ymax=[float(v) for v in bounds]

    textured=0
    for geometry in geometries:
        payload=_texture_payload(geometry)
        if payload is None:
            continue
        vertices,faces,uv,texture=payload
        _raster_textured(
            vertices,
            faces,
            uv,
            texture,
            zbuf,
            rgb,
            xmin,
            xmax,
            ymin,
            ymax,
        )
        textured+=1

    if textured==0:
        raise RuntimeError("no textured geometry for UV render")

    image=Image.fromarray(rgb,"RGB")
    if render_size!=int(output_size):
        image=image.resize(
            (int(output_size),int(output_size)),
            Image.Resampling.LANCZOS,
        )
    return image


def _full_bounds(vertices):
    lo=vertices.min(axis=0)
    hi=vertices.max(axis=0)
    span=max(float(hi[0]-lo[0]),float(hi[1]-lo[1]))*1.08
    cx=float((lo[0]+hi[0])*0.5)
    cy=float((lo[1]+hi[1])*0.5)
    return (
        cx-span*0.5,
        cx+span*0.5,
        cy-span*0.5,
        cy+span*0.5,
    ),lo,hi


def _head_bounds(geometries,vertices):
    lo=vertices.min(axis=0)
    hi=vertices.max(axis=0)
    center_x=float((lo[0]+hi[0])*0.5)
    y_cut=float(lo[1]+(hi[1]-lo[1])*0.83)
    x_half=float((hi[0]-lo[0])*0.34)

    points=[]
    for geometry in geometries:
        v=np.asarray(geometry.vertices,dtype=np.float32)
        f=np.asarray(geometry.faces,dtype=np.int32)
        centroids=v[f].mean(axis=1)
        selected=np.flatnonzero(
            (centroids[:,1]>=y_cut)
            & (np.abs(centroids[:,0]-center_x)<=x_half)
        )
        if len(selected):
            points.append(v[f[selected]].reshape(-1,3))

    if not points:
        raise RuntimeError("no head-region geometry")

    head=np.concatenate(points,axis=0)
    h_lo=head.min(axis=0)
    h_hi=head.max(axis=0)
    span=max(float(h_hi[0]-h_lo[0]),float(h_hi[1]-h_lo[1]))*1.12
    cx=float((h_lo[0]+h_hi[0])*0.5)
    cy=float((h_lo[1]+h_hi[1])*0.5)
    return (
        cx-span*0.5,
        cx+span*0.5,
        cy-span*0.5,
        cy+span*0.5,
    )


def render_preview(
    input_glb:Path,
    output_dir:Path,
    size:int=768,
    face_size:int=768,
    supersample:int=2,
):
    geometries,vertices=_load_scene(input_glb)
    full_bounds,lo,hi=_full_bounds(vertices)
    textured=sum(_texture_payload(g) is not None for g in geometries)

    if textured:
        full=_render_uv_region(
            geometries,
            full_bounds,
            int(size),
            int(supersample),
        )
        face=_render_uv_region(
            geometries,
            _head_bounds(geometries,vertices),
            int(face_size),
            int(supersample),
        )
        renderer="hayuya-cpu-uv-bilinear-zbuffer-ss2-v2"
    else:
        full,_,_=_render_point_fallback(geometries,int(size))
        face=full.crop(
            (
                int(full.width*0.22),
                0,
                int(full.width*0.78),
                int(full.height*0.46),
            )
        ).resize(
            (int(face_size),int(face_size)),
            Image.Resampling.LANCZOS,
        )
        renderer="hayuya-cpu-vertex-evidence-fallback-v1"

    turntable=output_dir/"turntable"
    faces=output_dir/"faces"
    turntable.mkdir(parents=True,exist_ok=True)
    faces.mkdir(parents=True,exist_ok=True)
    full_path=turntable/"12_180.png"
    face_path=faces/"12_180.png"
    full.save(full_path)
    face.save(face_path)

    payload={
        "schema":2,
        "renderer":renderer,
        "source":str(input_glb),
        "front_convention":"+Z raw Hunyuan coordinates; filename retained as 12_180 for Judge compatibility",
        "supersample":int(supersample),
        "textured_geometries":int(textured),
        "vertices":int(len(vertices)),
        "bounds":{
            "min":[float(x) for x in lo],
            "max":[float(x) for x in hi],
        },
        "turntable":[str(full_path)],
        "faces":[str(face_path)],
        "preflight_only":True,
    }
    (output_dir/"software_manifest.json").write_text(
        json.dumps(payload,indent=2)+"\n",
        encoding="utf-8",
    )
    print(
        "HAYUYA_SOFTWARE_FRONT_PASS",
        json.dumps(payload,separators=(",",":")),
    )
    return payload


def main():
    p=argparse.ArgumentParser(
        description="HAYUYA CPU GLB evidence renderer with real UV filtering."
    )
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--size",type=int,default=768)
    p.add_argument("--face-size",type=int,default=768)
    p.add_argument("--supersample",type=int,default=2)
    a=p.parse_args()
    render_preview(
        a.input,
        a.output_dir,
        a.size,
        a.face_size,
        a.supersample,
    )


if __name__=="__main__":
    main()
