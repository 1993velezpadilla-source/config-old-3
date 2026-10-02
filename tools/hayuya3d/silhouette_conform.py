#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, label


FRONT_NODE="source_visible_front"
SUPPORT_NODE="occluded_low_frequency"


def _load_scene(path:Path):
    import trimesh
    scene=trimesh.load(path,force="scene",process=False)
    if FRONT_NODE not in scene.graph.nodes_geometry:
        raise RuntimeError(f"{FRONT_NODE} node missing")
    if SUPPORT_NODE not in scene.graph.nodes_geometry:
        raise RuntimeError(f"{SUPPORT_NODE} node missing")
    for node in (FRONT_NODE,SUPPORT_NODE):
        transform,_=scene.graph.get(node)
        if not np.allclose(transform,np.eye(4),atol=1e-7):
            raise RuntimeError(f"non-identity transform on {node}")
    return scene


def _geometry(scene,node:str):
    _,geometry_name=scene.graph.get(node)
    return scene.geometry[geometry_name]


def _bounds(scene,overscan:float):
    vertices=np.concatenate([
        np.asarray(_geometry(scene,FRONT_NODE).vertices,dtype=np.float64),
        np.asarray(_geometry(scene,SUPPORT_NODE).vertices,dtype=np.float64),
    ],axis=0)
    lo=vertices.min(axis=0)
    hi=vertices.max(axis=0)
    extent=hi-lo
    span=max(float(extent[0]),float(extent[1]))*float(overscan)
    cx=float((lo[0]+hi[0])*0.5)
    cy=float((lo[1]+hi[1])*0.5)
    return (
        cx-span*0.5,
        cx+span*0.5,
        cy-span*0.5,
        cy+span*0.5,
    ),lo,hi


def _rasterize(geometry,bounds,grid:int):
    vertices=np.asarray(geometry.vertices,dtype=np.float64)
    faces=np.asarray(geometry.faces,dtype=np.int64)
    xmin,xmax,ymin,ymax=[float(x) for x in bounds]
    px=(vertices[:,0]-xmin)/max(xmax-xmin,1e-12)*(int(grid)-1)
    py=(ymax-vertices[:,1])/max(ymax-ymin,1e-12)*(int(grid)-1)
    points=np.stack([px,py],axis=1)
    image=Image.new("1",(int(grid),int(grid)),0)
    draw=ImageDraw.Draw(image)
    for tri in points[faces]:
        draw.polygon(
            [tuple(map(float,p)) for p in tri],
            fill=1,
        )
    return np.asarray(image,dtype=bool)


def _source_outline(front_geometry,bounds,grid:int,alpha_threshold:int):
    material=getattr(front_geometry.visual,"material",None)
    texture=getattr(material,"baseColorTexture",None)
    if texture is None:
        raise RuntimeError("front material has no baseColorTexture")
    rgba=np.asarray(texture.convert("RGBA"),dtype=np.uint8)
    alpha=rgba[:,:,3].astype(np.float32)

    vertices=np.asarray(front_geometry.vertices,dtype=np.float64)
    uv=np.asarray(front_geometry.visual.uv,dtype=np.float64)
    if len(uv)!=len(vertices):
        raise RuntimeError("front UV/vertex count mismatch")

    x=vertices[:,0]
    y=vertices[:,1]
    ax,bx=np.linalg.lstsq(
        np.stack([x,np.ones_like(x)],axis=1),
        uv[:,0],
        rcond=None,
    )[0]
    ay,by=np.linalg.lstsq(
        np.stack([y,np.ones_like(y)],axis=1),
        uv[:,1],
        rcond=None,
    )[0]
    u_rmse=float(np.sqrt(np.mean((uv[:,0]-(ax*x+bx))**2)))
    v_rmse=float(np.sqrt(np.mean((uv[:,1]-(ay*y+by))**2)))
    if u_rmse>0.01 or v_rmse>0.01:
        raise RuntimeError(
            f"front UV mapping not planar enough: u_rmse={u_rmse} v_rmse={v_rmse}"
        )

    xmin,xmax,ymin,ymax=[float(q) for q in bounds]
    world_x=np.linspace(xmin,xmax,int(grid),dtype=np.float64)
    world_y=np.linspace(ymax,ymin,int(grid),dtype=np.float64)
    uu=ax*world_x+bx
    vv=ay*world_y+by

    th,tw=alpha.shape
    tx=np.clip(uu*(tw-1),0.0,tw-1.0)
    ty=np.clip((1.0-vv)*(th-1),0.0,th-1.0)
    x0=np.floor(tx).astype(np.int32)
    y0=np.floor(ty).astype(np.int32)
    x1=np.minimum(x0+1,tw-1)
    y1=np.minimum(y0+1,th-1)
    fx=(tx-x0).astype(np.float32)
    fy=(ty-y0).astype(np.float32)

    a00=alpha[np.ix_(y0,x0)]
    a01=alpha[np.ix_(y0,x1)]
    a10=alpha[np.ix_(y1,x0)]
    a11=alpha[np.ix_(y1,x1)]
    top=a00*(1.0-fx[None,:])+a01*fx[None,:]
    bottom=a10*(1.0-fx[None,:])+a11*fx[None,:]
    sampled=top*(1.0-fy[:,None])+bottom*fy[:,None]

    valid_u=(uu>=0.0)&(uu<=1.0)
    valid_v=(vv>=0.0)&(vv<=1.0)
    valid=valid_v[:,None]&valid_u[None,:]
    outline=valid&(sampled>=float(alpha_threshold))
    return outline,{
        "alpha_threshold":int(alpha_threshold),
        "u_rmse":u_rmse,
        "v_rmse":v_rmse,
        "outline_pixels":int(np.count_nonzero(outline)),
    }


