#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from judge_model_provenance import model_provenance


PROMPT = r"""
You are HAYUYA's final production 3D character QA judge. The supplied board is
explicitly labeled SOURCE REFERENCES, CANDIDATE TURNTABLE, and CANDIDATE FACE
CLOSEUPS. The character may intentionally be horror, undead, scarred, masked,
aged, asymmetric, or otherwise unsettling. Do NOT reject intentional features
that are supported by the source. Reject accidental reconstruction defects.

Inspect the candidate as a production asset, not as a pretty picture. Look hard
for: melted or collapsed face anatomy; wrong or missing eyes/nose/mouth/jaw;
identity drift from the source; fused/missing fingers or limbs; impossible body
connections; cloth fused into anatomy; texture washout/clay look; blurry or
duplicated facial details; UV/material seams; multi-view contradictions where
features move/disappear/change shape; wrong silhouette or clothing structure;
and any severe visual artifact that a human 3D artist would reject.

Return STRICT JSON only, exactly with this schema:
{
  "pass": true,
  "confidence": 0.0,
  "critical_issues": [],
  "scores": {
    "face_anatomy": 0,
    "face_source_fidelity": 0,
    "body_anatomy": 0,
    "hands": 0,
    "material_texture": 0,
    "multiview_consistency": 0,
    "source_fidelity": 0
  },
  "notes": []
}
All scores are 0-100, where 100 means production-clean and strongly supported
by the source. If the face is visibly corrupted, "pass" MUST be false even if
the rest of the model is excellent. Never let an average score rescue a
critical face/body/multiview failure.
""".strip()

FACE_FIDELITY_PROMPT = r"""
You are HAYUYA's strict SOURCE-FIDELITY face judge.

The supplied comparison board has exactly four labeled panels:
1) SOURCE FACE — AUTHORITATIVE
2) CANDIDATE 150°
3) CANDIDATE 180°
4) CANDIDATE 210°

The candidate is intended to be the SAME character as the source. Judge whether
the actual face structure is preserved. Do NOT reward matching hood, clothing,
colors, lighting, background, horror theme, age, damage, or general style.
Compare facial geometry feature-by-feature: overall width/height, cranium and
forehead, eye size/placement/orbital depth, nose bridge/tip/nostrils, mouth and
lips, jaw/chin, cheekbones, skin/flesh topology, and the spatial relationships
between these features.

Intentional horror, undead, aged, asymmetric, scarred, or unsettling features
shown in the source are valid and should be preserved. A technically clean or
detailed render that has a materially different face is a SOURCE-FIDELITY
FAILURE and "pass" MUST be false. Use all three candidate views; do not let one
favorable angle rescue a mismatch.

Return STRICT JSON only, exactly with this schema:
{
  "pass": false,
  "confidence": 0.0,
  "critical_issues": [],
  "scores": {
    "face_anatomy": 0,
    "face_source_fidelity": 0,
    "body_anatomy": 100,
    "hands": 100,
    "material_texture": 100,
    "multiview_consistency": 0,
    "source_fidelity": 0
  },
  "notes": []
}
All scores are 0-100. For this face-only board, body_anatomy, hands, and
material_texture are placeholders and must not influence pass/fail.
face_source_fidelity >=75 means strongly supported by the source; 60-74 is
questionable; below 60 is a clear mismatch.
""".strip()


def _extract_text(result) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, list) and result:
        item = result[0]
        if isinstance(item, dict):
            generated = item.get("generated_text")
            if isinstance(generated, str):
                return generated
            if isinstance(generated, list) and generated:
                last = generated[-1]
                if isinstance(last, dict):
                    content = last.get("content")
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        texts = []
                        for part in content:
                            if isinstance(part, dict) and isinstance(part.get("text"), str):
                                texts.append(part["text"])
                        if texts:
                            return "\n".join(texts)
    return str(result)


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    fence = chr(96) * 3
    if cleaned.startswith(fence + "json"):
        cleaned = cleaned[len(fence) + 4 :].lstrip()
    elif cleaned.startswith(fence):
        cleaned = cleaned[len(fence) :].lstrip()
    if cleaned.endswith(fence):
        cleaned = cleaned[: -len(fence)].rstrip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError(f"InternVL returned no JSON object: {text[:500]}")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise RuntimeError("InternVL JSON was not an object")
    required = {
        "face_anatomy",
        "face_source_fidelity",
        "body_anatomy",
        "hands",
        "material_texture",
        "multiview_consistency",
        "source_fidelity",
    }
    scores = payload.get("scores")
    if not isinstance(scores, dict) or not required.issubset(scores):
        raise RuntimeError(f"InternVL JSON missing required scores: {payload}")
    payload["pass"] = bool(payload.get("pass"))
    payload["critical_issues"] = [
        str(x) for x in (payload.get("critical_issues") or []) if str(x).strip()
    ]
    payload["notes"] = [str(x) for x in (payload.get("notes") or [])]
    payload["confidence"] = float(payload.get("confidence") or 0.0)
    payload["scores"] = {key: float(scores[key]) for key in required}
    return payload


def _judge_board(pipe, board: Path) -> dict:
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "url": str(board.resolve())},
            {"type": "text", "text": PROMPT},
        ],
    }]
    result = pipe(
        text=messages,
        max_new_tokens=900,
        do_sample=False,
        return_full_text=False,
    )
    raw = _extract_text(result)
    parsed = _parse_json(raw)
    return {
        "board": str(board),
        "raw": raw,
        "verdict": parsed,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="HAYUYA Judge v4 InternVL visual critic.")
    p.add_argument("--board", type=Path, action="append", required=True)
    p.add_argument("--model", default="OpenGVLab/InternVL3_5-8B-HF")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()

    import torch
    from transformers import pipeline

    pipe = pipeline(
        "image-text-to-text",
        model=a.model,
        device_map="auto" if torch.cuda.is_available() else None,
        dtype="auto",
        trust_remote_code=True,
    )

    passes = [_judge_board(pipe, board) for board in a.board]
    report = {
        "schema": 1,
        "model": a.model,
        "provenance": model_provenance(a.model, pipe.model),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "passes": passes,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("HAYUYA_JUDGE_V4_INTERNVL " + json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
