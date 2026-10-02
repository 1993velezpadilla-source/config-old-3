#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class DeformationFrameAudit:
    animation_index:int
    time:float
    sampled_vertices:int
    nonfinite_vertices:int
    bounds_ratio:float
    max_displacement_ratio:float
    max_edge_stretch_ratio:float
    min_edge_stretch_ratio:float
    ready:bool
    errors:list[str]


@dataclass
class DeformationQAAudit:
    path:str
    applicable:bool
    ready:bool
    animation_count:int
    sampled_frames:int
    sampled_vertices:int
    max_bounds_ratio:float
    min_bounds_ratio:float
    max_displacement_ratio:float
    max_edge_stretch_ratio:float
    min_edge_stretch_ratio:float
    nonfinite_vertices:int
    catastrophic_frames:int
    frames:list[DeformationFrameAudit]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-deformation-qa-v1"


def _deps():
    import numpy as np
    return np


def _matrix_from_gltf(values:list[float]):
    np=_deps()
    return np.asarray(values,dtype=np.float64).reshape((4,4),order="F")


def _quat_matrix(q:list[float]):
    np=_deps()
    x,y,z,w=(float(v) for v in q)
    norm=math.sqrt(x*x+y*y+z*z+w*w)
    if norm<=1e-12:
        raise ValueError("zero-length quaternion")
    x,y,z,w=x/norm,y/norm,z/norm,w/norm
    return np.asarray([
        [1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),0],
        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),0],
        [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y),0],
        [0,0,0,1],
    ],dtype=np.float64)


def _trs_matrix(
    translation:list[float],
    rotation:list[float],
    scale:list[float],
):
    np=_deps()
    t=np.eye(4,dtype=np.float64)
    t[:3,3]=np.asarray(translation,dtype=np.float64)
    r=_quat_matrix(rotation)
    s=np.diag([
        float(scale[0]),float(scale[1]),float(scale[2]),1.0
    ])
    return t@r@s


def _default_node_trs(node:dict):
    if "matrix" in node:
        return None
    return (
        [float(x) for x in node.get("translation",[0,0,0])],
        [float(x) for x in node.get("rotation",[0,0,0,1])],
        [float(x) for x in node.get("scale",[1,1,1])],
    )


def _local_matrix(node:dict, override:dict|None=None):
    if "matrix" in node and not override:
        return _matrix_from_gltf(node["matrix"])
    if "matrix" in node and override:
        raise ValueError(
            "animated node using matrix transform is unsupported by deformation QA"
        )
    translation,rotation,scale=_default_node_trs(node)
    override=override or {}
    translation=list(override.get("translation",translation))
    rotation=list(override.get("rotation",rotation))
    scale=list(override.get("scale",scale))
    return _trs_matrix(translation,rotation,scale)


def _parents(doc:dict)->list[int|None]:
    nodes=doc.get("nodes") or []
    parents=[None]*len(nodes)
    for parent,node in enumerate(nodes):
        for child in node.get("children") or []:
            if isinstance(child,int) and 0<=child<len(nodes):
                if parents[child] is not None:
                    raise ValueError(
                        f"node {child} has multiple parents"
                    )
                parents[child]=parent
    return parents


def _global_matrices(doc:dict,overrides:dict[int,dict]):
    np=_deps()
    nodes=doc.get("nodes") or []
    parents=_parents(doc)
    cache={}

    def resolve(index:int):
        if index in cache:
            return cache[index]
        local=_local_matrix(nodes[index],overrides.get(index))
        parent=parents[index]
        result=local if parent is None else resolve(parent)@local
        cache[index]=result
        return result

    return [resolve(i) for i in range(len(nodes))]


def _read_accessor(path:Path,index:int):
    from skin_weight_qa import _read_accessor,_read_glb
    doc,binary=_read_glb(path)
    return _read_accessor(doc,binary,index)


def _animation_channel_data(path:Path,doc:dict,animation:dict):
    channels=[]
    samplers=animation.get("samplers") or []
    for channel in animation.get("channels") or []:
        sampler_index=channel.get("sampler")
        if not isinstance(sampler_index,int) or not (0<=sampler_index<len(samplers)):
            continue
        sampler=samplers[sampler_index]
        times=[
            float(row[0])
            for row in _read_accessor(path,int(sampler["input"]))
        ]
        values=[
            [float(x) for x in row]
            for row in _read_accessor(path,int(sampler["output"]))
        ]
        interpolation=str(sampler.get("interpolation") or "LINEAR").upper()
        target=channel.get("target") or {}
        node=target.get("node")
        path_name=str(target.get("path") or "")
        if not isinstance(node,int):
            continue
        if interpolation=="CUBICSPLINE":
            values=values[1::3]
        channels.append({
            "node":node,
            "path":path_name,
            "times":times,
            "values":values,
            "interpolation":interpolation,
        })
    return channels


