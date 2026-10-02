#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class ShadingPrimitiveAudit:
    mesh_index:int
    primitive_index:int
    vertices:int
    has_normal_map:bool
    normals_present:bool
    tangents_present:bool
    nonfinite_normals:int
    nonunit_normals:int
    nonfinite_tangents:int
    nonunit_tangents:int
    invalid_handedness:int
    nonorthogonal_tangents:int
    ready:bool
    errors:list[str]
    warnings:list[str]


@dataclass
class ShadingBasisAudit:
    path:str
    applicable:bool
    ready:bool
    primitive_count:int
    normal_mapped_primitives:int
    explicit_tangent_primitives:int
    missing_normals:int
    missing_required_tangents:int
    nonfinite_vectors:int
    nonunit_vectors:int
    invalid_handedness:int
    nonorthogonal_tangents:int
    primitives:list[ShadingPrimitiveAudit]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-shading-basis-qa-v1"


def _material_has_normal_map(doc:dict,index)->bool:
    materials=doc.get("materials") or []
    return bool(
        isinstance(index,int)
        and 0<=index<len(materials)
        and isinstance(materials[index].get("normalTexture"),dict)
    )


def _vec3_metrics(rows,*,unit_tolerance:float):
    nonfinite=0
    nonunit=0
    vectors=[]
    for row in rows:
        try:
            vec=[float(row[0]),float(row[1]),float(row[2])]
        except Exception:
            nonfinite+=1
            vectors.append(None)
            continue
        if not all(math.isfinite(x) for x in vec):
            nonfinite+=1
            vectors.append(None)
            continue
        norm=math.sqrt(sum(x*x for x in vec))
        if abs(norm-1.0)>unit_tolerance:
            nonunit+=1
        vectors.append((vec,norm))
    return vectors,nonfinite,nonunit


