#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

HAYUYA_AAA_MAX_TRIANGLES = 2_000_000
UPSTREAM_PREVIEW_SAFETY_FACES = 16_777_216


def main() -> int:
    parser = argparse.ArgumentParser(description="Thin Hayuya adapter for microsoft/TRELLIS.2.")
    parser.add_argument("--backend-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1993)
    parser.add_argument("--resolution", type=int, choices=[512, 1024, 1536], default=1024)
    parser.add_argument(
        "--faces",
        type=int,
        default=2_000_000,
        help="Hero triangle target; HAYUYA 3D production ceiling is 2,000,000.",
    )
    parser.add_argument("--texture-size", type=int, choices=[1024, 2048, 4096], default=4096)
    args = parser.parse_args()
    if args.faces < 100_000 or args.faces > HAYUYA_AAA_MAX_TRIANGLES:
        parser.error(
            f"--faces must be between 100000 and {HAYUYA_AAA_MAX_TRIANGLES}"
        )

    backend_root = args.backend_root.resolve()
    if not backend_root.is_dir():
        parser.error(f"backend root does not exist: {backend_root}")

    sys.path.insert(0, str(backend_root))

    from PIL import Image
    import torch
    import o_voxel
    from trellis2.pipelines import Trellis2ImageTo3DPipeline

    if not torch.cuda.is_available():
        raise RuntimeError("TRELLIS.2 requires an NVIDIA CUDA GPU")

    pipeline_type = {
        512: "512",
        1024: "1024_cascade",
        1536: "1536_cascade",
    }[args.resolution]

    image = Image.open(args.input).convert("RGBA")
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
    pipeline.cuda()

    meshes = pipeline.run(
        image,
        seed=args.seed,
        pipeline_type=pipeline_type,
    )
    if not meshes:
        raise RuntimeError("TRELLIS.2 returned no mesh")

    mesh = meshes[0]
    # Upstream nvdiffrast preview/rendering safety ceiling. This is deliberately
    # much higher than HAYUYA's 2M production target, so it must never act as an
    # early quality cap on the Hero Master.
    mesh.simplify(UPSTREAM_PREVIEW_SAFETY_FACES)

    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=args.faces,
        texture_size=args.texture_size,
        remesh=True,
        remesh_band=1,
        remesh_project=0,
        verbose=True,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    glb.export(args.output, extension_webp=True)
    data = args.output.read_bytes()
    if data[:4] != b"glTF":
        raise RuntimeError(f"invalid GLB magic: {data[:16]!r}")
    try:
        from mesh_gate import inspect as inspect_mesh_gate
        report = inspect_mesh_gate(args.output, require_normals=False)
        actual = (
            f" actual_faces={report.faces} actual_vertices={report.vertices}"
        )
    except Exception as exc:
        actual = f" actual_mesh_audit_unavailable={type(exc).__name__}"
    print(
        f"HAYUYA_TRELLIS2_READY output={args.output} bytes={len(data)} "
        f"resolution={args.resolution} target_faces={args.faces} "
        f"texture={args.texture_size}" + actual
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
