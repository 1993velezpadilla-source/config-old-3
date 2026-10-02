#!/usr/bin/env python3
from __future__ import annotations

import math
import re
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any


ANATOMY_RULES: tuple[tuple[tuple[str,...],str], ...] = (
    (("eye","eyes","eyelid","eyelids","iris","pupil","sclera"),"eyes"),
    (("mouth","lip","lips","tongue","oral"),"mouth"),
    (("tooth","teeth","gum","gums","dental"),"teeth"),
    (("hand","hands","finger","fingers","palm","knuckle","knuckles","nail","nails"),"hands"),
    (("hair","hairline","eyebrow","eyebrows","beard","moustache","mustache"),"hair"),
    (("ear","ears"),"ears"),
    (("scar","scars","wound","wounds","lesion","lesions"),"wounds"),
)


@dataclass
class AnatomyTargetEvidence:
    target:str
    expected:int
    evaluated:int
    min_score:float|None
    mean_score:float|None
    references:list[str]
    missing:list[str]
    ready:bool


@dataclass
class CriticalAnatomyEvidence:
    required:bool
    ready:bool
    expected:int
    evaluated:int
    missing:list[str]
    targets:list[AnatomyTargetEvidence]
    method:str="hayuya-critical-anatomy-reference-evidence-v1"


def _tokens(path:Path)->set[str]:
    parts=[]
    for raw in [*path.parts[:-1],path.stem]:
        parts.extend(
            token for token in re.split(r"[^a-z0-9]+",raw.lower())
            if token
        )
    return set(parts)


def infer_anatomy_target(path:Path)->str|None:
    tokens=_tokens(path)
    for needles,target in ANATOMY_RULES:
        if any(token in tokens for token in needles):
            return target
    return None


def _finite_score(value:Any)->float|None:
    try:
        score=float(value)
    except (TypeError,ValueError):
        return None
    return score if math.isfinite(score) else None


def critical_anatomy_evidence(
    detail_images:list[Path],
    appearance_details:list[dict]|None,
)->CriticalAnatomyEvidence:
    refs=[
        (path,target)
        for path in detail_images
        if (target:=infer_anatomy_target(path)) is not None
    ]
    if not refs:
        return CriticalAnatomyEvidence(
            required=False,
            ready=True,
            expected=0,
            evaluated=0,
            missing=[],
            targets=[],
        )

    candidates=[]
    for item in appearance_details or []:
        if not isinstance(item,dict):
            continue
        source=str(item.get("source") or "")
        if not source:
            continue
        score=_finite_score(item.get("score"))
        if score is None:
            continue
        target=infer_anatomy_target(Path(source))
        candidates.append((source,target,score))

    consumed=set()
    matched:dict[str,list[tuple[str,float]]]={}
    missing=[]
    for ref,target in refs:
        match=None
        for index,(source,candidate_target,score) in enumerate(candidates):
            if index in consumed:
                continue
            same_source=source==str(ref) or Path(source).name==ref.name
            if not same_source:
                continue
            if candidate_target not in {None,target}:
                continue
            match=(index,score)
            break
        if match is None:
            missing.append(str(ref))
            continue
        consumed.add(match[0])
        matched.setdefault(target,[]).append((str(ref),float(match[1])))

    target_reports=[]
    for target in sorted({target for _,target in refs}):
        target_refs=[str(path) for path,t in refs if t==target]
        target_missing=[item for item in missing if item in target_refs]
        scores=[score for _,score in matched.get(target,[])]
        target_reports.append(AnatomyTargetEvidence(
            target=target,
            expected=len(target_refs),
            evaluated=len(scores),
            min_score=(min(scores) if scores else None),
            mean_score=(
                sum(scores)/len(scores)
                if scores else None
            ),
            references=target_refs,
            missing=target_missing,
            ready=bool(
                len(scores)==len(target_refs)
                and not target_missing
            ),
        ))

    evaluated=sum(item.evaluated for item in target_reports)
    return CriticalAnatomyEvidence(
        required=True,
        ready=bool(evaluated==len(refs) and not missing),
        expected=len(refs),
        evaluated=evaluated,
        missing=missing,
        targets=target_reports,
    )


def as_report(
    detail_images:list[Path],
    appearance_details:list[dict]|None,
)->dict:
    return asdict(
        critical_anatomy_evidence(
            detail_images,
            appearance_details,
        )
    )
