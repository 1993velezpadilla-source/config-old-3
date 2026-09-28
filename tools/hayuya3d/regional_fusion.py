#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class HeadWrapResult:
    base_mesh:str
    donor_mesh:str
    raw_output_glb:str|None
    output_glb:str|None
    attempted:bool
    geometry_ready:bool
    rebake_ready:bool
    ready_for_judge:bool
    up_axis:int|None
    alignment_scale:float|None
    head_vertices:int
    changed_vertices:int
    clamped_vertices:int
    mean_displacement_normalized:float|None
    max_displacement_normalized:float|None
    seam_max_displacement_normalized:float|None
    bbox_drift_fraction:float|None
    rebake_required:list[str]
    rebake_resolved:list[str]
    skin_payload_preserved:bool|None=None
    skin_runtime_ready:bool|None=None
    rig_preserved:bool|None=None
    skin_weights_ready:bool|None=None
    error:str|None=None
    method:str="hayuya-head-wrap-regional-fusion-v2"


def _deps():
    import numpy as np
    import trimesh
    from scipy.spatial import cKDTree
    return np,trimesh,cKDTree


def _scene_meshes(path:Path):
    from material_bridge import _scene_meshes as load
    return load(path)


def _all_vertices(meshes):
    np,_,_=_deps()
    arrays=[np.asarray(mesh.vertices,dtype=np.float64) for mesh in meshes if len(mesh.vertices)]
    if not arrays:
        raise ValueError("mesh contains no vertices")
    return np.concatenate(arrays,axis=0)


def _smoothstep(values):
    np,_,_=_deps()
    values=np.clip(values,0.0,1.0)
    return values*values*(3.0-2.0*values)


def _head_wrap_influence(values):
    """Seam-protected head transfer curve.

    Squaring smoothstep keeps the lower neck nearly fixed while still reaching
    full donor influence across the upper head. This satisfies the existing
    1.2% neck-seam gate without weakening that gate.
    """
    s=_smoothstep(values)
    return s*s


def _bbox(vertices):
    np,_,_=_deps()
    lo=np.min(vertices,axis=0)
    hi=np.max(vertices,axis=0)
    return lo,hi,(lo+hi)*0.5,hi-lo


def _rig_blocked(path:Path)->tuple[bool,str|None]:
    if path.suffix.lower()!=".glb":
        return False,None
    try:
        from gltf_audit import audit_glb
        audit=audit_glb(path)
        if audit.skin_count>0 or audit.skinned_mesh_nodes>0:
            return True,(
                f"skinned_geometry_transfer_requires_weight_transfer:"
                f"skins={audit.skin_count}:nodes={audit.skinned_mesh_nodes}"
            )
        return False,None
    except Exception as exc:
        return True,f"rig_audit_failed:{type(exc).__name__}:{exc}"



