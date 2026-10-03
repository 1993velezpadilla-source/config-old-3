#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file

SPACE_ID = "tencent/Hunyuan3D-2mv"


def _paths(value: Any) -> list[Path]:
    out: list[Path] = []
    if isinstance(value, str):
        p = Path(value)
        if p.exists():
            out.append(p)
        return out
    if isinstance(value, dict):
        for key in ("path", "name", "value"):
            v = value.get(key)
            if isinstance(v, str):
                p = Path(v)
                if p.exists():
                    out.append(p)
        for v in value.values():
            out.extend(_paths(v))
        return out
    if isinstance(value, (list, tuple)):
        for item in value:
            out.extend(_paths(item))
        return out
    for attr in ("path", "name"):
        v = getattr(value, attr, None)
        if isinstance(v, str):
            p = Path(v)
            if p.exists():
                out.append(p)
    return out


def _client(token: str | None, timeout: float = 240.0) -> Client:
    kwargs = {"verbose": True, "httpx_kwargs": {"timeout": float(timeout)}}
    if token:
        kwargs["token"] = token
    return Client(SPACE_ID, **kwargs)


def generate(
    views: dict[str, Path],
    output: Path,
    *,
    token: str | None = None,
    seed: int = 1993,
    steps: int = 30,
    guidance_scale: float = 5.0,
    octree_resolution: int = 384,
    num_chunks: int = 8000,
    remove_background: bool = False,
    textured: bool = True,
) -> dict[str, Any]:
    normalized: dict[str, Path] = {}
    for role in ("front", "back", "left", "right"):
        raw = views.get(role)
        if raw is None:
            continue
        path = Path(raw)
        if not path.is_file():
            raise FileNotFoundError(path)
        normalized[role] = path
    if not normalized:
        raise ValueError("Hunyuan3D-2mv requires at least one canonical view")

    client = _client(token)
    info = client.view_api(return_format="dict")
    named = dict(info.get("named_endpoints") or {})
    endpoint = "/generation_all" if textured and "/generation_all" in named else "/shape_generation"
    if endpoint not in named:
        raise RuntimeError(
            "Hunyuan3D-2mv generation endpoint unavailable; "
            f"available={sorted(named)}"
        )

    # Public Space contract:
    # caption, image, front, back, left, right, steps, guidance, seed,
    # octree_resolution, remove_background, num_chunks, randomize_seed.
    def f(role: str):
        path = normalized.get(role)
        return handle_file(str(path.resolve())) if path is not None else None

    args = (
        None,
        None,
        f("front"),
        f("back"),
        f("left"),
        f("right"),
        int(steps),
        float(guidance_scale),
        int(seed),
        int(octree_resolution),
        bool(remove_background),
        int(num_chunks),
        False,
    )

    result = None
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            result = client.predict(*args, api_name=endpoint)
            break
        except Exception as exc:
            last_error = exc
            message = f"{type(exc).__name__}: {exc}"
            lower = message.lower()
            if "zerogpu quota" in lower or "exceeded your zerogpu quota" in lower:
                raise
            transient = any(
                marker in lower
                for marker in (
                    "queue",
                    "502 bad gateway",
                    "503 service unavailable",
                    "504 gateway timeout",
                    "server disconnected",
                    "connection reset",
                    "remoteprotocolerror",
                    "readtimeout",
                    "connecttimeout",
                    "timed out",
                    "temporarily unavailable",
                    "cancellederror",
                )
            )
            if not transient or attempt >= 4:
                raise
            delay = min(20, 4 * attempt)
            print(
                "HAYUYA_HUNYUAN2MV_RETRY",
                json.dumps(
                    {
                        "attempt": attempt,
                        "delay_seconds": delay,
                        "error": message[:500],
                    },
                    separators=(",", ":"),
                ),
            )
            time.sleep(delay)
            client = _client(token)

    if result is None:
        raise RuntimeError(
            "Hunyuan3D-2mv returned no result after retries: "
            + repr(last_error)
        )

    found = []
    seen = set()
    for path in _paths(result):
        resolved = str(path.resolve())
        if resolved not in seen:
            seen.add(resolved)
            found.append(path)
    model_paths = [
        p for p in found
        if p.suffix.lower() in {".glb", ".gltf", ".obj", ".ply"}
    ]
    if not model_paths:
        raise RuntimeError(
            "Hunyuan3D-2mv returned no downloadable mesh: "
            + repr(result)[:1400]
        )

    # generation_all returns raw then textured export. Prefer the final model.
    src = model_paths[-1]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, output)
    blob = output.read_bytes()
    if len(blob) < 1024:
        raise RuntimeError(
            f"Hunyuan3D-2mv output unexpectedly small: {len(blob)} bytes"
        )

    meta = {
        "schema": 1,
        "generator": "tencent/Hunyuan3D-2mv",
        "space": SPACE_ID,
        "endpoint": endpoint,
        "views": {k: str(v) for k, v in normalized.items()},
        "view_count": len(normalized),
        "seed": int(seed),
        "steps": int(steps),
        "guidance_scale": float(guidance_scale),
        "octree_resolution": int(octree_resolution),
        "num_chunks": int(num_chunks),
        "native_model_generated_geometry": True,
        "textured_requested": bool(textured),
        "production_default": False,
        "license_policy": (
            "comparison/diagnostic challenger only until the Hunyuan model "
            "license is explicitly approved for the intended game distribution"
        ),
        "path": str(output),
        "bytes": len(blob),
    }
    output.with_suffix(".generation.json").write_text(
        json.dumps(meta, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "HAYUYA_HUNYUAN2MV_PASS",
        json.dumps(meta, separators=(",", ":")),
    )
    return meta
