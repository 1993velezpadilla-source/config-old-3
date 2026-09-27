#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class LocalDetailFusionResult:
    base_mesh:str
    donor_mesh:str
    output_glb:str
    region:str
    ready:bool
    basecolor_image_index:int|None
    changed_pixels:int
    unchanged_pixels:int
    changed_fraction:float
    donor_alignment_p95_ratio:float|None
    skin_payload_preserved:bool
    runtime_payload_preserved:bool
    geometry_preserved:bool
    skipped_uv_seam_faces:int
    seam_boundary_pairs:int
    seam_added_delta_p95:float|None
    seam_added_delta_max:float|None
    seam_ready:bool
    error:str|None=None
    method:str="hayuya-local-basecolor-fusion-v2"


def _deps():
    import numpy as np
    import trimesh
    from scipy.spatial import cKDTree
    return np,trimesh,cKDTree


def _smoothstep(x):
    np,_,_=_deps()
    x=np.clip(x,0.0,1.0)
    return x*x*(3.0-2.0*x)


def _single_mesh(path:Path):
    np,trimesh,_=_deps()
    scene=trimesh.load(path,force="scene",process=False)
    meshes=[]
    for node_name in scene.graph.nodes_geometry:
        transform,geom_name=scene.graph[node_name]
        geom=scene.geometry[geom_name]
        if not hasattr(geom,"faces") or not len(geom.faces):
            continue
        mesh=geom.copy()
        mesh.apply_transform(transform)
        meshes.append(mesh)
    if len(meshes)!=1:
        raise ValueError(
            "local detail fusion v1 requires exactly one triangle mesh "
            f"(got {len(meshes)})"
        )
    mesh=meshes[0]
    uv=getattr(getattr(mesh,"visual",None),"uv",None)
    if uv is None or len(uv)!=len(mesh.vertices):
        raise ValueError("base mesh has no per-vertex UVs")
    return mesh


def _basecolor_image(path:Path):
    from texture_gate import embedded_images
    matches=[
        (index,mime,data)
        for index,mime,data,roles in embedded_images(path)
        if "baseColor" in set(roles or [])
    ]
    if len(matches)!=1:
        raise ValueError(
            "local detail fusion v1 requires exactly one embedded baseColor "
            f"image (got {len(matches)})"
        )
    return matches[0]


def _wrap_uv(values):
    np,_,_=_deps()
    raw=np.asarray(values,dtype=np.float64)
    wrapped=np.mod(raw,1.0)
    integer_upper=(
        (np.abs(wrapped)<=1e-10)
        &(raw>0.0)
    )
    wrapped[integer_upper]=1.0
    return wrapped


def _region_weight_from_height(h,region:str):
    region=str(region or "").lower()
    if region=="head":
        return _smoothstep((h-0.66)/0.18)
    if region=="middle":
        lower=_smoothstep((h-0.18)/0.18)
        upper=_smoothstep((0.84-h)/0.18)
        return lower*upper
    if region=="lower":
        return _smoothstep((0.46-h)/0.20)
    raise ValueError(
        f"local detail region {region!r} is not executable in v1"
    )


def _normalized_heights(vertices,up_axis:int):
    np,_,_=_deps()
    values=np.asarray(vertices,dtype=np.float64)[:,up_axis]
    lo=float(np.min(values))
    hi=float(np.max(values))
    extent=max(hi-lo,1e-9)
    return (values-lo)/extent


def _region_weights(vertices,region:str,up_axis:int):
    return _region_weight_from_height(
        _normalized_heights(vertices,up_axis),
        region,
    )


def _deterministic_donor_cloud(
    donor:Path,
    *,
    samples:int,
):
    np,_,_=_deps()
    from material_bridge import build_source_color_cloud
    state=np.random.get_state()
    try:
        np.random.seed(424242)
        return build_source_color_cloud(
            donor,total_samples=max(2000,int(samples))
        )
    finally:
        np.random.set_state(state)