def build_head_wrap_geometry(
    base_mesh:Path,
    donor_mesh:Path,
    output_glb:Path,
    *,
    head_start:float=0.72,
    full_influence:float=0.84,
    max_displacement_fraction:float=0.055,
    seam_limit_fraction:float=0.012,
    bbox_drift_limit:float=0.08,
    up_axis:str|int|None=None,
)->HeadWrapResult:
    """Create an unskinned head-shape challenger on the base topology.

    The donor is uniformly aligned to the base bounds. Only the upper character
    region is moved toward nearest donor head samples. A smooth neck falloff,
    displacement clamp and seam/bounds gates prevent hard Frankenstein cuts.
    """
    if base_mesh.suffix.lower()==".glb":
        try:
            from gltf_audit import audit_glb
            base_audit=audit_glb(base_mesh)
            if base_audit.skin_count>0 or base_audit.skinned_mesh_nodes>0:
                return build_rig_preserving_head_wrap_geometry(
                    base_mesh,
                    donor_mesh,
                    output_glb,
                    head_start=head_start,
                    full_influence=full_influence,
                    max_displacement_fraction=max_displacement_fraction,
                    seam_limit_fraction=seam_limit_fraction,
                    bbox_drift_limit=bbox_drift_limit,
                    up_axis=up_axis,
                )
        except Exception as exc:
            return HeadWrapResult(
                base_mesh=str(base_mesh),donor_mesh=str(donor_mesh),
                raw_output_glb=None,output_glb=None,
                attempted=True,geometry_ready=False,rebake_ready=False,
                ready_for_judge=False,up_axis=None,alignment_scale=None,
                head_vertices=0,changed_vertices=0,clamped_vertices=0,
                mean_displacement_normalized=None,max_displacement_normalized=None,
                seam_max_displacement_normalized=None,bbox_drift_fraction=None,
                rebake_required=[],rebake_resolved=[],
                skin_payload_preserved=False,skin_runtime_ready=False,
                error=f"skinned_head_wrap_probe_failed:{type(exc).__name__}:{exc}",
            )
    np,trimesh,cKDTree=_deps()
    try:
        base_meshes=_scene_meshes(base_mesh)
        donor_meshes=_scene_meshes(donor_mesh)
        base_vertices=_all_vertices(base_meshes)
        donor_vertices=_all_vertices(donor_meshes)

        base_lo,base_hi,base_center,base_extent=_bbox(base_vertices)
        donor_lo,donor_hi,donor_center,donor_extent=_bbox(donor_vertices)
        if isinstance(up_axis,str):
            axis_map={"x":0,"y":1,"z":2}
            if up_axis.lower() not in axis_map:
                raise ValueError(f"invalid up_axis: {up_axis}")
            resolved_up_axis=axis_map[up_axis.lower()]
        elif isinstance(up_axis,int):
            if up_axis not in (0,1,2):
                raise ValueError(f"invalid up_axis index: {up_axis}")
            resolved_up_axis=up_axis
        else:
            resolved_up_axis=int(np.argmax(base_extent))
        base_height=float(base_extent[resolved_up_axis])
        donor_height=float(donor_extent[resolved_up_axis])
        if base_height<=1e-9 or donor_height<=1e-9:
            raise ValueError("collapsed character bounds")

        scale=base_height/donor_height
        aligned=(donor_vertices-donor_center)*scale+base_center
        aligned_lo,aligned_hi,_,aligned_extent=_bbox(aligned)

        diagonal=max(float(np.linalg.norm(base_extent)),1e-9)
        donor_norm_h=(aligned[:,resolved_up_axis]-base_lo[resolved_up_axis])/base_height
        donor_head=aligned[donor_norm_h>=max(0.68,head_start-0.04)]
        if len(donor_head)<16:
            raise RuntimeError(
                f"donor head region too sparse: {len(donor_head)} vertices"
            )
        tree=cKDTree(donor_head)

        output_meshes=[]
        all_applied=[]
        seam_applied=[]
        head_vertices=0
        changed_vertices=0
        clamped_vertices=0

        for original in base_meshes:
            mesh=original.copy()
            vv=np.asarray(mesh.vertices,dtype=np.float64).copy()
            normalized=(vv[:,resolved_up_axis]-base_lo[resolved_up_axis])/base_height
            mask=normalized>=head_start
            ids=np.flatnonzero(mask)
            head_vertices+=int(len(ids))
            if len(ids):
                distances,nearest=tree.query(vv[ids],k=1,workers=-1)
                targets=donor_head[np.asarray(nearest,dtype=np.int64)]
                displacement=targets-vv[ids]
                raw_norm=np.linalg.norm(displacement,axis=1)
                max_disp=max_displacement_fraction*diagonal
                clamp_scale=np.ones_like(raw_norm)
                too_large=raw_norm>max_disp
                clamp_scale[too_large]=max_disp/np.maximum(raw_norm[too_large],1e-12)
                clamped_vertices+=int(np.count_nonzero(too_large))
                displacement*=clamp_scale[:,None]

                t=(normalized[ids]-head_start)/max(full_influence-head_start,1e-9)
                influence=_head_wrap_influence(t)
                applied=displacement*influence[:,None]
                vv[ids]+=applied
                changed_vertices+=int(np.count_nonzero(
                    np.linalg.norm(applied,axis=1)>1e-10
                ))
                all_applied.append(applied)

                seam_mask=normalized[ids]<(head_start+(full_influence-head_start)*0.35)
                if np.any(seam_mask):
                    seam_applied.append(applied[seam_mask])

            mesh.vertices=vv
            output_meshes.append(mesh)

        if head_vertices<=0:
            raise RuntimeError("base mesh has no vertices inside head region")

        output_glb.parent.mkdir(parents=True,exist_ok=True)
        output_glb.write_bytes(
            trimesh.exchange.gltf.export_glb(trimesh.Scene(output_meshes))
        )
        if output_glb.read_bytes()[:4]!=b"glTF":
            raise RuntimeError("head wrap export is not a valid GLB")

        moved=np.concatenate(all_applied,axis=0) if all_applied else np.zeros((0,3))
        moved_norm=np.linalg.norm(moved,axis=1)/diagonal if len(moved) else np.zeros(0)
        seam=np.concatenate(seam_applied,axis=0) if seam_applied else np.zeros((0,3))
        seam_norm=np.linalg.norm(seam,axis=1)/diagonal if len(seam) else np.zeros(0)

        wrapped=_all_vertices(_scene_meshes(output_glb))
        _,_,_,wrapped_extent=_bbox(wrapped)
        bbox_drift=float(np.max(
            np.abs(wrapped_extent-base_extent)/np.maximum(base_extent,1e-9)
        ))
        seam_max=float(np.max(seam_norm)) if len(seam_norm) else 0.0
        max_disp_norm=float(np.max(moved_norm)) if len(moved_norm) else 0.0
        mean_disp_norm=float(np.mean(moved_norm)) if len(moved_norm) else 0.0

        geometry_ready=bool(
            seam_max<=seam_limit_fraction
            and bbox_drift<=bbox_drift_limit
            and math.isfinite(max_disp_norm)
        )
        error=None
        if not geometry_ready:
            reasons=[]
            if seam_max>seam_limit_fraction:
                reasons.append(
                    f"neck_seam_drift={seam_max:.6f}>{seam_limit_fraction:.6f}"
                )
            if bbox_drift>bbox_drift_limit:
                reasons.append(
                    f"bbox_drift={bbox_drift:.6f}>{bbox_drift_limit:.6f}"
                )
            error=";".join(reasons)

        return HeadWrapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            raw_output_glb=str(output_glb),
            output_glb=str(output_glb),
            attempted=True,
            geometry_ready=geometry_ready,
            rebake_ready=False,
            ready_for_judge=False,
            up_axis=resolved_up_axis,
            alignment_scale=round(float(scale),8),
            head_vertices=head_vertices,
            changed_vertices=changed_vertices,
            clamped_vertices=clamped_vertices,
            mean_displacement_normalized=round(mean_disp_norm,8),
            max_displacement_normalized=round(max_disp_norm,8),
            seam_max_displacement_normalized=round(seam_max,8),
            bbox_drift_fraction=round(bbox_drift,8),
            rebake_required=["normal","occlusion"],
            rebake_resolved=[],
            error=error,
        )
    except Exception as exc:
        return HeadWrapResult(
            base_mesh=str(base_mesh),donor_mesh=str(donor_mesh),
            raw_output_glb=None,output_glb=None,
            attempted=True,geometry_ready=False,rebake_ready=False,
            ready_for_judge=False,up_axis=None,alignment_scale=None,
            head_vertices=0,changed_vertices=0,clamped_vertices=0,
            mean_displacement_normalized=None,max_displacement_normalized=None,
            seam_max_displacement_normalized=None,bbox_drift_fraction=None,
            rebake_required=["normal","occlusion"],rebake_resolved=[],
            error=f"{type(exc).__name__}:{exc}",
        )