def _coverage(scene,grid:int,overscan:float,alpha_threshold:int,edge_fill_radius:int):
    front=_geometry(scene,FRONT_NODE)
    support=_geometry(scene,SUPPORT_NODE)
    bounds,lo,hi=_bounds(scene,overscan)
    front_mask=_rasterize(front,bounds,grid)
    support_mask=_rasterize(support,bounds,grid)
    outline,outline_meta=_source_outline(
        front,bounds,grid,alpha_threshold
    )

    front_keep=front_mask&outline
    support_fill=support_mask&outline&~front_keep
    keep=front_keep|support_fill

    distance=distance_transform_edt(~keep)
    edge_fill=(outline&~keep)&(
        distance<=float(max(1,int(edge_fill_radius)))
    )
    keep2=keep|edge_fill
    missing=outline&~keep2
    outline_pixels=max(int(np.count_nonzero(outline)),1)
    return {
        "bounds":bounds,
        "lo":lo,
        "hi":hi,
        "outline":outline,
        "keep":keep2,
        "missing":missing,
        "front_pixels":int(np.count_nonzero(front_keep)),
        "support_fill_pixels":int(np.count_nonzero(support_fill)),
        "edge_fill_pixels":int(np.count_nonzero(edge_fill)),
        "missing_pixels":int(np.count_nonzero(missing)),
        "coverage":float(np.count_nonzero(keep2)/outline_pixels),
        "outline_meta":outline_meta,
    }


def _recompute_planar_uv(scene):
    _,lo,hi=_bounds(scene,1.0)
    du=max(float(hi[0]-lo[0]),1e-12)
    dv=max(float(hi[1]-lo[1]),1e-12)
    for node in (FRONT_NODE,SUPPORT_NODE):
        geometry=_geometry(scene,node)
        vertices=np.asarray(geometry.vertices,dtype=np.float64)
        uv=np.stack([
            np.clip((vertices[:,0]-lo[0])/du,0.0,1.0),
            np.clip((vertices[:,1]-lo[1])/dv,0.0,1.0),
        ],axis=1)
        geometry.visual.uv=uv


