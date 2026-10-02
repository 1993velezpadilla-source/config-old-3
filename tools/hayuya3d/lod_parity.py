#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class LODParityItem:
    name:str
    path:str
    ready:bool
    shape_p95_distance_ratio:float
    shape_max_distance_ratio:float
    bbox_extent_ratio_min:float
    bbox_extent_ratio_max:float
    components:int
    faces:int
    missing_material_channels:list[str]
    attachment_ready:bool
    attachment_components:int
    attachment_accessories:int
    attachment_floating_components:int
    attachment_accessory_retention_ready:bool
    rig_required:bool
    rig_ready:bool
    morph_required:bool
    morph_ready:bool|None
    morph_target_count:int
    skin_weights_ready:bool|None
    animation_integrity_ready:bool|None
    deformation_ready:bool|None
    errors:list[str]


@dataclass
class LODParityReport:
    master:str
    ready:bool
    lod_count:int
    items:list[LODParityItem]
    face_chain_monotonic:bool
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-lod-parity-qa-v1"


def _deps():
    import numpy as np
    import trimesh
    from scipy.spatial import cKDTree
    return np,trimesh,cKDTree


def _combined_mesh(path:Path):
    np,trimesh,_=_deps()
    from material_bridge import _scene_meshes
    meshes=_scene_meshes(path)
    return trimesh.util.concatenate(meshes)


def _deterministic_surface_samples(mesh,count:int,seed:int):
    np,trimesh,_=_deps()
    state=np.random.get_state()
    try:
        np.random.seed(int(seed)&0xFFFFFFFF)
        points,_=trimesh.sample.sample_surface(
            mesh,max(128,int(count))
        )
        return np.asarray(points,dtype=np.float64)
    finally:
        np.random.set_state(state)


def _shape_distance(
    master_mesh,
    lod_mesh,
    *,
    samples:int,
)->tuple[float,float]:
    np,_,cKDTree=_deps()
    master_points=_deterministic_surface_samples(
        master_mesh,samples,1337
    )
    lod_points=_deterministic_surface_samples(
        lod_mesh,samples,7331
    )
    master_extent=np.asarray(
        master_mesh.bounds[1]-master_mesh.bounds[0],
        dtype=np.float64,
    )
    diagonal=max(float(np.linalg.norm(master_extent)),1e-9)

    master_tree=cKDTree(master_points)
    lod_tree=cKDTree(lod_points)
    d_lod_to_master,_=master_tree.query(
        lod_points,k=1,workers=-1
    )
    d_master_to_lod,_=lod_tree.query(
        master_points,k=1,workers=-1
    )
    distances=np.concatenate([
        np.asarray(d_lod_to_master,dtype=np.float64),
        np.asarray(d_master_to_lod,dtype=np.float64),
    ])/diagonal
    return (
        float(np.percentile(distances,95.0)),
        float(np.max(distances)),
    )