def _align_cloud(
    points,
    base_vertices,
    *,
    region:str|None=None,
    up_axis:int=1,
    donor_scope:str="full",
):
    """Align donor color evidence to the full asset or one semantic region."""
    np,_,cKDTree=_deps()
    points=np.asarray(points,dtype=np.float64)
    base=np.asarray(base_vertices,dtype=np.float64)
    scope=str(donor_scope or "full").lower()
    if scope not in {"full","region"}:
        raise ValueError(
            f"unsupported donor_scope {donor_scope!r}; expected full or region"
        )

    target=base
    if scope=="region":
        heights=_normalized_heights(base,int(up_axis))
        resolved=str(region or "").lower()
        if resolved=="head":
            target=base[heights>=0.58]
        elif resolved=="middle":
            target=base[(heights>=0.18)&(heights<=0.84)]
        elif resolved=="lower":
            target=base[heights<=0.46]
        if len(target)<16:
            raise RuntimeError(
                f"semantic alignment region {region!r} is too sparse: {len(target)}"
            )

    p_lo=np.min(points,axis=0)
    p_hi=np.max(points,axis=0)
    b_lo=np.min(target,axis=0)
    b_hi=np.max(target,axis=0)
    p_center=(p_lo+p_hi)*0.5
    b_center=(b_lo+b_hi)*0.5
    p_diag=max(float(np.linalg.norm(p_hi-p_lo)),1e-9)
    b_diag=max(float(np.linalg.norm(b_hi-b_lo)),1e-9)
    scale=b_diag/p_diag
    aligned=(points-p_center)*scale+b_center
    tree=cKDTree(aligned)
    distances,_=tree.query(target,k=1,workers=-1)
    p95=float(np.percentile(distances/b_diag,95.0))
    return aligned,b_diag,p95


def _uv_axis_crosses_wrap(values)->bool:
    np,_,_=_deps()
    values=np.asarray(values,dtype=np.float64)
    span=float(np.ptp(values))
    if span<=0.5:
        return False
    eps=1e-8
    # A face that explicitly uses only the 0/1 atlas boundary is allowed to
    # span the full image. This is common on simple unwraps and is not itself a
    # wrap seam. Ambiguous 0.98->0.02 style faces remain fail-closed.
    boundary_only=bool(np.all(
        (values<=eps)|(values>=1.0-eps)
    ))
    return not boundary_only


def _barycentric_grid(tri_xy,min_x,max_x,min_y,max_y):
    np,_,_=_deps()
    xs=np.arange(min_x,max_x+1,dtype=np.float64)+0.5
    ys=np.arange(min_y,max_y+1,dtype=np.float64)+0.5
    xx,yy=np.meshgrid(xs,ys)
    p=np.stack([xx,yy],axis=-1)
    a,b,c=tri_xy
    v0=b-a
    v1=c-a
    v2=p-a
    den=v0[0]*v1[1]-v1[0]*v0[1]
    if abs(float(den))<=1e-12:
        return None,None
    u=(v2[...,0]*v1[1]-v1[0]*v2[...,1])/den
    v=(v0[0]*v2[...,1]-v2[...,0]*v0[1])/den
    w=1.0-u-v
    inside=(u>=-1e-6)&(v>=-1e-6)&(w>=-1e-6)
    bary=np.stack([w,u,v],axis=-1)
    return bary,inside


def _feather_fusion_boundary(before_rgb,after_rgb,support_mask,*,radius_px:float):
    """Fade only the UV-island/paint boundary; preserve interior donor detail."""
    np,_,_=_deps()
    from scipy.ndimage import distance_transform_edt

    before=np.asarray(before_rgb,dtype=np.float64)
    after=np.asarray(after_rgb,dtype=np.float64)
    support=np.asarray(support_mask,dtype=bool)
    if not np.any(support):
        return np.asarray(after_rgb,dtype=np.uint8),support

    distance=distance_transform_edt(support)
    radius=max(1.0,float(radius_px))
    feather=_smoothstep(np.clip(distance/radius,0.0,1.0))
    delta=after-before
    blended=before+delta*feather[...,None]
    out=np.clip(np.rint(blended),0,255).astype(np.uint8)
    changed=np.any(out!=np.asarray(before_rgb,dtype=np.uint8),axis=-1)
    return out,changed


