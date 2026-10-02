#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import struct
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any


JSON_CHUNK=0x4E4F534A
BIN_CHUNK=0x004E4942

_COMPONENTS={
    5120:("b",1),
    5121:("B",1),
    5122:("h",2),
    5123:("H",2),
    5125:("I",4),
    5126:("f",4),
}
_TYPE_SIZE={
    "SCALAR":1,
    "VEC2":2,
    "VEC3":3,
    "VEC4":4,
    "MAT2":4,
    "MAT3":9,
    "MAT4":16,
}


@dataclass
class SkinWeightPrimitiveAudit:
    mesh_index:int
    primitive_index:int
    skin_joint_count:int
    vertex_count:int
    weighted_vertices:int
    zero_weight_vertices:int
    non_normalized_vertices:int
    invalid_joint_references:int
    negative_or_nonfinite_weights:int
    max_influences:int
    mean_influences:float
    ready:bool


@dataclass
class SkinWeightAudit:
    path:str
    applicable:bool
    ready:bool
    skin_count:int
    skinned_mesh_count:int
    primitive_count:int
    weighted_vertices:int
    zero_weight_vertices:int
    non_normalized_vertices:int
    invalid_joint_references:int
    negative_or_nonfinite_weights:int
    max_influences:int
    primitives:list[SkinWeightPrimitiveAudit]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-gltf-skin-weight-audit-v1"


def _read_glb(path:Path)->tuple[dict,bytes]:
    blob=path.read_bytes()
    if len(blob)<20 or blob[:4]!=b"glTF":
        raise ValueError("not a GLB")
    version,total=struct.unpack_from("<II",blob,4)
    if version!=2 or total>len(blob):
        raise ValueError("invalid GLB header")
    offset=12
    doc=None
    binary=b""
    while offset+8<=total:
        length,kind=struct.unpack_from("<II",blob,offset)
        offset+=8
        end=offset+length
        if end>total:
            raise ValueError("GLB chunk exceeds file")
        payload=blob[offset:end]
        if kind==JSON_CHUNK:
            doc=json.loads(payload.rstrip(b"\x00 \t\r\n").decode("utf-8"))
        elif kind==BIN_CHUNK:
            binary=payload
        offset=end
    if doc is None:
        raise ValueError("GLB JSON chunk missing")
    return doc,binary


def _normalize_integer(value:int,component_type:int)->float:
    if component_type==5120:
        return max(float(value)/127.0,-1.0)
    if component_type==5121:
        return float(value)/255.0
    if component_type==5122:
        return max(float(value)/32767.0,-1.0)
    if component_type==5123:
        return float(value)/65535.0
    if component_type==5125:
        return float(value)/4294967295.0
    return float(value)


def _read_accessor(doc:dict,binary:bytes,index:int)->list[list[float|int]]:
    accessors=doc.get("accessors") or []
    views=doc.get("bufferViews") or []
    if not isinstance(index,int) or index<0 or index>=len(accessors):
        raise ValueError(f"invalid accessor index {index}")
    accessor=accessors[index]
    if "sparse" in accessor:
        raise ValueError("sparse skin accessors are not supported by weight audit v1")
    view_index=accessor.get("bufferView")
    if not isinstance(view_index,int) or view_index<0 or view_index>=len(views):
        raise ValueError(f"accessor {index} has invalid bufferView")
    view=views[view_index]
    component_type=int(accessor.get("componentType"))
    if component_type not in _COMPONENTS:
        raise ValueError(f"unsupported componentType {component_type}")
    accessor_type=str(accessor.get("type"))
    width=_TYPE_SIZE.get(accessor_type)
    if width is None:
        raise ValueError(f"unsupported accessor type {accessor_type}")
    count=int(accessor.get("count") or 0)
    fmt_char,component_bytes=_COMPONENTS[component_type]
    packed=component_bytes*width
    stride=int(view.get("byteStride") or packed)
    if stride<packed:
        raise ValueError("bufferView byteStride smaller than accessor element")
    base=int(view.get("byteOffset") or 0)+int(accessor.get("byteOffset") or 0)
    normalized=bool(accessor.get("normalized"))
    fmt="<"+fmt_char*width
    output=[]
    for row in range(count):
        pos=base+row*stride
        if pos+packed>len(binary):
            raise ValueError(f"accessor {index} reads past BIN chunk")
        values=list(struct.unpack_from(fmt,binary,pos))
        if normalized and component_type!=5126:
            values=[_normalize_integer(int(v),component_type) for v in values]
        output.append(values)
    return output


