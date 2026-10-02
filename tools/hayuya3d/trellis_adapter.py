#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("SPCONV_ALGO", "native")


def main() -> int:
    parser = argparse.ArgumentParser(description="Hayuya adapter for microsoft/TRELLIS single/multi-image generation.")
    parser.add_argument("--backend-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1993)
    parser.add_argument("--texture-size", type=int, choices=[512, 1024, 2048], default=2048)
    parser.add_argument("--simplify", type=float, default=0.95)
    parser.add_argument("--multiimage-mode", choices=["stochastic", "multidiffusion"], default="multidiffusion")
    args = parser.parse_args()

    backend_root = args.backend_root.resolve()
    sys.path.insert(0, str(backend_root))

    from PIL import Image
    import torch
    from trellis.pipelines import TrellisImageTo3DPipeline
    from trellis.utils import postprocessing_utils

    if not torch.cuda.is_available():
        raise RuntimeError("TRELLIS requires an NVIDIA CUDA GPU")

    images = [Image.open(p).convert("RGBA") for p in args.input]
    pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
    pipeline.cuda()

    common = dict(
        seed=args.seed,
        sparse_structure_sampler_params={"steps": 12, "cfg_strength": 7.5},
        slat_sampler_params={"steps": 12, "cfg_strength": 3.0},
    )
    if len(images) == 1:
        outputs = pipeline.run(images[0], **common)
    else:
        outputs = pipeline.run_multi_image(
            images,
            mode=args.multiimage_mode,
            **common,
        )

    glb = postprocessing_utils.to_glb(
        outputs["gaussian"][0],
        outputs["mesh"][0],
        simplify=args.simplify,
        texture_size=args.texture_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    glb.export(args.output)
    data = args.output.read_bytes()
    if data[:4] != b"glTF":
        raise RuntimeError(f"invalid GLB magic: {data[:16]!r}")
    print(
        f"HAYUYA_TRELLIS_READY output={args.output} bytes={len(data)} "
        f"inputs={len(images)} mode={args.multiimage_mode}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