def build_rig_preserving_head_wrap_geometry(
    base_mesh:Path,
    donor_mesh:Path,
    output_glb:Path,
    *,
    head_start:float=0.72,
    full_influence:float=0.84,
    max_displacement_fraction:float=0.055,
    seam_limit_fraction:float=0.012,
    bbox_drift_limit:float=0.08,
    up_axis:str|int|None=None,
)->HeadWrapResult:
    """Patch only skinned POSITION accessors and preserve JOINTS/WEIGHTS bytes."""
    np,_,cKDTree=_deps()
    try:
        from gltf_audit import audit_glb
        from gltf_position_patch import (
            _doc_and_bin,
            mesh_nodes_identity_for_accessors,
            mesh_position_accessors,
            patch_position_accessors,
            read_position_accessor,
        )
        from skin_weight_qa import audit_skin_weights

        before_rig=audit_glb(base_mesh)
        before_skin=audit_skin_weights(base_mesh)
        if not before_rig.rig_ready:
            raise RuntimeError("base rig is not valid")
        if not before_skin.applicable or not before_skin.ready:
            raise RuntimeError("base skin weights are not valid")

        doc,_,_=_doc_and_bin(base_mesh)
        accessors=mesh_position_accessors(doc,skinned_only=True)
        if not accessors:
            raise RuntimeError("no skinned POSITION accessors")
        if not mesh_nodes_identity_for_accessors(doc,accessors):
            raise RuntimeError(
                "skinned mesh node has non-identity transform; "
                "object-space POSITION patch is unsafe"
            )

        arrays=[
            np.asarray(read_position_accessor(base_mesh,index),dtype=np.float64)
            for index in accessors
        ]
        counts=[len(array) for array in arrays]
        base_vertices=np.concatenate(arrays,axis=0)
        donor_vertices=_all_vertices(_scene_meshes(donor_mesh))

        base_lo,base_hi,base_center,base_extent=_bbox(base_vertices)
        _,_,donor_center,donor_extent=_bbox(donor_vertices)
        if isinstance(up_axis,str):
            axis_map={"x":0,"y":1,"z":2}
            if up_axis.lower() not in axis_map:
                raise ValueError(f"invalid up_axis: {up_axis}")
            resolved_up_axis=axis_map[up_axis.lower()]
        elif isinstance(up_axis,int):
            if up_axis not in (0,1,2):
                raise ValueError(f"invalid up_axis index: {up_axis}")
            resolved_up_axis=up_axis
        else:
            resolved_up_axis=int(np.argmax(base_extent))

        base_height=float(base_extent[resolved_up_axis])
        donor_height=float(donor_extent[resolved_up_axis])
        if base_height<=1e-9 or donor_height<=1e-9:
            raise ValueError("collapsed character bounds")

        scale=base_height/donor_height
        aligned=(donor_vertices-donor_center)*scale+base_center
        donor_norm_h=(
            aligned[:,resolved_up_axis]-base_lo[resolved_up_axis]
        )/base_height
        donor_head=aligned[
            donor_norm_h>=max(0.68,head_start-0.04)
        ]
        if len(donor_head)<16:
            raise RuntimeError(
                f"donor head region too sparse: {len(donor_head)} vertices"
            )
        tree=cKDTree(donor_head)

        diagonal=max(float(np.linalg.norm(base_extent)),1e-9)
        normalized=(
            base_vertices[:,resolved_up_axis]-base_lo[resolved_up_axis]
        )/base_height
        ids=np.flatnonzero(normalized>=head_start)
        if len(ids)<=0:
            raise RuntimeError("base has no head-region vertices")

        _,nearest=tree.query(base_vertices[ids],k=1,workers=-1)
        targets=donor_head[np.asarray(nearest,dtype=np.int64)]
        displacement=targets-base_vertices[ids]
        raw_norm=np.linalg.norm(displacement,axis=1)
        max_disp=max_displacement_fraction*diagonal
        clamp_scale=np.ones_like(raw_norm)
        too_large=raw_norm>max_disp
        clamp_scale[too_large]=max_disp/np.maximum(
            raw_norm[too_large],
            1e-12,
        )
        displacement*=clamp_scale[:,None]
        t=(normalized[ids]-head_start)/max(
            full_influence-head_start,
            1e-9,
        )
        influence=_head_wrap_influence(t)
        applied=displacement*influence[:,None]

        wrapped=base_vertices.copy()
        wrapped[ids]+=applied
        moved_norm=np.linalg.norm(applied,axis=1)/diagonal
        seam_mask=normalized[ids] < (
            head_start+(full_influence-head_start)*0.35
        )
        seam_norm=(
            np.linalg.norm(applied[seam_mask],axis=1)/diagonal
            if np.any(seam_mask)
            else np.zeros(0)
        )

        _,_,_,wrapped_extent=_bbox(wrapped)
        bbox_drift=float(np.max(
            np.abs(wrapped_extent-base_extent)
            /np.maximum(base_extent,1e-9)
        ))
        seam_max=float(np.max(seam_norm)) if len(seam_norm) else 0.0
        max_disp_norm=float(np.max(moved_norm)) if len(moved_norm) else 0.0
        mean_disp_norm=float(np.mean(moved_norm)) if len(moved_norm) else 0.0
        geometry_ready=bool(
            seam_max<=seam_limit_fraction
            and bbox_drift<=bbox_drift_limit
            and math.isfinite(max_disp_norm)
        )
        if not geometry_ready:
            reasons=[]
            if seam_max>seam_limit_fraction:
                reasons.append(
                    f"neck_seam_drift={seam_max:.6f}>{seam_limit_fraction:.6f}"
                )
            if bbox_drift>bbox_drift_limit:
                reasons.append(
                    f"bbox_drift={bbox_drift:.6f}>{bbox_drift_limit:.6f}"
                )
            raise RuntimeError(";".join(reasons) or "geometry gate failed")

        replacements={}
        offset=0
        for accessor,count in zip(accessors,counts):
            replacements[accessor]=wrapped[offset:offset+count].tolist()
            offset+=count

        patch=patch_position_accessors(
            base_mesh,
            output_glb,
            replacements,
        )
        if not patch.ready or not patch.skin_payload_preserved:
            raise RuntimeError(
                patch.error or "POSITION patch changed skin payload"
            )

        after_rig=audit_glb(output_glb)
        after_skin=audit_skin_weights(output_glb)
        rig_preserved=bool(
            after_rig.rig_ready
            and before_rig.skin_count==after_rig.skin_count
            and before_rig.joint_count==after_rig.joint_count
            and before_rig.animation_count==after_rig.animation_count
            and before_rig.skinned_mesh_nodes==after_rig.skinned_mesh_nodes
        )
        skin_ready=bool(after_skin.applicable and after_skin.ready)
        if not rig_preserved or not skin_ready:
            raise RuntimeError(
                "rig or skin-weight audit regressed after POSITION patch"
            )

        required=[
            channel for channel in ("normal","occlusion")
            if channel in set(before_rig.material_channels or [])
        ]
        return HeadWrapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            raw_output_glb=str(output_glb),
            output_glb=str(output_glb),
            attempted=True,
            geometry_ready=True,
            rebake_ready=not required,
            ready_for_judge=not required,
            up_axis=resolved_up_axis,
            alignment_scale=round(float(scale),8),
            head_vertices=int(len(ids)),
            changed_vertices=int(np.count_nonzero(
                np.linalg.norm(applied,axis=1)>1e-10
            )),
            clamped_vertices=int(np.count_nonzero(too_large)),
            mean_displacement_normalized=round(mean_disp_norm,8),
            max_displacement_normalized=round(max_disp_norm,8),
            seam_max_displacement_normalized=round(seam_max,8),
            bbox_drift_fraction=round(bbox_drift,8),
            rebake_required=required,
            rebake_resolved=[],
            skin_payload_preserved=True,
            skin_runtime_ready=True,
            rig_preserved=True,
            skin_weights_ready=True,
            error=None,
        )
    except Exception as exc:
        return HeadWrapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            raw_output_glb=None,
            output_glb=None,
            attempted=True,
            geometry_ready=False,
            rebake_ready=False,
            ready_for_judge=False,
            up_axis=None,
            alignment_scale=None,
            head_vertices=0,
            changed_vertices=0,
            clamped_vertices=0,
            mean_displacement_normalized=None,
            max_displacement_normalized=None,
            seam_max_displacement_normalized=None,
            bbox_drift_fraction=None,
            rebake_required=[],
            rebake_resolved=[],
            skin_payload_preserved=False,
            skin_runtime_ready=False,
            rig_preserved=False,
            skin_weights_ready=False,
            error=f"{type(exc).__name__}:{exc}",
        )


