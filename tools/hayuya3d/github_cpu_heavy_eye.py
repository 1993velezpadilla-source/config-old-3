#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

def _named(items):
    out=[]
    for raw in items:
        if "=" not in raw:
            raise ValueError(raw)
        name,path=raw.split("=",1)
        p=Path(path)
        if not p.is_file():
            raise FileNotFoundError(p)
        out.append((name,p))
    return out

def _torchao_config():
    # INT8 weight-only is supported on CPU by TorchAO. The previous INT4
    # PLAIN_INT32 path is not supported on CPU and failed on GitHub runners.
    from transformers import TorchAoConfig
    try:
        from torchao.quantization import Int8WeightOnlyConfig
        return TorchAoConfig(quant_type=Int8WeightOnlyConfig())
    except Exception:
        return TorchAoConfig("int8wo")

def _provenance(model_id,model):
    rev=getattr(getattr(model,"config",None),"_commit_hash",None)
    params=int(sum(int(p.numel()) for p in model.parameters()))
    return {
        "model_id":model_id,
        "resolved_revision":rev,
        "num_parameters":params,
        "quantization":"torchao-int8-weight-only-cpu",
        "device":"cpu",
    }

def qrealign(rows,model_id):
    import torch
    from PIL import Image
    from transformers import AutoModelForImageTextToText,AutoProcessor

    processor=AutoProcessor.from_pretrained(model_id)
    model=AutoModelForImageTextToText.from_pretrained(
        model_id,
        device_map="cpu",
        dtype="auto",
        low_cpu_mem_usage=True,
        quantization_config=_torchao_config(),
    ).eval()
    levels=["excellent","good","fair","poor","bad"]
    weights=[1.0,0.75,0.5,0.25,0.0]
    messages=[{"role":"user","content":[
        {"type":"image"},
        {"type":"text","text":"How would you rate the quality of this face reconstruction? Judge anatomical cleanliness, detail, and visible reconstruction defects."},
    ]}]
    prompt=processor.apply_chat_template(messages,add_generation_prompt=True)+"The quality of the image is"
    token_ids=[processor.tokenizer(" "+x,add_special_tokens=False).input_ids[0] for x in levels]
    images=[]
    for name,path in rows:
        inputs=processor(text=[prompt],images=[Image.open(path).convert("RGB")],return_tensors="pt")
        with torch.inference_mode():
            logits=model(**inputs).logits[0,-1,token_ids]
            probs=logits.float().softmax(-1)
        score=float((probs*torch.tensor(weights)).sum().item())
        images.append({
            "name":name,"path":str(path),"score":round(score,6),
            "probabilities":{k:round(float(v),6) for k,v in zip(levels,probs.tolist())},
        })
    vals=sorted(x["score"] for x in images)
    return {
        "schema":1,"ready":True,"model":model_id,
        "provenance":_provenance(model_id,model),
        "images":images,
        "mean":round(sum(vals)/len(vals),6),
        "minimum":round(vals[0],6),
        "p10":round(vals[max(0,int(math.floor((len(vals)-1)*.10)))],6),
        "maximum":round(vals[-1],6),
        "method":"qrealign-pro-9b-torchao-int8-cpu-github",
    }

VQ_QUESTION=(
    "Rate only the visible quality of this reconstructed 3D character face. "
    "Penalize melted facial anatomy, malformed eyes/nose/mouth/jaw, clay-like "
    "texture, blur, duplicated detail, and reconstruction artifacts. "
    "Return one score from 1 to 5 in <answer>NUMBER</answer>."
)

def visualquality(rows,model_id):
    import torch
    from transformers import AutoProcessor,Qwen2_5_VLForConditionalGeneration
    from qwen_vl_utils import process_vision_info

    model=Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id,
        device_map="cpu",
        dtype="auto",
        low_cpu_mem_usage=True,
        quantization_config=_torchao_config(),
    ).eval()
    processor=AutoProcessor.from_pretrained(model_id)
    evidence=[]
    for name,path in rows:
        message=[{"role":"user","content":[
            {"type":"image","image":str(path.resolve())},
            {"type":"text","text":VQ_QUESTION},
        ]}]
        text=processor.apply_chat_template(message,tokenize=False,add_generation_prompt=True,add_vision_id=True)
        image_inputs,video_inputs=process_vision_info(message)
        inputs=processor(text=[text],images=image_inputs,videos=video_inputs,padding=True,return_tensors="pt")
        with torch.inference_mode():
            generated=model.generate(**inputs,use_cache=True,max_new_tokens=32,do_sample=False)
        trimmed=generated[:,inputs["input_ids"].shape[1]:]
        raw=processor.batch_decode(trimmed,skip_special_tokens=True,clean_up_tokenization_spaces=False)[0]
        m=re.findall(r"<answer>\s*([0-9]+(?:\.[0-9]+)?)\s*</answer>",raw,re.I|re.S)
        if not m:
            raise RuntimeError("no VisualQuality score: "+raw[:300])
        score=float(m[-1])
        if not math.isfinite(score) or not 1<=score<=5:
            raise RuntimeError(score)
        evidence.append({"name":name,"path":str(path),"score":score,"raw":raw[:500]})
    vals=sorted(x["score"] for x in evidence)
    return {
        "schema":1,"ready":True,"model":model_id,
        "provenance":_provenance(model_id,model),
        "images":evidence,
        "mean":round(sum(vals)/len(vals),4),
        "minimum":round(vals[0],4),
        "median":round(vals[len(vals)//2],4),
        "maximum":round(vals[-1],4),
        "method":"visualquality-r1-7b-torchao-int8-cpu-github",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("eye",choices=["qrealign","visualquality"])
    p.add_argument("--image",action="append",required=True,help="NAME=PATH")
    p.add_argument("--json",type=Path,required=True)
    a=p.parse_args()
    rows=_named(a.image)
    if a.eye=="qrealign":
        payload=qrealign(rows,"q-future/Q-ReAlign-Pro-9B")
    else:
        payload=visualquality(rows,"TianheWu/VisualQuality-R1-7B")
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
