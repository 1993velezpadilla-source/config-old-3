#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class AccessoryCandidate:
    component_id:int
    spatial_label:str
    face_count:int
    face_fraction:float
    normalized_centroid:list[float]
    normalized_extent:list[float]
    attachment_distance_ratio:float


@dataclass
class AccessoryMatch:
    base_component_id:int
    donor_component_id:int
    spatial_label:str
    confidence:float
    ambiguity_margin:float|None
    centroid_distance:float
    extent_log_distance:float
    attachment_delta:float
    face_fraction_log_distance:float
    ready:bool
    blockers:list[str]


@dataclass
class AccessoryMatchReport:
    base_mesh:str
    donor_mesh:str
    ready:bool
    base_accessories:int
    donor_accessories:int
    matches:list[AccessoryMatch]
    unmatched_base:list[int]
    unmatched_donor:list[int]
    ambiguous_base:list[int]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-detached-accessory-match-v1"


def _deps():
    import numpy as np
    from scipy.spatial import cKDTree
    return np,cKDTree


def _candidate_geometry(
    path:Path,
    *,
    mode:str,
    up_axis:str,
)->tuple[list[AccessoryCandidate],dict]:
    np,cKDTree=_deps()
    from part_map import _component_ids,_load_mesh,build_part_map

    mesh=_load_mesh(path)
    vertices=np.asarray(mesh.vertices,dtype=np.float64)
    faces=np.asarray(mesh.faces,dtype=np.int64)
    if not len(vertices) or not len(faces):
        raise ValueError("mesh has no triangle geometry")

    part_map=build_part_map(
        path,
        mode=mode,
        up_axis=up_axis,
    )
    component_ids=_component_ids(faces)
    component_by_id={
        int(item.component_id):item
        for item in part_map.components
    }
    main=next(
        (
            item for item in part_map.components
            if item.main_component
        ),
        None,
    )
    if main is None:
        raise RuntimeError("part map has no main component")

    main_face_mask=component_ids==int(main.component_id)
    main_vertices=np.unique(faces[main_face_mask].reshape(-1))
    main_points=vertices[main_vertices]
    if not len(main_points):
        raise RuntimeError("main component contains no vertices")
    main_tree=cKDTree(main_points)

    lo=np.min(vertices,axis=0)
    hi=np.max(vertices,axis=0)
    extent=hi-lo
    diagonal=max(float(np.linalg.norm(extent)),1e-9)
    safe_extent=np.maximum(extent,diagonal*1e-6)

    candidates=[]
    for component_id in part_map.accessory_component_ids:
        component=component_by_id.get(int(component_id))
        if component is None:
            continue
        mask=component_ids==int(component_id)
        used=np.unique(faces[mask].reshape(-1))
        vv=vertices[used]
        if not len(vv):
            continue
        centroid=np.mean(vv,axis=0)
        comp_extent=np.max(vv,axis=0)-np.min(vv,axis=0)
        distances,_=main_tree.query(vv,k=1,workers=-1)
        attachment=float(np.min(distances))/diagonal
        candidates.append(AccessoryCandidate(
            component_id=int(component_id),
            spatial_label=str(component.spatial_label),
            face_count=int(component.face_count),
            face_fraction=float(component.face_fraction),
            normalized_centroid=[
                round(float(x),8)
                for x in ((centroid-lo)/safe_extent)
            ],
            normalized_extent=[
                round(float(x),8)
                for x in (comp_extent/safe_extent)
            ],
            attachment_distance_ratio=round(attachment,8),
        ))

    meta={
        "vertices":int(len(vertices)),
        "faces":int(len(faces)),
        "diagonal":diagonal,
        "main_component_id":int(main.component_id),
    }
    return candidates,meta


def inspect_accessories(
    path:Path,
    *,
    mode:str,
    up_axis:str="y",
)->list[AccessoryCandidate]:
    candidates,_=_candidate_geometry(
        path,
        mode=mode,
        up_axis=up_axis,
    )
    return candidates


def _pair_metrics(
    base:AccessoryCandidate,
    donor:AccessoryCandidate,
)->tuple[float,float,float,float,float]:
    np,_=_deps()
    bc=np.asarray(base.normalized_centroid,dtype=np.float64)
    dc=np.asarray(donor.normalized_centroid,dtype=np.float64)
    centroid=float(np.linalg.norm(bc-dc))

    be=np.maximum(
        np.asarray(base.normalized_extent,dtype=np.float64),
        1e-5,
    )
    de=np.maximum(
        np.asarray(donor.normalized_extent,dtype=np.float64),
        1e-5,
    )
    extent=float(
        np.linalg.norm(np.log(de/be))/math.sqrt(3.0)
    )
    attachment=abs(
        float(base.attachment_distance_ratio)
        -float(donor.attachment_distance_ratio)
    )
    bf=max(float(base.face_fraction),1e-8)
    df=max(float(donor.face_fraction),1e-8)
    face=abs(math.log(df/bf))

    cost=(
        2.4*centroid
        +0.65*extent
        +1.3*attachment
        +0.15*face
    )
    confidence=max(0.0,min(1.0,1.0-cost))
    return confidence,centroid,extent,attachment,face


