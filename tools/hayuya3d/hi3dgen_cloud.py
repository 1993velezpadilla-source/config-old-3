#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file

SPACE_ID = "Stable-X/Hi3DGen"


def _find_path(value: Any) -> Path | None:
    if isinstance(value, str):
        p=Path(value)
        return p if p.exists() else None
    if isinstance(value, dict):
        for key in ("path","name","value"):
            v=value.get(key)
            if isinstance(v,str):
                p=Path(v)
                if p.exists() and p.suffix.lower() in {".glb",".gltf",".obj",".ply"}:
                    return p
        for v in value.values():
            p=_find_path(v)
            if p is not None:
                return p
    if isinstance(value,(list,tuple)):
        for item in reversed(value):
            p=_find_path(item)
            if p is not None:
                return p
    for attr in ("path","name"):
        v=getattr(value,attr,None)
        if isinstance(v,str):
            p=Path(v)
            if p.exists():
                return p
    return None


def _connect(token: str | None, timeout: float=240.0) -> tuple[Client,str]:
    kwargs={"verbose":True,"httpx_kwargs":{"timeout":float(timeout)}}
    if token:
        kwargs["token"]=token
    client=Client(SPACE_ID,**kwargs)
    api=client.view_api(return_format="dict")
    named=dict(api.get("named_endpoints") or {})
    preferred=("/generate_3d","/generate3d","/generate")
    endpoint=next((name for name in preferred if name in named),None)
    if endpoint is None:
        endpoint=next(
            (
                name for name in named
                if "generate" in name.lower()
                and "convert" not in name.lower()
                and "preprocess" not in name.lower()
            ),
            None,
        )
    if endpoint is None:
        raise RuntimeError(
            "Hi3DGen public Space exposes no generation endpoint; "
            f"available={sorted(named)}"
        )
    return client,endpoint


def generate(
    image: Path,
    output: Path,
    *,
    token: str | None=None,
    seed: int=1993,
    ss_guidance_strength: float=3.0,
    ss_sampling_steps: int=50,
    slat_guidance_strength: float=3.0,
    slat_sampling_steps: int=6,
) -> dict[str,Any]:
    image=Path(image)
    output=Path(output)
    if not image.is_file():
        raise FileNotFoundError(image)

    client,endpoint=_connect(token)
    args=(
        handle_file(str(image.resolve())),
        int(seed),
        float(ss_guidance_strength),
        int(ss_sampling_steps),
        float(slat_guidance_strength),
        int(slat_sampling_steps),
    )

    result=None
    last_error: Exception | None=None
    for attempt in range(1,5):
        try:
            result=client.predict(*args,api_name=endpoint)
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
            if not transient or attempt>=4:
                raise
            delay=min(20,4*attempt)
            print(
                "HAYUYA_HI3DGEN_RETRY",
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
            client,endpoint=_connect(token)

    if result is None:
        raise RuntimeError(
            "Hi3DGen generation returned no result after retries: "
            +repr(last_error)
        )

    src=_find_path(result)
    if src is None:
        raise RuntimeError(
            "Hi3DGen returned no downloadable mesh: "
            +repr(result)[:1400]
        )

    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,output)
    blob=output.read_bytes()
    if len(blob)<1024:
        raise RuntimeError(f"Hi3DGen mesh unexpectedly small: {len(blob)} bytes")
    if output.suffix.lower()==".glb" and blob[:4]!=b"glTF":
        raise RuntimeError("Hi3DGen output is not a GLB")

    meta={
        "schema":1,
        "generator":"Stable-X/Hi3DGen",
        "space":SPACE_ID,
        "endpoint":endpoint,
        "seed":int(seed),
        "ss_guidance_strength":float(ss_guidance_strength),
        "ss_sampling_steps":int(ss_sampling_steps),
        "slat_guidance_strength":float(slat_guidance_strength),
        "slat_sampling_steps":int(slat_sampling_steps),
        "normal_bridge":True,
        "native_model_generated_geometry":True,
        "textured":False,
        "license":"MIT",
        "production_default":True,
        "path":str(output),
        "bytes":len(blob),
    }
    output.with_suffix(".generation.json").write_text(
        json.dumps(meta,indent=2)+"\n",
        encoding="utf-8",
    )
    print("HAYUYA_HI3DGEN_NATIVE_PASS",json.dumps(meta,separators=(",",":")))
    return meta
