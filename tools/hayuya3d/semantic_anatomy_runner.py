#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Iterable

from anatomy_reference import infer_anatomy_target
from semantic_anatomy_qa import (
    aggregate_semantic_reports,
    build_critical_plan,
)


@dataclass
class SemanticAnatomyRun:
    required:bool
    attempted:bool
    ready:bool
    critical_targets:list[str]
    plan:str|None
    rendered_views:list[str]
    detector_reports:list[str]
    aggregate:dict|None
    error:str|None=None
    method:str="hayuya-semantic-anatomy-runner-v1"


def infer_critical_targets(
    detail_images:Iterable[Path],
)->list[str]:
    targets=[]
    for path in detail_images:
        target=infer_anatomy_target(Path(path))
        if target and target not in targets:
            targets.append(target)
    return targets


HEAD_CLOSEUP_TARGETS={"eyes","mouth","teeth","hair","ears"}


def frame_targets(
    critical_targets:Iterable[str],
    frame:str,
)->list[str]:
    targets=[
        str(x).strip().lower()
        for x in critical_targets
        if str(x).strip()
    ]
    if frame=="head":
        return [
            target for target in targets
            if target in HEAD_CLOSEUP_TARGETS
        ]
    if frame=="full":
        return [
            target for target in targets
            if target not in HEAD_CLOSEUP_TARGETS
        ]
    return list(targets)


def render_specs(
    critical_targets:Iterable[str],
    views:Iterable[str],
)->list[tuple[str,str]]:
    targets=[
        str(x).strip().lower()
        for x in critical_targets
        if str(x).strip()
    ]
    specs=[]
    if frame_targets(targets,"full"):
        for view in views:
            view=str(view)
            spec=(view,"full")
            if spec not in specs:
                specs.append(spec)
    if frame_targets(targets,"head"):
        for view in ("front","side"):
            spec=(view,"head")
            if spec not in specs:
                specs.append(spec)
    return specs


def semantic_stack_ready()->tuple[bool,list[str]]:
    missing=[]
    if shutil.which("blender") is None:
        missing.append("blender")
    for module in ("torch","transformers","PIL"):
        if importlib.util.find_spec(module) is None:
            missing.append(module)
    return not missing,missing


