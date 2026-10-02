#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import struct
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class AnimationChannelAudit:
    animation_index:int
    channel_index:int
    node:int|None
    target_path:str
    interpolation:str
    keyframes:int
    ready:bool
    errors:list[str]


@dataclass
class AnimationQAAudit:
    path:str
    applicable:bool
    ready:bool
    animation_count:int
    channel_count:int
    sampler_count:int
    total_keyframes:int
    rotation_channels:int
    translation_channels:int
    scale_channels:int
    weight_channels:int
    channels:list[AnimationChannelAudit]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-animation-qa-v1"


def _read_float_accessor(
    path:Path,
    index:int,
)->tuple[str,list[tuple[float,...]]]:
    from gltf_position_patch import _accessor_layout,_doc_and_bin

    doc,binary,_=_doc_and_bin(path)
    accessor,_,component,dims,packed,stride,base=_accessor_layout(
        doc,index
    )
    if component!=5126:
        raise ValueError(
            f"animation accessor {index} must use FLOAT componentType"
        )
    accessor_type=str(accessor.get("type") or "")
    rows=[]
    fmt="<"+"f"*dims
    for row in range(int(accessor.get("count") or 0)):
        pos=base+row*stride
        if pos+packed>len(binary):
            raise ValueError(
                f"animation accessor {index} reads past BIN chunk"
            )
        values=tuple(float(x) for x in struct.unpack_from(fmt,binary,pos))
        if not all(math.isfinite(x) for x in values):
            raise ValueError(
                f"animation accessor {index} contains non-finite values"
            )
        rows.append(values)
    return accessor_type,rows


def _mesh_diagonal(path:Path,doc:dict)->float:
    try:
        from gltf_position_patch import (
            mesh_position_accessors,
            read_position_accessor,
        )
        rows=[]
        for index in mesh_position_accessors(doc,skinned_only=False):
            rows.extend(read_position_accessor(path,index))
        if not rows:
            return 1.0
        mins=[min(row[i] for row in rows) for i in range(3)]
        maxs=[max(row[i] for row in rows) for i in range(3)]
        diag=math.sqrt(sum((b-a)**2 for a,b in zip(mins,maxs)))
        return max(diag,1e-9)
    except Exception:
        return 1.0


