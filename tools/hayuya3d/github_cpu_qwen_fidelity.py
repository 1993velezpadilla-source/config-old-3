#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

REQUIRED_SCORES = {
    "face_source_fidelity",
    "face_anatomy",
    "shape_match",
    "feature_geometry_match",
    "multiview_consistency",
}

PROMPT = """You are HAYUYA's source-fidelity face judge.

IMAGE 1 is the authoritative SOURCE FACE.
IMAGES 2-4 are three rendered views of the CANDIDATE face for the same intended character.

Judge whether the candidate reproduces the SOURCE FACE, not whether the render is merely attractive or technically clean.
Do NOT reward matching hood, clothes, colors, lighting, background, horror theme, age, damage, or general style.
Compare the actual facial structure feature-by-feature: overall face width/height, cranium/forehead, eye size and placement, orbital depth, nose bridge/tip/nostrils, mouth/lips, jaw/chin, cheekbones, skin/flesh topology, and the relationships between those features.
Intentional horror, undead, aged, asymmetric, scarred, or unsettling features present in the source are valid and must be preserved.
A clean, detailed render with a materially different face is a SOURCE-FIDELITY FAILURE and pass MUST be false.
Use all three candidate views to avoid being fooled by one angle.

Return STRICT JSON only:
{
  "pass": false,
  "confidence": 0.0,
  "critical_issues": [],
  "scores": {
    "face_source_fidelity": 0,
    "face_anatomy": 0,
    "shape_match": 0,
    "feature_geometry_match": 0,
    "multiview_consistency": 0
  },
  "notes": []
}
Scores are 0-100. A face_source_fidelity score >=75 means the face is strongly supported by the source; 60-74 is questionable; below 60 is a clear mismatch.
"""

def _torchao_config():
    from transformers import TorchAoConfig
    try:
        from torchao.quantization import Int8WeightOnlyConfig
        return TorchAoConfig(quant_type=Int8WeightOnlyConfig())
    except Exception:
        return TorchAoConfig("int8wo")

def _provenance(model_id, model):
    rev = getattr(getattr(model, "config", None), "_commit_hash", None)
    params = int(sum(int(p.numel()) for p in model.parameters()))
    return {
        "model_id": model_id,
        "resolved_revision": rev,
        "num_parameters": params,
        "quantization": "torchao-int8-weight-only-cpu",
        "device": "cpu",
    }

def _extract_json(text: str) -> dict:
    dec = json.JSONDecoder()
    matches = []
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(text[i:])
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        scores = obj.get("scores")
        if isinstance(scores, dict) and REQUIRED_SCORES.issubset(scores):
            matches.append(obj)
    if not matches:
        raise RuntimeError("Qwen returned no valid fidelity JSON: " + text[:600])
    obj = matches[-1]
    scores = obj["scores"]
    parsed_scores = {k: float(scores[k]) for k in REQUIRED_SCORES}
    for key, value in parsed_scores.items():
        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise RuntimeError(f"invalid score {key}={value}")
    return {
        "pass": bool(obj.get("pass")),
        "confidence": float(obj.get("confidence") or 0.0),
        "critical_issues": [str(x) for x in (obj.get("critical_issues") or [])],
        "scores": parsed_scores,
        "notes": [str(x) for x in (obj.get("notes") or [])],
    }

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--candidate", type=Path, action="append", required=True)
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--model", default="Qwen/Qwen2.5-VL-7B-Instruct")
    a = p.parse_args()

    if not a.source.is_file():
        raise FileNotFoundError(a.source)
    if len(a.candidate) < 3:
        raise RuntimeError("need at least three candidate face views")
    for path in a.candidate:
        if not path.is_file():
            raise FileNotFoundError(path)

    import torch
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
    from qwen_vl_utils import process_vision_info

    processor = AutoProcessor.from_pretrained(
        a.model,
        min_pixels=256 * 28 * 28,
        max_pixels=768 * 28 * 28,
    )
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        a.model,
        device_map="cpu",
        dtype="auto",
        low_cpu_mem_usage=True,
        quantization_config=_torchao_config(),
    ).eval()

    content = [
        {"type": "text", "text": "IMAGE 1 — AUTHORITATIVE SOURCE FACE"},
        {"type": "image", "image": str(a.source.resolve())},
    ]
    for i, path in enumerate(a.candidate[:3], start=2):
        content.extend([
            {"type": "text", "text": f"IMAGE {i} — CANDIDATE FACE VIEW"},
            {"type": "image", "image": str(path.resolve())},
        ])
    content.append({"type": "text", "text": PROMPT})
    messages = [{"role": "user", "content": content}]

    rendered = processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        add_vision_id=True,
    )
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[rendered],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            use_cache=True,
            max_new_tokens=500,
            do_sample=False,
        )
    trimmed = generated[:, inputs["input_ids"].shape[1]:]
    raw = processor.batch_decode(
        trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]
    verdict = _extract_json(raw)
    payload = {
        "schema": 1,
        "ready": True,
        "model": a.model,
        "provenance": _provenance(a.model, model),
        "source": str(a.source),
        "candidates": [str(x) for x in a.candidate[:3]],
        "verdict": verdict,
        "raw": raw[:2000],
        "method": "qwen2.5-vl-7b-source-face-fidelity-int8-cpu-github",
    }
    a.json.parent.mkdir(parents=True, exist_ok=True)
    a.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