def _lerp(a:list[float],b:list[float],t:float)->list[float]:
    return [
        float(x)+(float(y)-float(x))*float(t)
        for x,y in zip(a,b)
    ]


def _slerp(a:list[float],b:list[float],t:float)->list[float]:
    np=_deps()
    qa=np.asarray(a,dtype=np.float64)
    qb=np.asarray(b,dtype=np.float64)
    qa=qa/max(float(np.linalg.norm(qa)),1e-12)
    qb=qb/max(float(np.linalg.norm(qb)),1e-12)
    dot=float(np.dot(qa,qb))
    if dot<0.0:
        qb=-qb
        dot=-dot
    dot=max(-1.0,min(1.0,dot))
    if dot>0.9995:
        out=qa+(qb-qa)*float(t)
        out=out/max(float(np.linalg.norm(out)),1e-12)
        return [float(x) for x in out]
    theta=math.acos(dot)
    sin_theta=math.sin(theta)
    w0=math.sin((1.0-t)*theta)/sin_theta
    w1=math.sin(t*theta)/sin_theta
    out=w0*qa+w1*qb
    return [float(x) for x in out]


def _sample_channel(channel:dict,time:float)->list[float]|None:
    times=channel["times"]
    values=channel["values"]
    if not times or not values:
        return None
    if time<=times[0]:
        return list(values[0])
    if time>=times[-1]:
        return list(values[-1])
    right=1
    while right<len(times) and times[right]<time:
        right+=1
    left=max(0,right-1)
    if right>=len(times):
        return list(values[-1])
    if channel["interpolation"]=="STEP":
        return list(values[left])
    span=max(times[right]-times[left],1e-12)
    alpha=(time-times[left])/span
    if channel["path"]=="rotation":
        return _slerp(values[left],values[right],alpha)
    return _lerp(values[left],values[right],alpha)


def _sample_times(channels:list[dict],max_frames:int)->list[float]:
    times=sorted({
        float(t)
        for channel in channels
        for t in channel["times"]
        if math.isfinite(float(t))
    })
    if len(times)<=max_frames:
        return times
    indices=[
        round(i*(len(times)-1)/(max_frames-1))
        for i in range(max_frames)
    ]
    return [times[i] for i in sorted(set(indices))]


def _animation_overrides(channels:list[dict],time:float)->dict[int,dict]:
    overrides={}
    for channel in channels:
        path_name=channel["path"]
        if path_name not in {"translation","rotation","scale"}:
            continue
        value=_sample_channel(channel,time)
        if value is None:
            continue
        overrides.setdefault(channel["node"],{})[path_name]=value
    return overrides


def _inverse_bind_matrices(path:Path,doc:dict,skin:dict):
    np=_deps()
    joints=skin.get("joints") or []
    accessor=skin.get("inverseBindMatrices")
    if accessor is None:
        return [np.eye(4,dtype=np.float64) for _ in joints]
    rows=_read_accessor(path,int(accessor))
    if len(rows)!=len(joints):
        raise ValueError(
            "inverseBindMatrices count does not match skin joints"
        )
    return [_matrix_from_gltf([float(x) for x in row]) for row in rows]


def _primitive_arrays(path:Path,doc:dict,primitive:dict):
    np=_deps()
    attrs=primitive.get("attributes") or {}
    if "POSITION" not in attrs:
        raise ValueError("skinned primitive missing POSITION")
    positions=np.asarray(
        _read_accessor(path,int(attrs["POSITION"])),
        dtype=np.float64,
    )
    joint_keys=sorted(k for k in attrs if k.startswith("JOINTS_"))
    weight_keys=sorted(k for k in attrs if k.startswith("WEIGHTS_"))
    if not joint_keys or len(joint_keys)!=len(weight_keys):
        raise ValueError("skinned primitive missing matching JOINTS/WEIGHTS")
    joints=np.concatenate([
        np.asarray(_read_accessor(path,int(attrs[key])),dtype=np.int64)
        for key in joint_keys
    ],axis=1)
    weights=np.concatenate([
        np.asarray(_read_accessor(path,int(attrs[key])),dtype=np.float64)
        for key in weight_keys
    ],axis=1)
    if len(positions)!=len(joints) or len(positions)!=len(weights):
        raise ValueError("skin accessor vertex counts differ")

    indices=None
    if isinstance(primitive.get("indices"),int):
        raw=np.asarray(
            _read_accessor(path,int(primitive["indices"])),
            dtype=np.int64,
        ).reshape(-1)
        indices=raw
    return positions,joints,weights,indices