def audit_animation(
    path:Path,
    *,
    quaternion_tolerance:float=0.05,
    catastrophic_translation_factor:float=1000.0,
    catastrophic_scale:float=1000.0,
)->AnimationQAAudit:
    warnings=[]
    errors=[]
    channels_out=[]
    try:
        from gltf_audit import read_glb_json
        doc=read_glb_json(path)
    except Exception as exc:
        return AnimationQAAudit(
            path=str(path),
            applicable=False,
            ready=False,
            animation_count=0,
            channel_count=0,
            sampler_count=0,
            total_keyframes=0,
            rotation_channels=0,
            translation_channels=0,
            scale_channels=0,
            weight_channels=0,
            channels=[],
            warnings=[],
            errors=[f"{type(exc).__name__}:{exc}"],
        )

    animations=doc.get("animations") or []
    if not animations:
        return AnimationQAAudit(
            path=str(path),
            applicable=False,
            ready=False,
            animation_count=0,
            channel_count=0,
            sampler_count=0,
            total_keyframes=0,
            rotation_channels=0,
            translation_channels=0,
            scale_channels=0,
            weight_channels=0,
            channels=[],
            warnings=["asset has no animation clips"],
            errors=[],
        )

    nodes=doc.get("nodes") or []
    diag=_mesh_diagonal(path,doc)
    total_keyframes=0
    sampler_total=0
    rotation_channels=0
    translation_channels=0
    scale_channels=0
    weight_channels=0

    for animation_index,animation in enumerate(animations):
        samplers=animation.get("samplers") or []
        sampler_total+=len(samplers)
        seen_targets=set()
        for channel_index,channel in enumerate(animation.get("channels") or []):
            channel_errors=[]
            target=channel.get("target") or {}
            node=target.get("node")
            target_path=str(target.get("path") or "")
            sampler_index=channel.get("sampler")
            interpolation="LINEAR"
            keyframes=0

            if not isinstance(node,int) or not (0<=node<len(nodes)):
                channel_errors.append(
                    f"invalid target node: {node}"
                )
            if target_path not in {"translation","rotation","scale","weights"}:
                channel_errors.append(
                    f"unsupported animation target path: {target_path!r}"
                )

            target_key=(node,target_path)
            if target_key in seen_targets:
                channel_errors.append(
                    f"duplicate target channel in animation: node={node} path={target_path}"
                )
            seen_targets.add(target_key)

            if (
                not isinstance(sampler_index,int)
                or not (0<=sampler_index<len(samplers))
            ):
                channel_errors.append(
                    f"invalid sampler index: {sampler_index}"
                )
            else:
                sampler=samplers[sampler_index]
                interpolation=str(
                    sampler.get("interpolation") or "LINEAR"
                ).upper()
                if interpolation not in {"LINEAR","STEP","CUBICSPLINE"}:
                    channel_errors.append(
                        f"unsupported interpolation: {interpolation}"
                    )

                input_index=sampler.get("input")
                output_index=sampler.get("output")
                try:
                    input_type,times=_read_float_accessor(
                        path,int(input_index)
                    )
                    output_type,values=_read_float_accessor(
                        path,int(output_index)
                    )
                    if input_type!="SCALAR":
                        channel_errors.append(
                            f"animation input must be SCALAR, got {input_type}"
                        )
                    keyframes=len(times)
                    if keyframes<=0:
                        channel_errors.append("animation channel has no keyframes")
                    else:
                        flattened=[row[0] for row in times]
                        if any(value<0.0 for value in flattened):
                            channel_errors.append(
                                "animation timestamps must be non-negative"
                            )
                        if any(
                            b<=a
                            for a,b in zip(flattened,flattened[1:])
                        ):
                            channel_errors.append(
                                "animation timestamps are not strictly increasing"
                            )

                    expected=(
                        keyframes*3
                        if interpolation=="CUBICSPLINE"
                        else keyframes
                    )
                    if target_path!="weights" and len(values)!=expected:
                        channel_errors.append(
                            "animation output sample count mismatch: "
                            f"{len(values)} != {expected}"
                        )

                    if target_path in {"translation","scale"}:
                        if output_type!="VEC3":
                            channel_errors.append(
                                f"{target_path} output must be VEC3, got {output_type}"
                            )
                    elif target_path=="rotation":
                        if output_type!="VEC4":
                            channel_errors.append(
                                f"rotation output must be VEC4, got {output_type}"
                            )

                    value_rows=values
                    if interpolation=="CUBICSPLINE":
                        value_rows=values[1::3]

                    if target_path=="translation":
                        translation_channels+=1
                        catastrophic=diag*catastrophic_translation_factor
                        for row in value_rows:
                            magnitude=math.sqrt(sum(x*x for x in row))
                            if magnitude>catastrophic:
                                channel_errors.append(
                                    "catastrophic translation magnitude: "
                                    f"{magnitude:.6g} > {catastrophic:.6g}"
                                )
                                break
                    elif target_path=="rotation":
                        rotation_channels+=1
                        for row in value_rows:
                            norm=math.sqrt(sum(x*x for x in row))
                            if abs(norm-1.0)>quaternion_tolerance:
                                channel_errors.append(
                                    "rotation quaternion is not normalized: "
                                    f"norm={norm:.6f}"
                                )
                                break
                    elif target_path=="scale":
                        scale_channels+=1
                        for row in value_rows:
                            if any(abs(x)>catastrophic_scale for x in row):
                                channel_errors.append(
                                    "catastrophic animation scale value"
                                )
                                break
                    elif target_path=="weights":
                        weight_channels+=1

                except Exception as exc:
                    channel_errors.append(
                        f"{type(exc).__name__}:{exc}"
                    )

            total_keyframes+=keyframes
            channel_result=AnimationChannelAudit(
                animation_index=animation_index,
                channel_index=channel_index,
                node=node if isinstance(node,int) else None,
                target_path=target_path,
                interpolation=interpolation,
                keyframes=keyframes,
                ready=not channel_errors,
                errors=channel_errors,
            )
            channels_out.append(channel_result)
            errors.extend(
                f"animation[{animation_index}].channel[{channel_index}]: {item}"
                for item in channel_errors
            )

    channel_count=len(channels_out)
    ready=bool(
        animations
        and channel_count>0
        and not errors
        and all(item.ready for item in channels_out)
    )
    return AnimationQAAudit(
        path=str(path),
        applicable=True,
        ready=ready,
        animation_count=len(animations),
        channel_count=channel_count,
        sampler_count=sampler_total,
        total_keyframes=total_keyframes,
        rotation_channels=rotation_channels,
        translation_channels=translation_channels,
        scale_channels=scale_channels,
        weight_channels=weight_channels,
        channels=channels_out,
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA glTF animation integrity QA."
    )
    parser.add_argument("glb",type=Path)
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    report=audit_animation(args.glb)
    payload=json.dumps(asdict(report),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
