#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_model(repo: Path, device: str):
    import torch

    model = torch.hub.load(
        str(repo.resolve()),
        "dinov2_vits14",
        source="local",
        pretrained=True,
    )
    model.eval().to(device)
    return model


def encode(paths: list[Path], repo: Path, *, device: str, batch_size: int):
    import numpy as np
    import torch
    from PIL import Image

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = load_model(repo, device)
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
    outputs = []

    for start in range(0, len(paths), batch_size):
        chunk = paths[start:start + batch_size]
        arrays = []
        for path in chunk:
            image = Image.open(path).convert("RGB").resize((224, 224), Image.Resampling.BICUBIC)
            arrays.append(np.asarray(image, dtype=np.float32) / 255.0)

        tensor = torch.from_numpy(np.stack(arrays, axis=0)).permute(0, 3, 1, 2)
        tensor = ((tensor - mean) / std).to(device)
        with torch.inference_mode():
            feature = model(tensor)
        if isinstance(feature, dict):
            selected = feature.get("x_norm_clstoken")
            feature = selected if selected is not None else next(iter(feature.values()))
        feature = feature.reshape(feature.shape[0], -1)
        feature = torch.nn.functional.normalize(feature, dim=-1)
        outputs.append(feature.detach().cpu().numpy())

    return np.concatenate(outputs, axis=0)


def main() -> int:
    parser = argparse.ArgumentParser(description="HAYUYA isolated DINOv2 embedding worker.")
    parser.add_argument("--backend-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=24)
    args = parser.parse_args()

    features = encode(
        args.input,
        args.backend_root,
        device=args.device,
        batch_size=args.batch_size,
    )

    import numpy as np
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output, features)

    print(json.dumps({
        "count": int(features.shape[0]),
        "dimension": int(features.shape[1]),
        "output": str(args.output),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
