#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file

SPACE_ID = "TencentARC/Pixal3D"


def _as_path(value: Any) -> Path | None:
    if isinstance(value, str):
        p=Path(value)
        return p if p.exists() else None
    if isinstance(value, dict):
        for key in ("path","name","value"):
            v=value.get(key)
            if isinstance(v,str):
                p=Path(v)
                if p.exists():
                    return p
        for v in value.values():
            p=_as_path(v)
            if p is not None:
                return p
    if isinstance(value,(list,tuple)):
        for item in reversed(value):
            p=_as_path(item)
            if p is not None:
                return p
    for attr in ("path","name"):
        v=getattr(value,attr,None)
        if isinstance(v,str):
            p=Path(v)
            if p.exists():
                return p
    return None


def _connect(token: str | None, timeout: float=300.0) -> tuple[Client,dict]:
    kwargs={"verbose":True,"httpx_kwargs":{"timeout":float(timeout)}}
    if token:
        kwargs["token"]=token
    client=Client(SPACE_ID,**kwargs)
    api=client.view_api(return_format="dict")
    named=dict(api.get("named_endpoints") or {})
    return client,named


def _endpoint(named: dict, preferred: tuple[str,...], contains: str) -> str:
    for name in preferred:
        if name in named:
            return name
    for name in named:
        if contains in name.lower():
            return name
    raise RuntimeError(
        f"Pixal3D endpoint {contains!r} unavailable; available={sorted(named)}"
    )


def generate(
    image: Path,
    output: Path,
    *,
    token: str | None=None,
    seed: int=1993,
    resolution: int=1536,
    decimation_target: int=1_000_000,
    texture_size: int=4096,
) -> dict[str,Any]:
    image=Path(image)
    output=Path(output)
    if not image.is_file():
        raise FileNotFoundError(image)
    if resolution not in {1024,1536}:
        raise ValueError("Pixal3D public quality lane supports 1024 or 1536")
    decimation_target=max(100_000,min(1_000_000,int(decimation_target)))
    texture_size=max(1024,min(4096,int(texture_size)))

    client,named=_connect(token)
    preprocess_ep=_endpoint(named,("/preprocess",),"preprocess")
    generate_ep=_endpoint(named,("/generate_3d","/generate3d"),"generate")
    extract_ep=_endpoint(named,("/extract_glb_api","/extract_glb"),"extract")

    session_id=f"hayuya-{seed}-{int(time.time())}"
    processed=client.predict(
        handle_file(str(image.resolve())),
        api_name=preprocess_ep,
    )

    # Mirror the official high-quality defaults exposed by the current Space.
    gen_args=(
        processed,
        int(seed),
        int(resolution),
        7.5, 0.7, 12, 5.0,
        7.5, 0.5, 12, 3.0,
        1.0, 0.0, 12, 3.0,
        -1.0,
        "deg",
        session_id,
    )

    generation=None
    last_error: Exception | None=None
    for attempt in range(1,4):
        try:
            generation=client.predict(*gen_args,api_name=generate_ep)
            break
        except Exception as exc:
            last_error=exc
            message=f"{type(exc).__name__}: {exc}"
            lower=message.lower()
            if "zerogpu quota" in lower or "exceeded your zerogpu quota" in lower:
                raise
            transient=any(marker in lower for marker in (
                "queue","502 bad gateway","503 service unavailable",
                "504 gateway timeout","server disconnected","connection reset",
                "remoteprotocolerror","readtimeout","connecttimeout",
                "timed out","temporarily unavailable","cancellederror",
            ))
            if not transient or attempt>=3:
                raise
            delay=min(20,5*attempt)
            print(
                "HAYUYA_PIXAL3D_RETRY",
                json.dumps(
                    {
                        "attempt":attempt,
                        "delay_seconds":delay,
                        "error":message[:500],
                    },
                    separators=(",",":"),
                ),
            )
            time.sleep(delay)
            client,named=_connect(token)

    if generation is None:
        raise RuntimeError(
            "Pixal3D generation returned no result after retries: "
            +repr(last_error)
        )

    state_path=None
    if isinstance(generation,dict):
        state_path=generation.get("state_path")
    if not state_path:
        raise RuntimeError(
            "Pixal3D generation did not return state_path: "
            +repr(generation)[:1600]
        )

    extracted=client.predict(
        str(state_path),
        int(decimation_target),
        int(texture_size),
        session_id,
        api_name=extract_ep,
    )
    src=_as_path(extracted)
    if src is None:
        raise RuntimeError(
            "Pixal3D extraction returned no downloadable GLB: "
            +repr(extracted)[:1600]
        )

    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,output)
    blob=output.read_bytes()
    if len(blob)<1024 or blob[:4]!=b"glTF":
        raise RuntimeError(
            f"Pixal3D output invalid: bytes={len(blob)} magic={blob[:4]!r}"
        )

    meta={
        "schema":1,
        "generator":"TencentARC/Pixal3D",
        "space":SPACE_ID,
        "preprocess_endpoint":preprocess_ep,
        "generate_endpoint":generate_ep,
        "extract_endpoint":extract_ep,
        "seed":int(seed),
        "resolution":int(resolution),
        "decimation_target":int(decimation_target),
        "texture_size":int(texture_size),
        "pixel_aligned_conditioning":True,
        "native_model_generated_geometry":True,
        "pbr_requested":True,
        "license":"MIT",
        "production_default":True,
        "path":str(output),
        "bytes":len(blob),
    }
    output.with_suffix(".generation.json").write_text(
        json.dumps(meta,indent=2)+"\n",
        encoding="utf-8",
    )
    print("HAYUYA_PIXAL3D_NATIVE_PASS",json.dumps(meta,separators=(",",":")))
    return meta
