#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class UVPrimitiveAudit:
    mesh_index:int
    primitive_index:int
    material_index:int|None
    textured:bool
    normal_mapped:bool
    position_count:int
    required_texcoord_sets:list[int]
    present_texcoord_sets:list[int]
    missing_texcoord_sets:list[int]
    triangle_count:int
    degenerate_geometry_triangles:int
    degenerate_uv_triangles:int
    degenerate_uv_ratio:float
    tangent_present:bool
    tangent_valid:bool|None
    tangent_derivable:bool|None
    ready:bool
    errors:list[str]


@dataclass
class UVTangentAudit:
    path:str
    applicable:bool
    ready:bool
    primitive_count:int
    textured_primitives:int
    normal_mapped_primitives:int
    missing_uv_primitives:int
    degenerate_uv_triangles:int
    invalid_tangent_primitives:int
    primitives:list[UVPrimitiveAudit]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-uv-tangent-qa-v1"


def _deps():
    import numpy as np
    return np


def _material_texcoord_sets(material:dict)->tuple[set[int],set[int]]:
    required=set()
    normal_sets=set()

    def add(texture_info, *, normal:bool=False):
        if not isinstance(texture_info,dict):
            return
        if not isinstance(texture_info.get("index"),int):
            return
        texcoord=int(texture_info.get("texCoord") or 0)
        required.add(texcoord)
        if normal:
            normal_sets.add(texcoord)

    pbr=material.get("pbrMetallicRoughness") or {}
    add(pbr.get("baseColorTexture"))
    add(pbr.get("metallicRoughnessTexture"))
    add(material.get("normalTexture"),normal=True)
    add(material.get("occlusionTexture"))
    add(material.get("emissiveTexture"))
    return required,normal_sets


def _indices_for_primitive(path:Path,primitive:dict,position_count:int):
    np=_deps()
    from skin_weight_qa import _read_accessor
    from gltf_position_patch import _doc_and_bin
    doc,binary,_=_doc_and_bin(path)
    index=primitive.get("indices")
    if isinstance(index,int):
        rows=_read_accessor(doc,binary,index)
        return np.asarray(
            [int(row[0]) for row in rows],
            dtype=np.int64,
        )
    return np.arange(position_count,dtype=np.int64)


def _read_rows(path:Path,index:int):
    from skin_weight_qa import _read_accessor
    from gltf_position_patch import _doc_and_bin
    doc,binary,_=_doc_and_bin(path)
    return _read_accessor(doc,binary,index)


