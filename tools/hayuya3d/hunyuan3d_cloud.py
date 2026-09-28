#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
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


def _connect_client(
    *,
    token: str | None,
    timeout: float,
    attempts: int = 5,
) -> tuple[Client, dict[str, dict[str, Any]]]:
    """Connect to the public Hunyuan Space with retries that include config fetch.

    Gradio Client fetches the Space config during construction. Treating only
    predict() as retryable left HAYUYA vulnerable to short Hugging Face/ZeroGPU
    outages before generation even started.
    """
    kwargs = {"verbose": True, "httpx_kwargs": {"timeout": float(timeout)}}
    if token:
        kwargs["token"] = token

    last_error: Exception | None = None
    for attempt in range(1, int(attempts) + 1):
        try:
            client = Client(SPACE_ID, **kwargs)
            named = _named_endpoints(client)
            return client, named
        except Exception as exc:
            last_error = exc
            message = f"{type(exc).__name__}: {exc}"
            lower = message.lower()
            transient = any(
                marker in lower
                for marker in (
                    "could not fetch config",
                    "502 bad gateway",
                    "503 service unavailable",
                    "504 gateway timeout",
                    "server disconnected",
                    "connection reset",
                    "connection refused",
                    "remoteprotocolerror",
                    "readtimeout",
                    "connecttimeout",
                    "timed out",
                    "temporarily unavailable",
                )
            )
            if not transient or attempt >= int(attempts):
                raise
            delay = min(20, 3 * attempt)
            print(
                "HAYUYA_HUNYUAN_CONNECT_RETRY",
                json.dumps(
                    {
                        "attempt": attempt,
                        "max_attempts": int(attempts),
                        "delay_seconds": delay,
                        "error": message[:500],
                    },
                    separators=(",", ":"),
                ),
            )
            time.sleep(delay)

    raise RuntimeError(
        "Hunyuan3D Space connection returned no client after retries: "
        + repr(last_error)
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
    remove_background: bool = False,
) -> dict[str, Any]:
    if not image.is_file():
        raise FileNotFoundError(image)

    client, named = _connect_client(token=token, timeout=180.0)
    endpoint = _pick_shape_endpoint(named)

    # Current official Space signature discovered at runtime:
    # image, mv front/back/left/right, steps, guidance, seed,
    # octree resolution, remove-background, chunks, randomize-seed.
    args = (
        handle_file(str(image.resolve())),
        None,
        None,
        None,
        None,
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
    for attempt in range(1, 6):
        try:
            result = client.predict(*args, api_name=endpoint)
            break
        except Exception as exc:
            last_error = exc
            message = f"{type(exc).__name__}: {exc}"
            lower = message.lower()
            if "zerogpu quota" in lower or "exceeded your zerogpu quota" in lower:
                raise
            transient = any(marker in lower for marker in (
                "cancellederror",
                "cancellederror",
                "queue",
                "502 bad gateway",
                "503 service unavailable",
                "504 gateway timeout",
                "server disconnected",
                "connection reset",
                "connection refused",
                "remoteprotocolerror",
                "readtimeout",
                "connecttimeout",
                "timed out",
                "temporarily unavailable",
            ))
            if not transient or attempt >= 5:
                raise
            delay = min(24, 4 * attempt)
            print(
                "HAYUYA_HUNYUAN_TRANSIENT_RETRY",
                json.dumps({
                    "attempt": attempt,
                    "max_attempts": 5,
                    "delay_seconds": delay,
                    "error": message[:500],
                    "reconnect_before_retry": True,
                }, separators=(",", ":")),
            )
            time.sleep(delay)
            # A cancelled Gradio SSE job can leave the client bound to a dead
            # queue/event. Reconnect and rediscover the endpoint before retrying.
            client, named = _connect_client(token=token, timeout=180.0)
            endpoint = _pick_shape_endpoint(named)
    if result is None:
        raise RuntimeError(
            "Hunyuan3D generation returned no result after retries: "
            + repr(last_error)
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
        "remove_background": bool(remove_background),
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


def generate_textured_material_donor(
    image: Path,
    output: Path,
    *,
    token: str | None = None,
    seed: int = 1993,
    steps: int = 20,
    guidance_scale: float = 5.0,
    octree_resolution: int = 256,
    num_chunks: int = 8000,
) -> dict[str, Any]:
    """Generate Hunyuan's own textured mesh for use as material evidence only.

    The public generation_all route face-reduces before texture painting, so this
    output must never replace the Ultra native shape. HAYUYA uses it strictly as
    a material donor for the separately generated 512 native geometry.
    """
    if not image.is_file():
        raise FileNotFoundError(image)

    client, named = _connect_client(token=token, timeout=240.0)
    endpoint = "/generation_all"
    if endpoint not in named:
        raise RuntimeError(
            "Hunyuan3D public Space exposes no generation_all endpoint; "
            f"available={sorted(named)}"
        )

    args = (
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
    )
    result = None
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            result = client.predict(*args, api_name=endpoint)
            break
        except Exception as exc:
            last_error = exc
            message = f"{type(exc).__name__}: {exc}"
            lower = message.lower()
            if "zerogpu quota" in lower or "exceeded your zerogpu quota" in lower:
                raise
            transient = any(marker in lower for marker in (
                "cancellederror",
                "queue",
                "502 bad gateway",
                "503 service unavailable",
                "504 gateway timeout",
                "server disconnected",
                "connection reset",
                "connection refused",
                "remoteprotocolerror",
                "readtimeout",
                "connecttimeout",
                "timed out",
                "temporarily unavailable",
                "unexpected sse line",
            ))
            if not transient or attempt >= 5:
                raise
            delay = min(24, 4 * attempt)
            print(
                "HAYUYA_HUNYUAN_TEXTURE_TRANSIENT_RETRY",
                json.dumps({
                    "attempt": attempt,
                    "max_attempts": 5,
                    "delay_seconds": delay,
                    "error": message[:500],
                    "reconnect_before_retry": True,
                }, separators=(",", ":")),
            )
            time.sleep(delay)
            client, named = _connect_client(token=token, timeout=240.0)
            if endpoint not in named:
                raise RuntimeError(
                    "Hunyuan3D public Space lost generation_all endpoint after reconnect; "
                    f"available={sorted(named)}"
                )
    if result is None:
        raise RuntimeError(
            "Hunyuan3D textured donor returned no result after retries: "
            + repr(last_error)
        )

    if not isinstance(result, (list, tuple)) or len(result) < 2:
        raise RuntimeError(
            "Hunyuan3D generation_all returned unexpected payload: "
            + repr(result)[:1600]
        )

    textured = _as_path(result[1])
    if textured is None:
        raise RuntimeError(
            "Hunyuan3D generation_all returned no downloadable textured GLB: "
            + repr(result)[:1600]
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(textured, output)
    blob = output.read_bytes()
    if len(blob) < 1024 or blob[:4] != b"glTF":
        raise RuntimeError(
            f"Hunyuan3D textured donor is not a valid GLB: bytes={len(blob)}"
        )

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
        "native_model_generated_material": True,
        "geometry_authority": False,
        "purpose": "material-donor-only",
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
    print(
        "HAYUYA_HUNYUAN3D_TEXTURED_DONOR_PASS",
        json.dumps(meta, separators=(",", ":")),
    )
    return meta
