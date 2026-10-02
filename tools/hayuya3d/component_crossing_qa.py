#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class ComponentCrossingPair:
    component_a:int
    component_b:int
    faces_a:int
    faces_b:int
    fraction_a:float
    fraction_b:float
    candidate_pairs:int
    crossing_pairs:int
    ready:bool
    errors:list[str]


@dataclass
class ComponentCrossingAudit:
    path:str
    applicable:bool
    ready:bool
    component_count:int
    large_component_count:int
    tested_pairs:int
    candidate_triangle_pairs:int
    crossing_triangle_pairs:int
    ignored_accessory_components:list[int]
    pairs:list[ComponentCrossingPair]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-large-component-surface-crossing-v1"


def _deps():
    import numpy as np
    return np


def _load(path:Path):
    from part_map import _component_ids,_load_mesh
    mesh=_load_mesh(path)
    np=_deps()
    vertices=np.asarray(mesh.vertices,dtype=np.float64)
    faces=np.asarray(mesh.faces,dtype=np.int64)
    ids=_component_ids(faces)
    return mesh,vertices,faces,ids


def _segment_triangle_crosses(
    p0,
    p1,
    tri,
    *,
    eps:float,
)->bool:
    np=_deps()
    direction=p1-p0
    v0,v1,v2=tri
    edge1=v1-v0
    edge2=v2-v0
    h=np.cross(direction,edge2)
    a=float(np.dot(edge1,h))
    if abs(a)<=eps:
        return False
    inv=1.0/a
    s=p0-v0
    u=inv*float(np.dot(s,h))
    if u<=eps or u>=1.0-eps:
        return False
    q=np.cross(s,edge1)
    v=inv*float(np.dot(direction,q))
    if v<=eps or u+v>=1.0-eps:
        return False
    t=inv*float(np.dot(edge2,q))
    # Interior of the segment only: endpoint contact is not a penetration.
    return eps<t<1.0-eps


def _triangles_cross(a,b,*,eps:float)->bool:
    for p0,p1 in ((a[0],a[1]),(a[1],a[2]),(a[2],a[0])):
        if _segment_triangle_crosses(p0,p1,b,eps=eps):
            return True
    for p0,p1 in ((b[0],b[1]),(b[1],b[2]),(b[2],b[0])):
        if _segment_triangle_crosses(p0,p1,a,eps=eps):
            return True
    return False


def _spatial_hash(
    triangles,
    global_min,
    cell_size,
    *,
    max_cells_per_triangle:int,
):
    np=_deps()
    table={}
    mins=np.min(triangles,axis=1)
    maxs=np.max(triangles,axis=1)
    for index,(lo,hi) in enumerate(zip(mins,maxs)):
        first=np.floor((lo-global_min)/cell_size).astype(np.int64)
        last=np.floor((hi-global_min)/cell_size).astype(np.int64)
        spans=(last-first+1)
        cells=int(spans[0]*spans[1]*spans[2])
        if cells>max_cells_per_triangle:
            return None,mins,maxs,(
                f"triangle {index} spans {cells} spatial cells; "
                f"limit={max_cells_per_triangle}"
            )
        for x in range(int(first[0]),int(last[0])+1):
            for y in range(int(first[1]),int(last[1])+1):
                for z in range(int(first[2]),int(last[2])+1):
                    table.setdefault((x,y,z),[]).append(index)
    return table,mins,maxs,None


def _candidate_pairs(
    tris_a,
    tris_b,
    *,
    max_candidate_pairs:int,
):
    np=_deps()
    all_points=np.concatenate([
        tris_a.reshape(-1,3),
        tris_b.reshape(-1,3),
    ],axis=0)
    global_min=np.min(all_points,axis=0)
    global_max=np.max(all_points,axis=0)
    extent=np.maximum(global_max-global_min,1e-9)
    target_cells=max(
        8,
        min(48,int(round((len(tris_a)+len(tris_b))**(1.0/3.0)*2.0))),
    )
    cell_size=np.maximum(extent/target_cells,1e-9)

    table,b_mins,b_maxs,error=_spatial_hash(
        tris_b,
        global_min,
        cell_size,
        max_cells_per_triangle=512,
    )
    if error:
        raise RuntimeError(error)
    a_mins=np.min(tris_a,axis=1)
    a_maxs=np.max(tris_a,axis=1)

    pairs=[]
    seen=set()
    for a_index,(lo,hi) in enumerate(zip(a_mins,a_maxs)):
        first=np.floor((lo-global_min)/cell_size).astype(np.int64)
        last=np.floor((hi-global_min)/cell_size).astype(np.int64)
        candidates=set()
        for x in range(int(first[0]),int(last[0])+1):
            for y in range(int(first[1]),int(last[1])+1):
                for z in range(int(first[2]),int(last[2])+1):
                    candidates.update(table.get((x,y,z),()))
        for b_index in candidates:
            key=(a_index,int(b_index))
            if key in seen:
                continue
            seen.add(key)
            if not (
                np.all(b_maxs[b_index]>=lo)
                and np.all(b_mins[b_index]<=hi)
            ):
                continue
            pairs.append(key)
            if len(pairs)>max_candidate_pairs:
                raise RuntimeError(
                    "surface-crossing candidate pair budget exceeded: "
                    f"{len(pairs)}>{max_candidate_pairs}"
                )
    return pairs


