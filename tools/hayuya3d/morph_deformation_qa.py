#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class MorphPoseAudit:
    mesh_index:int
    primitive_index:int
    source:str
    time:float|None
    max_displacement_ratio:float
    bounds_ratio:float
    nonfinite_vertices:int
    ready:bool
    errors:list[str]


@dataclass
class MorphDeformationAudit:
    path:str
    applicable:bool
    ready:bool
    morph_meshes:int
    morph_primitives:int
    morph_targets:int
    sampled_poses:int
    nonfinite_vertices:int
    catastrophic_poses:int
    max_displacement_ratio:float
    max_bounds_ratio:float
    min_bounds_ratio:float
    poses:list[MorphPoseAudit]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-morph-deformation-qa-v1"


def _deps():
    import numpy as np
    return np


def _read(path:Path):
    from skin_weight_qa import _read_glb,_read_accessor
    doc,binary=_read_glb(path)
    return doc,binary,_read_accessor


def _finite_array(rows,*,label:str):
    np=_deps()
    arr=np.asarray(rows,dtype=np.float64)
    if not np.isfinite(arr).all():
        raise ValueError(f"{label} contains non-finite values")
    return arr


def _base_positions(doc,binary,read_accessor,primitive,*,label:str):
    attrs=primitive.get("attributes") or {}
    index=attrs.get("POSITION")
    if not isinstance(index,int):
        raise ValueError(f"{label} missing POSITION accessor")
    arr=_finite_array(
        read_accessor(doc,binary,index),
        label=f"{label}.POSITION",
    )
    if arr.ndim!=2 or arr.shape[1]!=3:
        raise ValueError(f"{label}.POSITION is not VEC3")
    return arr


def _target_position_deltas(
    doc,
    binary,
    read_accessor,
    primitive,
    vertex_count:int,
    *,
    label:str,
):
    np=_deps()
    out=[]
    for target_index,target in enumerate(primitive.get("targets") or []):
        if not isinstance(target,dict):
            raise ValueError(
                f"{label}.target[{target_index}] is malformed"
            )
        accessor=target.get("POSITION")
        if accessor is None:
            out.append(np.zeros((vertex_count,3),dtype=np.float64))
            continue
        if not isinstance(accessor,int):
            raise ValueError(
                f"{label}.target[{target_index}].POSITION accessor invalid"
            )
        arr=_finite_array(
            read_accessor(doc,binary,accessor),
            label=f"{label}.target[{target_index}].POSITION",
        )
        if arr.shape!=(vertex_count,3):
            raise ValueError(
                f"{label}.target[{target_index}] POSITION shape "
                f"{arr.shape} != {(vertex_count,3)}"
            )
        out.append(arr)
    return out


def _mesh_target_count(mesh:dict)->int:
    counts=[
        len(primitive.get("targets") or [])
        for primitive in mesh.get("primitives") or []
    ]
    return max(counts,default=0)


def _default_weights(mesh:dict,node:dict|None,count:int)->list[float]:
    raw=(
        (node or {}).get("weights")
        if node is not None and (node or {}).get("weights") is not None
        else mesh.get("weights")
    )
    if raw is None:
        return [0.0]*count
    if len(raw)!=count:
        raise ValueError(
            f"default morph weight count {len(raw)} != target count {count}"
        )
    values=[float(x) for x in raw]
    if not all(math.isfinite(x) for x in values):
        raise ValueError("default morph weights contain non-finite values")
    return values


