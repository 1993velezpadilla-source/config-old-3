#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image


def _score_sets(model, preprocess, sources: list[Path], candidates: list[Path], device: str) -> dict:
    if not sources or not candidates:
        raise ValueError("DreamSim requires non-empty source and candidate sets")

    import torch

    source_tensors = [
        preprocess(Image.open(path).convert("RGB")).to(device)
        for path in sources
    ]
    candidate_tensors = [
        preprocess(Image.open(path).convert("RGB")).to(device)
        for path in candidates
    ]

    per_source = []
    all_distances = []
    with torch.inference_mode():
        for source_path, source_tensor in zip(sources, source_tensors):
            rows = []
            for candidate_path, candidate_tensor in zip(candidates, candidate_tensors):
                distance = float(model(source_tensor, candidate_tensor).detach().cpu().item())
                if not math.isfinite(distance):
                    raise RuntimeError("non-finite DreamSim distance")
                rows.append({
                    "candidate": str(candidate_path),
                    "distance": round(distance, 6),
                })
                all_distances.append(distance)
            rows.sort(key=lambda item: item["distance"])
            per_source.append({
                "source": str(source_path),
                "best": rows[0],
                "top3": rows[:3],
            })

    best_values = [float(row["best"]["distance"]) for row in per_source]
    return {
        "sources": len(sources),
        "candidates": len(candidates),
        "per_source": per_source,
        "mean_best_distance": round(sum(best_values) / len(best_values), 6),
        "worst_best_distance": round(max(best_values), 6),
        "best_best_distance": round(min(best_values), 6),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="HAYUYA Judge v4 DreamSim fidelity worker.")
    p.add_argument("--source-full", type=Path, action="append", default=[])
    p.add_argument("--candidate-full", type=Path, action="append", default=[])
    p.add_argument("--source-face", type=Path, action="append", default=[])
    p.add_argument("--candidate-face", type=Path, action="append", default=[])
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()

    import torch
    from dreamsim import dreamsim

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = dreamsim(pretrained=True, device=device)
    model.eval()

    report = {
        "schema": 1,
        "model": "DreamSim",
        "device": device,
        "full": _score_sets(
            model, preprocess, a.source_full, a.candidate_full, device
        ),
        "face": (
            _score_sets(
                model, preprocess, a.source_face, a.candidate_face, device
            )
            if a.source_face and a.candidate_face
            else None
        ),
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("HAYUYA_JUDGE_V4_DREAMSIM " + json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
