#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image

from judge_model_provenance import model_provenance


LEVELS = ["excellent", "good", "fair", "poor", "bad"]
WEIGHTS = [1.0, 0.75, 0.5, 0.25, 0.0]


def _finite(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise RuntimeError("non-finite Q-ReAlign score")
    return value


def score_images(paths: list[Path], model_id: str) -> dict:
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    if not paths:
        raise ValueError("no images supplied")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        dtype="auto",
        device_map="auto" if device == "cuda" else None,
    ).eval()
    if device == "cpu":
        model.to(device)

    messages = [{
        "role": "user",
        "content": [
            {"type": "image"},
            {"type": "text", "text": "How would you rate the quality of this image?"},
        ],
    }]
    prompt = (
        processor.apply_chat_template(messages, add_generation_prompt=True)
        + "The quality of the image is"
    )
    token_ids = [
        processor.tokenizer(" " + level, add_special_tokens=False).input_ids[0]
        for level in LEVELS
    ]

    rows = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        inputs = processor(
            text=[prompt],
            images=[image],
            return_tensors="pt",
        )
        first_device = next(model.parameters()).device
        inputs = {
            key: value.to(first_device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }
        with torch.inference_mode():
            logits = model(**inputs).logits[0, -1, token_ids]
            probs = logits.float().softmax(-1)
            weights = torch.tensor(WEIGHTS, device=probs.device)
            score = _finite((probs * weights).sum().item())
        rows.append({
            "path": str(path),
            "score": round(score, 6),
            "probabilities": {
                level: round(float(prob), 6)
                for level, prob in zip(LEVELS, probs.detach().cpu().tolist())
            },
        })

    values = sorted(float(row["score"]) for row in rows)
    p10_index = max(0, min(len(values) - 1, int(math.floor((len(values) - 1) * 0.10))))
    return {
        "schema": 1,
        "model": model_id,
        "provenance": model_provenance(model_id, model),
        "device": device,
        "images": rows,
        "count": len(rows),
        "mean": round(sum(values) / len(values), 6),
        "minimum": round(values[0], 6),
        "p10": round(values[p10_index], 6),
        "maximum": round(values[-1], 6),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="HAYUYA Judge v4 Q-ReAlign worker.")
    p.add_argument("--image", type=Path, action="append", required=True)
    p.add_argument("--model", default="q-future/Q-ReAlign-Pro-9B")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    report = score_images(a.image, a.model)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("HAYUYA_JUDGE_V4_QREALIGN " + json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