def compare_lod(
    master:Path,
    lod:Path,
    *,
    name:str|None=None,
    mode:str="prop",
    samples:int=6000,
    max_shape_p95_ratio:float=0.075,
    min_bbox_extent_ratio:float=0.70,
    max_bbox_extent_ratio:float=1.30,
)->LODParityItem:
    np,_,_=_deps()
    errors=[]
    try:
        master_mesh=_combined_mesh(master)
        lod_mesh=_combined_mesh(lod)
        p95,max_dist=_shape_distance(
            master_mesh,lod_mesh,samples=samples
        )

        master_extent=np.asarray(
            master_mesh.bounds[1]-master_mesh.bounds[0],
            dtype=np.float64,
        )
        lod_extent=np.asarray(
            lod_mesh.bounds[1]-lod_mesh.bounds[0],
            dtype=np.float64,
        )
        valid_axes=master_extent>1e-9
        ratios=lod_extent[valid_axes]/master_extent[valid_axes]
        ratio_min=float(np.min(ratios)) if len(ratios) else 0.0
        ratio_max=float(np.max(ratios)) if len(ratios) else 0.0

        from qa import inspect_mesh
        master_qa=inspect_mesh(
            master,
            backend="lod_parity_master",
            mode=mode,
            target_faces=max(1,len(master_mesh.faces)),
        )
        lod_qa=inspect_mesh(
            lod,
            backend="lod_parity_lod",
            mode=mode,
            target_faces=max(1,len(lod_mesh.faces)),
        )
        required_channels=set(master_qa.pbr_channels or [])
        actual_channels=set(lod_qa.pbr_channels or [])
        missing=sorted(required_channels-actual_channels)

        if p95>max_shape_p95_ratio:
            errors.append(
                f"shape p95 drift {p95:.6f} > {max_shape_p95_ratio:.6f}"
            )
        if ratio_min<min_bbox_extent_ratio:
            errors.append(
                f"bbox extent collapse {ratio_min:.6f} < {min_bbox_extent_ratio:.6f}"
            )
        if ratio_max>max_bbox_extent_ratio:
            errors.append(
                f"bbox extent expansion {ratio_max:.6f} > {max_bbox_extent_ratio:.6f}"
            )
        if missing:
            errors.append(
                "material channels lost: "+",".join(missing)
            )
        if not lod_qa.valid:
            errors.append("LOD inspect_mesh validation failed")

        from composite_attachment_qa import audit_composite_attachments
        master_attachment=audit_composite_attachments(
            master,
            mode=mode,
        )
        lod_attachment=audit_composite_attachments(
            lod,
            mode=mode,
        )
        attachment_ready=bool(
            lod_attachment.applicable
            and lod_attachment.ready
        )
        if not attachment_ready:
            errors.append(
                "LOD composite attachment QA failed: "
                +"; ".join(lod_attachment.errors[:3])
            )

        lod0=bool(
            str(name or lod.stem).strip().upper().startswith("LOD0")
        )
        attachment_accessory_retention_ready=bool(
            not lod0
            or int(lod_attachment.accessory_candidates)
                >=int(master_attachment.accessory_candidates)
        )
        if not attachment_accessory_retention_ready:
            errors.append(
                "LOD0 lost detached accessory candidates: "
                f"master={master_attachment.accessory_candidates} "
                f"lod={lod_attachment.accessory_candidates}"
            )

        from gltf_audit import audit_glb
        master_rig=audit_glb(master)
        lod_rig=audit_glb(lod)
        rig_required=bool(master_rig.skin_count>0)
        morph_required=bool(master_rig.morph_target_count>0)
        morph_ready=(
            bool(
                lod_rig.morph_ready
                and lod_rig.morph_target_count==master_rig.morph_target_count
                and lod_rig.morph_mesh_count==master_rig.morph_mesh_count
                and lod_rig.morph_primitive_count==master_rig.morph_primitive_count
            )
            if morph_required else None
        )
        if morph_required and not morph_ready:
            errors.append(
                "LOD morph/blendshape payload does not match Hero Master: "
                f"master={master_rig.morph_target_count} "
                f"lod={lod_rig.morph_target_count}"
            )
        skin_weights_ready=None
        animation_ready=None
        deformation_ready=None
        rig_ready=bool(
            not rig_required
            or (
                lod_rig.rig_ready
                and lod_rig.skin_count==master_rig.skin_count
                and lod_rig.joint_count==master_rig.joint_count
                and lod_rig.animation_count==master_rig.animation_count
            )
        )
        if rig_required:
            if not rig_ready:
                errors.append(
                    "LOD rig/skin/joint/animation structure does not match master"
                )
            try:
                from skin_weight_qa import audit_skin_weights
                skin=audit_skin_weights(lod)
                skin_weights_ready=bool(
                    skin.applicable and skin.ready
                )
            except Exception:
                skin_weights_ready=False
            if not skin_weights_ready:
                errors.append("LOD skin-weight QA failed")

            try:
                from animation_qa import audit_animation
                animation=audit_animation(lod)
                animation_ready=bool(
                    animation.applicable and animation.ready
                )
            except Exception:
                animation_ready=False
            if not animation_ready:
                errors.append("LOD animation-integrity QA failed")

            try:
                from deformation_qa import audit_deformation
                deformation=audit_deformation(
                    lod,max_frames_per_animation=6
                )
                deformation_ready=bool(
                    deformation.applicable
                    and deformation.ready
                )
            except Exception:
                deformation_ready=False
            if not deformation_ready:
                errors.append("LOD deformation QA failed")

        return LODParityItem(
            name=name or lod.stem,
            path=str(lod),
            ready=not errors,
            shape_p95_distance_ratio=round(p95,6),
            shape_max_distance_ratio=round(max_dist,6),
            bbox_extent_ratio_min=round(ratio_min,6),
            bbox_extent_ratio_max=round(ratio_max,6),
            components=int(lod_qa.components),
            faces=int(lod_qa.faces),
            missing_material_channels=missing,
            attachment_ready=attachment_ready,
            attachment_components=int(
                lod_attachment.component_count
            ),
            attachment_accessories=int(
                lod_attachment.accessory_candidates
            ),
            attachment_floating_components=int(
                lod_attachment.floating_components
            ),
            attachment_accessory_retention_ready=(
                attachment_accessory_retention_ready
            ),
            rig_required=rig_required,
            rig_ready=rig_ready,
            morph_required=morph_required,
            morph_ready=morph_ready,
            morph_target_count=int(lod_rig.morph_target_count or 0),
            skin_weights_ready=skin_weights_ready,
            animation_integrity_ready=animation_ready,
            deformation_ready=deformation_ready,
            errors=errors,
        )
    except Exception as exc:
        return LODParityItem(
            name=name or lod.stem,
            path=str(lod),
            ready=False,
            shape_p95_distance_ratio=0.0,
            shape_max_distance_ratio=0.0,
            bbox_extent_ratio_min=0.0,
            bbox_extent_ratio_max=0.0,
            components=0,
            faces=0,
            missing_material_channels=[],
            attachment_ready=False,
            attachment_components=0,
            attachment_accessories=0,
            attachment_floating_components=0,
            attachment_accessory_retention_ready=False,
            rig_required=False,
            rig_ready=False,
            morph_required=False,
            morph_ready=None,
            morph_target_count=0,
            skin_weights_ready=None,
            animation_integrity_ready=None,
            deformation_ready=None,
            errors=[f"{type(exc).__name__}:{exc}"],
        )


