#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class AccessorySwapResult:
    base_mesh:str
    donor_mesh:str
    output_glb:str
    ready:bool
    base_component_id:int|None
    donor_component_id:int|None
    confidence:float|None
    spatial_label:str|None
    alignment_scale:float|None
    centroid_correction_ratio:float|None
    bbox_drift_fraction:float|None
    output_components:int
    output_faces:int
    component_crossing_ready:bool
    self_intersection_ready:bool
    attachment_ready:bool
    attachment_floating_components:int
    attachment_oversized_floating_components:int
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-detached-accessory-swap-v1"


def _deps():
    import numpy as np
    import trimesh
    return np,trimesh


def _bbox(vertices):
    np,_=_deps()
    vv=np.asarray(vertices,dtype=np.float64)
    lo=np.min(vv,axis=0)
    hi=np.max(vv,axis=0)
    return lo,hi,(lo+hi)*0.5,hi-lo


def _runtime_payload_blocks_swap(path:Path)->list[str]:
    blockers=[]
    try:
        from gltf_audit import audit_glb
        audit=audit_glb(path)
        if audit.skin_count>0 or audit.skinned_mesh_nodes>0:
            blockers.append("skin")
        if audit.animation_count>0:
            blockers.append("animation")
        if audit.morph_target_count>0:
            blockers.append("morph_targets")
    except Exception as exc:
        blockers.append(
            f"runtime_audit_failed:{type(exc).__name__}:{exc}"
        )
    return blockers


def _submesh_for_component(mesh,component_ids,component_id:int):
    np,_=_deps()
    face_ids=np.flatnonzero(
        np.asarray(component_ids,dtype=np.int64)==int(component_id)
    )
    if not len(face_ids):
        raise ValueError(
            f"component {component_id} has no faces"
        )
    return mesh.submesh(
        [face_ids],
        append=True,
        repair=False,
    )


