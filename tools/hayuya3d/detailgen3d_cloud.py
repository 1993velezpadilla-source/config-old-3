#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file


def _named_endpoints(client: Client) -> dict:
    api = client.view_api(print_info=False, return_format="dict")
    return api.get("named_endpoints", {}) if isinstance(api, dict) else {}


def _parameter_names(spec: dict) -> list[str]:
    return [str(p.get("parameter_name") or "") for p in spec.get("parameters", [])]


def _pick_endpoint(named: dict) -> tuple[str, dict]:
    for preferred in ("/run_refinement", "/refine", "/generate_details"):
        if preferred in named:
            return preferred, named[preferred]
    for key, spec in named.items():
        low = str(key).lower()
        params = [x.lower() for x in _parameter_names(spec)]
        if (
            ("refine" in low or "detail" in low)
            and any("mesh" in x for x in params)
            and any("image" in x for x in params)
        ):
            return key, spec
    raise RuntimeError(
        "DetailGen3D refinement endpoint unavailable; found="
        + repr(list(named))
    )


def _walk_paths(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk_paths(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk_paths(v)
    else:
        for attr in ("path", "url"):
            raw = getattr(value, attr, None)
            if isinstance(raw, str):
                yield raw


def _extract_glb(value: Any) -> Path:
    candidates = []
    for raw in _walk_paths(value):
        if not isinstance(raw, str) or not raw.lower().endswith(".glb"):
            continue
        try:
            p = Path(raw)
            if p.is_file():
                candidates.append(p)
        except Exception:
            pass
    if not candidates:
        raise RuntimeError(
            "DetailGen3D returned no downloaded GLB: " + repr(value)[:1000]
        )
    return candidates[0]


def _call_named(
    client: Client,
    endpoint: str,
    spec: dict,
    values: dict[str, Any],
):
    params = _parameter_names(spec)
    args = []
    missing = []
    for name in params:
        if name in values:
            args.append(values[name])
            continue
        low = name.lower()
        if "image" in low:
            args.append(values["rgb_image"])
        elif "mesh" in low or "model" in low:
            args.append(values["mesh"])
        elif "random" in low and "seed" in low:
            args.append(False)
        elif "seed" in low:
            args.append(values["seed"])
        elif "step" in low:
            args.append(values["num_inference_steps"])
        elif "guidance" in low or "cfg" in low:
            args.append(values["guidance_scale"])
        else:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"DetailGen3D endpoint {endpoint} has unsupported parameters: {missing}"
        )
    return client.predict(*args, api_name=endpoint)


def _aligned_to_base_bbox(base_mesh: Path, refined_mesh: Path, output: Path) -> dict:
    import numpy as np
    import trimesh

    def merged(path: Path):
        loaded = trimesh.load(path, force="scene", process=False)
        meshes = (
            list(loaded.geometry.values())
            if hasattr(loaded, "geometry")
            else [loaded]
        )
        meshes = [m for m in meshes if hasattr(m, "vertices") and len(m.vertices)]
        if not meshes:
            raise RuntimeError(f"mesh has no geometry: {path}")
        return trimesh.util.concatenate(meshes)

    base = merged(base_mesh)
    refined = merged(refined_mesh)

    bmin, bmax = base.bounds
    rmin, rmax = refined.bounds
    bcenter = (bmin + bmax) * 0.5
    rcenter = (rmin + rmax) * 0.5
    bext = bmax - bmin
    rext = rmax - rmin
    bspan = float(np.max(bext))
    rspan = float(np.max(rext))
    if bspan <= 1e-9 or rspan <= 1e-9:
        raise RuntimeError("collapsed bounds during DetailGen3D alignment")

    scale = bspan / rspan
    refined.apply_translation(-rcenter)
    refined.apply_scale(scale)
    refined.apply_translation(bcenter)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(refined)))
    data = output.read_bytes()
    if data[:4] != b"glTF":
        raise RuntimeError("DetailGen3D aligned export is not GLB")
    return {
        "scale": scale,
        "base_span": bspan,
        "refined_span_before": rspan,
        "base_center": [float(x) for x in bcenter],
        "refined_center_before": [float(x) for x in rcenter],
    }


def refine(
    image: Path,
    coarse_mesh: Path,
    output: Path,
    *,
    token: str | None = None,
    seed: int = 1993,
    space: str = "VAST-AI/DetailGen3D",
    num_inference_steps: int = 50,
    guidance_scale: float = 10.0,
) -> dict:
    """Image-conditioned open geometry enhancement via VAST DetailGen3D."""
    kwargs = {"verbose": True, "httpx_kwargs": {"timeout": 180.0}}
    if token:
        kwargs["token"] = token
    client = Client(space, **kwargs)
    named = _named_endpoints(client)
    endpoint, spec = _pick_endpoint(named)

    values = {
        "rgb_image": handle_file(str(image.resolve())),
        "image": handle_file(str(image.resolve())),
        "mesh": handle_file(str(coarse_mesh.resolve())),
        "seed": int(seed),
        "randomize_seed": False,
        "num_inference_steps": int(num_inference_steps),
        "guidance_scale": float(guidance_scale),
    }
    result = _call_named(client, endpoint, spec, values)
    downloaded = _extract_glb(result)

    raw = output.with_name(output.stem + "_raw.glb")
    raw.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(downloaded, raw)
    alignment = _aligned_to_base_bbox(coarse_mesh, raw, output)

    blob = output.read_bytes()
    payload = {
        "path": str(output),
        "raw_path": str(raw),
        "generator": "VAST-AI/DetailGen3D",
        "service_space": space,
        "compute": "public Hugging Face ZeroGPU Space",
        "seed": int(seed),
        "num_inference_steps": int(num_inference_steps),
        "guidance_scale": float(guidance_scale),
        "alignment": alignment,
        "bytes": len(blob),
        "quality_role": "image_conditioned_geometry_refiner",
    }
    print("HAYUYA_DETAILGEN3D_CLOUD_PASS", payload)
    return payload