def _edges(indices,vertex_count:int,max_edges:int=20000):
    np=_deps()
    if indices is None or len(indices)<3:
        # Conservative fallback chain for point/line-like fixtures.
        if vertex_count<2:
            return np.zeros((0,2),dtype=np.int64)
        return np.asarray(
            [(i,i+1) for i in range(min(vertex_count-1,max_edges))],
            dtype=np.int64,
        )
    triangles=np.asarray(indices,dtype=np.int64).reshape(-1,3)
    edge_set=set()
    for tri in triangles:
        a,b,c=(int(x) for x in tri)
        for x,y in ((a,b),(b,c),(c,a)):
            if x==y:
                continue
            edge_set.add((min(x,y),max(x,y)))
            if len(edge_set)>=max_edges:
                break
        if len(edge_set)>=max_edges:
            break
    return np.asarray(sorted(edge_set),dtype=np.int64)


def _skin_primitive(
    positions,
    joints,
    weights,
    *,
    mesh_global,
    joint_globals,
    inverse_binds,
):
    np=_deps()
    try:
        mesh_inverse=np.linalg.inv(mesh_global)
    except Exception as exc:
        raise ValueError(f"mesh global matrix is singular: {exc}")
    matrices=[
        mesh_inverse@joint_globals[i]@inverse_binds[i]
        for i in range(len(joint_globals))
    ]
    result=np.zeros((len(positions),3),dtype=np.float64)
    for vertex in range(len(positions)):
        source=np.asarray(
            [positions[vertex,0],positions[vertex,1],positions[vertex,2],1.0],
            dtype=np.float64,
        )
        accum=np.zeros(4,dtype=np.float64)
        weight_sum=0.0
        for joint,weight in zip(joints[vertex],weights[vertex]):
            w=float(weight)
            if w<=1e-8:
                continue
            j=int(joint)
            if not (0<=j<len(matrices)):
                raise ValueError(f"invalid active joint index {j}")
            accum+=w*(matrices[j]@source)
            weight_sum+=w
        if weight_sum<=1e-8:
            raise ValueError("zero-weight vertex reached deformation QA")
        if abs(weight_sum-1.0)>0.02:
            accum/=weight_sum
        local=accum
        world=mesh_global@local
        result[vertex]=world[:3]
    return result