def run_semantic_anatomy(
    final_glb:Path,
    detail_images:Iterable[Path],
    out_dir:Path,
    *,
    policy:str="auto",
    views:Iterable[str]=("front","side","rear"),
    minimum_views_per_part:int=1,
    python_executable:str|None=None,
)->SemanticAnatomyRun:
    policy=str(policy).lower()
    if policy not in {"off","auto","required"}:
        raise ValueError(
            "semantic anatomy policy must be off, auto, or required"
        )

    targets=infer_critical_targets(detail_images)
    required=bool(targets)
    if policy=="off" or not required:
        return SemanticAnatomyRun(
            required=required,
            attempted=False,
            ready=not required,
            critical_targets=targets,
            plan=None,
            rendered_views=[],
            detector_reports=[],
            aggregate=None,
            error=None,
        )

    ready_stack,missing=semantic_stack_ready()
    if not ready_stack:
        error="semantic_stack_unavailable:"+",".join(missing)
        if policy=="required":
            return SemanticAnatomyRun(
                required=True,
                attempted=False,
                ready=False,
                critical_targets=targets,
                plan=None,
                rendered_views=[],
                detector_reports=[],
                aggregate=None,
                error=error,
            )
        return SemanticAnatomyRun(
            required=True,
            attempted=False,
            ready=False,
            critical_targets=targets,
            plan=None,
            rendered_views=[],
            detector_reports=[],
            aggregate=None,
            error=error,
        )

    root=Path(__file__).resolve().parent
    render_script=root/"blender_reference_render.py"
    detector_script=root/"semantic_part_detector.py"
    out_dir.mkdir(parents=True,exist_ok=True)
    plan_data=build_critical_plan(targets)
    plan_path=out_dir/"semantic_anatomy_plan.json"
    plan_path.write_text(
        json.dumps(plan_data,indent=2)+"\n",
        encoding="utf-8",
    )
    frame_plans={}
    for frame in ("full","head"):
        selected=frame_targets(targets,frame)
        if not selected:
            continue
        frame_plan=build_critical_plan(selected)
        frame_plan_path=out_dir/f"semantic_anatomy_plan_{frame}.json"
        frame_plan_path.write_text(
            json.dumps(frame_plan,indent=2)+"\n",
            encoding="utf-8",
        )
        frame_plans[frame]=(frame_plan_path,frame_plan)
    if plan_data.get("status")!="ready":
        return SemanticAnatomyRun(
            required=True,
            attempted=False,
            ready=False,
            critical_targets=targets,
            plan=str(plan_path),
            rendered_views=[],
            detector_reports=[],
            aggregate=None,
            error=(
                "critical_plan_not_ready:"
                +";".join(plan_data.get("warnings") or [])
            ),
        )

    py=python_executable or sys.executable
    rendered=[]
    reports=[]
    report_data=[]
    try:
        for view,frame in render_specs(targets,views):
            if view not in {"front","side","rear","top"}:
                raise ValueError(f"unsupported semantic render view: {view}")
            label=view if frame=="full" else f"{view}_{frame}"
            render_path=out_dir/f"{label}.png"
            subprocess.run(
                [
                    "blender","-b",
                    "--python",str(render_script),
                    "--",
                    "--input",str(final_glb),
                    "--output",str(render_path),
                    "--size","1024",
                    "--view",view,
                    "--frame",frame,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            rendered.append(str(render_path))

            detector_dir=out_dir/f"detected_{label}"
            frame_plan_path,frame_plan_data=frame_plans[frame]
            if frame_plan_data.get("status")!="ready":
                raise RuntimeError(
                    f"semantic {frame} plan is not ready: "
                    +";".join(frame_plan_data.get("warnings") or [])
                )
            subprocess.run(
                [
                    py,str(detector_script),
                    "--image",str(render_path),
                    "--plan",str(frame_plan_path),
                    "--out",str(detector_dir),
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            report_path=detector_dir/"semantic_parts.json"
            if not report_path.is_file():
                raise RuntimeError(
                    f"semantic detector produced no report for {view}"
                )
            reports.append(str(report_path))
            report_data.append(
                json.loads(report_path.read_text(encoding="utf-8"))
            )

        aggregate=aggregate_semantic_reports(
            report_data,
            critical_targets=targets,
            minimum_views_per_part=minimum_views_per_part,
        )
        aggregate_path=out_dir/"semantic_anatomy.json"
        aggregate_path.write_text(
            json.dumps(asdict(aggregate),indent=2)+"\n",
            encoding="utf-8",
        )
        return SemanticAnatomyRun(
            required=True,
            attempted=True,
            ready=bool(aggregate.ready),
            critical_targets=targets,
            plan=str(plan_path),
            rendered_views=rendered,
            detector_reports=reports,
            aggregate=asdict(aggregate),
            error=(
                None
                if aggregate.ready
                else "semantic_anatomy_incomplete:"
                    +",".join(aggregate.missing_parts)
            ),
        )
    except Exception as exc:
        return SemanticAnatomyRun(
            required=True,
            attempted=True,
            ready=False,
            critical_targets=targets,
            plan=str(plan_path),
            rendered_views=rendered,
            detector_reports=reports,
            aggregate=None,
            error=f"{type(exc).__name__}:{exc}",
        )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description=(
            "Render a final HAYUYA character and validate explicitly "
            "referenced critical anatomy using GroundingDINO + SAM2."
        )
    )
    parser.add_argument("--glb",type=Path,required=True)
    parser.add_argument(
        "--detail",
        type=Path,
        action="append",
        default=[],
    )
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument(
        "--policy",
        choices=["off","auto","required"],
        default="auto",
    )
    parser.add_argument(
        "--minimum-views-per-part",
        type=int,
        default=1,
    )
    args=parser.parse_args()
    result=run_semantic_anatomy(
        args.glb,
        args.detail,
        args.out,
        policy=args.policy,
        minimum_views_per_part=args.minimum_views_per_part,
    )
    print(json.dumps(asdict(result),indent=2))
    if result.required and not result.ready:
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