def _conform_iteration(
    scene,
    *,
    grid:int,
    overscan:float,
    alpha_threshold:int,
    edge_fill_radius:int,
    min_component_area:int,
    max_component_distance:float,
    per_component_cap_px:float,
    per_iteration_cap_px:float,
):
    state=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )
    missing=state["missing"]
    keep=state["keep"]
    bounds=state["bounds"]

    distance,indices=distance_transform_edt(
        ~keep,
        return_indices=True,
    )
    labels,count=label(missing)
    components=[]
    for component_id in range(1,int(count)+1):
        ys,xs=np.where(labels==component_id)
        area=int(len(xs))
        if area<int(min_component_area):
            continue
        values=distance[ys,xs]
        index=int(np.argmax(values))
        target_y=int(ys[index])
        target_x=int(xs[index])
        nearest_y=int(indices[0,target_y,target_x])
        nearest_x=int(indices[1,target_y,target_x])
        max_distance=float(values[index])
        if max_distance>float(max_component_distance):
            continue
        components.append({
            "area":area,
            "max_distance_px":max_distance,
            "target":[target_x,target_y],
            "anchor":[nearest_x,nearest_y],
        })

    xmin,xmax,ymin,ymax=[float(x) for x in bounds]
    moved_vertices=0
    max_iteration_world=0.0
    for node in (FRONT_NODE,SUPPORT_NODE):
        geometry=_geometry(scene,node)
        vertices=np.asarray(geometry.vertices,dtype=np.float64).copy()
        px=(vertices[:,0]-xmin)/max(xmax-xmin,1e-12)*(int(grid)-1)
        py=(ymax-vertices[:,1])/max(ymax-ymin,1e-12)*(int(grid)-1)
        total=np.zeros((len(vertices),2),dtype=np.float64)

        for component in components:
            target_x,target_y=component["target"]
            anchor_x,anchor_y=component["anchor"]
            delta=np.array([
                float(target_x-anchor_x),
                float(target_y-anchor_y),
            ],dtype=np.float64)
            delta_length=max(float(np.linalg.norm(delta)),1e-9)
            max_distance=float(component["max_distance_px"])
            radius=max(10.0,min(28.0,max_distance*2.4))
            sigma=radius*0.48
            radius2=(px-anchor_x)**2+(py-anchor_y)**2
            weight=np.exp(-0.5*radius2/(sigma*sigma))
            weight[radius2>radius*radius]=0.0
            delta*=min(
                1.0,
                float(per_component_cap_px)/delta_length,
            )
            total+=weight[:,None]*delta[None,:]

        magnitude=np.linalg.norm(total,axis=1)
        over=magnitude>float(per_iteration_cap_px)
        if np.any(over):
            total[over]*=(
                float(per_iteration_cap_px)/
                magnitude[over]
            )[:,None]

        dx=total[:,0]/max(int(grid)-1,1)*(xmax-xmin)
        dy=-total[:,1]/max(int(grid)-1,1)*(ymax-ymin)
        displacement=np.sqrt(dx*dx+dy*dy)
        moved_vertices+=int(np.count_nonzero(displacement>1e-7))
        if len(displacement):
            max_iteration_world=max(
                max_iteration_world,
                float(displacement.max()),
            )

        vertices[:,0]+=dx
        vertices[:,1]+=dy
        geometry.vertices=vertices

    _recompute_planar_uv(scene)
    after=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )
    return {
        "before_missing":int(state["missing_pixels"]),
        "after_missing":int(after["missing_pixels"]),
        "before_coverage":float(state["coverage"]),
        "after_coverage":float(after["coverage"]),
        "moved_vertices":int(moved_vertices),
        "max_iteration_world_displacement":float(max_iteration_world),
        "components":components,
    }