def audit_component_crossings(
    path:Path,
    *,
    min_face_fraction:float=0.08,
    max_candidate_pairs:int=250_000,
    max_reported_crossings:int=256,
)->ComponentCrossingAudit:
    np=_deps()
    warnings=[]
    errors=[]
    try:
        mesh,vertices,faces,component_ids=_load(path)
        unique,counts=np.unique(component_ids,return_counts=True)
    except Exception as exc:
        return ComponentCrossingAudit(
            path=str(path),applicable=False,ready=False,
            component_count=0,large_component_count=0,tested_pairs=0,
            candidate_triangle_pairs=0,crossing_triangle_pairs=0,
            ignored_accessory_components=[],pairs=[],warnings=[],
            errors=[f"{type(exc).__name__}:{exc}"],
        )

    total=max(len(faces),1)
    meta=[]
    ignored=[]
    for component_id,count in zip(unique,counts):
        fraction=float(count/total)
        face_ids=np.flatnonzero(component_ids==component_id)
        item={
            "id":int(component_id),
            "count":int(count),
            "fraction":fraction,
            "face_ids":face_ids,
        }
        if fraction<min_face_fraction:
            ignored.append(int(component_id))
        else:
            meta.append(item)

    if len(meta)<2:
        return ComponentCrossingAudit(
            path=str(path),
            applicable=False,
            ready=True,
            component_count=len(unique),
            large_component_count=len(meta),
            tested_pairs=0,
            candidate_triangle_pairs=0,
            crossing_triangle_pairs=0,
            ignored_accessory_components=ignored,
            pairs=[],
            warnings=warnings,
            errors=[],
        )

    diagonal=max(
        float(np.linalg.norm(
            np.max(vertices,axis=0)-np.min(vertices,axis=0)
        )),
        1e-9,
    )
    eps=max(diagonal*1e-9,1e-10)
    pair_reports=[]
    tested_pairs=0
    candidate_total=0
    crossing_total=0

    for ai in range(len(meta)):
        for bi in range(ai+1,len(meta)):
            a=meta[ai]
            b=meta[bi]
            tris_a=vertices[faces[a["face_ids"]]]
            tris_b=vertices[faces[b["face_ids"]]]

            a_lo=np.min(tris_a,axis=(0,1))
            a_hi=np.max(tris_a,axis=(0,1))
            b_lo=np.min(tris_b,axis=(0,1))
            b_hi=np.max(tris_b,axis=(0,1))
            overlap=np.minimum(a_hi,b_hi)-np.maximum(a_lo,b_lo)
            if np.any(overlap<=eps):
                continue

            tested_pairs+=1
            pair_errors=[]
            crossings=0
            candidates=[]
            try:
                candidates=_candidate_pairs(
                    tris_a,
                    tris_b,
                    max_candidate_pairs=max_candidate_pairs,
                )
                candidate_total+=len(candidates)
                for a_index,b_index in candidates:
                    if _triangles_cross(
                        tris_a[a_index],
                        tris_b[b_index],
                        eps=eps,
                    ):
                        crossings+=1
                        crossing_total+=1
                        if crossings>=max_reported_crossings:
                            pair_errors.append(
                                "crossing report truncated at "
                                f"{max_reported_crossings} triangle pairs"
                            )
                            break
            except Exception as exc:
                pair_errors.append(
                    f"{type(exc).__name__}:{exc}"
                )

            if crossings:
                pair_errors.append(
                    f"large component surfaces cross at {crossings} triangle pairs"
                )
            ready=not pair_errors
            if not ready:
                errors.extend(
                    f"components {a['id']}/{b['id']}: {item}"
                    for item in pair_errors
                )
            pair_reports.append(ComponentCrossingPair(
                component_a=a["id"],
                component_b=b["id"],
                faces_a=a["count"],
                faces_b=b["count"],
                fraction_a=round(a["fraction"],6),
                fraction_b=round(b["fraction"],6),
                candidate_pairs=len(candidates),
                crossing_pairs=crossings,
                ready=ready,
                errors=pair_errors,
            ))

    return ComponentCrossingAudit(
        path=str(path),
        applicable=True,
        ready=not errors,
        component_count=len(unique),
        large_component_count=len(meta),
        tested_pairs=tested_pairs,
        candidate_triangle_pairs=candidate_total,
        crossing_triangle_pairs=crossing_total,
        ignored_accessory_components=ignored,
        pairs=pair_reports,
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA large-component surface crossing QA."
    )
    parser.add_argument("mesh",type=Path)
    parser.add_argument("--json",type=Path)
    parser.add_argument("--min-face-fraction",type=float,default=0.08)
    args=parser.parse_args()
    report=audit_component_crossings(
        args.mesh,
        min_face_fraction=args.min_face_fraction,
    )
    payload=json.dumps(asdict(report),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