def prepare_head_wrap_challenger(
    base_mesh:Path,
    donor_mesh:Path,
    out_dir:Path,
    *,
    texture_size:int,
    blender:str|Path|None=None,
    require_rebake:bool=True,
    up_axis:str|int|None=None,
)->HeadWrapResult:
    out_dir.mkdir(parents=True,exist_ok=True)
    raw=out_dir/"head_wrap_raw.glb"
    try:
        from gltf_audit import audit_glb
        base_rig=audit_glb(base_mesh)
    except Exception:
        base_rig=None
    if base_rig is not None and base_rig.skin_count>0:
        result=build_rig_preserving_head_wrap_geometry(
            base_mesh,
            donor_mesh,
            raw,
            up_axis=up_axis,
        )
    else:
        result=build_head_wrap_geometry(
            base_mesh,donor_mesh,raw,up_axis=up_axis
        )
    if not result.geometry_ready:
        return result

    # Topology and UVs are preserved, but tangent-space normal/AO evidence is
    # geometry-dependent. Rebake before the challenger is eligible for promotion.
    try:
        from gltf_audit import audit_glb
        audit=audit_glb(base_mesh)
        required=[
            channel for channel in ("normal","occlusion")
            if channel in set(audit.material_channels or [])
        ]
    except Exception:
        required=["normal","occlusion"]

    result.rebake_required=list(required)
    if not required:
        result.rebake_ready=True
        result.ready_for_judge=True
        return result

    final=out_dir/"head_wrap_rebaked.glb"
    try:
        if base_rig is not None and base_rig.skin_count>0:
            from rig_preserving_rebake import (
                rebake_material_channels_preserve_rig,
            )
            rebake=rebake_material_channels_preserve_rig(
                base_mesh,
                raw,
                final,
                required=required,
                max_texture_size=texture_size,
                blender=blender,
            )
            result.rig_preserved=bool(rebake.rig_preserved)
            result.skin_weights_ready=bool(rebake.skin_weights_ready)
            result.skin_payload_preserved=bool(
                rebake.skin_payload_preserved
            )
        else:
            from material_rebake import rebake_material_channels
            rebake=rebake_material_channels(
                base_mesh,
                raw,
                final,
                required=required,
                max_texture_size=texture_size,
                blender=blender,
            )
        result.output_glb=str(final)
        result.rebake_resolved=list(rebake.resolved_channels)
        result.rebake_ready=not rebake.remaining_channels
        result.ready_for_judge=bool(
            result.geometry_ready
            and (result.rebake_ready or not require_rebake)
        )
        if rebake.error and not result.error:
            result.error=rebake.error
        if require_rebake and not result.rebake_ready and not result.error:
            result.error=(
                "head_wrap_material_rebake_incomplete:"
                + ",".join(rebake.remaining_channels)
            )
        return result
    except Exception as exc:
        result.output_glb=str(raw)
        result.rebake_ready=False
        result.ready_for_judge=not require_rebake
        result.error=f"rebake_failed:{type(exc).__name__}:{exc}"
        return result


def write_head_wrap_result(result:HeadWrapResult,path:Path)->Path:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(asdict(result),indent=2)+"\n",encoding="utf-8")
    return path


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(description="HAYUYA seam-aware head-wrap regional fusion.")
    parser.add_argument("--base",type=Path,required=True)
    parser.add_argument("--donor",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--texture-size",type=int,default=4096)
    parser.add_argument("--blender")
    parser.add_argument("--allow-unrebaked",action="store_true")
    args=parser.parse_args()
    result=prepare_head_wrap_challenger(
        args.base,args.donor,args.output_dir,
        texture_size=args.texture_size,
        blender=args.blender,
        require_rebake=not args.allow_unrebaked,
    )
    write_head_wrap_result(result,args.output_dir/"head_wrap_result.json")
    print(json.dumps(asdict(result),indent=2))
    return 0 if result.ready_for_judge else 2


if __name__=="__main__":
    raise SystemExit(main())