def _targeted_extremity_pass(
    scene,
    *,
    grid:int,
    overscan:float,
    alpha_threshold:int,
    edge_fill_radius:int,
):
    state=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )
    missing=state["missing"]
    keep=state["keep"]
    bounds=state["bounds"]

    distance,indices=distance_transform_edt(
        ~keep,
        return_indices=True,
    )
    labels,count=label(missing)
    scale=float(grid)/768.0
    controls=[]
    selected=[]

    for component_id in range(1,int(count)+1):
        ys,xs=np.where(labels==component_id)
        area=int(len(xs))
        if area<20:
            continue

        cx=float(xs.mean())/max(float(grid),1.0)
        cy=float(ys.mean())/max(float(grid),1.0)
        region=None
        if cy<0.24 and cx>0.50:
            region="head_top"
        elif 0.30<=cy<=0.49 and cx<0.47:
            region="thumb_hand"

        if region is None:
            continue

        values=distance[ys,xs]
        max_distance=float(values.max(initial=0.0))
        if max_distance>18.0*scale:
            continue

        order=np.argsort(values)[::-1]
        peaks=[]
        min_sep=(6.0 if region=="thumb_hand" else 5.0)*scale
        max_peaks=3 if region=="thumb_hand" else 2

        for index in order:
            target_x=int(xs[index])
            target_y=int(ys[index])
            if any(
                (target_x-p["target"][0])**2+
                (target_y-p["target"][1])**2 <
                min_sep*min_sep
                for p in peaks
            ):
                continue

            anchor_y=int(indices[0,target_y,target_x])
            anchor_x=int(indices[1,target_y,target_x])
            peak_distance=float(values[index])
            peak={
                "target":[target_x,target_y],
                "anchor":[anchor_x,anchor_y],
                "distance_px":peak_distance,
            }
            peaks.append(peak)
            if len(peaks)>=max_peaks:
                break

        if not peaks:
            continue

        selected.append({
            "region":region,
            "area":area,
            "centroid":[float(xs.mean()),float(ys.mean())],
            "max_distance_px":max_distance,
            "peaks":peaks,
        })

        for peak in peaks:
            target_x,target_y=peak["target"]
            anchor_x,anchor_y=peak["anchor"]
            peak_distance=float(peak["distance_px"])
            if region=="thumb_hand":
                cap=6.0*scale
                radius=max(
                    9.0*scale,
                    min(15.0*scale,peak_distance*1.8),
                )
            else:
                cap=3.5*scale
                radius=max(
                    7.0*scale,
                    min(11.0*scale,peak_distance*1.8),
                )
            controls.append({
                "region":region,
                "target":[target_x,target_y],
                "anchor":[anchor_x,anchor_y],
                "cap_px":float(cap),
                "radius_px":float(radius),
            })

    xmin,xmax,ymin,ymax=[float(x) for x in bounds]
    moved_vertices=0
    max_iteration_world=0.0
    per_iteration_cap=7.0*scale

    for node in (FRONT_NODE,SUPPORT_NODE):
        geometry=_geometry(scene,node)
        vertices=np.asarray(geometry.vertices,dtype=np.float64).copy()
        px=(
            (vertices[:,0]-xmin)/
            max(xmax-xmin,1e-12)*
            (int(grid)-1)
        )
        py=(
            (ymax-vertices[:,1])/
            max(ymax-ymin,1e-12)*
            (int(grid)-1)
        )
        total=np.zeros((len(vertices),2),dtype=np.float64)

        for control in controls:
            target_x,target_y=control["target"]
            anchor_x,anchor_y=control["anchor"]
            delta=np.array([
                float(target_x-anchor_x),
                float(target_y-anchor_y),
            ],dtype=np.float64)
            delta_length=max(float(np.linalg.norm(delta)),1e-9)
            cap=float(control["cap_px"])
            radius=float(control["radius_px"])
            sigma=radius*0.45
            radius2=(px-anchor_x)**2+(py-anchor_y)**2
            weight=np.exp(-0.5*radius2/(sigma*sigma))
            weight[radius2>radius*radius]=0.0
            delta*=min(1.0,cap/delta_length)
            total+=weight[:,None]*delta[None,:]

        magnitude=np.linalg.norm(total,axis=1)
        over=magnitude>per_iteration_cap
        if np.any(over):
            total[over]*=(
                per_iteration_cap/
                magnitude[over]
            )[:,None]

        dx=total[:,0]/max(int(grid)-1,1)*(xmax-xmin)
        dy=-total[:,1]/max(int(grid)-1,1)*(ymax-ymin)
        displacement=np.sqrt(dx*dx+dy*dy)
        moved_vertices+=int(np.count_nonzero(displacement>1e-7))
        if len(displacement):
            max_iteration_world=max(
                max_iteration_world,
                float(displacement.max()),
            )

        vertices[:,0]+=dx
        vertices[:,1]+=dy
        geometry.vertices=vertices

    _recompute_planar_uv(scene)
    after=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )

    return {
        "policy":"targeted-thumb-head-multipeak-v1",
        "before_missing":int(state["missing_pixels"]),
        "after_missing":int(after["missing_pixels"]),
        "before_coverage":float(state["coverage"]),
        "after_coverage":float(after["coverage"]),
        "moved_vertices":int(moved_vertices),
        "max_iteration_world_displacement":float(max_iteration_world),
        "selected_components":selected,
        "controls":controls,
    }


