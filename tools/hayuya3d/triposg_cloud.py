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


def _pick_endpoint(named: dict, preferred: str, contains: str) -> tuple[str, dict]:
    if preferred in named:
        return preferred, named[preferred]
    key = next((k for k in named if contains.lower() in str(k).lower()), None)
    if key is None:
        raise RuntimeError(
            f"TripoSG endpoint {preferred} unavailable; found={list(named)}"
        )
    return key, named[key]


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


def _as_file_input(value: Any):
    for raw in _walk_paths(value):
        if not isinstance(raw, str):
            continue
        try:
            path = Path(raw)
            if path.is_file():
                return handle_file(str(path.resolve()))
        except Exception:
            pass
        if raw.startswith("http://") or raw.startswith("https://"):
            return handle_file(raw)
    raise RuntimeError("TripoSG output exposed no reusable file input")


def _extract_downloaded_glb(value: Any) -> Path:
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
            "TripoSG returned no downloaded GLB: " + repr(value)[:1000]
        )
    return candidates[-1]


def _call_named(
    client: Client,
    endpoint: str,
    spec: dict,
    values: dict[str, Any],
):
    params = _parameter_names(spec)
    missing = [name for name in params if name not in values]
    if missing:
        raise RuntimeError(
            f"TripoSG endpoint {endpoint} has unsupported parameters: {missing}"
        )
    return client.predict(
        *[values[name] for name in params],
        api_name=endpoint,
    )


def generate(
    image: Path,
    output: Path,
    *,
    token: str | None = None,
    seed: int = 1993,
    space: str = "VAST-AI/TripoSG",
    apply_texture: bool = True,
) -> dict:
    """Generate an unsimplified TripoSG Hero candidate via VAST's public Space.

    The public app exposes a simplify toggle. HAYUYA deliberately disables
    simplification for the Hero Master stage; runtime decimation belongs later.
    """
    kwargs = {"verbose": True, "httpx_kwargs": {"timeout": 180.0}}
    if token:
        kwargs["token"] = token
    client = Client(space, **kwargs)
    named = _named_endpoints(client)

    if "/start_session" in named:
        try:
            client.predict(api_name="/start_session")
        except Exception as exc:
            print(
                "::warning::TripoSG start_session failed; continuing with "
                f"Gradio session: {type(exc).__name__}: {exc}"
            )

    seg_ep, seg_spec = _pick_endpoint(
        named, "/run_segmentation", "segmentation"
    )
    seg_params = _parameter_names(seg_spec)
    if len(seg_params) != 1:
        raise RuntimeError(
            f"Unexpected TripoSG segmentation signature: {seg_params}"
        )
    segmented = client.predict(
        handle_file(str(image.resolve())),
        api_name=seg_ep,
    )
    segmented_input = _as_file_input(segmented)

    gen_ep, gen_spec = _pick_endpoint(named, "/image_to_3d", "image_to_3d")
    gen_values = {
        "image": segmented_input,
        "seed": int(seed),
        "num_inference_steps": 50,
        "guidance_scale": 7.0,
        "simplify": False,
        # Ignored by the public app when simplify=False, but supplied because it
        # remains part of the API signature.
        "target_face_num": 1_000_000,
    }
    generated = _call_named(client, gen_ep, gen_spec, gen_values)
    raw_glb = _extract_downloaded_glb(generated)

    chosen = raw_glb
    texture_error = None
    if apply_texture:
        try:
            tex_ep, tex_spec = _pick_endpoint(named, "/run_texture", "texture")
            tex_values = {
                "image": handle_file(str(image.resolve())),
                "mesh_path": handle_file(str(raw_glb.resolve())),
                "mesh": handle_file(str(raw_glb.resolve())),
                "model": handle_file(str(raw_glb.resolve())),
                "seed": int(seed),
            }
            textured = _call_named(client, tex_ep, tex_spec, tex_values)
            chosen = _extract_downloaded_glb(textured)
        except Exception as exc:
            texture_error = f"{type(exc).__name__}: {exc}"
            print(
                "::warning::TripoSG texture stage unavailable; preserving raw "
                "Hero geometry: " + texture_error
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chosen, output)
    blob = output.read_bytes()
    if blob[:4] != b"glTF" or len(blob) < 1024:
        raise RuntimeError(
            f"TripoSG produced invalid GLB: magic={blob[:16]!r} bytes={len(blob)}"
        )

    payload = {
        "path": str(output),
        "generator": "VAST-AI/TripoSG",
        "service_space": space,
        "compute": "public Hugging Face ZeroGPU Space",
        "seed": int(seed),
        "simplified": False,
        "requested_face_limit": None,
        "texture_attempted": bool(apply_texture),
        "textured": bool(apply_texture and texture_error is None),
        "texture_error": texture_error,
        "bytes": len(blob),
        "quality_role": "dense_hero_candidate",
    }
    print("HAYUYA_TRIPOSG_CLOUD_PASS", payload)
    return payload