def _weight_sampler(
    path:Path,
    doc:dict,
    binary:bytes,
    read_accessor,
    sampler:dict,
    target_count:int,
):
    np=_deps()
    input_index=sampler.get("input")
    output_index=sampler.get("output")
    if not isinstance(input_index,int) or not isinstance(output_index,int):
        raise ValueError("morph animation sampler has invalid accessor index")

    times_arr=_finite_array(
        read_accessor(doc,binary,input_index),
        label="morph animation input",
    ).reshape(-1)
    if len(times_arr)<1:
        raise ValueError("morph animation has no timestamps")
    times=[float(x) for x in times_arr]
    if any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError("morph animation timestamps are not strictly increasing")

    raw=_finite_array(
        read_accessor(doc,binary,output_index),
        label="morph animation output",
    ).reshape(-1)
    interpolation=str(sampler.get("interpolation") or "LINEAR").upper()
    if interpolation not in {"LINEAR","STEP","CUBICSPLINE"}:
        raise ValueError(
            f"unsupported morph interpolation: {interpolation}"
        )

    multiplier=3 if interpolation=="CUBICSPLINE" else 1
    expected=len(times)*target_count*multiplier
    if len(raw)!=expected:
        raise ValueError(
            "morph animation output scalar count mismatch: "
            f"{len(raw)} != {expected} "
            f"(keys={len(times)} targets={target_count} interpolation={interpolation})"
        )

    if interpolation=="CUBICSPLINE":
        chunks=raw.reshape((len(times),3,target_count))
        in_tangents=chunks[:,0,:]
        values=chunks[:,1,:]
        out_tangents=chunks[:,2,:]
    else:
        values=raw.reshape((len(times),target_count))
        in_tangents=None
        out_tangents=None

    samples=[]
    for key,time in enumerate(times):
        samples.append((float(time),values[key].copy(),f"key[{key}]"))

    if interpolation=="CUBICSPLINE" and len(times)>1:
        for key in range(len(times)-1):
            dt=times[key+1]-times[key]
            p0=values[key]
            p1=values[key+1]
            m0=out_tangents[key]
            m1=in_tangents[key+1]
            # Sample every eighth of the Hermite interval. Sparse quarter-point
            # probes can miss narrow tangent-driven overshoot between keys.
            for step in (0.125,0.25,0.375,0.5,0.625,0.75,0.875):
                s=float(step)
                h00=2*s**3-3*s**2+1
                h10=s**3-2*s**2+s
                h01=-2*s**3+3*s**2
                h11=s**3-s**2
                value=(
                    h00*p0
                    +h10*dt*m0
                    +h01*p1
                    +h11*dt*m1
                )
                time=times[key]+s*dt
                samples.append((
                    float(time),
                    value,
                    f"cubic[{key}]@{s:.2f}",
                ))
    elif interpolation=="LINEAR" and len(times)>1:
        for key in range(len(times)-1):
            samples.append((
                (times[key]+times[key+1])*0.5,
                (values[key]+values[key+1])*0.5,
                f"linear[{key}]@0.50",
            ))

    return samples


def _pose_metrics(
    base,
    deltas,
    weights,
    *,
    catastrophic_displacement_ratio:float,
    catastrophic_bounds_ratio:float,
):
    np=_deps()
    weights=np.asarray(weights,dtype=np.float64)
    if not np.isfinite(weights).all():
        return 0.0,float("inf"),len(base),[
            "morph weights contain non-finite values"
        ]

    morphed=np.asarray(base,dtype=np.float64).copy()
    for target_index,delta in enumerate(deltas):
        morphed+=float(weights[target_index])*delta

    finite=np.isfinite(morphed).all(axis=1)
    nonfinite=int(np.count_nonzero(~finite))
    errors=[]
    if nonfinite:
        errors.append(f"non-finite morphed vertices: {nonfinite}")
    if not np.any(finite):
        return float("inf"),float("inf"),nonfinite,errors

    base_lo=np.min(base,axis=0)
    base_hi=np.max(base,axis=0)
    base_diag=max(float(np.linalg.norm(base_hi-base_lo)),1e-9)
    valid=morphed[finite]
    lo=np.min(valid,axis=0)
    hi=np.max(valid,axis=0)
    bounds_ratio=float(np.linalg.norm(hi-lo))/base_diag

    displacement=np.linalg.norm(
        valid-np.asarray(base,dtype=np.float64)[finite],
        axis=1,
    )/base_diag
    max_disp=float(np.max(displacement)) if len(displacement) else 0.0

    if max_disp>catastrophic_displacement_ratio:
        errors.append(
            "morph displacement explosion: "
            f"{max_disp:.6f}>{catastrophic_displacement_ratio:.6f}"
        )
    if bounds_ratio>catastrophic_bounds_ratio:
        errors.append(
            "morph bounds explosion: "
            f"{bounds_ratio:.6f}>{catastrophic_bounds_ratio:.6f}"
        )
    if bounds_ratio<1.0/catastrophic_bounds_ratio:
        errors.append(
            "morph bounds collapse: "
            f"{bounds_ratio:.6f}<{1.0/catastrophic_bounds_ratio:.6f}"
        )

    return max_disp,bounds_ratio,nonfinite,errors