def audit_deformation(
    path:Path,
    *,
    max_frames_per_animation:int=12,
    catastrophic_bounds_ratio:float=20.0,
    catastrophic_displacement_ratio:float=25.0,
    catastrophic_edge_stretch:float=20.0,
    catastrophic_edge_collapse:float=0.005,
)->DeformationQAAudit:
    np=_deps()
    warnings=[]
    errors=[]
    frame_reports=[]
    try:
        from skin_weight_qa import _read_glb
        doc,_=_read_glb(path)
    except Exception as exc:
        return DeformationQAAudit(
            path=str(path),applicable=False,ready=False,
            animation_count=0,sampled_frames=0,sampled_vertices=0,
            max_bounds_ratio=0.0,min_bounds_ratio=0.0,
            max_displacement_ratio=0.0,max_edge_stretch_ratio=0.0,
            min_edge_stretch_ratio=0.0,nonfinite_vertices=0,
            catastrophic_frames=0,frames=[],warnings=[],
            errors=[f"{type(exc).__name__}:{exc}"],
        )

    animations=doc.get("animations") or []
    skins=doc.get("skins") or []
    nodes=doc.get("nodes") or []
    meshes=doc.get("meshes") or []
    skinned_nodes=[
        (index,node)
        for index,node in enumerate(nodes)
        if isinstance(node.get("mesh"),int)
        and isinstance(node.get("skin"),int)
    ]
    if not animations or not skins or not skinned_nodes:
        return DeformationQAAudit(
            path=str(path),applicable=False,ready=False,
            animation_count=len(animations),sampled_frames=0,sampled_vertices=0,
            max_bounds_ratio=0.0,min_bounds_ratio=0.0,
            max_displacement_ratio=0.0,max_edge_stretch_ratio=0.0,
            min_edge_stretch_ratio=0.0,nonfinite_vertices=0,
            catastrophic_frames=0,frames=[],warnings=[
                "deformation QA requires both animation clips and skinned mesh nodes"
            ],errors=[],
        )

    default_globals=_global_matrices(doc,{})
    primitive_specs=[]
    bind_points=[]
    total_vertices=0

    try:
        for node_index,node in skinned_nodes:
            mesh_index=int(node["mesh"])
            skin_index=int(node["skin"])
            if not (0<=mesh_index<len(meshes)) or not (0<=skin_index<len(skins)):
                raise ValueError("invalid mesh/skin node reference")
            skin=skins[skin_index]
            joint_nodes=[int(x) for x in (skin.get("joints") or [])]
            inverse_binds=_inverse_bind_matrices(path,doc,skin)
            joint_globals=[default_globals[j] for j in joint_nodes]
            mesh_global=default_globals[node_index]
            for primitive in meshes[mesh_index].get("primitives") or []:
                positions,joints,weights,indices=_primitive_arrays(
                    path,doc,primitive
                )
                bind=_skin_primitive(
                    positions,joints,weights,
                    mesh_global=mesh_global,
                    joint_globals=joint_globals,
                    inverse_binds=inverse_binds,
                )
                edges=_edges(indices,len(positions))
                primitive_specs.append({
                    "node_index":node_index,
                    "skin_index":skin_index,
                    "positions":positions,
                    "joints":joints,
                    "weights":weights,
                    "edges":edges,
                    "bind":bind,
                })
                bind_points.append(bind)
                total_vertices+=len(bind)
    except Exception as exc:
        return DeformationQAAudit(
            path=str(path),applicable=True,ready=False,
            animation_count=len(animations),sampled_frames=0,
            sampled_vertices=0,max_bounds_ratio=0.0,min_bounds_ratio=0.0,
            max_displacement_ratio=0.0,max_edge_stretch_ratio=0.0,
            min_edge_stretch_ratio=0.0,nonfinite_vertices=0,
            catastrophic_frames=0,frames=[],warnings=warnings,
            errors=[f"bind_pose:{type(exc).__name__}:{exc}"],
        )

    all_bind=np.concatenate(bind_points,axis=0)
    bind_lo=np.min(all_bind,axis=0)
    bind_hi=np.max(all_bind,axis=0)
    bind_diag=max(float(np.linalg.norm(bind_hi-bind_lo)),1e-9)

    overall_max_bounds=0.0
    overall_min_bounds=float("inf")
    overall_max_disp=0.0
    overall_max_edge=0.0
    overall_min_edge=float("inf")
    overall_nonfinite=0
    catastrophic_frames=0

    for animation_index,animation in enumerate(animations):
        channels=_animation_channel_data(path,doc,animation)
        times=_sample_times(channels,max(2,int(max_frames_per_animation)))
        if not times:
            errors.append(
                f"animation[{animation_index}] has no sampleable timestamps"
            )
            continue

        for time in times:
            frame_errors=[]
            nonfinite=0
            max_disp=0.0
            max_edge_ratio=0.0
            min_edge_ratio=float("inf")
            frame_points=[]
            try:
                globals_now=_global_matrices(
                    doc,_animation_overrides(channels,time)
                )
                for spec in primitive_specs:
                    node_index=spec["node_index"]
                    skin_index=spec["skin_index"]
                    skin=skins[skin_index]
                    joint_nodes=[int(x) for x in (skin.get("joints") or [])]
                    inverse_binds=_inverse_bind_matrices(path,doc,skin)
                    deformed=_skin_primitive(
                        spec["positions"],
                        spec["joints"],
                        spec["weights"],
                        mesh_global=globals_now[node_index],
                        joint_globals=[globals_now[j] for j in joint_nodes],
                        inverse_binds=inverse_binds,
                    )
                    bad=int(np.count_nonzero(~np.isfinite(deformed).all(axis=1)))
                    nonfinite+=bad
                    frame_points.append(deformed)

                    displacement=np.linalg.norm(
                        deformed-spec["bind"],axis=1
                    )/bind_diag
                    if len(displacement):
                        max_disp=max(max_disp,float(np.max(displacement)))

                    edges=spec["edges"]
                    if len(edges):
                        a=edges[:,0]
                        b=edges[:,1]
                        bind_lengths=np.linalg.norm(
                            spec["bind"][a]-spec["bind"][b],axis=1
                        )
                        def_lengths=np.linalg.norm(
                            deformed[a]-deformed[b],axis=1
                        )
                        valid=bind_lengths>1e-9
                        ratios=def_lengths[valid]/bind_lengths[valid]
                        if len(ratios):
                            max_edge_ratio=max(
                                max_edge_ratio,float(np.max(ratios))
                            )
                            min_edge_ratio=min(
                                min_edge_ratio,float(np.min(ratios))
                            )

                merged=np.concatenate(frame_points,axis=0)
                finite_rows=merged[
                    np.isfinite(merged).all(axis=1)
                ]
                if len(finite_rows):
                    lo=np.min(finite_rows,axis=0)
                    hi=np.max(finite_rows,axis=0)
                    bounds_ratio=(
                        float(np.linalg.norm(hi-lo))/bind_diag
                    )
                else:
                    bounds_ratio=float("inf")

                if nonfinite:
                    frame_errors.append(
                        f"non-finite deformed vertices: {nonfinite}"
                    )
                if bounds_ratio>catastrophic_bounds_ratio:
                    frame_errors.append(
                        f"bounds explosion: {bounds_ratio:.4f}x"
                    )
                if bounds_ratio<1.0/catastrophic_bounds_ratio:
                    frame_errors.append(
                        f"bounds collapse: {bounds_ratio:.4f}x"
                    )
                if max_disp>catastrophic_displacement_ratio:
                    frame_errors.append(
                        f"vertex displacement explosion: {max_disp:.4f}x"
                    )
                if max_edge_ratio>catastrophic_edge_stretch:
                    frame_errors.append(
                        f"edge stretch explosion: {max_edge_ratio:.4f}x"
                    )
                if (
                    min_edge_ratio!=float("inf")
                    and min_edge_ratio<catastrophic_edge_collapse
                ):
                    frame_errors.append(
                        f"edge collapse: {min_edge_ratio:.6f}x"
                    )

            except Exception as exc:
                bounds_ratio=0.0
                frame_errors.append(
                    f"{type(exc).__name__}:{exc}"
                )

            ready=not frame_errors
            if not ready:
                catastrophic_frames+=1
                errors.extend(
                    f"animation[{animation_index}] t={time:.6f}: {item}"
                    for item in frame_errors
                )
            min_edge_value=(
                0.0 if min_edge_ratio==float("inf")
                else min_edge_ratio
            )
            frame_reports.append(DeformationFrameAudit(
                animation_index=animation_index,
                time=round(float(time),6),
                sampled_vertices=total_vertices,
                nonfinite_vertices=nonfinite,
                bounds_ratio=round(float(bounds_ratio),6),
                max_displacement_ratio=round(float(max_disp),6),
                max_edge_stretch_ratio=round(float(max_edge_ratio),6),
                min_edge_stretch_ratio=round(float(min_edge_value),6),
                ready=ready,
                errors=frame_errors,
            ))
            overall_max_bounds=max(overall_max_bounds,float(bounds_ratio))
            if bounds_ratio>0:
                overall_min_bounds=min(overall_min_bounds,float(bounds_ratio))
            overall_max_disp=max(overall_max_disp,float(max_disp))
            overall_max_edge=max(overall_max_edge,float(max_edge_ratio))
            if min_edge_ratio!=float("inf"):
                overall_min_edge=min(overall_min_edge,float(min_edge_ratio))
            overall_nonfinite+=nonfinite

    if overall_min_bounds==float("inf"):
        overall_min_bounds=0.0
    if overall_min_edge==float("inf"):
        overall_min_edge=0.0

    ready=bool(
        frame_reports
        and catastrophic_frames==0
        and overall_nonfinite==0
        and not errors
    )
    return DeformationQAAudit(
        path=str(path),
        applicable=True,
        ready=ready,
        animation_count=len(animations),
        sampled_frames=len(frame_reports),
        sampled_vertices=total_vertices,
        max_bounds_ratio=round(overall_max_bounds,6),
        min_bounds_ratio=round(overall_min_bounds,6),
        max_displacement_ratio=round(overall_max_disp,6),
        max_edge_stretch_ratio=round(overall_max_edge,6),
        min_edge_stretch_ratio=round(overall_min_edge,6),
        nonfinite_vertices=overall_nonfinite,
        catastrophic_frames=catastrophic_frames,
        frames=frame_reports,
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA sampled glTF skin-deformation QA."
    )
    parser.add_argument("glb",type=Path)
    parser.add_argument("--json",type=Path)
    parser.add_argument("--max-frames",type=int,default=12)
    args=parser.parse_args()
    report=audit_deformation(
        args.glb,
        max_frames_per_animation=args.max_frames,
    )
    payload=json.dumps(asdict(report),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