def match_accessories(
    base_mesh:Path,
    donor_mesh:Path,
    *,
    mode:str,
    base_up_axis:str="y",
    donor_up_axis:str|None=None,
    min_confidence:float=0.55,
    min_ambiguity_margin:float=0.08,
    max_centroid_distance:float=0.22,
    max_attachment_distance:float=0.18,
)->AccessoryMatchReport:
    donor_up_axis=donor_up_axis or base_up_axis
    warnings=[]
    errors=[]
    try:
        base,_=_candidate_geometry(
            base_mesh,
            mode=mode,
            up_axis=base_up_axis,
        )
        donor,_=_candidate_geometry(
            donor_mesh,
            mode=mode,
            up_axis=donor_up_axis,
        )
    except Exception as exc:
        return AccessoryMatchReport(
            base_mesh=str(base_mesh),
            donor_mesh=str(donor_mesh),
            ready=False,
            base_accessories=0,
            donor_accessories=0,
            matches=[],
            unmatched_base=[],
            unmatched_donor=[],
            ambiguous_base=[],
            warnings=[],
            errors=[f"{type(exc).__name__}:{exc}"],
        )

    if not base:
        warnings.append(
            "base has no detached accessory candidate to replace safely"
        )
    if not donor:
        warnings.append(
            "donor has no detached accessory candidate"
        )

    pair_rows=[]
    for b in base:
        rows=[]
        for d in donor:
            if d.spatial_label!=b.spatial_label:
                continue
            metrics=_pair_metrics(b,d)
            rows.append((metrics[0],d,metrics))
        rows.sort(key=lambda item:item[0],reverse=True)
        pair_rows.append((b,rows))

    provisional=[]
    ambiguous=[]
    for b,rows in pair_rows:
        if not rows:
            continue
        best_conf,best_d,best_metrics=rows[0]
        second_conf=rows[1][0] if len(rows)>1 else None
        margin=(
            best_conf-second_conf
            if second_conf is not None else None
        )
        blockers=[]
        if best_conf<min_confidence:
            blockers.append(
                f"confidence={best_conf:.4f}<{min_confidence:.4f}"
            )
        if best_metrics[1]>max_centroid_distance:
            blockers.append(
                "normalized centroid mismatch "
                f"{best_metrics[1]:.4f}>{max_centroid_distance:.4f}"
            )
        if (
            b.attachment_distance_ratio>max_attachment_distance
            or best_d.attachment_distance_ratio>max_attachment_distance
        ):
            blockers.append(
                "accessory is too detached from the main body for an "
                "automatic attachment-preserving replacement"
            )
        if (
            margin is not None
            and margin<min_ambiguity_margin
        ):
            blockers.append(
                f"ambiguous donor margin={margin:.4f}"
                f"<{min_ambiguity_margin:.4f}"
            )
            ambiguous.append(b.component_id)

        provisional.append((
            best_conf,
            b,
            best_d,
            best_metrics,
            margin,
            blockers,
        ))

    # One donor component may not satisfy two base components. Resolve strongest
    # unambiguous pair first and fail the weaker duplicate rather than guessing.
    provisional.sort(key=lambda row:row[0],reverse=True)
    used_donors=set()
    matches=[]
    for conf,b,d,metrics,margin,blockers in provisional:
        blockers=list(blockers)
        if d.component_id in used_donors:
            blockers.append(
                "donor component already matched to a stronger base component"
            )
        ready=not blockers
        if ready:
            used_donors.add(d.component_id)
        matches.append(AccessoryMatch(
            base_component_id=b.component_id,
            donor_component_id=d.component_id,
            spatial_label=b.spatial_label,
            confidence=round(float(conf),6),
            ambiguity_margin=(
                None if margin is None else round(float(margin),6)
            ),
            centroid_distance=round(float(metrics[1]),6),
            extent_log_distance=round(float(metrics[2]),6),
            attachment_delta=round(float(metrics[3]),6),
            face_fraction_log_distance=round(float(metrics[4]),6),
            ready=ready,
            blockers=blockers,
        ))

    matched_base={
        item.base_component_id
        for item in matches
        if item.ready
    }
    matched_donor={
        item.donor_component_id
        for item in matches
        if item.ready
    }
    unmatched_base=sorted(
        item.component_id
        for item in base
        if item.component_id not in matched_base
    )
    unmatched_donor=sorted(
        item.component_id
        for item in donor
        if item.component_id not in matched_donor
    )
    ready_matches=[item for item in matches if item.ready]

    return AccessoryMatchReport(
        base_mesh=str(base_mesh),
        donor_mesh=str(donor_mesh),
        ready=bool(ready_matches),
        base_accessories=len(base),
        donor_accessories=len(donor),
        matches=matches,
        unmatched_base=unmatched_base,
        unmatched_donor=unmatched_donor,
        ambiguous_base=sorted(set(ambiguous)),
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description=(
            "HAYUYA detached accessory correspondence QA. "
            "This proves replacement correspondence; it does not perform a swap."
        )
    )
    parser.add_argument("--base",type=Path,required=True)
    parser.add_argument("--donor",type=Path,required=True)
    parser.add_argument(
        "--mode",
        choices=["prop","character","architecture"],
        required=True,
    )
    parser.add_argument("--base-up-axis",choices=["x","y","z"],default="y")
    parser.add_argument("--donor-up-axis",choices=["x","y","z"])
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    result=match_accessories(
        args.base,
        args.donor,
        mode=args.mode,
        base_up_axis=args.base_up_axis,
        donor_up_axis=args.donor_up_axis,
    )
    payload=json.dumps(asdict(result),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if result.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
