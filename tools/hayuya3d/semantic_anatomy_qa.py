#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Iterable

from part_segmentation_plan import (
    CRITICAL_CHARACTER_TARGETS,
    PROFILE_PARTS,
)


@dataclass
class SemanticPartEvidence:
    part:str
    required:bool
    detected_views:int
    best_grounding_score:float|None
    best_sam_iou_score:float|None
    max_mask_area_ratio:float|None
    views:list[str]
    ready:bool


@dataclass
class SemanticAnatomyReport:
    required:bool
    ready:bool
    critical_targets:list[str]
    required_parts:list[str]
    detected_parts:list[str]
    missing_parts:list[str]
    view_count:int
    parts:list[SemanticPartEvidence]
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-semantic-anatomy-multiview-v1"


def required_parts_for_targets(
    critical_targets:Iterable[str],
)->list[str]:
    parts=[]
    for target in critical_targets:
        key=str(target).strip().lower()
        for part in CRITICAL_CHARACTER_TARGETS.get(key,[]):
            if part not in parts:
                parts.append(part)
    return parts


def build_critical_plan(
    critical_targets:Iterable[str],
)->dict:
    targets=[
        str(x).strip().lower()
        for x in critical_targets
        if str(x).strip()
    ]
    required=required_parts_for_targets(targets)
    prompts=PROFILE_PARTS["character.humanoid"]["prompts"]
    missing_prompts=[
        part for part in required
        if part not in prompts or not prompts.get(part)
    ]
    return {
        "schema":1,
        "asset_profile":"character.humanoid",
        "status":"ready" if required and not missing_prompts else (
            "not_required" if not required else "blocked"
        ),
        "critical_targets":targets,
        "required":required,
        "optional":[],
        "prompts":{
            part:list(prompts[part])
            for part in required
            if part in prompts
        },
        "detectors":["groundingdino","sam2"] if required else [],
        "projection":"multi_view_required_for_critical_anatomy",
        "confidence_gate":0.72,
        "warnings":[
            *[
                "unknown_critical_target:"+target
                for target in targets
                if target not in CRITICAL_CHARACTER_TARGETS
            ],
            *[
                "required_part_missing_prompt:"+part
                for part in missing_prompts
            ],
        ],
    }


def _finite(value):
    try:
        number=float(value)
    except (TypeError,ValueError):
        return None
    if number!=number or number in (float("inf"),float("-inf")):
        return None
    return number


def aggregate_semantic_reports(
    reports:Iterable[dict],
    *,
    critical_targets:Iterable[str],
    minimum_views_per_part:int=1,
)->SemanticAnatomyReport:
    targets=[
        str(x).strip().lower()
        for x in critical_targets
        if str(x).strip()
    ]
    required=required_parts_for_targets(targets)
    if not required:
        return SemanticAnatomyReport(
            required=False,
            ready=True,
            critical_targets=targets,
            required_parts=[],
            detected_parts=[],
            missing_parts=[],
            view_count=0,
            parts=[],
            warnings=[],
            errors=[],
        )

    evidence={
        part:{
            "views":set(),
            "grounding":[],
            "sam":[],
            "areas":[],
        }
        for part in required
    }
    warnings=[]
    errors=[]
    view_count=0

    for index,report in enumerate(reports):
        if not isinstance(report,dict):
            errors.append(f"report[{index}] is not an object")
            continue
        image=str(report.get("image") or f"view_{index}")
        view_count+=1
        detections=report.get("detections") or []
        if not isinstance(detections,list):
            errors.append(f"report[{index}] detections is not a list")
            continue
        for detection in detections:
            if not isinstance(detection,dict):
                continue
            part=str(detection.get("part") or "")
            if part not in evidence:
                continue
            evidence[part]["views"].add(image)
            grounding=_finite(detection.get("grounding_score"))
            sam=_finite(detection.get("sam_iou_score"))
            area=_finite(detection.get("mask_area_ratio"))
            if grounding is not None:
                evidence[part]["grounding"].append(grounding)
            if sam is not None:
                evidence[part]["sam"].append(sam)
            if area is not None:
                evidence[part]["areas"].append(area)

    items=[]
    missing=[]
    detected=[]
    min_views=max(1,int(minimum_views_per_part))
    for part in required:
        item=evidence[part]
        views=sorted(item["views"])
        ready=len(views)>=min_views
        if ready:
            detected.append(part)
        else:
            missing.append(part)
        items.append(SemanticPartEvidence(
            part=part,
            required=True,
            detected_views=len(views),
            best_grounding_score=(
                max(item["grounding"])
                if item["grounding"] else None
            ),
            best_sam_iou_score=(
                max(item["sam"])
                if item["sam"] else None
            ),
            max_mask_area_ratio=(
                max(item["areas"])
                if item["areas"] else None
            ),
            views=views,
            ready=ready,
        ))

    if view_count<1:
        errors.append("no semantic detector reports were supplied")
    if missing:
        warnings.append(
            "critical semantic parts missing from final GLB renders: "
            +",".join(missing)
        )

    return SemanticAnatomyReport(
        required=True,
        ready=bool(view_count>=1 and not missing and not errors),
        critical_targets=targets,
        required_parts=required,
        detected_parts=detected,
        missing_parts=missing,
        view_count=view_count,
        parts=items,
        warnings=warnings,
        errors=errors,
    )


def load_and_aggregate(
    report_paths:Iterable[Path],
    *,
    critical_targets:Iterable[str],
    minimum_views_per_part:int=1,
)->SemanticAnatomyReport:
    reports=[]
    errors=[]
    for path in report_paths:
        try:
            reports.append(
                json.loads(
                    Path(path).read_text(encoding="utf-8")
                )
            )
        except Exception as exc:
            errors.append(
                f"{path}:{type(exc).__name__}:{exc}"
            )
    result=aggregate_semantic_reports(
        reports,
        critical_targets=critical_targets,
        minimum_views_per_part=minimum_views_per_part,
    )
    if errors:
        result.errors.extend(errors)
        result.ready=False
    return result


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description=(
            "Aggregate GroundingDINO/SAM2 semantic evidence "
            "across final HAYUYA GLB renders."
        )
    )
    parser.add_argument(
        "--report",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument(
        "--critical-target",
        action="append",
        default=[],
        choices=sorted(CRITICAL_CHARACTER_TARGETS),
    )
    parser.add_argument(
        "--minimum-views-per-part",
        type=int,
        default=1,
    )
    parser.add_argument("--json",type=Path)
    args=parser.parse_args()
    result=load_and_aggregate(
        args.report,
        critical_targets=args.critical_target,
        minimum_views_per_part=args.minimum_views_per_part,
    )
    payload=json.dumps(asdict(result),indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if result.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
