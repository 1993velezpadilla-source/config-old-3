#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class SelfIntersectionComponent:
    component_id:int
    face_count:int
    face_fraction:float
    candidate_pairs:int
    tested_pairs:int
    crossing_pairs:int
    ready:bool
    errors:list[str]


@dataclass
class SelfIntersectionAudit:
    path:str
    applicable:bool
    ready:bool
    component_count:int
    audited_component_count:int
    candidate_triangle_pairs:int
    tested_triangle_pairs:int
    crossing_triangle_pairs:int
    ignored_small_components:list[int]
    components:list[SelfIntersectionComponent]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-intra-component-self-intersection-v1"


def _deps():
    import numpy as np
    return np


def audit_self_intersections(
    path:Path,
    *,
    min_face_fraction:float=0.08,
    max_candidate_pairs:int=500_000,
    max_crossings_per_component:int=256,
)->SelfIntersectionAudit:
    np=_deps()
    warnings=[]
    errors=[]
    try:
        from part_map import _component_ids,_load_mesh
        from component_crossing_qa import (
            _candidate_pairs,
            _triangles_cross,
        )
        mesh=_load_mesh(path)
        vertices=np.asarray(mesh.vertices,dtype=np.float64)
        faces=np.asarray(mesh.faces,dtype=np.int64)
        component_ids=_component_ids(faces)
        unique,counts=np.unique(component_ids,return_counts=True)
    except Exception as exc:
        return SelfIntersectionAudit(
            path=str(path),applicable=False,ready=False,
            component_count=0,audited_component_count=0,
            candidate_triangle_pairs=0,tested_triangle_pairs=0,
            crossing_triangle_pairs=0,ignored_small_components=[],
            components=[],warnings=[],
            errors=[f"{type(exc).__name__}:{exc}"],
        )

    if not len(faces):
        return SelfIntersectionAudit(
            path=str(path),applicable=False,ready=False,
            component_count=0,audited_component_count=0,
            candidate_triangle_pairs=0,tested_triangle_pairs=0,
            crossing_triangle_pairs=0,ignored_small_components=[],
            components=[],warnings=[],
            errors=["mesh contains no faces"],
        )

    diagonal=max(
        float(np.linalg.norm(
            np.max(vertices,axis=0)-np.min(vertices,axis=0)
        )),
        1e-9,
    )
    eps=max(diagonal*1e-9,1e-10)
    total=max(len(faces),1)
    ignored=[]
    reports=[]
    candidate_total=0
    tested_total=0
    crossing_total=0

    for component_id,count in zip(unique,counts):
        fraction=float(count/total)
        if fraction<min_face_fraction:
            ignored.append(int(component_id))
            continue

        global_face_ids=np.flatnonzero(component_ids==component_id)
        component_faces=faces[global_face_ids]
        triangles=vertices[component_faces]
        pair_errors=[]
        candidates=[]
        tested=0
        crossings=0
        try:
            raw_candidates=_candidate_pairs(
                triangles,
                triangles,
                max_candidate_pairs=max_candidate_pairs*2,
            )
            seen=set()
            for a,b in raw_candidates:
                a=int(a)
                b=int(b)
                if a==b:
                    continue
                pair=(min(a,b),max(a,b))
                if pair in seen:
                    continue
                seen.add(pair)
                # Adjacent faces intentionally meet at shared vertices/edges.
                if set(component_faces[pair[0]].tolist()) & set(
                    component_faces[pair[1]].tolist()
                ):
                    continue
                candidates.append(pair)
                if len(candidates)>max_candidate_pairs:
                    raise RuntimeError(
                        "self-intersection candidate pair budget exceeded: "
                        f"{len(candidates)}>{max_candidate_pairs}"
                    )

            candidate_total+=len(candidates)
            for a,b in candidates:
                tested+=1
                tested_total+=1
                if _triangles_cross(
                    triangles[a],
                    triangles[b],
                    eps=eps,
                ):
                    crossings+=1
                    crossing_total+=1
                    if crossings>=max_crossings_per_component:
                        pair_errors.append(
                            "crossing report truncated at "
                            f"{max_crossings_per_component} triangle pairs"
                        )
                        break
        except Exception as exc:
            pair_errors.append(
                f"{type(exc).__name__}:{exc}"
            )

        if crossings:
            pair_errors.append(
                f"component surface self-intersects at {crossings} triangle pairs"
            )
        ready=not pair_errors
        if not ready:
            errors.extend(
                f"component {int(component_id)}: {item}"
                for item in pair_errors
            )
        reports.append(SelfIntersectionComponent(
            component_id=int(component_id),
            face_count=int(count),
            face_fraction=round(fraction,6),
            candidate_pairs=len(candidates),
            tested_pairs=tested,
            crossing_pairs=crossings,
            ready=ready,
            errors=pair_errors,
        ))

    applicable=bool(reports)
    return SelfIntersectionAudit(
        path=str(path),
        applicable=applicable,
        ready=not errors,
        component_count=len(unique),
        audited_component_count=len(reports),
        candidate_triangle_pairs=candidate_total,
        tested_triangle_pairs=tested_total,
        crossing_triangle_pairs=crossing_total,
        ignored_small_components=ignored,
        components=reports,
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA intra-component surface self-intersection QA."
    )
    parser.add_argument("mesh",type=Path)
    parser.add_argument("--json",type=Path)
    parser.add_argument("--min-face-fraction",type=float,default=0.08)
    args=parser.parse_args()
    report=audit_self_intersections(
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
