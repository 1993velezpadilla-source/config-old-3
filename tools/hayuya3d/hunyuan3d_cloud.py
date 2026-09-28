#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file

SPACE_ID = "tencent/Hunyuan3D-2.1"


def _named_endpoints(client: Client) -> dict[str, dict[str, Any]]:
    info = client.view_api(return_format="dict")
    return dict(info.get("named_endpoints") or {})


def _as_path(value: Any) -> Path | None:
    if isinstance(value, str):
        p = Path(value)
        return p if p.exists() else None
    if isinstance(value, dict):
        for key in ("path", "name", "value"):
            v = value.get(key)
            if isinstance(v, str):
                p = Path(v)
                if p.exists():
                    return p
    for attr in ("path", "name"):
        v = getattr(value, attr, None)
        if isinstance(v, str):
            p = Path(v)
            if p.exists():
                return p
    if isinstance(value, (list, tuple)):
        for item in value:
            p = _as_path(item)
            if p is not None:
                return p
    return None


def _pick_shape_endpoint(named: dict[str, dict[str, Any]]) -> str:
    preferred = [
        "/shape_generation",
        "/generate_shape",
        "/generation",
    ]
    for name in preferred:
        if name in named:
            return name
    for name in named:
        lower = name.lower()
        if "shape" in lower and "generation" in lower:
            return name
    raise RuntimeError(
        "Hunyuan3D public Space exposes no shape-generation endpoint; "
        f"available={sorted(named)}"
    )


def generate_shape(
    image: Path,
    output: Path,
    *,
    token: str | None = None,
    seed: int = 1993,
    steps: int = 30,
    guidance_scale: float = 5.0,
    octree_resolution: int = 384,
    num_chunks: int = 8000,
) -> dict[str, Any]:
    if not image.is_file():
        raise FileNotFoundError(image)

    kwargs = {"verbose": True, "httpx_kwargs": {"timeout": 180.0}}
    if token:
        kwargs["token"] = token
    client = Client(SPACE_ID, **kwargs)
    named = _named_endpoints(client)
    endpoint = _pick_shape_endpoint(named)

    # Official Space signature:
    # caption, image, mv front/back/left/right, steps, guidance, seed,
    # octree resolution, remove-background, chunks, randomize-seed.
    result = client.predict(
        None,
        handle_file(str(image.resolve())),
        None,
        None,
        None,
        None,
        int(steps),
        float(guidance_scale),
        int(seed),
        int(octree_resolution),
        False,
        int(num_chunks),
        False,
        api_name=endpoint,
    )

    src = _as_path(result)
    if src is None:
        raise RuntimeError(
            "Hunyuan3D shape endpoint returned no downloadable mesh: "
            + repr(result)[:1200]
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, output)
    blob = output.read_bytes()
    if len(blob) < 1024:
        raise RuntimeError(f"Hunyuan3D mesh unexpectedly small: {len(blob)} bytes")

    meta = {
        "schema": 1,
        "generator": "tencent/Hunyuan3D-2.1",
        "space": SPACE_ID,
        "endpoint": endpoint,
        "seed": int(seed),
        "steps": int(steps),
        "guidance_scale": float(guidance_scale),
        "octree_resolution": int(octree_resolution),
        "num_chunks": int(num_chunks),
        "native_model_generated_geometry": True,
        "textured": False,
        "production_default": False,
        "license_policy": (
            "research/benchmark opt-in only; Hunyuan3D 2.1 Community License "
            "must be reviewed before production distribution"
        ),
        "path": str(output),
        "bytes": len(blob),
    }
    output.with_suffix(".generation.json").write_text(
        json.dumps(meta, indent=2) + "\n",
        encoding="utf-8",
    )
    print("HAYUYA_HUNYUAN3D_NATIVE_PASS", json.dumps(meta, separators=(",", ":")))
    return meta