def _seam_added_delta(before_rgb,after_rgb,changed_mask):
    np,_,_=_deps()
    before=np.asarray(before_rgb,dtype=np.float64)
    after=np.asarray(after_rgb,dtype=np.float64)
    changed=np.asarray(changed_mask,dtype=bool)
    values=[]

    def collect(a_slice,b_slice):
        a_changed=changed[a_slice]
        b_changed=changed[b_slice]
        boundary=a_changed & (~b_changed)
        if not np.any(boundary):
            return
        before_diff=np.mean(
            np.abs(before[a_slice]-before[b_slice]),
            axis=-1,
        )
        after_diff=np.mean(
            np.abs(after[a_slice]-after[b_slice]),
            axis=-1,
        )
        added=np.maximum(0.0,after_diff-before_diff)
        values.extend(
            float(x) for x in added[boundary]
        )

    collect((slice(None),slice(1,None)),(slice(None),slice(None,-1)))
    collect((slice(None),slice(None,-1)),(slice(None),slice(1,None)))
    collect((slice(1,None),slice(None)),(slice(None,-1),slice(None)))
    collect((slice(None,-1),slice(None)),(slice(1,None),slice(None)))

    if not values:
        return 0,0.0,0.0
    arr=np.asarray(values,dtype=np.float64)
    return (
        int(len(arr)),
        float(np.percentile(arr,95.0)),
        float(np.max(arr)),
    )