def _residual_thumb_bridge_pass(
    scene,
    *,
    grid:int,
    overscan:float,
    alpha_threshold:int,
    edge_fill_radius:int,
):
    state=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )
    missing=state["missing"]
    keep=state["keep"]
    bounds=state["bounds"]

    distance,indices=distance_transform_edt(
        ~keep,
        return_indices=True,
    )
    labels,count=label(missing)
    scale=float(grid)/768.0
    controls=[]
    selected=[]

    for component_id in range(1,int(count)+1):
        ys,xs=np.where(labels==component_id)
        area=int(len(xs))
        if area<8:
            continue

        cx=float(xs.mean())/max(float(grid),1.0)
        cy=float(ys.mean())/max(float(grid),1.0)
        width=int(xs.max()-xs.min()+1)
        height=int(ys.max()-ys.min()+1)

        region=None
        if (
            0.33<=cx<=0.37
            and 0.35<=cy<=0.42
            and area<=100
            and width<=14
            and height<=24
        ):
            region="thumb_bridge"
        elif (
            0.52<=cx<=0.58
            and cy<0.22
            and area<=110
        ):
            region="head_top_residual"

        if region is None:
            continue

        values=distance[ys,xs]
        index=int(np.argmax(values))
        target_x=int(xs[index])
        target_y=int(ys[index])
        anchor_y=int(indices[0,target_y,target_x])
        anchor_x=int(indices[1,target_y,target_x])
        peak_distance=float(values[index])

        if region=="thumb_bridge":
            if peak_distance>12.0*scale:
                continue
            cap=4.5*scale
            radius=10.5*scale
        else:
            if peak_distance>10.0*scale:
                continue
            cap=2.25*scale
            radius=7.5*scale

        control={
            "region":region,
            "area":area,
            "bbox":[
                int(xs.min()),int(ys.min()),
                int(xs.max()),int(ys.max()),
            ],
            "centroid":[float(xs.mean()),float(ys.mean())],
            "target":[target_x,target_y],
            "anchor":[anchor_x,anchor_y],
            "distance_px":peak_distance,
            "cap_px":float(cap),
            "radius_px":float(radius),
        }
        selected.append(control)
        controls.append(control)

    xmin,xmax,ymin,ymax=[float(x) for x in bounds]
    moved_vertices=0
    max_iteration_world=0.0
    per_iteration_cap=5.0*scale

    for node in (FRONT_NODE,SUPPORT_NODE):
        geometry=_geometry(scene,node)
        vertices=np.asarray(geometry.vertices,dtype=np.float64).copy()
        px=(
            (vertices[:,0]-xmin)/
            max(xmax-xmin,1e-12)*
            (int(grid)-1)
        )
        py=(
            (ymax-vertices[:,1])/
            max(ymax-ymin,1e-12)*
            (int(grid)-1)
        )
        total=np.zeros((len(vertices),2),dtype=np.float64)

        for control in controls:
            target_x,target_y=control["target"]
            anchor_x,anchor_y=control["anchor"]
            delta=np.array([
                float(target_x-anchor_x),
                float(target_y-anchor_y),
            ],dtype=np.float64)
            delta_length=max(float(np.linalg.norm(delta)),1e-9)
            cap=float(control["cap_px"])
            radius=float(control["radius_px"])
            sigma=radius*0.42
            radius2=(px-anchor_x)**2+(py-anchor_y)**2
            weight=np.exp(-0.5*radius2/(sigma*sigma))
            weight[radius2>radius*radius]=0.0
            delta*=min(1.0,cap/delta_length)
            total+=weight[:,None]*delta[None,:]

        magnitude=np.linalg.norm(total,axis=1)
        over=magnitude>per_iteration_cap
        if np.any(over):
            total[over]*=(
                per_iteration_cap/
                magnitude[over]
            )[:,None]

        dx=total[:,0]/max(int(grid)-1,1)*(xmax-xmin)
        dy=-total[:,1]/max(int(grid)-1,1)*(ymax-ymin)
        displacement=np.sqrt(dx*dx+dy*dy)
        moved_vertices+=int(np.count_nonzero(displacement>1e-7))
        if len(displacement):
            max_iteration_world=max(
                max_iteration_world,
                float(displacement.max()),
            )

        vertices[:,0]+=dx
        vertices[:,1]+=dy
        geometry.vertices=vertices

    _recompute_planar_uv(scene)
    after=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )

    return {
        "policy":"residual-thumb-bridge-head-top-v1",
        "before_missing":int(state["missing_pixels"]),
        "after_missing":int(after["missing_pixels"]),
        "before_coverage":float(state["coverage"]),
        "after_coverage":float(after["coverage"]),
        "moved_vertices":int(moved_vertices),
        "max_iteration_world_displacement":float(max_iteration_world),
        "selected_components":selected,
        "controls":controls,
    }