def audit_morph_deformation(
    path:Path,
    *,
    catastrophic_target_delta_ratio:float=2.0,
    catastrophic_displacement_ratio:float=5.0,
    catastrophic_bounds_ratio:float=20.0,
)->MorphDeformationAudit:
    np=_deps()
    warnings=[]
    errors=[]
    poses=[]
    try:
        doc,binary,read_accessor=_read(path)
    except Exception as exc:
        return MorphDeformationAudit(
            path=str(path),applicable=False,ready=False,
            morph_meshes=0,morph_primitives=0,morph_targets=0,
            sampled_poses=0,nonfinite_vertices=0,catastrophic_poses=0,
            max_displacement_ratio=0.0,max_bounds_ratio=0.0,
            min_bounds_ratio=0.0,poses=[],warnings=[],
            errors=[f"{type(exc).__name__}:{exc}"],
        )

    meshes=doc.get("meshes") or []
    nodes=doc.get("nodes") or []
    animations=doc.get("animations") or []
    mesh_nodes={}
    for node_index,node in enumerate(nodes):
        mesh_index=node.get("mesh")
        if isinstance(mesh_index,int):
            mesh_nodes.setdefault(mesh_index,[]).append((node_index,node))

    primitive_data={}
    morph_meshes=0
    morph_primitives=0
    morph_targets=0

    try:
        for mesh_index,mesh in enumerate(meshes):
            target_count=_mesh_target_count(mesh)
            if target_count<=0:
                continue
            morph_meshes+=1
            morph_targets+=target_count
            for primitive_index,primitive in enumerate(mesh.get("primitives") or []):
                targets=primitive.get("targets") or []
                if not targets:
                    continue
                morph_primitives+=1
                label=f"mesh[{mesh_index}].primitive[{primitive_index}]"
                base=_base_positions(
                    doc,binary,read_accessor,primitive,label=label
                )
                deltas=_target_position_deltas(
                    doc,binary,read_accessor,primitive,len(base),label=label
                )
                if len(deltas)!=target_count:
                    raise ValueError(
                        f"{label} target count {len(deltas)} != mesh target count {target_count}"
                    )

                base_lo=np.min(base,axis=0)
                base_hi=np.max(base,axis=0)
                base_diag=max(float(np.linalg.norm(base_hi-base_lo)),1e-9)
                for target_index,delta in enumerate(deltas):
                    max_delta=float(np.max(np.linalg.norm(delta,axis=1)))/base_diag
                    if max_delta>catastrophic_target_delta_ratio:
                        errors.append(
                            f"{label}.target[{target_index}] delta explosion "
                            f"{max_delta:.6f}>{catastrophic_target_delta_ratio:.6f}"
                        )

                primitive_data[(mesh_index,primitive_index)]=(
                    base,deltas,target_count
                )

                node_options=mesh_nodes.get(mesh_index) or [(None,None)]
                for node_index,node in node_options:
                    defaults=_default_weights(mesh,node,target_count)
                    max_disp,bounds,nonfinite,pose_errors=_pose_metrics(
                        base,deltas,defaults,
                        catastrophic_displacement_ratio=catastrophic_displacement_ratio,
                        catastrophic_bounds_ratio=catastrophic_bounds_ratio,
                    )
                    poses.append(MorphPoseAudit(
                        mesh_index=mesh_index,
                        primitive_index=primitive_index,
                        source=(
                            f"default_node[{node_index}]"
                            if node_index is not None else "default_mesh"
                        ),
                        time=None,
                        max_displacement_ratio=round(max_disp,6),
                        bounds_ratio=round(bounds,6),
                        nonfinite_vertices=nonfinite,
                        ready=not pose_errors,
                        errors=pose_errors,
                    ))

                # Every morph target gets a unit-weight structural probe even
                # when no animation currently drives it.
                for target_index in range(target_count):
                    weights=np.zeros(target_count,dtype=np.float64)
                    weights[target_index]=1.0
                    max_disp,bounds,nonfinite,pose_errors=_pose_metrics(
                        base,deltas,weights,
                        catastrophic_displacement_ratio=catastrophic_displacement_ratio,
                        catastrophic_bounds_ratio=catastrophic_bounds_ratio,
                    )
                    poses.append(MorphPoseAudit(
                        mesh_index=mesh_index,
                        primitive_index=primitive_index,
                        source=f"unit_target[{target_index}]",
                        time=None,
                        max_displacement_ratio=round(max_disp,6),
                        bounds_ratio=round(bounds,6),
                        nonfinite_vertices=nonfinite,
                        ready=not pose_errors,
                        errors=pose_errors,
                    ))

        for animation_index,animation in enumerate(animations):
            samplers=animation.get("samplers") or []
            for channel_index,channel in enumerate(animation.get("channels") or []):
                target=channel.get("target") or {}
                if target.get("path")!="weights":
                    continue
                node_index=target.get("node")
                if not isinstance(node_index,int) or not (0<=node_index<len(nodes)):
                    errors.append(
                        f"animation[{animation_index}].channel[{channel_index}] "
                        "weights target node is invalid"
                    )
                    continue
                mesh_index=nodes[node_index].get("mesh")
                if not isinstance(mesh_index,int) or not (0<=mesh_index<len(meshes)):
                    errors.append(
                        f"animation[{animation_index}].channel[{channel_index}] "
                        "weights target node has no valid mesh"
                    )
                    continue
                target_count=_mesh_target_count(meshes[mesh_index])
                sampler_index=channel.get("sampler")
                if (
                    target_count<=0
                    or not isinstance(sampler_index,int)
                    or not (0<=sampler_index<len(samplers))
                ):
                    errors.append(
                        f"animation[{animation_index}].channel[{channel_index}] "
                        "has no valid morph sampler/targets"
                    )
                    continue
                try:
                    samples=_weight_sampler(
                        path,doc,binary,read_accessor,
                        samplers[sampler_index],
                        target_count,
                    )
                except Exception as exc:
                    errors.append(
                        f"animation[{animation_index}].channel[{channel_index}]: "
                        f"{type(exc).__name__}:{exc}"
                    )
                    continue

                for (m,p),(base,deltas,count) in primitive_data.items():
                    if m!=mesh_index:
                        continue
                    for time,weights,source in samples:
                        max_disp,bounds,nonfinite,pose_errors=_pose_metrics(
                            base,deltas,weights,
                            catastrophic_displacement_ratio=catastrophic_displacement_ratio,
                            catastrophic_bounds_ratio=catastrophic_bounds_ratio,
                        )
                        poses.append(MorphPoseAudit(
                            mesh_index=m,
                            primitive_index=p,
                            source=(
                                f"animation[{animation_index}]."
                                f"channel[{channel_index}].{source}"
                            ),
                            time=round(float(time),6),
                            max_displacement_ratio=round(max_disp,6),
                            bounds_ratio=round(bounds,6),
                            nonfinite_vertices=nonfinite,
                            ready=not pose_errors,
                            errors=pose_errors,
                        ))
    except Exception as exc:
        errors.append(f"{type(exc).__name__}:{exc}")

    applicable=morph_targets>0
    nonfinite=sum(item.nonfinite_vertices for item in poses)
    catastrophic=sum(1 for item in poses if not item.ready)
    if poses:
        max_disp=max(item.max_displacement_ratio for item in poses)
        max_bounds=max(item.bounds_ratio for item in poses)
        positive_bounds=[
            item.bounds_ratio for item in poses
            if item.bounds_ratio>0 and math.isfinite(item.bounds_ratio)
        ]
        min_bounds=min(positive_bounds) if positive_bounds else 0.0
    else:
        max_disp=0.0
        max_bounds=0.0
        min_bounds=0.0

    for pose in poses:
        errors.extend(
            f"{pose.source}: {item}"
            for item in pose.errors
        )

    ready=bool(
        not applicable
        or (
            poses
            and not errors
            and catastrophic==0
            and nonfinite==0
        )
    )
    return MorphDeformationAudit(
        path=str(path),
        applicable=applicable,
        ready=ready,
        morph_meshes=morph_meshes,
        morph_primitives=morph_primitives,
        morph_targets=morph_targets,
        sampled_poses=len(poses),
        nonfinite_vertices=nonfinite,
        catastrophic_poses=catastrophic,
        max_displacement_ratio=round(float(max_disp),6),
        max_bounds_ratio=round(float(max_bounds),6),
        min_bounds_ratio=round(float(min_bounds),6),
        poses=poses,
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description=(
            "HAYUYA morph/blendshape deformation QA: unit targets and "
            "animated weight-channel sampling including cubic overshoot."
        )
    )
    parser.add_argument("glb",type=Path)
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    report=audit_morph_deformation(args.glb)
    payload=json.dumps(asdict(report),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
