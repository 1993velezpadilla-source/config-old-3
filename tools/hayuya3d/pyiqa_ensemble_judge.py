#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

GENERAL_METRICS=["topiq_nr","musiq","clipiqa+","maniqa"]
FACE_METRICS=["topiq_nr-face","topiq_nr_swin-face"]


def _named(items:list[str])->list[tuple[str,Path]]:
    out=[]
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"expected NAME=PATH, got {raw!r}")
        name,path=raw.split("=",1)
        p=Path(path)
        if not name.strip() or not p.is_file():
            raise FileNotFoundError(f"{name}={p}")
        out.append((name.strip(),p))
    return out


def _scalar(value):
    try:
        return float(value.detach().float().reshape(-1)[0].cpu().item())
    except Exception:
        return float(value)


def _range(metric):
    raw=getattr(metric,"score_range",None)
    if raw is None:
        return None
    try:
        return [float(raw[0]),float(raw[1])]
    except Exception:
        return None


def _run_metric(pyiqa,torch,device,metric_name:str,rows:list[tuple[str,Path]]):
    metric=pyiqa.create_metric(metric_name,device=device)
    values={}
    for name,path in rows:
        values[name]=round(_scalar(metric(str(path))),7)
    payload={
        "higher_better":bool(getattr(metric,"higher_better",not getattr(metric,"lower_better",False))),
        "score_range":_range(metric),
        "values":values,
    }
    del metric
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return payload


def run(general_rows,face_rows):
    import torch
    import pyiqa
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    report={
        "schema":2,
        "device":str(device),
        "ready":True,
        "general_images":[name for name,_ in general_rows],
        "face_images":[name for name,_ in face_rows],
        "metrics":{},
        "warnings":[],
        "method":"pyiqa-independent-multi-eye-v2",
    }
    if not general_rows:
        report["ready"]=False
        report["warnings"].append("no_general_images")
    if not face_rows:
        report["ready"]=False
        report["warnings"].append("no_face_images")

    for metric_name in GENERAL_METRICS:
        if not general_rows:
            continue
        try:
            report["metrics"][metric_name]=_run_metric(
                pyiqa,torch,device,metric_name,general_rows
            )
        except Exception as exc:
            report["ready"]=False
            report["warnings"].append(f"{metric_name}:{type(exc).__name__}:{exc}")

    for metric_name in FACE_METRICS:
        if not face_rows:
            continue
        try:
            report["metrics"][metric_name]=_run_metric(
                pyiqa,torch,device,metric_name,face_rows
            )
        except Exception as exc:
            report["ready"]=False
            report["warnings"].append(f"{metric_name}:{type(exc).__name__}:{exc}")
    return report


def main()->int:
    p=argparse.ArgumentParser(description="HAYUYA Judge v5 independent PyIQA ensemble.")
    p.add_argument("--image",action="append",default=[],help="NAME=PATH")
    p.add_argument("--face-image",action="append",default=[],help="NAME=PATH")
    p.add_argument("--json",type=Path,required=True)
    a=p.parse_args()
    try:
        payload=run(_named(a.image),_named(a.face_image))
        code=0 if payload["ready"] else 2
    except Exception as exc:
        payload={
            "schema":2,"ready":False,"metrics":{},
            "warnings":[f"{type(exc).__name__}:{exc}"],
            "method":"pyiqa-independent-multi-eye-v2",
        }
        code=2
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return code


if __name__=="__main__":
    raise SystemExit(main())