def _decisive_thumb_head_pass(
    scene,
    *,
    grid:int,
    overscan:float,
    alpha_threshold:int,
    edge_fill_radius:int,
    pass_index:int,
):
    state=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )
    missing=state["missing"]
    keep=state["keep"]
    bounds=state["bounds"]

    distance,indices=distance_transform_edt(
        ~keep,
        return_indices=True,
    )
    labels,count=label(missing)
    scale=float(grid)/768.0
    controls=[]
    selected=[]

    for component_id in range(1,int(count)+1):
        ys,xs=np.where(labels==component_id)
        area=int(len(xs))
        if area<8:
            continue

        cx=float(xs.mean())/max(float(grid),1.0)
        cy=float(ys.mean())/max(float(grid),1.0)
        region=None

        # Correct residual thumb-middle component observed in #44:
        # x~=329, y~=326 at 768 evidence resolution.
        if (
            0.395<=cx<=0.455
            and 0.375<=cy<=0.475
            and area>=18
        ):
            region="thumb_middle"
        elif (
            0.515<=cx<=0.590
            and cy<0.225
            and area>=8
        ):
            region="head_top"
        if region is None:
            continue

        values=distance[ys,xs]
        order=np.argsort(values)[::-1]
        peaks=[]
        min_sep=6.0*scale
        max_peaks=4

        for index in order:
            target_x=int(xs[index])
            target_y=int(ys[index])
            if any(
                (target_x-p["target"][0])**2+
                (target_y-p["target"][1])**2 <
                min_sep*min_sep
                for p in peaks
            ):
                continue

            anchor_y=int(indices[0,target_y,target_x])
            anchor_x=int(indices[1,target_y,target_x])
            peak={
                "target":[target_x,target_y],
                "anchor":[anchor_x,anchor_y],
                "distance_px":float(values[index]),
            }
            peaks.append(peak)
            if len(peaks)>=max_peaks:
                break

        if not peaks:
            continue

        selected.append({
            "region":region,
            "area":area,
            "bbox":[
                int(xs.min()),int(ys.min()),
                int(xs.max()),int(ys.max()),
            ],
            "centroid":[float(xs.mean()),float(ys.mean())],
            "max_distance_px":float(values.max(initial=0.0)),
            "peaks":peaks,
        })

        for peak in peaks:
            target_x,target_y=peak["target"]
            anchor_x,anchor_y=peak["anchor"]
            peak_distance=float(peak["distance_px"])
            if region=="thumb_middle":
                cap=(8.5 if int(pass_index)==0 else 7.0)*scale
                radius=(18.0 if int(pass_index)==0 else 15.0)*scale
            else:
                cap=(3.5 if int(pass_index)==0 else 3.0)*scale
                radius=(9.0 if int(pass_index)==0 else 8.0)*scale

            controls.append({
                "region":region,
                "target":[target_x,target_y],
                "anchor":[anchor_x,anchor_y],
                "distance_px":peak_distance,
                "cap_px":float(cap),
                "radius_px":float(radius),
            })

    xmin,xmax,ymin,ymax=[float(x) for x in bounds]
    moved_vertices=0
    max_iteration_world=0.0
    per_iteration_cap=(9.0 if int(pass_index)==0 else 8.0)*scale

    for node in (FRONT_NODE,SUPPORT_NODE):
        geometry=_geometry(scene,node)
        vertices=np.asarray(geometry.vertices,dtype=np.float64).copy()
        px=(
            (vertices[:,0]-xmin)/
            max(xmax-xmin,1e-12)*
            (int(grid)-1)
        )
        py=(
            (ymax-vertices[:,1])/
            max(ymax-ymin,1e-12)*
            (int(grid)-1)
        )
        total=np.zeros((len(vertices),2),dtype=np.float64)

        for control in controls:
            target_x,target_y=control["target"]
            anchor_x,anchor_y=control["anchor"]
            delta=np.array([
                float(target_x-anchor_x),
                float(target_y-anchor_y),
            ],dtype=np.float64)
            delta_length=max(float(np.linalg.norm(delta)),1e-9)
            cap=float(control["cap_px"])
            radius=float(control["radius_px"])
            sigma=radius*0.45
            radius2=(px-anchor_x)**2+(py-anchor_y)**2
            weight=np.exp(-0.5*radius2/(sigma*sigma))
            weight[radius2>radius*radius]=0.0
            delta*=min(1.0,cap/delta_length)
            total+=weight[:,None]*delta[None,:]

        magnitude=np.linalg.norm(total,axis=1)
        over=magnitude>per_iteration_cap
        if np.any(over):
            total[over]*=(
                per_iteration_cap/
                magnitude[over]
            )[:,None]

        dx=total[:,0]/max(int(grid)-1,1)*(xmax-xmin)
        dy=-total[:,1]/max(int(grid)-1,1)*(ymax-ymin)
        displacement=np.sqrt(dx*dx+dy*dy)
        moved_vertices+=int(np.count_nonzero(displacement>1e-7))
        if len(displacement):
            max_iteration_world=max(
                max_iteration_world,
                float(displacement.max()),
            )

        vertices[:,0]+=dx
        vertices[:,1]+=dy
        geometry.vertices=vertices

    _recompute_planar_uv(scene)
    after=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )
    return {
        "policy":"decisive-thumb-middle-head-top-v1",
        "pass_index":int(pass_index),
        "before_missing":int(state["missing_pixels"]),
        "after_missing":int(after["missing_pixels"]),
        "before_coverage":float(state["coverage"]),
        "after_coverage":float(after["coverage"]),
        "moved_vertices":int(moved_vertices),
        "max_iteration_world_displacement":float(max_iteration_world),
        "selected_components":selected,
        "controls":controls,
    }


