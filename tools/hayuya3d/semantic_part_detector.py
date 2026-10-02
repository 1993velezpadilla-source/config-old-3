#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import math
from pathlib import Path

import torch
from PIL import Image

from transformers import (
    AutoModelForZeroShotObjectDetection,
    AutoProcessor,
    Sam2Model,
    Sam2Processor,
)


def parse_args():
    p=argparse.ArgumentParser(description="GroundingDINO + SAM2 semantic part detector for HAYUYA.")
    p.add_argument("--image",required=True,type=Path)
    p.add_argument("--plan",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--box-threshold",type=float,default=0.24)
    p.add_argument("--text-threshold",type=float,default=0.18)
    p.add_argument("--grounding-model",default="IDEA-Research/grounding-dino-tiny")
    p.add_argument("--sam-model",default="facebook/sam2-hiera-tiny")
    return p.parse_args()


def device_name():
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends,"mps",None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def clamp_box(box,w,h):
    x1,y1,x2,y2=[float(x) for x in box]
    x1=max(0,min(w-1,x1)); x2=max(0,min(w,x2))
    y1=max(0,min(h-1,y1)); y2=max(0,min(h,y2))
    if x2<x1: x1,x2=x2,x1
    if y2<y1: y1,y2=y2,y1
    return [x1,y1,x2,y2]


def main()->int:
    a=parse_args()
    plan=json.loads(a.plan.read_text(encoding="utf-8"))
    prompts=plan.get("prompts") or {}
    required=set(plan.get("required") or [])
    optional=set(plan.get("optional") or [])

    image=Image.open(a.image).convert("RGB")
    w,h=image.size
    dev=device_name()

    gd_proc=AutoProcessor.from_pretrained(a.grounding_model)
    gd_model=AutoModelForZeroShotObjectDetection.from_pretrained(a.grounding_model).to(dev)
    gd_model.eval()

    sam_proc=Sam2Processor.from_pretrained(a.sam_model)
    sam_model=Sam2Model.from_pretrained(a.sam_model).to(dev)
    sam_model.eval()

    a.out.mkdir(parents=True,exist_ok=True)
    results=[]
    unresolved=[]

    with torch.no_grad():
        for part,queries in prompts.items():
            query_list=[str(x).strip().lower() for x in (queries or []) if str(x).strip()]
            if not query_list:
                continue
            # GroundingDINO expects text phrases separated by periods.
            text=". ".join(query_list)+"."
            inputs=gd_proc(images=image,text=text,return_tensors="pt").to(dev)
            outputs=gd_model(**inputs)
            post=gd_proc.post_process_grounded_object_detection
            params=inspect.signature(post).parameters
            kwargs={"target_sizes":[(h,w)]}
            if "box_threshold" in params:
                kwargs["box_threshold"]=a.box_threshold
            elif "threshold" in params:
                kwargs["threshold"]=a.box_threshold
            if "text_threshold" in params:
                kwargs["text_threshold"]=a.text_threshold
            elif "text_score_threshold" in params:
                kwargs["text_score_threshold"]=a.text_threshold
            detections=post(outputs,inputs.input_ids,**kwargs)[0]

            boxes=detections.get("boxes")
            scores=detections.get("scores")
            labels=detections.get("text_labels") or detections.get("labels")
            if boxes is None or len(boxes)==0:
                unresolved.append({"part":part,"required":part in required,"reason":"no_grounding_detection"})
                continue

            order=torch.argsort(scores,descending=True)
            best_idx=int(order[0].item())
            score=float(scores[best_idx].item())
            box=clamp_box(boxes[best_idx].detach().cpu().tolist(),w,h)
            label=str(labels[best_idx]) if labels is not None else part

            sam_inputs=sam_proc(
                images=image,
                input_boxes=[[box]],
                return_tensors="pt",
            ).to(dev)
            sam_outputs=sam_model(**sam_inputs,multimask_output=False)
            masks=sam_proc.post_process_masks(
                sam_outputs.pred_masks.cpu(),
                sam_inputs["original_sizes"].cpu(),
            )[0]
            # [objects, masks, H, W] or [objects, H, W] depending on version.
            mask=masks
            while getattr(mask,"ndim",0)>2:
                mask=mask[0]
            mask=(mask>0).to(torch.uint8).numpy()*255
            mask_img=Image.fromarray(mask,mode="L")
            mask_path=a.out/f"{part}.png"
            mask_img.save(mask_path,optimize=True)
            area=float((mask>0).sum())/float(w*h)

            iou_scores=getattr(sam_outputs,"iou_scores",None)
            sam_score=None
            if iou_scores is not None:
                try:
                    sam_score=float(iou_scores.detach().cpu().reshape(-1)[0].item())
                except Exception:
                    sam_score=None

            results.append({
                "part":part,
                "required":part in required,
                "optional":part in optional,
                "query":text,
                "grounding_label":label,
                "grounding_score":round(score,5),
                "sam_iou_score":None if sam_score is None else round(sam_score,5),
                "box_xyxy":[round(float(x),3) for x in box],
                "box_normalized":[
                    round(box[0]/w,6),round(box[1]/h,6),
                    round(box[2]/w,6),round(box[3]/h,6)
                ],
                "mask_area_ratio":round(area,6),
                "mask":mask_path.name,
            })

    detected={x["part"] for x in results}
    missing_required=sorted(required-detected)
    report={
        "schema":1,
        "image":str(a.image),
        "size":[w,h],
        "asset_profile":plan.get("asset_profile"),
        "weapon_family":plan.get("weapon_family","auto"),
        "detectors":{
            "grounding_dino":a.grounding_model,
            "sam2":a.sam_model,
            "device":dev,
        },
        "thresholds":{
            "box":a.box_threshold,
            "text":a.text_threshold,
        },
        "detections":results,
        "unresolved":unresolved,
        "missing_required":missing_required,
        "coverage":round((len(required)-len(missing_required))/max(1,len(required)),4),
        "passed":not missing_required,
    }
    (a.out/"semantic_parts.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_SEMANTIC_PARTS",json.dumps({
        "passed":report["passed"],
        "coverage":report["coverage"],
        "detected":len(results),
        "missing_required":missing_required,
        "device":dev,
    },separators=(",",":")))
    print(json.dumps(report,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
