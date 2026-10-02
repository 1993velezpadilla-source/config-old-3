#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path


@dataclass
class JudgeV5Report:
    schema:int
    method:str
    policy_id:str
    passed:bool
    status:str
    calibration_status:str
    automatic_approval_enabled:bool
    hard_fail_reasons:list[str]
    advisories:list[str]
    evidence:dict
    judge_v4:dict
    visualquality_r1:dict|None
    siglip2:dict|None
    cvlface:dict|None
    ediffiqa:dict|None
    pyiqa:dict|None


def _read(path:Path)->dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dict(value):
    if value is None:
        return {}
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value,dict):
        return value
    raise TypeError(type(value).__name__)


def _run_json_worker(
    python:str,
    script:Path,
    args:list[str],
    report:Path,
    log:Path,
    *,
    timeout:int=7200,
)->dict:
    command=[python,str(script),*args,"--json",str(report)]
    proc=subprocess.run(
        command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        timeout=timeout,check=False,
    )
    log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(proc.stdout or "",encoding="utf-8")
    if proc.returncode!=0:
        raise RuntimeError(
            f"{script.name} failed exit={proc.returncode}: {(proc.stdout or '')[-5000:]}"
        )
    if not report.is_file():
        raise RuntimeError(f"{script.name} produced no report")
    payload=_read(report)
    if payload.get("ready") is False:
        raise RuntimeError(
            f"{script.name} ready=false warnings={payload.get('warnings')}"
        )
    return payload


def _representative(paths:list[Path],count:int=8)->list[tuple[int,Path]]:
    rows=[(i,p) for i,p in enumerate(paths) if p.is_file()]
    if len(rows)<=count:
        return rows
    indices=[]
    for k in range(count):
        idx=round(k*(len(rows)-1)/max(1,count-1))
        if idx not in indices:
            indices.append(idx)
    return [rows[i] for i in indices]


def _scores(report:dict,key:str="score")->list[float]:
    out=[]
    for row in report.get("images") or []:
        try:
            value=float(row[key])
            if math.isfinite(value):
                out.append(value)
        except Exception:
            pass
    return out


def _checkpoint_failures(
    payload:dict,
    *,
    label:str,
    expected_model:str,
    min_parameters:int=100_000_000,
)->list[str]:
    p=(payload or {}).get("provenance") or {}
    out=[]
    if p.get("model_id")!=expected_model:
        out.append(
            f"{label}_checkpoint_model:{p.get('model_id')}!={expected_model}"
        )
    if not p.get("resolved_revision"):
        out.append(f"{label}_checkpoint_revision_missing")
    try:
        params=int(p.get("num_parameters") or 0)
    except Exception:
        params=0
    if params<min_parameters:
        out.append(
            f"{label}_checkpoint_parameters:{params}<{min_parameters}"
        )
    return out


def _metric_values(pyiqa:dict,metric_name:str)->list[float]:
    metric=(pyiqa.get("metrics") or {}).get(metric_name) or {}
    values=metric.get("values") or {}
    out=[]
    for value in values.values():
        try:
            value=float(value)
            if math.isfinite(value):
                out.append(value)
        except Exception:
            pass
    return out