def conform(
    input_glb:Path,
    output_glb:Path,
    *,
    report:Path|None,
    iterations:int,
    grid:int,
    overscan:float,
    alpha_threshold:int,
    edge_fill_radius:int,
):
    scene=_load_scene(input_glb)
    original={}
    topology={}
    for node in (FRONT_NODE,SUPPORT_NODE):
        geometry=_geometry(scene,node)
        original[node]=np.asarray(
            geometry.vertices,dtype=np.float64
        ).copy()
        topology[node]={
            "vertices":int(len(geometry.vertices)),
            "faces":int(len(geometry.faces)),
        }

    initial=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )
    initial_bounds=tuple(float(v) for v in initial["bounds"])
    passes=[]
    for _ in range(max(1,int(iterations))):
        result=_conform_iteration(
            scene,
            grid=grid,
            overscan=overscan,
            alpha_threshold=alpha_threshold,
            edge_fill_radius=edge_fill_radius,
            min_component_area=20,
            max_component_distance=28.0,
            per_component_cap_px=12.0,
            per_iteration_cap_px=14.0,
        )
        passes.append(result)
        if result["after_missing"]>=result["before_missing"]:
            break
        if result["after_missing"]<=512:
            break

    targeted_extremity=_targeted_extremity_pass(
        scene,
        grid=grid,
        overscan=overscan,
        alpha_threshold=alpha_threshold,
        edge_fill_radius=edge_fill_radius,
    )

    residual_thumb_bridge=_residual_thumb_bridge_pass(
        scene,
        grid=grid,
        overscan=overscan,
        alpha_threshold=alpha_threshold,
        edge_fill_radius=edge_fill_radius,
    )

    decisive_thumb_head_passes=[]
    for decisive_index in range(2):
        decisive=_decisive_thumb_head_pass(
            scene,
            grid=grid,
            overscan=overscan,
            alpha_threshold=alpha_threshold,
            edge_fill_radius=edge_fill_radius,
            pass_index=decisive_index,
        )
        decisive_thumb_head_passes.append(decisive)
        if decisive["after_missing"]>=decisive["before_missing"]:
            break

    final=_coverage(
        scene,grid,overscan,alpha_threshold,edge_fill_radius
    )

    max_xy_displacement=0.0
    max_xy_displacement_targeted=0.0
    max_xy_displacement_nontarget=0.0
    max_z_displacement=0.0
    xmin0,xmax0,ymin0,ymax0=initial_bounds

    for node in (FRONT_NODE,SUPPORT_NODE):
        geometry=_geometry(scene,node)
        current=np.asarray(geometry.vertices,dtype=np.float64)
        if len(current)!=topology[node]["vertices"]:
            raise RuntimeError("vertex count changed during silhouette conform")
        if len(geometry.faces)!=topology[node]["faces"]:
            raise RuntimeError("face count changed during silhouette conform")
        base=original[node]
        delta=current-base
        xy=np.linalg.norm(delta[:,:2],axis=1)
        max_xy_displacement=max(
            max_xy_displacement,
            float(xy.max(initial=0.0)),
        )
        max_z_displacement=max(
            max_z_displacement,
            float(np.abs(delta[:,2]).max(initial=0.0)),
        )

        px0=(
            (base[:,0]-xmin0)/
            max(xmax0-xmin0,1e-12)
        )
        py0=(
            (ymax0-base[:,1])/
            max(ymax0-ymin0,1e-12)
        )
        targeted=(
            (
                (px0>=0.37)&(px0<=0.49)&
                (py0>=0.30)&(py0<=0.50)
            )
            |
            (
                (px0>=0.49)&(px0<=0.62)&
                (py0<=0.27)
            )
        )
        if np.any(targeted):
            max_xy_displacement_targeted=max(
                max_xy_displacement_targeted,
                float(xy[targeted].max(initial=0.0)),
            )
        if np.any(~targeted):
            max_xy_displacement_nontarget=max(
                max_xy_displacement_nontarget,
                float(xy[~targeted].max(initial=0.0)),
            )

    if max_z_displacement>1e-9:
        raise RuntimeError(
            f"silhouette conform changed depth: {max_z_displacement}"
        )
    if max_xy_displacement_nontarget>0.055:
        raise RuntimeError(
            "silhouette conform exceeded non-target XY safety cap: "
            f"{max_xy_displacement_nontarget}"
        )
    if max_xy_displacement_targeted>0.075:
        raise RuntimeError(
            "silhouette conform exceeded targeted XY safety cap: "
            f"{max_xy_displacement_targeted}"
        )
    if final["coverage"]<=initial["coverage"]:
        raise RuntimeError(
            "silhouette conform did not improve source-outline coverage"
        )

    payload={
        "schema":1,
        "policy":"localized-screen-space-silhouette-conform-v1",
        "input":str(input_glb),
        "output":str(output_glb),
        "grid":int(grid),
        "iterations_requested":int(iterations),
        "iterations_executed":int(len(passes)),
        "overscan":float(overscan),
        "alpha_threshold":int(alpha_threshold),
        "edge_fill_radius":int(edge_fill_radius),
        "initial":{
            "missing_inside_outline":int(initial["missing_pixels"]),
            "outline_coverage":float(initial["coverage"]),
        },
        "final":{
            "missing_inside_outline":int(final["missing_pixels"]),
            "outline_coverage":float(final["coverage"]),
        },
        "max_xy_displacement":float(max_xy_displacement),
        "max_xy_displacement_targeted":float(max_xy_displacement_targeted),
        "max_xy_displacement_nontarget":float(max_xy_displacement_nontarget),
        "max_z_displacement":float(max_z_displacement),
        "topology":topology,
        "passes":passes,
        "targeted_extremity_pass":targeted_extremity,
        "residual_thumb_bridge_pass":residual_thumb_bridge,
        "decisive_thumb_head_passes":decisive_thumb_head_passes,
    }

    output_glb.parent.mkdir(parents=True,exist_ok=True)
    data=scene.export(file_type="glb")
    if input_glb.resolve()==output_glb.resolve():
        temp=output_glb.with_suffix(".conform.tmp.glb")
        temp.write_bytes(data)
        temp.replace(output_glb)
    else:
        output_glb.write_bytes(data)

    if report is not None:
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(
            json.dumps(payload,indent=2)+"\n",
            encoding="utf-8",
        )

    print(
        "HAYUYA_SILHOUETTE_CONFORM_PASS",
        json.dumps(payload,separators=(",",":")),
    )
    return payload


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--report",type=Path)
    parser.add_argument("--iterations",type=int,default=2)
    parser.add_argument("--grid",type=int,default=768)
    parser.add_argument("--overscan",type=float,default=1.42)
    parser.add_argument("--alpha-threshold",type=int,default=48)
    parser.add_argument("--edge-fill-radius",type=int,default=6)
    args=parser.parse_args()
    conform(
        args.input,
        args.output,
        report=args.report,
        iterations=args.iterations,
        grid=args.grid,
        overscan=args.overscan,
        alpha_threshold=args.alpha_threshold,
        edge_fill_radius=args.edge_fill_radius,
    )


if __name__=="__main__":
    main()
