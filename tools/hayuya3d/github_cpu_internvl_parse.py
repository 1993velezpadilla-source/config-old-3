#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path

REQUIRED={"face_anatomy","face_source_fidelity","body_anatomy","hands","material_texture","multiview_consistency","source_fidelity"}

def extract(text:str)->dict:
    dec=json.JSONDecoder()
    matches=[]
    for i,ch in enumerate(text):
        if ch!="{":
            continue
        try:
            obj,end=dec.raw_decode(text[i:])
        except Exception:
            continue
        if isinstance(obj,dict):
            scores=obj.get("scores")
            if isinstance(scores,dict) and REQUIRED.issubset(scores):
                matches.append(obj)
    if not matches:
        raise RuntimeError("no valid InternVL verdict JSON found")
    obj=matches[-1]
    return {
        "pass":bool(obj.get("pass")),
        "confidence":float(obj.get("confidence") or 0.0),
        "critical_issues":[str(x) for x in (obj.get("critical_issues") or [])],
        "scores":{k:float(obj["scores"][k]) for k in REQUIRED},
        "notes":[str(x) for x in (obj.get("notes") or [])],
    }

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--log",type=Path,required=True)
    p.add_argument("--json",type=Path,required=True)
    p.add_argument("--model",default="lmstudio-community/InternVL3_5-8B-GGUF:Q6_K")
    a=p.parse_args()
    verdict=extract(a.log.read_text(encoding="utf-8",errors="replace"))
    payload={
        "schema":1,
        "ready":True,
        "model":a.model,
        "quantization":"Q6_K",
        "runtime":"llama.cpp-cpu",
        "verdict":verdict,
    }
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