def run_judge_v5(
    *,
    judge_v4,
    source_images:list[Path],
    final_glb:Path,
    out_dir:Path,
    policy_path:Path=Path("hayuya/standards/judge_v5_policy.json"),
    python_executable:str|None=None,
)->JudgeV5Report:
    out_dir.mkdir(parents=True,exist_ok=True)
    failures=[]
    advisories=[]
    v4=_dict(judge_v4)
    policy=_read(policy_path)
    policy_id=str(policy.get("id","unknown"))
    calibration_status=str(policy.get("calibration_status","unknown"))
    approval_enabled=bool(policy.get("approval_enabled",False))

    if v4.get("passed") is not True:
        failures.append("judge_v4_rejected_or_missing")

    # Authoritative V5 is only valid when the actual heavyweight V4 checkpoints
    # can be proven at runtime; labels alone are not accepted.
    failures.extend(_checkpoint_failures(
        v4.get("qrealign") or {},
        label="qrealign",
        expected_model="q-future/Q-ReAlign-Pro-9B",
        min_parameters=1_000_000_000,
    ))
    failures.extend(_checkpoint_failures(
        v4.get("internvl") or {},
        label="internvl",
        expected_model="OpenGVLab/InternVL3_5-8B-HF",
        min_parameters=1_000_000_000,
    ))

    evidence=v4.get("evidence") or {}
    v4_dir=out_dir.parent/"judge_v4"
    normalized_turns=sorted((v4_dir/"evidence"/"turn_full").glob("*.png"))
    normalized_sources=sorted((v4_dir/"evidence"/"source_full").glob("*.png"))
    candidate_faces=[
        Path(p) for p in (evidence.get("candidate_face_crops") or [])
        if Path(p).is_file()
    ]
    # Only use source images where the independent MediaPipe pass actually
    # detected a face. V4's generic source_face_crops can include non-face detail
    # references (clothing/hands/etc.), which must never contaminate identity.
    detected_source_face_paths=[
        str(item.get("path"))
        for item in ((v4.get("face_landmarks") or {}).get("source") or [])
        if item.get("path")
    ]
    source_faces=[
        Path(p) for p in detected_source_face_paths
        if Path(p).is_file()
    ]
    source_images=[Path(p) for p in source_images if Path(p).is_file()]

    if len(normalized_turns)!=24:
        failures.append(f"judge_v5_turntable_evidence:{len(normalized_turns)}!=24")
    if not normalized_sources and not source_images:
        failures.append("judge_v5_source_evidence_missing")
    if not final_glb.is_file():
        failures.append("judge_v5_final_glb_missing")

    audit_turns=[(i,p) for i,p in enumerate(normalized_turns) if p.is_file()]
    audit_faces=[(i,p) for i,p in enumerate(candidate_faces) if p.is_file()]
    python=(
        python_executable
        or os.environ.get("HAYUYA_JUDGE_V4_PYTHON")
        or ""
    )
    if not python:
        failures.append("judge_v5_python_missing")

    visualquality=None
    siglip=None
    cvlface=None
    ediffiqa=None
    pyiqa=None
    here=Path(__file__).resolve().parent

    if python and audit_turns:
        try:
            named=[
                *[(f"turn_{index:02d}",path) for index,path in audit_turns],
                *[(f"face_{index:02d}",path) for index,path in audit_faces],
            ]
            args=sum((["--image",f"{name}={path}"] for name,path in named),[])
            visualquality=_run_json_worker(
                python,here/"judge_v5_visualquality_r1_worker.py",args,
                out_dir/"visualquality_r1.json",out_dir/"visualquality_r1.log",
                timeout=10800,
            )
            failures.extend(_checkpoint_failures(
                visualquality,
                label="visualquality",
                expected_model="TianheWu/VisualQuality-R1-7B",
                min_parameters=1_000_000_000,
            ))
            scores=_scores(visualquality)
            if not scores:
                failures.append("visualquality_r1_no_scores")
            else:
                # Catastrophic-only veto until HAYUYA human calibration is complete.
                if min(scores)<1.75:
                    failures.append(
                        f"visualquality_r1_catastrophic_min:{min(scores):.3f}<1.75"
                    )
                face_scores=[
                    float(x["score"]) for x in visualquality.get("images") or []
                    if str(x.get("name","")).startswith("face_")
                ]
                if face_scores and statistics.median(face_scores)<2.25:
                    failures.append(
                        "visualquality_r1_face_catastrophic_median:"
                        f"{statistics.median(face_scores):.3f}<2.25"
                    )
        except Exception as exc:
            failures.append(
                f"visualquality_r1_worker:{type(exc).__name__}:{exc}"
            )

        try:
            siglip_sources=(
                normalized_sources if normalized_sources else source_images
            )
            args=[]
            for source in siglip_sources:
                args.extend(["--source",str(source)])
            for index,path in audit_turns:
                args.extend(["--candidate",f"turn_{index:02d}={path}"])
            for index,path in audit_faces:
                args.extend(["--candidate",f"face_{index:02d}={path}"])
            siglip=_run_json_worker(
                python,here/"siglip2_reference_judge.py",args,
                out_dir/"siglip2.json",out_dir/"siglip2.log",
                timeout=7200,
            )
            failures.extend(_checkpoint_failures(
                siglip,
                label="siglip2",
                expected_model="google/siglip2-giant-opt-patch16-384",
                min_parameters=100_000_000,
            ))
            full_rows=[
                row for row in (siglip.get("candidates") or [])
                if str(row.get("name","")).startswith("turn_")
            ]
            full_centroid=[
                float(row["cosine_similarity"])
                for row in full_rows
                if math.isfinite(float(row["cosine_similarity"]))
            ]
            full_best_source=[
                float(row["max_source_similarity"])
                for row in full_rows
                if math.isfinite(float(row["max_source_similarity"]))
            ]
            coverage=[
                float(row["best_similarity"])
                for row in (siglip.get("source_coverage") or [])
                if math.isfinite(float(row["best_similarity"]))
            ]
            floor=float((policy.get("siglip2") or {}).get(
                "best_full_body_catastrophic_floor",0.20
            ))
            mean_floor=float((policy.get("siglip2") or {}).get(
                "mean_full_body_catastrophic_floor",0.12
            ))
            source_floor=float((policy.get("siglip2") or {}).get(
                "per_source_best_catastrophic_floor",0.22
            ))
            if len(full_rows)!=24:
                failures.append(
                    f"siglip2_full_body_coverage:{len(full_rows)}!=24"
                )
            if not full_centroid or not full_best_source:
                failures.append("siglip2_no_full_body_scores")
            else:
                if max(full_best_source)<floor:
                    failures.append(
                        f"siglip2_catastrophic_best:{max(full_best_source):.4f}<{floor:.4f}"
                    )
                if sum(full_centroid)/len(full_centroid)<mean_floor:
                    failures.append(
                        "siglip2_catastrophic_mean:"
                        f"{sum(full_centroid)/len(full_centroid):.4f}<{mean_floor:.4f}"
                    )
            if not coverage:
                failures.append("siglip2_source_coverage_missing")
            else:
                for index,value in enumerate(coverage):
                    if value<source_floor:
                        failures.append(
                            f"siglip2_source_{index}_unmatched:"
                            f"{value:.4f}<{source_floor:.4f}"
                        )
        except Exception as exc:
            failures.append(f"siglip2_worker:{type(exc).__name__}:{exc}")

        face_expected=bool(
            ((v4.get("face_landmarks") or {}).get("face_expected_from_source"))
        )
        if face_expected:
            try:
                if not source_faces:
                    raise RuntimeError("no source face crops from Judge v4")
                if not candidate_faces:
                    raise RuntimeError("no candidate face crops from Judge v4")
                args=[]
                for path in source_faces:
                    args.extend(["--source",str(path)])
                for path in candidate_faces:
                    args.extend(["--candidate",str(path)])
                args.extend(["--aligned-dir",str(out_dir/"adaface_aligned")])
                cvlface=_run_json_worker(
                    python,here/"cvlface_identity_judge.py",args,
                    out_dir/"cvlface.json",out_dir/"cvlface.log",
                    timeout=7200,
                )
                front=cvlface.get("front_cosine_similarity")
                median=cvlface.get("median_cosine_similarity")
                candidate_fraction=float(
                    cvlface.get("candidate_detection_fraction") or 0.0
                )
                fpol=policy.get("face_identity") or {}
                detect_min=float(fpol.get("candidate_detection_fraction_min",0.80))
                front_min=float(fpol.get("front_cosine_catastrophic_floor",0.30))
                median_min=float(fpol.get("median_cosine_catastrophic_floor",0.28))
                if candidate_fraction<detect_min:
                    failures.append(
                        f"adaface_detection_coverage:{candidate_fraction:.3f}<{detect_min:.3f}"
                    )
                if front is None:
                    failures.append("adaface_front_face_missing")
                elif float(front)<front_min:
                    failures.append(
                        f"adaface_catastrophic_front:{float(front):.4f}<{front_min:.4f}"
                    )
                if median is None:
                    failures.append("adaface_median_missing")
                elif float(median)<median_min:
                    failures.append(
                        f"adaface_catastrophic_median:{float(median):.4f}<{median_min:.4f}"
                    )
            except Exception as exc:
                failures.append(
                    f"cvlface_worker:{type(exc).__name__}:{exc}"
                )
        else:
            advisories.append(
                "AdaFace identity veto marked N/A because source face was not "
                "established by the independent MediaPipe source detector."
            )
        if face_expected and not source_faces:
            failures.append("adaface_detected_source_face_evidence_missing")

        if face_expected:
            try:
                ediff_args=[]
                for index,path in audit_faces:
                    ediff_args.extend(["--image",f"face_{index:02d}={path}"])
                ediffiqa=_run_json_worker(
                    python,here/"ediffiqa_face_judge.py",ediff_args,
                    out_dir/"ediffiqa.json",out_dir/"ediffiqa.log",
                    timeout=3600,
                )
                epol=policy.get("ediffiqa") or {}
                detect_min=float(epol.get("candidate_detection_fraction_min",0.80))
                minimum_floor=float(epol.get("minimum_catastrophic_floor",0.15))
                median_floor=float(epol.get("median_catastrophic_floor",0.30))
                frac=float(ediffiqa.get("detection_fraction") or 0.0)
                minimum=ediffiqa.get("minimum")
                median=ediffiqa.get("median")
                if frac<detect_min:
                    failures.append(
                        f"ediffiqa_detection_coverage:{frac:.3f}<{detect_min:.3f}"
                    )
                if minimum is None or float(minimum)<minimum_floor:
                    failures.append(
                        f"ediffiqa_minimum:{minimum}<{minimum_floor:.3f}"
                    )
                if median is None or float(median)<median_floor:
                    failures.append(
                        f"ediffiqa_median:{median}<{median_floor:.3f}"
                    )
            except Exception as exc:
                failures.append(
                    f"ediffiqa_worker:{type(exc).__name__}:{exc}"
                )

        try:
            args=[]
            for index,path in audit_turns:
                args.extend(["--image",f"turn_{index:02d}={path}"])
            for index,path in audit_faces:
                args.extend(["--image",f"face_{index:02d}={path}"])
                args.extend(["--face-image",f"face_{index:02d}={path}"])
            pyiqa=_run_json_worker(
                python,here/"pyiqa_ensemble_judge.py",args,
                out_dir/"pyiqa.json",out_dir/"pyiqa.log",
                timeout=7200,
            )
            required=set((policy.get("pyiqa") or {}).get("required_metrics") or [])
            # V2 intentionally adds a second independent face-specific TOPIQ eye.
            required.add("topiq_nr_swin-face")
            have=set((pyiqa.get("metrics") or {}).keys())
            for metric in sorted(required-have):
                failures.append(f"pyiqa_missing_metric:{metric}")
            # Record data, but do not pretend cross-dataset absolute IQA thresholds
            # are calibrated for HAYUYA. Calibration lock below prevents approval.
        except Exception as exc:
            failures.append(f"pyiqa_worker:{type(exc).__name__}:{exc}")

    failures=list(dict.fromkeys(failures))
    metric_pass=not failures

    # This is deliberate. Q-ReAlign itself warns that absolute scores need
    # domain recalibration; NTIRE face identity thresholds also vary by protocol.
    # Until our own human-labeled good/bad HAYUYA set calibrates the thresholds,
    # the system may REJECT, but it is not allowed to auto-APPROVE.
    calibrated=approval_enabled and calibration_status=="ready"
    passed=metric_pass and calibrated
    status=(
        "APPROVED" if passed
        else "REJECTED" if not metric_pass
        else "BLOCKED_UNCALIBRATED"
    )
    if metric_pass and not calibrated:
        advisories.append(
            f"automatic approval locked: calibration_status={calibration_status}"
        )

    report=JudgeV5Report(
        schema=5,
        method=(
            "HAYUYA Judge v5 hard-veto ensemble: ALL 24 Judge v4 turntable views + "
            "Q-ReAlign-Pro-9B + InternVL3.5 + MediaPipe + DreamSim; "
            "VisualQuality-R1-7B; SigLIP2-Giant; CVLFace AdaFace "
            "ViT-KPRPE WebFace12M; eDifFIQA-L face quality; "
            "PyIQA TOPIQ/MUSIQ/CLIPIQA/MANIQA "
            "+ dual face TOPIQ"
        ),
        policy_id=policy_id,
        passed=passed,
        status=status,
        calibration_status=calibration_status,
        automatic_approval_enabled=approval_enabled,
        hard_fail_reasons=failures,
        advisories=advisories,
        evidence={
            "final_glb":str(final_glb),
            "normalized_turntable":[str(p) for p in normalized_turns],
            "audited_turntable":[str(p) for _,p in audit_turns],
            "source_faces":[str(p) for p in source_faces],
            "candidate_faces":[str(p) for p in candidate_faces],
        },
        judge_v4=v4,
        visualquality_r1=visualquality,
        siglip2=siglip,
        cvlface=cvlface,
        ediffiqa=ediffiqa,
        pyiqa=pyiqa,
    )
    (out_dir/"judge_v5.json").write_text(
        json.dumps(asdict(report),indent=2)+"\n",encoding="utf-8"
    )
    return report


def main()->int:
    p=argparse.ArgumentParser(description="HAYUYA Judge v5 fail-closed final visual acceptance.")
    p.add_argument("--judge-v4",type=Path,required=True)
    p.add_argument("--source",type=Path,action="append",default=[])
    p.add_argument("--final-glb",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--policy",type=Path,default=Path("hayuya/standards/judge_v5_policy.json"))
    p.add_argument("--python")
    a=p.parse_args()
    report=run_judge_v5(
        judge_v4=_read(a.judge_v4),
        source_images=a.source,
        final_glb=a.final_glb,
        out_dir=a.output_dir,
        policy_path=a.policy,
        python_executable=a.python,
    )
    print("HAYUYA_JUDGE_V5 "+json.dumps(asdict(report),separators=(",",":")))
    # BLOCKED_UNCALIBRATED is a non-approval and therefore non-zero by design.
    return 0 if report.passed else 8


if __name__=="__main__":
    raise SystemExit(main())
