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

                if texture.shape[2] >= 4:
                    atop=(1.0-fx)*texture[ylo,xlo,3]+fx*texture[ylo,xhi,3]
                    abottom=(1.0-fx)*texture[yhi,xlo,3]+fx*texture[yhi,xhi,3]
                    alpha=(1.0-fy)*atop+fy*abottom
                    if alpha < 20.0:
                        continue

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
        np.asarray(texture.convert("RGBA"),dtype=np.uint8),
    )


def _load_scene(path:Path):
    scene=trimesh.load(path,force="scene",process=False)
    geometries=[]
    source_visible_front=[]
    occluded_support=[]

    # Preserve node identity so the evidence renderer can distinguish the
    # intentionally front-visible projection shell from occluded support
    # geometry. Apply scene transforms before rasterization.
    nodes=list(scene.graph.nodes_geometry)
    if nodes:
        for node in nodes:
            transform,geometry_name=scene.graph.get(node)
            geometry=scene.geometry[geometry_name].copy()
            if not (
                hasattr(geometry,"vertices")
                and hasattr(geometry,"faces")
                and len(geometry.vertices)
                and len(geometry.faces)
            ):
                continue
            if not np.allclose(transform,np.eye(4),atol=1e-7):
                geometry.apply_transform(transform)
            geometries.append(geometry)
            node_name=str(node)
            if node_name=="source_visible_front":
                source_visible_front.append(geometry)
            elif node_name=="occluded_low_frequency":
                occluded_support.append(geometry)
    else:
        geometries=[
            geometry.copy()
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
    return geometries,vertices,source_visible_front,occluded_support


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
    span=max(float(hi[0]-lo[0]),float(hi[1]-lo[1]))*1.40
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

    mask=Image.fromarray((zbuf>-np.inf).astype(np.uint8)*255,"L")
    return Image.fromarray(rgb,"RGB"),mask,lo,hi


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

    mask=(zbuf>-1e8).astype(np.uint8)*255
    image=Image.fromarray(rgb,"RGB")
    mask_image=Image.fromarray(mask,"L")
    if render_size!=int(output_size):
        image=image.resize(
            (int(output_size),int(output_size)),
            Image.Resampling.LANCZOS,
        )
        mask_image=mask_image.resize(
            (int(output_size),int(output_size)),
            Image.Resampling.NEAREST,
        )
    return image,mask_image


def _clamp_to_front_silhouette(
    image:Image.Image,
    rendered_mask:Image.Image,
    front_mask:Image.Image,
    *,
    dilation_pixels:int,
    rescue_pixels:int,
):
    from scipy.ndimage import (
        binary_dilation,
        binary_fill_holes,
        distance_transform_edt,
        label,
    )

    rendered=np.asarray(rendered_mask,dtype=np.uint8)>0
    front=np.asarray(front_mask,dtype=np.uint8)>0
    if not np.any(front):
        raise RuntimeError("source_visible_front silhouette mask was empty")

    # Core support kills the large hidden-geometry halo.
    core=binary_fill_holes(front)
    iterations=max(1,int(dilation_pixels))
    support=binary_dilation(core,iterations=iterations)

    # Thin-detail rescue: only consider rendered pixels very close to the true
    # source-alpha silhouette. Then rescue SMALL connected fringe components
    # (fingers, cloth tatters, hood tips) while rejecting the large secondary
    # silhouette lobes that caused #32-#34.
    rescue_radius=max(iterations+1,int(rescue_pixels))
    distance=distance_transform_edt(~front)

    # Proximity-band rescue: area is NOT a rejection criterion anymore.
    # Long cloth tatters or a whole finger can be a large connected component
    # while still being legitimate. The guard is geometric instead: only
    # rendered pixels within a narrow distance band around the true source
    # alpha silhouette are eligible. The old large secondary halo extends far
    # beyond this band and therefore remains rejected.
    rescued=rendered & ~support & (distance<=float(rescue_radius))
    labels,count=label(rescued)

    front_pixels=int(np.count_nonzero(front))
    rescued_component_pixels=[]
    for component_id in range(1,int(count)+1):
        area=int(np.count_nonzero(labels==component_id))
        if area:
            rescued_component_pixels.append(area)

    keep=rendered & (support|rescued)
    removed=rendered & ~keep

    arr=np.asarray(image.convert("RGB"),dtype=np.uint8).copy()
    arr[~keep]=np.array([18,18,18],dtype=np.uint8)
    out_mask=Image.fromarray(keep.astype(np.uint8)*255,"L")
    return Image.fromarray(arr,"RGB"),out_mask,{
        "front_pixels":front_pixels,
        "rendered_pixels":int(np.count_nonzero(rendered)),
        "kept_pixels":int(np.count_nonzero(keep)),
        "dilation_pixels":int(iterations),
        "rescue_pixels":int(rescue_radius),
        "rescue_policy":"strict_source_alpha_proximity_band",
        "rescued_pixels":int(np.count_nonzero(rescued)),
        "rescued_components":int(len(rescued_component_pixels)),
        "largest_rescued_component":int(max(rescued_component_pixels) if rescued_component_pixels else 0),
        "removed_pixels":int(np.count_nonzero(removed)),
    }


def _source_planar_layer(
    source_visible_front,
    bounds,
    output_size:int,
    *,
    alpha_threshold:int=128,
):
    best=None
    for geometry in source_visible_front:
        payload=_texture_payload(geometry)
        if payload is None:
            continue
        vertices,_,uv,texture=payload
        if texture.shape[2] < 4 or len(vertices) < 8:
            continue
        if best is None or len(vertices)>len(best[0]):
            best=(vertices,uv,texture)

    if best is None:
        raise RuntimeError("source_visible_front has no RGBA texture payload")

    vertices,uv,texture=best
    x=np.asarray(vertices[:,0],dtype=np.float64)
    y=np.asarray(vertices[:,1],dtype=np.float64)
    u=np.asarray(uv[:,0],dtype=np.float64)
    v=np.asarray(uv[:,1],dtype=np.float64)

    ax,bx=np.linalg.lstsq(
        np.stack([x,np.ones_like(x)],axis=1),u,rcond=None
    )[0]
    ay,by=np.linalg.lstsq(
        np.stack([y,np.ones_like(y)],axis=1),v,rcond=None
    )[0]
    u_rmse=float(np.sqrt(np.mean((u-(ax*x+bx))**2)))
    v_rmse=float(np.sqrt(np.mean((v-(ay*y+by))**2)))
    if not np.isfinite(u_rmse+v_rmse) or u_rmse>0.01 or v_rmse>0.01:
        raise RuntimeError(
            f"source UV mapping is not planar enough: "
            f"u_rmse={u_rmse} v_rmse={v_rmse}"
        )

    size=int(output_size)
    xmin,xmax,ymin,ymax=[float(q) for q in bounds]
    world_x=np.linspace(xmin,xmax,size,dtype=np.float64)
    world_y=np.linspace(ymax,ymin,size,dtype=np.float64)
    uu=ax*world_x+bx
    vv=ay*world_y+by

    th,tw,_=texture.shape
    tx=np.clip(uu*(tw-1),0.0,tw-1.0)
    ty=np.clip((1.0-vv)*(th-1),0.0,th-1.0)
    x0=np.floor(tx).astype(np.int32)
    y0=np.floor(ty).astype(np.int32)
    x1=np.minimum(x0+1,tw-1)
    y1=np.minimum(y0+1,th-1)
    fx=(tx-x0).astype(np.float32)
    fy=(ty-y0).astype(np.float32)

    sampled=np.empty((size,size,4),dtype=np.float32)
    for channel in range(4):
        plane=np.asarray(texture[:,:,channel],dtype=np.float32)
        p00=plane[np.ix_(y0,x0)]
        p01=plane[np.ix_(y0,x1)]
        p10=plane[np.ix_(y1,x0)]
        p11=plane[np.ix_(y1,x1)]
        top=p00*(1.0-fx[None,:])+p01*fx[None,:]
        bottom=p10*(1.0-fx[None,:])+p11*fx[None,:]
        sampled[:,:,channel]=top*(1.0-fy[:,None])+bottom*fy[:,None]

    valid_u=(uu>=0.0)&(uu<=1.0)
    valid_v=(vv>=0.0)&(vv<=1.0)
    valid=valid_v[:,None]&valid_u[None,:]
    outline=valid&(sampled[:,:,3]>=float(alpha_threshold))
    rgb=np.clip(sampled[:,:,:3],0,255).astype(np.uint8)
    rgb[~outline]=np.array([18,18,18],dtype=np.uint8)

    return (
        Image.fromarray(outline.astype(np.uint8)*255,"L"),
        Image.fromarray(rgb,"RGB"),
        {
            "policy":"hard_source_alpha_screen_space",
            "alpha_threshold":int(alpha_threshold),
            "u_fit":[float(ax),float(bx)],
            "v_fit":[float(ay),float(by)],
            "u_rmse":u_rmse,
            "v_rmse":v_rmse,
            "outline_pixels":int(np.count_nonzero(outline)),
            "texture_size":[int(tw),int(th)],
        },
    )

def _hard_clip_to_outline(
    image:Image.Image,
    rendered_mask:Image.Image,
    outline_mask:Image.Image,
):
    rendered=np.asarray(rendered_mask,dtype=np.uint8)>0
    outline=np.asarray(outline_mask,dtype=np.uint8)>0
    if not np.any(outline):
        raise RuntimeError("hard source-alpha outline mask was empty")

    keep=rendered&outline
    outside=rendered&~outline
    missing=outline&~rendered

    arr=np.asarray(image.convert("RGB"),dtype=np.uint8).copy()
    arr[~keep]=np.array([18,18,18],dtype=np.uint8)
    out_mask=Image.fromarray(keep.astype(np.uint8)*255,"L")
    outline_pixels=int(np.count_nonzero(outline))
    kept_pixels=int(np.count_nonzero(keep))
    return Image.fromarray(arr,"RGB"),out_mask,{
        "policy":"hard_source_alpha_screen_space",
        "outline_pixels":outline_pixels,
        "rendered_pixels":int(np.count_nonzero(rendered)),
        "kept_pixels":kept_pixels,
        "removed_outside_outline":int(np.count_nonzero(outside)),
        "missing_inside_outline":int(np.count_nonzero(missing)),
        "outline_coverage":float(kept_pixels/max(outline_pixels,1)),
    }


def _compose_front_priority(
    front_image:Image.Image,
    front_mask:Image.Image,
    support_mask:Image.Image,
    outline_mask:Image.Image,
    source_rgb:Image.Image,
    *,
    edge_fill_pixels:int,
):
    from scipy.ndimage import distance_transform_edt

    front=np.asarray(front_mask,dtype=np.uint8)>0
    support=np.asarray(support_mask,dtype=np.uint8)>0
    outline=np.asarray(outline_mask,dtype=np.uint8)>0
    if not np.any(outline):
        raise RuntimeError("source outline mask was empty")

    front_keep=front&outline
    support_fill=support&outline&~front_keep
    keep=front_keep|support_fill

    # Recover only a narrow border strip that is INSIDE the authoritative
    # source outline and adjacent to real rendered geometry. This is for the
    # hand/hood shaving seen in #39; it can never create pixels outside outline.
    missing=outline&~keep
    dist_to_keep=distance_transform_edt(~keep)
    edge_fill=missing&(dist_to_keep<=float(max(1,int(edge_fill_pixels))))
    keep2=keep|edge_fill
    missing2=outline&~keep2

    front_rgb=np.asarray(front_image.convert("RGB"),dtype=np.uint8)
    projected_rgb=np.asarray(source_rgb.convert("RGB"),dtype=np.uint8)
    out=np.full_like(front_rgb,18,dtype=np.uint8)

    # Support and edge repair use the SAME projected source colors as the front
    # so material partition boundaries cannot show up as dark seam loops.
    out[support_fill]=projected_rgb[support_fill]
    out[edge_fill]=projected_rgb[edge_fill]
    out[front_keep]=front_rgb[front_keep]

    out_mask=Image.fromarray(keep2.astype(np.uint8)*255,"L")
    outline_pixels=int(np.count_nonzero(outline))
    return Image.fromarray(out,"RGB"),out_mask,{
        "policy":"front_priority_source_color_fill",
        "outline_pixels":outline_pixels,
        "front_pixels":int(np.count_nonzero(front_keep)),
        "support_fill_pixels":int(np.count_nonzero(support_fill)),
        "edge_fill_pixels":int(np.count_nonzero(edge_fill)),
        "edge_fill_radius":int(max(1,int(edge_fill_pixels))),
        "kept_pixels":int(np.count_nonzero(keep2)),
        "missing_inside_outline":int(np.count_nonzero(missing2)),
        "outline_coverage":float(np.count_nonzero(keep2)/max(outline_pixels,1)),
        "hidden_over_front_pixels_forbidden":int(np.count_nonzero(support&front_keep)),
    }

def _mask_edge_contact(mask:Image.Image,margin:int=4):
    arr=np.asarray(mask,dtype=np.uint8)>0
    if not np.any(arr):
        return {
            "any":False,
            "top":False,
            "bottom":False,
            "left":False,
            "right":False,
            "margin":int(margin),
        }
    m=max(1,int(margin))
    result={
        "top":bool(np.any(arr[:m,:])),
        "bottom":bool(np.any(arr[-m:,:])),
        "left":bool(np.any(arr[:,:m])),
        "right":bool(np.any(arr[:,-m:])),
        "margin":int(m),
    }
    result["any"]=bool(
        result["top"] or result["bottom"] or result["left"] or result["right"]
    )
    return result


def _expand_bounds(bounds,factor:float):
    xmin,xmax,ymin,ymax=[float(v) for v in bounds]
    cx=(xmin+xmax)*0.5
    cy=(ymin+ymax)*0.5
    width=(xmax-xmin)*float(factor)
    height=(ymax-ymin)*float(factor)
    return (
        cx-width*0.5,
        cx+width*0.5,
        cy-height*0.5,
        cy+height*0.5,
    )


def _render_uv_with_edge_retry(
    geometries,
    bounds,
    output_size:int,
    supersample:int,
    *,
    max_retries:int=2,
):
    active_bounds=tuple(float(v) for v in bounds)
    attempts=[]
    for attempt in range(max(0,int(max_retries))+1):
        image,mask=_render_uv_region(
            geometries,
            active_bounds,
            int(output_size),
            int(supersample),
        )
        contact=_mask_edge_contact(
            mask,
            margin=max(3,int(round(int(output_size)*0.006))),
        )
        attempts.append({
            "attempt":int(attempt),
            "bounds":[float(v) for v in active_bounds],
            "edge_contact":contact,
        })
        if not contact["any"]:
            return image,mask,active_bounds,attempts
        active_bounds=_expand_bounds(active_bounds,1.18)
    return image,mask,active_bounds,attempts


def _full_bounds(vertices):
    lo=vertices.min(axis=0)
    hi=vertices.max(axis=0)
    span=max(float(hi[0]-lo[0]),float(hi[1]-lo[1]))*1.42
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
    span=max(float(h_hi[0]-h_lo[0]),float(h_hi[1]-h_lo[1]))*1.95
    cx=float((h_lo[0]+h_hi[0])*0.5)
    cy=float((h_lo[1]+h_hi[1])*0.5)
    return (
        cx-span*0.5,
        cx+span*0.5,
        cy-span*0.5,
        cy+span*0.5,
    )


def _normalize_visible_to_canvas(
    image:Image.Image,
    mask:Image.Image,
    out_size:int,
    pad_fraction:float,
):
    mask_array=np.asarray(mask,dtype=np.uint8)
    ys,xs=np.where(mask_array>0)
    if len(xs)==0:
        raise RuntimeError("visible mask was empty")

    x0=int(xs.min())
    x1=int(xs.max())+1
    y0=int(ys.min())
    y1=int(ys.max())+1

    width=max(1,x1-x0)
    height=max(1,y1-y0)
    pad_x=max(2,int(round(width*float(pad_fraction))))
    pad_y=max(2,int(round(height*float(pad_fraction))))

    x0=max(0,x0-pad_x)
    x1=min(image.width,x1+pad_x)
    y0=max(0,y0-pad_y)
    y1=min(image.height,y1+pad_y)

    crop=image.crop((x0,y0,x1,y1))
    crop_mask=mask.crop((x0,y0,x1,y1))
    side=max(crop.width,crop.height)

    canvas=Image.new("RGB",(side,side),(18,18,18))
    canvas_mask=Image.new("L",(side,side),0)
    ox=(side-crop.width)//2
    oy=(side-crop.height)//2
    canvas.paste(crop,(ox,oy))
    canvas_mask.paste(crop_mask,(ox,oy))

    out=canvas.resize(
        (int(out_size),int(out_size)),
        Image.Resampling.LANCZOS,
    )
    out_mask=canvas_mask.resize(
        (int(out_size),int(out_size)),
        Image.Resampling.NEAREST,
    )
    return out,out_mask,{
        "source_bbox":[x0,y0,x1,y1],
        "source_content_size":[width,height],
        "pad_fraction":float(pad_fraction),
        "canvas_side":int(side),
    }


def render_preview(
    input_glb:Path,
    output_dir:Path,
    size:int=768,
    face_size:int=768,
    supersample:int=2,
):
    geometries,vertices,source_visible_front,occluded_support=_load_scene(input_glb)
    full_bounds,lo,hi=_full_bounds(vertices)
    textured=sum(_texture_payload(g) is not None for g in geometries)

    if textured:
        head_bounds=_head_bounds(geometries,vertices)

        # Use the all-geometry render ONLY to determine safe framing. Final
        # pixels are composited from front and hidden-support layers separately
        # so hidden geometry can never draw over the authored visible front.
        _,_,full_bounds_used,full_edge_attempts=_render_uv_with_edge_retry(
            geometries,
            full_bounds,
            int(size),
            int(supersample),
            max_retries=2,
        )
        head_bounds_used=head_bounds

        silhouette_clamp=None
        if source_visible_front:
            full_outline,full_source_rgb,full_outline_map=_source_planar_layer(
                source_visible_front,
                full_bounds_used,
                int(size),
                alpha_threshold=128,
            )
            face_outline,face_source_rgb,face_outline_map=_source_planar_layer(
                source_visible_front,
                head_bounds_used,
                int(face_size),
                alpha_threshold=128,
            )

            front_full,front_full_mask=_render_uv_region(
                source_visible_front,
                full_bounds_used,
                int(size),
                int(supersample),
            )
            front_face,front_face_mask=_render_uv_region(
                source_visible_front,
                head_bounds_used,
                int(face_size),
                int(supersample),
            )

            if occluded_support:
                _,support_full_mask=_render_uv_region(
                    occluded_support,
                    full_bounds_used,
                    int(size),
                    int(supersample),
                )
                _,support_face_mask=_render_uv_region(
                    occluded_support,
                    head_bounds_used,
                    int(face_size),
                    int(supersample),
                )
            else:
                support_full_mask=Image.new("L",(int(size),int(size)),0)
                support_face_mask=Image.new("L",(int(face_size),int(face_size)),0)

            full_raw,full_mask_raw,full_clamp=_compose_front_priority(
                front_full,
                front_full_mask,
                support_full_mask,
                full_outline,
                full_source_rgb,
                edge_fill_pixels=max(2,int(round(int(size)*0.004))),
            )
            face_raw,face_mask_raw,face_clamp=_compose_front_priority(
                front_face,
                front_face_mask,
                support_face_mask,
                face_outline,
                face_source_rgb,
                edge_fill_pixels=max(2,int(round(int(face_size)*0.004))),
            )

            face_edge_attempts=[{
                "attempt":0,
                "bounds":[float(v) for v in head_bounds_used],
                "edge_contact":_mask_edge_contact(
                    face_mask_raw,
                    margin=max(3,int(round(int(face_size)*0.006))),
                ),
                "retry_disabled_reason":"face evidence intentionally crops lower torso; bottom contact is not a head-clipping signal",
            }]

            silhouette_clamp={
                "enabled":True,
                "source_node":"source_visible_front",
                "support_node":"occluded_low_frequency",
                "policy":"front_priority_source_color_fill",
                "full":full_clamp,
                "face":face_clamp,
                "outline_mapping":{
                    "full":full_outline_map,
                    "face":face_outline_map,
                },
                "edge_retry":{
                    "full":full_edge_attempts,
                    "face":face_edge_attempts,
                },
            }
        else:
            full_raw,full_mask_raw=_render_uv_region(
                geometries,
                full_bounds_used,
                int(size),
                int(supersample),
            )
            face_raw,face_mask_raw=_render_uv_region(
                geometries,
                head_bounds_used,
                int(face_size),
                int(supersample),
            )
            face_edge_attempts=[]
            silhouette_clamp={
                "enabled":False,
                "reason":"source_visible_front node not present",
            }

        full,full_mask,full_fit=_normalize_visible_to_canvas(
            full_raw,
            full_mask_raw,
            int(size),
            0.12,
        )
        face,face_mask,face_fit=_normalize_visible_to_canvas(
            face_raw,
            face_mask_raw,
            int(face_size),
            0.10,
        )
        renderer="hayuya-cpu-uv-source-color-seamless-fill-ss2-v10"
    else:
        silhouette_clamp={
            "enabled":False,
            "reason":"untextured evidence fallback",
        }
        full_raw,full_mask_raw,_,_=_render_point_fallback(
            geometries,
            int(size),
        )
        full,full_mask,full_fit=_normalize_visible_to_canvas(
            full_raw,
            full_mask_raw,
            int(size),
            0.12,
        )
        face_box=(
            int(full_raw.width*0.20),
            0,
            int(full_raw.width*0.80),
            int(full_raw.height*0.48),
        )
        face_raw=full_raw.crop(face_box)
        face_mask_raw=full_mask_raw.crop(face_box)
        face,face_mask,face_fit=_normalize_visible_to_canvas(
            face_raw,
            face_mask_raw,
            int(face_size),
            0.10,
        )
        renderer="hayuya-cpu-vertex-evidence-autofit-v2"

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
        "auto_fit":{
            "full":full_fit,
            "face":face_fit,
        },
        "safe_padding":{
            "full":0.12,
            "face":0.10,
        },
        "silhouette_source":"hard_source_alpha_front_priority" if silhouette_clamp.get("enabled") else "renderer_zbuffer_visibility_mask",
        "silhouette_clamp":silhouette_clamp,
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
