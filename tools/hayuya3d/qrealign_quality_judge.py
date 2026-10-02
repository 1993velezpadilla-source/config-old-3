#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


LEVELS = ["excellent", "good", "fair", "poor", "bad"]
WEIGHTS = [1.0, 0.75, 0.5, 0.25, 0.0]


@dataclass
class ImageQualityEvidence:
    name: str
    path: str
    score: float
    probabilities: dict[str, float]
    good_excellent_mass: float
    poor_bad_mass: float


@dataclass
class QReAlignReport:
    schema: int
    model: str
    device: str
    ready: bool
    images: list[ImageQualityEvidence]
    warnings: list[str]
    method: str = "q-realign-next-token-quality-v1"


def _parse_named(items: list[str]) -> list[tuple[str, Path]]:
    out=[]
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"expected NAME=PATH, got {raw!r}")
        name, path = raw.split("=", 1)
        name=name.strip()
        p=Path(path)
        if not name or not p.is_file():
            raise FileNotFoundError(f"missing image {name}={p}")
        out.append((name,p))
    return out


def _move_inputs(inputs, device):
    for key, value in list(inputs.items()):
        if hasattr(value, "to"):
            inputs[key]=value.to(device)
    return inputs


def score_images(named: list[tuple[str, Path]], model_id: str) -> QReAlignReport:
    import torch
    from PIL import Image
    from transformers import AutoModelForImageTextToText, AutoProcessor

    device="cuda" if torch.cuda.is_available() else "cpu"
    processor=AutoProcessor.from_pretrained(model_id)
    model=AutoModelForImageTextToText.from_pretrained(model_id, dtype="auto")
    model=model.to(device).eval()

    token_ids=[
        processor.tokenizer(" " + word, add_special_tokens=False).input_ids[0]
        for word in LEVELS
    ]
    weight_tensor=torch.tensor(WEIGHTS, device=device, dtype=torch.float32)

    evidence=[]
    with torch.inference_mode():
        for name,path in named:
            image=Image.open(path).convert("RGB")
            messages=[{"role":"user","content":[
                {"type":"image"},
                {"type":"text","text":"How would you rate the quality of this image?"},
            ]}]
            prompt=(
                processor.apply_chat_template(messages, add_generation_prompt=True)
                + "The quality of the image is"
            )
            inputs=processor(text=[prompt], images=[image], return_tensors="pt")
            inputs=_move_inputs(inputs, device)
            logits=model(**inputs).logits[0,-1,token_ids].float()
            probs=torch.softmax(logits, dim=-1)
            score=float((probs*weight_tensor).sum().item())
            p=[float(x) for x in probs.detach().cpu().tolist()]
            prob_map={k:round(v,7) for k,v in zip(LEVELS,p)}
            evidence.append(ImageQualityEvidence(
                name=name,
                path=str(path),
                score=round(score,7),
                probabilities=prob_map,
                good_excellent_mass=round(p[0]+p[1],7),
                poor_bad_mass=round(p[3]+p[4],7),
            ))

    return QReAlignReport(
        schema=1,
        model=model_id,
        device=device,
        ready=len(evidence)==len(named) and bool(evidence),
        images=evidence,
        warnings=[],
    )


def main()->int:
    p=argparse.ArgumentParser(description="HAYUYA Judge v5 Q-ReAlign perceptual-quality eye.")
    p.add_argument("--image", action="append", default=[], required=True, help="NAME=PATH")
    p.add_argument("--model", default="q-future/Q-ReAlign-Mini-0.8B")
    p.add_argument("--json", type=Path, required=True)
    a=p.parse_args()
    try:
        report=score_images(_parse_named(a.image),a.model)
        payload=asdict(report)
        code=0 if report.ready else 2
    except Exception as exc:
        payload={
            "schema":1,
            "model":a.model,
            "ready":False,
            "images":[],
            "warnings":[f"{type(exc).__name__}:{exc}"],
            "method":"q-realign-next-token-quality-v1",
        }
        code=2
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return code


if __name__=="__main__":
    raise SystemExit(main())