def _mesh_skin_map(doc:dict)->dict[int,set[int]]:
    mapping:dict[int,set[int]]={}
    skins=doc.get("skins") or []
    meshes=doc.get("meshes") or []
    for node in doc.get("nodes") or []:
        mesh=node.get("mesh")
        skin=node.get("skin")
        if (
            isinstance(mesh,int) and 0<=mesh<len(meshes)
            and isinstance(skin,int) and 0<=skin<len(skins)
        ):
            mapping.setdefault(mesh,set()).add(skin)
    return mapping


def audit_skin_weights(
    path:Path,
    *,
    normalization_tolerance:float=0.02,
    active_weight_epsilon:float=1e-5,
)->SkinWeightAudit:
    warnings:list[str]=[]
    errors:list[str]=[]
    try:
        doc,binary=_read_glb(path)
    except Exception as exc:
        return SkinWeightAudit(
            path=str(path),applicable=False,ready=False,
            skin_count=0,skinned_mesh_count=0,primitive_count=0,
            weighted_vertices=0,zero_weight_vertices=0,
            non_normalized_vertices=0,invalid_joint_references=0,
            negative_or_nonfinite_weights=0,max_influences=0,
            primitives=[],warnings=[],errors=[f"{type(exc).__name__}:{exc}"],
        )

    skins=doc.get("skins") or []
    meshes=doc.get("meshes") or []
    mapping=_mesh_skin_map(doc)
    if not skins or not mapping:
        return SkinWeightAudit(
            path=str(path),applicable=False,ready=False,
            skin_count=len(skins),skinned_mesh_count=len(mapping),
            primitive_count=0,weighted_vertices=0,zero_weight_vertices=0,
            non_normalized_vertices=0,invalid_joint_references=0,
            negative_or_nonfinite_weights=0,max_influences=0,
            primitives=[],warnings=["no skinned mesh nodes"],errors=[],
        )

    primitive_reports=[]
    totals={
        "weighted":0,"zero":0,"norm":0,"invalid":0,"bad":0,"max":0,
    }

    for mesh_index,skin_indices in sorted(mapping.items()):
        if len(skin_indices)>1:
            warnings.append(
                f"mesh[{mesh_index}] is referenced by multiple skins: {sorted(skin_indices)}"
            )
        joint_count=min(
            len((skins[i].get("joints") or []))
            for i in skin_indices
        )
        for primitive_index,primitive in enumerate(meshes[mesh_index].get("primitives") or []):
            attrs=primitive.get("attributes") or {}
            joint_sets=sorted(
                key for key in attrs
                if key.startswith("JOINTS_")
            )
            weight_sets=sorted(
                key for key in attrs
                if key.startswith("WEIGHTS_")
            )
            if not joint_sets and not weight_sets:
                errors.append(
                    f"mesh[{mesh_index}].primitive[{primitive_index}] has skin but no JOINTS/WEIGHTS"
                )
                continue
            if [x.replace("JOINTS_","") for x in joint_sets] != [
                x.replace("WEIGHTS_","") for x in weight_sets
            ]:
                errors.append(
                    f"mesh[{mesh_index}].primitive[{primitive_index}] JOINTS/WEIGHTS sets mismatch"
                )
                continue
            try:
                joint_arrays=[_read_accessor(doc,binary,int(attrs[key])) for key in joint_sets]
                weight_arrays=[_read_accessor(doc,binary,int(attrs[key])) for key in weight_sets]
            except Exception as exc:
                errors.append(
                    f"mesh[{mesh_index}].primitive[{primitive_index}] accessor read failed: "
                    f"{type(exc).__name__}:{exc}"
                )
                continue

            vertex_count=len(weight_arrays[0]) if weight_arrays else 0
            if any(len(x)!=vertex_count for x in joint_arrays+weight_arrays):
                errors.append(
                    f"mesh[{mesh_index}].primitive[{primitive_index}] skin accessor counts differ"
                )
                continue

            weighted=zero=not_normalized=invalid=bad=0
            influence_counts=[]
            for vertex in range(vertex_count):
                pairs=[]
                for joints,weights in zip(joint_arrays,weight_arrays):
                    for joint,weight in zip(joints[vertex],weights[vertex]):
                        try:
                            j=int(joint)
                            w=float(weight)
                        except Exception:
                            bad+=1
                            continue
                        if not math.isfinite(w) or w<0:
                            bad+=1
                            continue
                        pairs.append((j,w))

                weight_sum=sum(w for _,w in pairs)
                active=[(j,w) for j,w in pairs if w>active_weight_epsilon]
                influence_counts.append(len(active))
                if weight_sum<=active_weight_epsilon:
                    zero+=1
                else:
                    weighted+=1
                    if abs(weight_sum-1.0)>normalization_tolerance:
                        not_normalized+=1
                invalid+=sum(
                    1 for j,w in active
                    if j<0 or j>=joint_count
                )

            maximum=max(influence_counts) if influence_counts else 0
            mean=(
                sum(influence_counts)/len(influence_counts)
                if influence_counts else 0.0
            )
            ready=bool(
                vertex_count>0
                and zero==0
                and not_normalized==0
                and invalid==0
                and bad==0
            )
            report=SkinWeightPrimitiveAudit(
                mesh_index=mesh_index,
                primitive_index=primitive_index,
                skin_joint_count=joint_count,
                vertex_count=vertex_count,
                weighted_vertices=weighted,
                zero_weight_vertices=zero,
                non_normalized_vertices=not_normalized,
                invalid_joint_references=invalid,
                negative_or_nonfinite_weights=bad,
                max_influences=maximum,
                mean_influences=round(float(mean),4),
                ready=ready,
            )
            primitive_reports.append(report)
            totals["weighted"]+=weighted
            totals["zero"]+=zero
            totals["norm"]+=not_normalized
            totals["invalid"]+=invalid
            totals["bad"]+=bad
            totals["max"]=max(totals["max"],maximum)

    if totals["max"]>4:
        warnings.append(
            f"max active skin influences is {totals['max']}; mobile tiers may require pruning to 4"
        )
    ready=bool(
        primitive_reports
        and all(item.ready for item in primitive_reports)
        and not errors
    )
    return SkinWeightAudit(
        path=str(path),
        applicable=True,
        ready=ready,
        skin_count=len(skins),
        skinned_mesh_count=len(mapping),
        primitive_count=len(primitive_reports),
        weighted_vertices=totals["weighted"],
        zero_weight_vertices=totals["zero"],
        non_normalized_vertices=totals["norm"],
        invalid_joint_references=totals["invalid"],
        negative_or_nonfinite_weights=totals["bad"],
        max_influences=totals["max"],
        primitives=primitive_reports,
        warnings=warnings,
        errors=errors,
    )


def write_skin_weight_audit(report:SkinWeightAudit,path:Path)->Path:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(asdict(report),indent=2)+"\n",encoding="utf-8")
    return path


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(description="Audit real glTF JOINTS/WEIGHTS data.")
    parser.add_argument("glb",type=Path)
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    report=audit_skin_weights(args.glb)
    payload=json.dumps(asdict(report),indent=2)
    print(payload)
    if args.json:
        write_skin_weight_audit(report,args.json)
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