def fuse_local_basecolor(
    base_mesh:Path,
    donor_mesh:Path,
    output_glb:Path,
    *,
    region:str,
    up_axis:str|int="y",
    donor_samples:int=60_000,
    max_alignment_p95_ratio:float=0.18,
    donor_scope:str="full",
)->LocalDetailFusionResult:
    np,_,cKDTree=_deps()
    try:
        axis_map={"x":0,"y":1,"z":2}
        if isinstance(up_axis,str):
            if up_axis.lower() not in axis_map:
                raise ValueError(f"invalid up_axis: {up_axis}")
            axis=axis_map[up_axis.lower()]
        else:
            axis=int(up_axis)
            if axis not in (0,1,2):
                raise ValueError(f"invalid up_axis index: {axis}")

        base=_single_mesh(base_mesh)
        image_index,mime,image_bytes=_basecolor_image(base_mesh)
        from PIL import Image
        with Image.open(io.BytesIO(image_bytes)) as image:
            source_had_alpha="A" in image.getbands()
            rgba=image.convert("RGBA")
            pixels=np.asarray(rgba,dtype=np.uint8).copy()
            original_pixels=pixels.copy()

        vertices=np.asarray(base.vertices,dtype=np.float64)
        faces=np.asarray(base.faces,dtype=np.int64)
        uv=np.asarray(base.visual.uv,dtype=np.float64)
        normalized_heights=_normalized_heights(vertices,axis)

        donor_points,donor_colors=_deterministic_donor_cloud(
            donor_mesh,samples=donor_samples
        )
        aligned,diag,alignment_p95=_align_cloud(
            donor_points,
            vertices,
            region=region,
            up_axis=axis,
            donor_scope=donor_scope,
        )
        if alignment_p95>max_alignment_p95_ratio:
            raise RuntimeError(
                "donor alignment too weak for local fusion: "
                f"p95={alignment_p95:.6f}>"
                f"{max_alignment_p95_ratio:.6f}"
            )
        tree=cKDTree(np.asarray(aligned,dtype=np.float64))
        _,nearest=tree.query(vertices,k=1,workers=-1)
        vertex_colors=np.clip(
            np.asarray(donor_colors,dtype=np.float64)[nearest],
            0,255,
        )

        h,w=pixels.shape[:2]
        blend_alpha=np.zeros((h,w),dtype=np.float64)
        skipped_seams=0
        for face in faces:
            tri_h=normalized_heights[face]
            tri_uv=_wrap_uv(uv[face])
            # Avoid painting across wrapped UV seams in v1. Those boundary
            # triangles stay base-exact until seam-aware unwrap support lands.
            if (
                _uv_axis_crosses_wrap(tri_uv[:,0])
                or _uv_axis_crosses_wrap(tri_uv[:,1])
            ):
                skipped_seams+=1
                continue

            tri_xy=np.empty((3,2),dtype=np.float64)
            # Raster coordinates are texel-edge coordinates while samples are
            # evaluated at pixel centers (+0.5). Mapping UV 1.0 to w/h (not
            # w-1/h-1) prevents a one-pixel unpainted border at atlas edges.
            tri_xy[:,0]=tri_uv[:,0]*w
            tri_xy[:,1]=(1.0-tri_uv[:,1])*h
            min_x=max(0,int(math.floor(float(np.min(tri_xy[:,0])))))
            max_x=min(w-1,int(math.ceil(float(np.max(tri_xy[:,0])))))
            min_y=max(0,int(math.floor(float(np.min(tri_xy[:,1])))))
            max_y=min(h-1,int(math.ceil(float(np.max(tri_xy[:,1])))))
            if max_x<min_x or max_y<min_y:
                continue

            bary,inside=_barycentric_grid(
                tri_xy,min_x,max_x,min_y,max_y
            )
            if bary is None or not np.any(inside):
                continue
            local_height=np.sum(
                bary*tri_h.reshape((1,1,3)),axis=-1
            )
            local_alpha=_region_weight_from_height(
                local_height,
                region,
            )
            donor_rgb=np.sum(
                bary[...,None]
                *vertex_colors[face].reshape((1,1,3,3)),
                axis=-2,
            )
            alpha=np.clip(local_alpha,0.0,1.0)
            active=inside&(alpha>1e-4)
            if not np.any(active):
                continue

            ys,xs=np.nonzero(active)
            gy=ys+min_y
            gx=xs+min_x
            a=alpha[active][:,None]
            base_rgb=pixels[gy,gx,:3].astype(np.float64)
            new_rgb=(
                base_rgb*(1.0-a)
                +donor_rgb[active]*a
            )
            pixels[gy,gx,:3]=np.clip(
                np.rint(new_rgb),0,255
            ).astype(np.uint8)
            blend_alpha[gy,gx]=np.maximum(
                blend_alpha[gy,gx],
                alpha[active],
            )

        # UV islands can end in the middle of a strongly painted semantic
        # region. Height-space alpha alone therefore cannot guarantee a soft
        # texture boundary. Feather only the *visible delta* for a few texels
        # inward from each painted island edge; the interior donor evidence is
        # untouched. At 2K this is ~8 px, small enough to preserve face detail.
        raw_support=blend_alpha>1e-4
        seam_feather_px=max(
            2.0,
            min(12.0,float(min(h,w))*0.004),
        )
        feathered_rgb,actual_changed=_feather_fusion_boundary(
            original_pixels[:,:,:3],
            pixels[:,:,:3],
            raw_support,
            radius_px=seam_feather_px,
        )
        pixels[:,:,:3]=feathered_rgb

        changed=int(np.count_nonzero(actual_changed))
        total=int(h*w)
        unchanged=total-changed
        seam_pairs,seam_p95,seam_max=_seam_added_delta(
            original_pixels[:,:,:3],
            pixels[:,:,:3],
            actual_changed,
        )
        seam_ready=bool(seam_p95<=12.0)
        if changed<=0:
            raise RuntimeError(
                "local fusion changed no texture pixels"
            )
        if unchanged<=0:
            raise RuntimeError(
                "local fusion unexpectedly replaced the entire atlas"
            )
        if not seam_ready:
            raise RuntimeError(
                "local fusion added a visible texture-boundary discontinuity: "
                f"p95={seam_p95:.3f}>12.000"
            )

        out_image=Image.fromarray(
            pixels,
            mode="RGBA",
        )
        buf=io.BytesIO()
        if source_had_alpha:
            out_image.save(buf,format="PNG",optimize=True)
        else:
            out_image.convert("RGB").save(
                buf,format="PNG",optimize=True
            )

        from glb_images import replace_embedded_images
        replace_embedded_images(
            base_mesh,
            output_glb,
            {image_index:("image/png",buf.getvalue())},
        )

        from gltf_position_patch import (
            runtime_payload_signature,
            skin_payload_signature,
        )
        skin_preserved=(
            skin_payload_signature(base_mesh)
            ==skin_payload_signature(output_glb)
        )
        runtime_preserved=(
            runtime_payload_signature(base_mesh)
            ==runtime_payload_signature(output_glb)
        )

        from qa import inspect_mesh
        base_qa=inspect_mesh(
            base_mesh,
            backend="local_fusion_base",
            mode="character",
            target_faces=max(1,len(faces)),
        )
        out_qa=inspect_mesh(
            output_glb,
            backend="local_fusion_output",
            mode="character",
            target_faces=max(1,len(faces)),
        )
        geometry_preserved=bool(
            base_qa.vertices==out_qa.vertices
            and base_qa.faces==out_qa.faces
            and base_qa.components==out_qa.components
            and list(base_qa.bbox or [])==list(out_qa.bbox or [])
        )
        if not geometry_preserved:
            raise RuntimeError(
                "local texture fusion changed geometry"
            )
        if not skin_preserved:
            raise RuntimeError(
                "local texture fusion changed JOINTS/WEIGHTS payload"
            )
        if not runtime_preserved:
            raise RuntimeError(
                "local texture fusion changed protected runtime payload "
                "(skin/animation/morph)"
            )

        return LocalDetailFusionResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            region=str(region),
            ready=True,
            basecolor_image_index=image_index,
            changed_pixels=changed,
            unchanged_pixels=unchanged,
            changed_fraction=round(changed/total,6),
            donor_alignment_p95_ratio=round(alignment_p95,6),
            skin_payload_preserved=True,
            runtime_payload_preserved=True,
            geometry_preserved=True,
            skipped_uv_seam_faces=skipped_seams,
            seam_boundary_pairs=seam_pairs,
            seam_added_delta_p95=round(seam_p95,6),
            seam_added_delta_max=round(seam_max,6),
            seam_ready=seam_ready,
        )
    except Exception as exc:
        return LocalDetailFusionResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            region=str(region),
            ready=False,
            basecolor_image_index=None,
            changed_pixels=0,
            unchanged_pixels=0,
            changed_fraction=0.0,
            donor_alignment_p95_ratio=None,
            skin_payload_preserved=False,
            runtime_payload_preserved=False,
            geometry_preserved=False,
            skipped_uv_seam_faces=0,
            seam_boundary_pairs=0,
            seam_added_delta_p95=None,
            seam_added_delta_max=None,
            seam_ready=False,
            error=f"{type(exc).__name__}:{exc}",
        )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA semantic local baseColor fusion challenger."
    )
    parser.add_argument("--base",type=Path,required=True)
    parser.add_argument("--donor",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument(
        "--region",
        choices=["head","middle","lower"],
        required=True,
    )
    parser.add_argument("--up-axis",choices=["x","y","z"],default="y")
    parser.add_argument(
        "--donor-scope",
        choices=["full","region"],
        default="full",
    )
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    result=fuse_local_basecolor(
        args.base,args.donor,args.output,
        region=args.region,
        up_axis=args.up_axis,
        donor_scope=args.donor_scope,
    )
    payload=json.dumps(asdict(result),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if result.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