def swap_detached_accessory(
    base_mesh:Path,
    donor_mesh:Path,
    output_glb:Path,
    *,
    mode:str,
    base_up_axis:str="y",
    donor_up_axis:str|None=None,
    max_bbox_drift_fraction:float=0.15,
    max_centroid_correction_ratio:float=0.12,
)->AccessorySwapResult:
    np,trimesh=_deps()
    warnings=[]
    errors=[]
    donor_up_axis=donor_up_axis or base_up_axis

    base_blockers=_runtime_payload_blocks_swap(base_mesh)
    donor_blockers=_runtime_payload_blocks_swap(donor_mesh)
    if base_blockers or donor_blockers:
        blockers=[]
        if base_blockers:
            blockers.append(
                "base="+",".join(base_blockers)
            )
        if donor_blockers:
            blockers.append(
                "donor="+",".join(donor_blockers)
            )
        return AccessorySwapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            ready=False,
            base_component_id=None,
            donor_component_id=None,
            confidence=None,
            spatial_label=None,
            alignment_scale=None,
            centroid_correction_ratio=None,
            bbox_drift_fraction=None,
            output_components=0,
            output_faces=0,
            component_crossing_ready=False,
            self_intersection_ready=False,
            attachment_ready=False,
            attachment_floating_components=0,
            attachment_oversized_floating_components=0,
            warnings=[],
            errors=[
                "detached accessory swap requires runtime-payload-free "
                "base and donor until new-vertex weight/morph transfer exists: "
                +";".join(blockers)
            ],
        )

    try:
        from accessory_match import match_accessories
        from part_map import _component_ids,_load_mesh

        match_report=match_accessories(
            base_mesh,
            donor_mesh,
            mode=mode,
            base_up_axis=base_up_axis,
            donor_up_axis=donor_up_axis,
        )
        ready_matches=[
            item for item in match_report.matches
            if item.ready
        ]
        if not ready_matches:
            raise RuntimeError(
                "no unambiguous detached accessory correspondence passed"
            )
        selected=max(
            ready_matches,
            key=lambda item:float(item.confidence),
        )

        base=_load_mesh(base_mesh)
        donor=_load_mesh(donor_mesh)
        base_faces=np.asarray(base.faces,dtype=np.int64)
        donor_faces=np.asarray(donor.faces,dtype=np.int64)
        base_components=_component_ids(base_faces)
        donor_components=_component_ids(donor_faces)
        base_component_count=int(len(np.unique(base_components)))

        base_acc=_submesh_for_component(
            base,
            base_components,
            selected.base_component_id,
        )
        donor_acc=_submesh_for_component(
            donor,
            donor_components,
            selected.donor_component_id,
        )

        keep_faces=np.flatnonzero(
            base_components!=selected.base_component_id
        )
        if not len(keep_faces):
            raise RuntimeError(
                "accessory swap would remove all base geometry"
            )
        base_body=base.submesh(
            [keep_faces],
            append=True,
            repair=False,
        )

        _,_,base_center,base_extent=_bbox(base.vertices)
        _,_,donor_center,donor_extent=_bbox(donor.vertices)
        base_diag=max(
            float(np.linalg.norm(base_extent)),
            1e-9,
        )
        donor_diag=max(
            float(np.linalg.norm(donor_extent)),
            1e-9,
        )
        scale=base_diag/donor_diag

        donor_vertices=np.asarray(
            donor_acc.vertices,
            dtype=np.float64,
        )
        aligned=(
            (donor_vertices-donor_center)*scale
            +base_center
        )

        base_acc_centroid=np.mean(
            np.asarray(base_acc.vertices,dtype=np.float64),
            axis=0,
        )
        donor_acc_centroid=np.mean(aligned,axis=0)
        correction=base_acc_centroid-donor_acc_centroid
        correction_ratio=(
            float(np.linalg.norm(correction))/base_diag
        )
        if correction_ratio>max_centroid_correction_ratio:
            raise RuntimeError(
                "accessory centroid correction too large: "
                f"{correction_ratio:.6f}>"
                f"{max_centroid_correction_ratio:.6f}"
            )
        aligned+=correction
        donor_acc.vertices=aligned

        output_glb.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        scene=trimesh.Scene()
        scene.add_geometry(
            base_body,
            node_name="hayuya_base_body",
        )
        scene.add_geometry(
            donor_acc,
            node_name="hayuya_donor_accessory",
        )
        output_glb.write_bytes(
            trimesh.exchange.gltf.export_glb(scene)
        )
        if (
            not output_glb.is_file()
            or output_glb.read_bytes()[:4]!=b"glTF"
        ):
            raise RuntimeError(
                "accessory swap did not produce a valid GLB"
            )

        from qa import inspect_mesh
        output_qa=inspect_mesh(
            output_glb,
            backend="composite_accessory",
            mode=mode,
            target_faces=max(
                1,
                int(len(base.faces)),
            ),
        )
        _,_,_,output_extent=_bbox(
            _load_mesh(output_glb).vertices
        )
        bbox_drift=float(np.max(
            np.abs(output_extent-base_extent)
            /np.maximum(base_extent,base_diag*1e-6)
        ))
        if bbox_drift>max_bbox_drift_fraction:
            errors.append(
                "accessory swap bbox drift "
                f"{bbox_drift:.6f}>{max_bbox_drift_fraction:.6f}"
            )
        if not output_qa.valid:
            errors.append(
                "accessory swap output failed mesh QA"
            )
        if int(output_qa.components)!=base_component_count:
            errors.append(
                "accessory swap changed component cardinality: "
                f"{base_component_count}->{int(output_qa.components)}"
            )

        from component_crossing_qa import (
            audit_component_crossings,
        )
        crossing=audit_component_crossings(
            output_glb
        )
        if not crossing.ready:
            errors.append(
                "accessory swap introduced major component crossings"
            )

        from self_intersection_qa import (
            audit_self_intersections,
        )
        self_cross=audit_self_intersections(
            output_glb
        )
        if not self_cross.ready:
            errors.append(
                "accessory swap introduced self intersections"
            )

        from composite_attachment_qa import (
            audit_composite_attachments,
        )
        attachment=audit_composite_attachments(
            output_glb,
            mode=mode,
        )
        warnings.extend(attachment.warnings or [])
        if not attachment.ready:
            errors.append(
                "accessory swap introduced detached/floating "
                "component topology"
            )
            errors.extend(attachment.errors or [])

        return AccessorySwapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            ready=not errors,
            base_component_id=int(
                selected.base_component_id
            ),
            donor_component_id=int(
                selected.donor_component_id
            ),
            confidence=round(
                float(selected.confidence),6
            ),
            spatial_label=str(
                selected.spatial_label
            ),
            alignment_scale=round(
                float(scale),8
            ),
            centroid_correction_ratio=round(
                correction_ratio,8
            ),
            bbox_drift_fraction=round(
                bbox_drift,8
            ),
            output_components=int(
                output_qa.components
            ),
            output_faces=int(
                output_qa.faces
            ),
            component_crossing_ready=bool(
                crossing.ready
            ),
            self_intersection_ready=bool(
                self_cross.ready
            ),
            attachment_ready=bool(
                attachment.ready
            ),
            attachment_floating_components=int(
                attachment.floating_components
            ),
            attachment_oversized_floating_components=int(
                attachment.oversized_floating_components
            ),
            warnings=warnings,
            errors=errors,
        )
    except Exception as exc:
        return AccessorySwapResult(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            output_glb=str(output_glb),
            ready=False,
            base_component_id=None,
            donor_component_id=None,
            confidence=None,
            spatial_label=None,
            alignment_scale=None,
            centroid_correction_ratio=None,
            bbox_drift_fraction=None,
            output_components=0,
            output_faces=0,
            component_crossing_ready=False,
            self_intersection_ready=False,
            attachment_ready=False,
            attachment_floating_components=0,
            attachment_oversized_floating_components=0,
            warnings=warnings,
            errors=[
                f"{type(exc).__name__}:{exc}"
            ],
        )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description=(
            "HAYUYA unskinned detached accessory swap challenger. "
            "Skinned/animated/morph assets fail closed."
        )
    )
    parser.add_argument(
        "--base",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--donor",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--mode",
        choices=[
            "prop","character","architecture"
        ],
        required=True,
    )
    parser.add_argument(
        "--base-up-axis",
        choices=["x","y","z"],
        default="y",
    )
    parser.add_argument(
        "--donor-up-axis",
        choices=["x","y","z"],
    )
    parser.add_argument(
        "--json",
        type=Path,
    )
    args=parser.parse_args()
    result=swap_detached_accessory(
        args.base,
        args.donor,
        args.output,
        mode=args.mode,
        base_up_axis=args.base_up_axis,
        donor_up_axis=args.donor_up_axis,
    )
    payload=json.dumps(
        asdict(result),
        indent=2,
    )
    print(payload)
    if args.json:
        args.json.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.json.write_text(
            payload+"\n",
            encoding="utf-8",
        )
    return 0 if result.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