def _triangle_indices(indices,mode:int):
    np=_deps()
    indices=np.asarray(indices,dtype=np.int64).reshape(-1)
    if mode==4:
        usable=(len(indices)//3)*3
        return indices[:usable].reshape(-1,3)
    if mode==5:
        out=[]
        for i in range(max(0,len(indices)-2)):
            tri=[int(indices[i]),int(indices[i+1]),int(indices[i+2])]
            if i%2:
                tri[0],tri[1]=tri[1],tri[0]
            out.append(tri)
        return np.asarray(out,dtype=np.int64).reshape(-1,3)
    if mode==6:
        if len(indices)<3:
            return np.zeros((0,3),dtype=np.int64)
        return np.asarray(
            [
                [int(indices[0]),int(indices[i]),int(indices[i+1])]
                for i in range(1,len(indices)-1)
            ],
            dtype=np.int64,
        )
    raise ValueError(f"unsupported primitive mode for UV audit: {mode}")


def _triangle_health(positions,uvs,triangles):
    np=_deps()
    if not len(triangles):
        return 0,0,0.0
    geom_bad=0
    uv_bad=0

    extent=np.max(positions,axis=0)-np.min(positions,axis=0)
    geom_scale=max(float(np.linalg.norm(extent)),1e-12)
    geom_eps=(geom_scale*geom_scale)*1e-14
    uv_eps=1e-12

    for tri in triangles:
        p=positions[tri]
        uv=uvs[tri]
        geom_cross=np.cross(p[1]-p[0],p[2]-p[0])
        geom_area2=float(np.linalg.norm(geom_cross))
        duv1=uv[1]-uv[0]
        duv2=uv[2]-uv[0]
        uv_det=abs(float(
            duv1[0]*duv2[1]-duv1[1]*duv2[0]
        ))
        if geom_area2<=geom_eps:
            geom_bad+=1
            continue
        if uv_det<=uv_eps:
            uv_bad+=1

    valid_geom=max(len(triangles)-geom_bad,1)
    return geom_bad,uv_bad,float(uv_bad/valid_geom)


def audit_uv_tangents(
    path:Path,
    *,
    max_degenerate_uv_ratio:float=0.02,
)->UVTangentAudit:
    np=_deps()
    warnings=[]
    errors=[]
    reports=[]

    try:
        from gltf_audit import read_glb_json
        doc=read_glb_json(path)
    except Exception as exc:
        return UVTangentAudit(
            path=str(path),applicable=False,ready=False,
            primitive_count=0,textured_primitives=0,
            normal_mapped_primitives=0,missing_uv_primitives=0,
            degenerate_uv_triangles=0,invalid_tangent_primitives=0,
            primitives=[],warnings=[],
            errors=[f"{type(exc).__name__}:{exc}"],
        )

    materials=doc.get("materials") or []
    primitive_count=0
    textured_count=0
    normal_count=0
    missing_count=0
    degenerate_total=0
    invalid_tangent_count=0

    for mesh_index,mesh in enumerate(doc.get("meshes") or []):
        for primitive_index,primitive in enumerate(mesh.get("primitives") or []):
            primitive_count+=1
            p_errors=[]
            attrs=primitive.get("attributes") or {}
            material_index=primitive.get("material")
            material=(
                materials[material_index]
                if isinstance(material_index,int)
                and 0<=material_index<len(materials)
                else {}
            )
            required_sets,normal_sets=_material_texcoord_sets(material)
            textured=bool(required_sets)
            normal_mapped=bool(normal_sets)
            if textured:
                textured_count+=1
            if normal_mapped:
                normal_count+=1

            position_index=attrs.get("POSITION")
            if not isinstance(position_index,int):
                p_errors.append("primitive has no POSITION accessor")
                position_count=0
                positions=np.zeros((0,3),dtype=np.float64)
            else:
                try:
                    positions=np.asarray(
                        _read_rows(path,position_index),
                        dtype=np.float64,
                    )
                    position_count=len(positions)
                    if (
                        positions.ndim!=2
                        or positions.shape[1]!=3
                        or not np.isfinite(positions).all()
                    ):
                        p_errors.append("POSITION accessor is non-finite or not VEC3")
                except Exception as exc:
                    positions=np.zeros((0,3),dtype=np.float64)
                    position_count=0
                    p_errors.append(
                        f"POSITION read failed: {type(exc).__name__}:{exc}"
                    )

            present_sets=sorted(
                int(name.split("_",1)[1])
                for name in attrs
                if str(name).startswith("TEXCOORD_")
                and str(name).split("_",1)[1].isdigit()
            )
            missing=sorted(required_sets-set(present_sets))
            if missing:
                missing_count+=1
                p_errors.append(
                    "missing required UV sets: "
                    +",".join(f"TEXCOORD_{x}" for x in missing)
                )

            triangle_count=0
            geom_bad=0
            uv_bad=0
            uv_ratio=0.0
            tangent_present=isinstance(attrs.get("TANGENT"),int)
            tangent_valid=None
            tangent_derivable=None

            primary_set=(
                min(normal_sets)
                if normal_sets
                else (min(required_sets) if required_sets else None)
            )
            if textured and primary_set is not None and primary_set not in missing:
                uv_index=attrs.get(f"TEXCOORD_{primary_set}")
                try:
                    uvs=np.asarray(
                        _read_rows(path,int(uv_index)),
                        dtype=np.float64,
                    )
                    if (
                        uvs.ndim!=2
                        or uvs.shape[1]!=2
                        or len(uvs)!=position_count
                        or not np.isfinite(uvs).all()
                    ):
                        raise ValueError(
                            "UV accessor must be finite VEC2 and match POSITION count"
                        )
                    raw_indices=_indices_for_primitive(
                        path,primitive,position_count
                    )
                    triangles=_triangle_indices(
                        raw_indices,
                        int(primitive.get("mode",4)),
                    )
                    triangle_count=len(triangles)
                    if len(triangles):
                        if (
                            int(np.min(triangles))<0
                            or int(np.max(triangles))>=position_count
                        ):
                            raise ValueError(
                                "triangle indices reference vertices out of range"
                            )
                    geom_bad,uv_bad,uv_ratio=_triangle_health(
                        positions,uvs,triangles
                    )
                    degenerate_total+=uv_bad
                    if uv_ratio>max_degenerate_uv_ratio:
                        p_errors.append(
                            "degenerate UV triangle ratio "
                            f"{uv_ratio:.6f}>{max_degenerate_uv_ratio:.6f}"
                        )
                    tangent_derivable=bool(
                        normal_mapped
                        and triangle_count>0
                        and uv_ratio<=max_degenerate_uv_ratio
                    )
                except Exception as exc:
                    p_errors.append(
                        f"UV/tangent derivation failed: {type(exc).__name__}:{exc}"
                    )
                    tangent_derivable=False if normal_mapped else None

            if tangent_present:
                try:
                    tangents=np.asarray(
                        _read_rows(path,int(attrs["TANGENT"])),
                        dtype=np.float64,
                    )
                    tangent_valid=bool(
                        tangents.ndim==2
                        and tangents.shape[1]==4
                        and len(tangents)==position_count
                        and np.isfinite(tangents).all()
                        and np.all(
                            np.linalg.norm(tangents[:,:3],axis=1)>1e-8
                        )
                    )
                    if not tangent_valid:
                        p_errors.append(
                            "TANGENT accessor is non-finite, zero-length, "
                            "not VEC4, or count-mismatched"
                        )
                except Exception as exc:
                    tangent_valid=False
                    p_errors.append(
                        f"TANGENT read failed: {type(exc).__name__}:{exc}"
                    )
                if tangent_valid is False:
                    invalid_tangent_count+=1

            if normal_mapped and not (
                tangent_valid is True
                or tangent_derivable is True
            ):
                p_errors.append(
                    "normal-mapped primitive has no valid or derivable tangent basis"
                )

            ready=not p_errors
            if not ready:
                errors.extend(
                    f"mesh[{mesh_index}].primitive[{primitive_index}]: {item}"
                    for item in p_errors
                )
            reports.append(UVPrimitiveAudit(
                mesh_index=mesh_index,
                primitive_index=primitive_index,
                material_index=(
                    int(material_index)
                    if isinstance(material_index,int)
                    else None
                ),
                textured=textured,
                normal_mapped=normal_mapped,
                position_count=position_count,
                required_texcoord_sets=sorted(required_sets),
                present_texcoord_sets=present_sets,
                missing_texcoord_sets=missing,
                triangle_count=triangle_count,
                degenerate_geometry_triangles=geom_bad,
                degenerate_uv_triangles=uv_bad,
                degenerate_uv_ratio=round(uv_ratio,8),
                tangent_present=tangent_present,
                tangent_valid=tangent_valid,
                tangent_derivable=tangent_derivable,
                ready=ready,
                errors=p_errors,
            ))

    applicable=bool(textured_count)
    return UVTangentAudit(
        path=str(path),
        applicable=applicable,
        ready=not errors,
        primitive_count=primitive_count,
        textured_primitives=textured_count,
        normal_mapped_primitives=normal_count,
        missing_uv_primitives=missing_count,
        degenerate_uv_triangles=degenerate_total,
        invalid_tangent_primitives=invalid_tangent_count,
        primitives=reports,
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA UV and tangent-basis structural QA."
    )
    parser.add_argument("glb",type=Path)
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    report=audit_uv_tangents(args.glb)
    payload=json.dumps(asdict(report),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
