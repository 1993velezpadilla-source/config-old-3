#!/usr/bin/env python3
from __future__ import annotations

import io
import json
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class RuntimeLODBudgetItem:
    name:str
    path:str
    ready:bool
    faces:int
    face_budget_max:int
    material_count:int
    material_slots_max:int
    primitive_count:int
    texture_count:int
    texture_max_edge:int
    texture_edge_max:int
    estimated_rgba_bytes:int
    joint_count:int
    morph_target_count:int
    errors:list[str]


@dataclass
class RuntimeBudgetReport:
    tier:str
    mode:str
    ready:bool
    lod_count:int
    items:list[RuntimeLODBudgetItem]
    total_estimated_rgba_bytes:int
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-runtime-budget-qa-v1"


def _lod_budget(plan:dict,name:str)->int:
    runtime=plan.get("runtime_target") or {}
    key=str(name).lower()
    if key.startswith("lod0"):
        budget=runtime.get("lod0_triangles")
    elif key.startswith("lod1"):
        budget=runtime.get("lod1_triangles")
    elif key.startswith("lod2"):
        budget=runtime.get("lod2_triangles")
    elif key.startswith("lod3"):
        budget=runtime.get("lod3_triangles")
    else:
        raise ValueError(f"unrecognized LOD name: {name}")
    if not isinstance(budget,(list,tuple)) or len(budget)<2:
        raise ValueError(f"missing triangle budget for {name}")
    return int(budget[1])


def _primitive_count(path:Path)->int:
    from gltf_audit import read_glb_json
    doc=read_glb_json(path)
    return sum(
        len(mesh.get("primitives") or [])
        for mesh in (doc.get("meshes") or [])
    )


def _texture_stats(path:Path)->tuple[int,int,int]:
    from PIL import Image
    from texture_gate import embedded_images

    count=0
    max_edge=0
    rgba_bytes=0
    for _,_,payload,_ in embedded_images(path):
        count+=1
        with Image.open(io.BytesIO(payload)) as image:
            width,height=image.size
        max_edge=max(max_edge,int(width),int(height))
        rgba_bytes+=int(width)*int(height)*4
    return count,max_edge,rgba_bytes


def audit_runtime_lod(
    path:Path,
    *,
    name:str,
    plan:dict,
    mode:str,
)->RuntimeLODBudgetItem:
    errors=[]
    face_budget=_lod_budget(plan,name)
    runtime=plan.get("runtime_target") or {}
    slots=runtime.get("material_slots_target") or [0,0]
    material_max=int(slots[1]) if len(slots)>=2 else 0
    texture_max=int(runtime.get("exceptional_texture_edge_px") or 0)

    try:
        from qa import inspect_mesh
        from gltf_audit import audit_glb

        mesh=inspect_mesh(
            path,
            backend=f"runtime_budget_{name}",
            mode=mode,
            target_faces=max(1,face_budget),
        )
        gltf=audit_glb(path)
        primitives=_primitive_count(path)
        texture_count,texture_edge,rgba_bytes=_texture_stats(path)

        if int(mesh.faces)>face_budget:
            errors.append(
                f"triangles {mesh.faces}>{face_budget}"
            )
        if material_max>0 and int(gltf.material_count)>material_max:
            errors.append(
                f"material slots {gltf.material_count}>{material_max}"
            )
        if texture_max>0 and texture_edge>texture_max:
            errors.append(
                f"texture edge {texture_edge}>{texture_max}"
            )
        if not mesh.valid:
            errors.append("mesh QA invalid")
        if not gltf.valid_glb:
            errors.append("invalid GLB")

        return RuntimeLODBudgetItem(
            name=name,
            path=str(path),
            ready=not errors,
            faces=int(mesh.faces),
            face_budget_max=face_budget,
            material_count=int(gltf.material_count),
            material_slots_max=material_max,
            primitive_count=int(primitives),
            texture_count=int(texture_count),
            texture_max_edge=int(texture_edge),
            texture_edge_max=texture_max,
            estimated_rgba_bytes=int(rgba_bytes),
            joint_count=int(gltf.joint_count),
            morph_target_count=int(gltf.morph_target_count),
            errors=errors,
        )
    except Exception as exc:
        return RuntimeLODBudgetItem(
            name=name,
            path=str(path),
            ready=False,
            faces=0,
            face_budget_max=face_budget,
            material_count=0,
            material_slots_max=material_max,
            primitive_count=0,
            texture_count=0,
            texture_max_edge=0,
            texture_edge_max=texture_max,
            estimated_rgba_bytes=0,
            joint_count=0,
            morph_target_count=0,
            errors=[f"{type(exc).__name__}:{exc}"],
        )


def audit_runtime_tier(
    lods:Iterable[Path|tuple[str,Path]],
    *,
    plan:dict,
    mode:str,
)->RuntimeBudgetReport:
    items=[]
    for index,item in enumerate(lods):
        if isinstance(item,tuple):
            name,path=item
        else:
            name=f"LOD{index}"
            path=Path(item)
        items.append(audit_runtime_lod(
            Path(path),
            name=str(name),
            plan=plan,
            mode=mode,
        ))

    warnings=[]
    errors=[]
    for item in items:
        if not item.ready:
            errors.append(
                f"{item.name}: "+"; ".join(item.errors)
            )

    # Primitive count is evidence only. HAYUYA deliberately does not pretend
    # that one per-asset draw-call ceiling is universal across engines/devices.
    if any(item.primitive_count>item.material_slots_max*4 for item in items if item.material_slots_max>0):
        warnings.append(
            "primitive count materially exceeds material-slot target; "
            "profile draw submission on target engines/devices"
        )

    total=sum(item.estimated_rgba_bytes for item in items)
    return RuntimeBudgetReport(
        tier=str(plan.get("tier") or "unknown"),
        mode=mode,
        ready=bool(items and all(item.ready for item in items)),
        lod_count=len(items),
        items=items,
        total_estimated_rgba_bytes=total,
        warnings=warnings,
        errors=errors,
    )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA per-tier runtime asset budget QA."
    )
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--lod",action="append",type=Path,default=[])
    parser.add_argument(
        "--mode",
        choices=["prop","character","architecture"],
        required=True,
    )
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    plan=json.loads(args.plan.read_text(encoding="utf-8"))
    report=audit_runtime_tier(
        args.lod,
        plan=plan,
        mode=args.mode,
    )
    payload=json.dumps(asdict(report),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
