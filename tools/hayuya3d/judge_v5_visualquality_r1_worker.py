#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from judge_model_provenance import model_provenance


MODEL_ID="TianheWu/VisualQuality-R1-7B"
QUESTION=(
    "You are doing the image quality assessment task. Here is the question: "
    "What is your overall rating on the quality of this picture? "
    "The rating should be a float between 1 and 5, rounded to two decimal places, "
    "with 1 representing very poor quality and 5 representing excellent quality. "
    "Please only output the final answer with one score in <answer> </answer> tags."
)


def _parse_named(raws:list[str])->list[tuple[str,Path]]:
    rows=[]
    for raw in raws:
        if "=" not in raw:
            raise ValueError(f"expected NAME=PATH, got {raw!r}")
        name,path=raw.split("=",1)
        p=Path(path)
        if not name.strip() or not p.is_file():
            raise FileNotFoundError(f"{name}={p}")
        rows.append((name.strip(),p))
    return rows


def _extract_score(text:str)->float:
    matches=re.findall(r"<answer>\s*([0-9]+(?:\.[0-9]+)?)\s*</answer>",text,re.I|re.S)
    if not matches:
        raise RuntimeError(f"VisualQuality-R1 returned no <answer> score: {text[:400]!r}")
    value=float(matches[-1])
    if not math.isfinite(value) or not (1.0<=value<=5.0):
        raise RuntimeError(f"VisualQuality-R1 score out of range: {value}")
    return value


def run(rows:list[tuple[str,Path]],model_id:str)->dict:
    import torch
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
    from qwen_vl_utils import process_vision_info

    device="cuda" if torch.cuda.is_available() else "cpu"
    model=Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16 if device=="cuda" else torch.float32,
        device_map="auto" if device=="cuda" else None,
    ).eval()
    if device=="cpu":
        model.to(device)
    processor=AutoProcessor.from_pretrained(model_id)
    processor.tokenizer.padding_side="left"

    evidence=[]
    for name,path in rows:
        message=[{
            "role":"user",
            "content":[
                {"type":"image","image":str(path.resolve())},
                {"type":"text","text":QUESTION},
            ],
        }]
        text=processor.apply_chat_template(
            message,tokenize=False,add_generation_prompt=True,add_vision_id=True
        )
        image_inputs,video_inputs=process_vision_info(message)
        inputs=processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        first_device=next(model.parameters()).device
        inputs={k:(v.to(first_device) if hasattr(v,"to") else v) for k,v in inputs.items()}
        with torch.inference_mode():
            generated=model.generate(
                **inputs,
                use_cache=True,
                max_new_tokens=32,
                do_sample=False,
            )
        trimmed=generated[:,inputs["input_ids"].shape[1]:]
        raw=processor.batch_decode(
            trimmed,skip_special_tokens=True,clean_up_tokenization_spaces=False
        )[0]
        score=_extract_score(raw)
        evidence.append({
            "name":name,
            "path":str(path),
            "score":round(score,4),
            "raw":raw[:500],
        })

    scores=[float(x["score"]) for x in evidence]
    ordered=sorted(scores)
    p10=ordered[max(0,int(math.floor((len(ordered)-1)*0.10)))]
    return {
        "schema":1,
        "model":model_id,
        "provenance":model_provenance(model_id,model),
        "device":device,
        "ready":len(evidence)==len(rows) and bool(evidence),
        "images":evidence,
        "mean":round(sum(scores)/len(scores),4),
        "minimum":round(min(scores),4),
        "p10":round(p10,4),
        "maximum":round(max(scores),4),
        "method":"VisualQuality-R1-7B-NeurIPS2025-RL2R-deterministic-v1",
        "warnings":[],
    }


def main()->int:
    p=argparse.ArgumentParser(description="HAYUYA independent VisualQuality-R1 quality eye.")
    p.add_argument("--image",action="append",required=True,help="NAME=PATH")
    p.add_argument("--model",default=MODEL_ID)
    p.add_argument("--json",type=Path,required=True)
    a=p.parse_args()
    try:
        payload=run(_parse_named(a.image),a.model)
        code=0 if payload["ready"] else 2
    except Exception as exc:
        payload={
            "schema":1,"model":a.model,"ready":False,"images":[],
            "warnings":[f"{type(exc).__name__}:{exc}"],
            "method":"VisualQuality-R1-7B-NeurIPS2025-RL2R-deterministic-v1",
        }
        code=2
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return code


if __name__=="__main__":
    raise SystemExit(main())