def audit_shading_basis(
    path:Path,
    *,
    unit_tolerance:float=0.05,
    orthogonality_tolerance:float=0.08,
    handedness_tolerance:float=0.02,
    require_explicit_tangents_for_normal_maps:bool=True,
)->ShadingBasisAudit:
    warnings=[]
    errors=[]
    primitive_reports=[]
    totals={
        "primitives":0,
        "normal_mapped":0,
        "explicit_tangents":0,
        "missing_normals":0,
        "missing_tangents":0,
        "nonfinite":0,
        "nonunit":0,
        "handedness":0,
        "orthogonal":0,
    }
    try:
        from skin_weight_qa import _read_accessor,_read_glb
        doc,binary=_read_glb(path)
    except Exception as exc:
        return ShadingBasisAudit(
            path=str(path),applicable=False,ready=False,
            primitive_count=0,normal_mapped_primitives=0,
            explicit_tangent_primitives=0,missing_normals=0,
            missing_required_tangents=0,nonfinite_vectors=0,
            nonunit_vectors=0,invalid_handedness=0,
            nonorthogonal_tangents=0,primitives=[],warnings=[],
            errors=[f"{type(exc).__name__}:{exc}"],
        )

    meshes=doc.get("meshes") or []
    for mesh_index,mesh in enumerate(meshes):
        for primitive_index,primitive in enumerate(mesh.get("primitives") or []):
            mode=int(primitive.get("mode",4))
            if mode!=4:
                continue
            totals["primitives"]+=1
            item_errors=[]
            item_warnings=[]
            attrs=primitive.get("attributes") or {}
            position_index=attrs.get("POSITION")
            normal_index=attrs.get("NORMAL")
            tangent_index=attrs.get("TANGENT")
            normal_map=_material_has_normal_map(
                doc,primitive.get("material")
            )
            if normal_map:
                totals["normal_mapped"]+=1

            try:
                positions=_read_accessor(
                    doc,binary,int(position_index)
                )
                vertex_count=len(positions)
            except Exception as exc:
                primitive_reports.append(ShadingPrimitiveAudit(
                    mesh_index=mesh_index,
                    primitive_index=primitive_index,
                    vertices=0,
                    has_normal_map=normal_map,
                    normals_present=normal_index is not None,
                    tangents_present=tangent_index is not None,
                    nonfinite_normals=0,nonunit_normals=0,
                    nonfinite_tangents=0,nonunit_tangents=0,
                    invalid_handedness=0,nonorthogonal_tangents=0,
                    ready=False,
                    errors=[
                        "POSITION accessor unavailable: "
                        f"{type(exc).__name__}:{exc}"
                    ],
                    warnings=[],
                ))
                errors.append(
                    f"mesh[{mesh_index}].primitive[{primitive_index}] "
                    "POSITION accessor unavailable"
                )
                continue

            normals_present=normal_index is not None
            tangents_present=tangent_index is not None
            if tangents_present:
                totals["explicit_tangents"]+=1

            normal_vectors=[]
            normal_bad=normal_nonunit=0
            tangent_bad=tangent_nonunit=0
            invalid_handedness=0
            nonorthogonal=0

            if not normals_present:
                totals["missing_normals"]+=1
                item_errors.append("triangle primitive has no NORMAL attribute")
            else:
                try:
                    normals=_read_accessor(
                        doc,binary,int(normal_index)
                    )
                    if len(normals)!=vertex_count:
                        item_errors.append(
                            f"NORMAL count {len(normals)} != POSITION {vertex_count}"
                        )
                    normal_vectors,normal_bad,normal_nonunit=(
                        _vec3_metrics(
                            normals,
                            unit_tolerance=unit_tolerance,
                        )
                    )
                    if normal_bad:
                        item_errors.append(
                            f"non-finite normals: {normal_bad}"
                        )
                    if normal_nonunit:
                        item_errors.append(
                            f"non-unit normals: {normal_nonunit}"
                        )
                except Exception as exc:
                    item_errors.append(
                        "NORMAL accessor read failed: "
                        f"{type(exc).__name__}:{exc}"
                    )
                    normal_bad=max(1,vertex_count)

            if normal_map and require_explicit_tangents_for_normal_maps and not tangents_present:
                totals["missing_tangents"]+=1
                item_errors.append(
                    "normal-mapped primitive has no explicit TANGENT basis"
                )
            elif normal_map and not tangents_present:
                item_warnings.append(
                    "normal-mapped primitive relies on runtime tangent reconstruction"
                )

            if tangents_present:
                try:
                    tangents=_read_accessor(
                        doc,binary,int(tangent_index)
                    )
                    if len(tangents)!=vertex_count:
                        item_errors.append(
                            f"TANGENT count {len(tangents)} != POSITION {vertex_count}"
                        )
                    xyz_rows=[]
                    for row in tangents:
                        if len(row)<4:
                            tangent_bad+=1
                            xyz_rows.append([float("nan")]*3)
                            continue
                        xyz_rows.append(row[:3])
                        try:
                            w=float(row[3])
                        except Exception:
                            invalid_handedness+=1
                            continue
                        if (
                            not math.isfinite(w)
                            or abs(abs(w)-1.0)>handedness_tolerance
                        ):
                            invalid_handedness+=1

                    tangent_vectors,tangent_nonfinite,tangent_nonunit=(
                        _vec3_metrics(
                            xyz_rows,
                            unit_tolerance=unit_tolerance,
                        )
                    )
                    tangent_bad+=tangent_nonfinite

                    if normals_present and normal_vectors:
                        count=min(
                            len(normal_vectors),
                            len(tangent_vectors),
                        )
                        for idx in range(count):
                            n=normal_vectors[idx]
                            t=tangent_vectors[idx]
                            if n is None or t is None:
                                continue
                            nvec,nnorm=n
                            tvec,tnorm=t
                            if nnorm<=1e-12 or tnorm<=1e-12:
                                continue
                            dot=sum(
                                a*b for a,b in zip(nvec,tvec)
                            )/(nnorm*tnorm)
                            if (
                                not math.isfinite(dot)
                                or abs(dot)>orthogonality_tolerance
                            ):
                                nonorthogonal+=1

                    if tangent_bad:
                        item_errors.append(
                            f"non-finite/malformed tangents: {tangent_bad}"
                        )
                    if tangent_nonunit:
                        item_errors.append(
                            f"non-unit tangents: {tangent_nonunit}"
                        )
                    if invalid_handedness:
                        item_errors.append(
                            "invalid tangent handedness: "
                            f"{invalid_handedness}"
                        )
                    if nonorthogonal:
                        item_errors.append(
                            "normal/tangent non-orthogonal vertices: "
                            f"{nonorthogonal}"
                        )
                except Exception as exc:
                    item_errors.append(
                        "TANGENT accessor read failed: "
                        f"{type(exc).__name__}:{exc}"
                    )
                    tangent_bad=max(1,vertex_count)

            totals["nonfinite"]+=normal_bad+tangent_bad
            totals["nonunit"]+=normal_nonunit+tangent_nonunit
            totals["handedness"]+=invalid_handedness
            totals["orthogonal"]+=nonorthogonal
            ready=not item_errors
            if item_errors:
                errors.extend(
                    f"mesh[{mesh_index}].primitive[{primitive_index}]: {msg}"
                    for msg in item_errors
                )
            warnings.extend(
                f"mesh[{mesh_index}].primitive[{primitive_index}]: {msg}"
                for msg in item_warnings
            )
            primitive_reports.append(ShadingPrimitiveAudit(
                mesh_index=mesh_index,
                primitive_index=primitive_index,
                vertices=vertex_count,
                has_normal_map=normal_map,
                normals_present=normals_present,
                tangents_present=tangents_present,
                nonfinite_normals=normal_bad,
                nonunit_normals=normal_nonunit,
                nonfinite_tangents=tangent_bad,
                nonunit_tangents=tangent_nonunit,
                invalid_handedness=invalid_handedness,
                nonorthogonal_tangents=nonorthogonal,
                ready=ready,
                errors=item_errors,
                warnings=item_warnings,
            ))

    applicable=totals["primitives"]>0
    if not applicable:
        warnings.append("no triangle primitives to audit")
    return ShadingBasisAudit(
        path=str(path),
        applicable=applicable,
        ready=bool(applicable and not errors),
        primitive_count=totals["primitives"],
        normal_mapped_primitives=totals["normal_mapped"],
        explicit_tangent_primitives=totals["explicit_tangents"],
        missing_normals=totals["missing_normals"],
        missing_required_tangents=totals["missing_tangents"],
        nonfinite_vectors=totals["nonfinite"],
        nonunit_vectors=totals["nonunit"],
        invalid_handedness=totals["handedness"],
        nonorthogonal_tangents=totals["orthogonal"],
        primitives=primitive_reports,
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA vertex normal/tangent basis QA."
    )
    parser.add_argument("glb",type=Path)
    parser.add_argument("--json",type=Path)
    parser.add_argument(
        "--allow-runtime-tangents",
        action="store_true",
    )
    args=parser.parse_args()
    report=audit_shading_basis(
        args.glb,
        require_explicit_tangents_for_normal_maps=(
            not args.allow_runtime_tangents
        ),
    )
    payload=json.dumps(asdict(report),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