def audit_lod_chain(
    master:Path,
    lods:Iterable[Path|tuple[str,Path]],
    *,
    mode:str="prop",
    samples:int=6000,
)->LODParityReport:
    items=[]
    for index,item in enumerate(lods):
        if isinstance(item,tuple):
            name,path=item
        else:
            path=Path(item)
            name=f"LOD{index}"
        items.append(compare_lod(
            master,
            Path(path),
            name=str(name),
            mode=mode,
            samples=samples,
        ))

    faces=[item.faces for item in items if item.faces>0]
    monotonic=all(
        a>=b for a,b in zip(faces,faces[1:])
    )
    errors=[]
    if not monotonic:
        errors.append(
            "LOD face counts are not monotonically non-increasing"
        )
    for item in items:
        if not item.ready:
            errors.append(
                f"{item.name} parity failed: "
                +"; ".join(item.errors)
            )
    warnings=[]
    if not items:
        errors.append("LOD chain is empty")

    return LODParityReport(
        master=str(master),
        ready=bool(items and monotonic and all(x.ready for x in items)),
        lod_count=len(items),
        items=items,
        face_chain_monotonic=monotonic,
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA Hero Master vs runtime LOD parity QA."
    )
    parser.add_argument("--master",type=Path,required=True)
    parser.add_argument("--lod",action="append",type=Path,default=[])
    parser.add_argument(
        "--mode",
        choices=["prop","character","architecture"],
        default="prop",
    )
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    report=audit_lod_chain(
        args.master,args.lod,mode=args.mode
    )
    payload=json.dumps(asdict(report),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
