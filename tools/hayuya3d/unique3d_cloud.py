#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file

SPACE_ID = "Wuvin/Unique3D"
ENDPOINT = "/generate3dv2"


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
    for attr in ("path","name"):
        v=getattr(value,attr,None)
        if isinstance(v,str):
            p=Path(v)
            if p.exists():
                return p
    if isinstance(value,(list,tuple)):
        for item in value:
            p=_as_path(item)
            if p is not None:
                return p
    return None


def _connect(token: str | None, *, timeout: float=180.0) -> Client:
    kwargs={"verbose":True,"httpx_kwargs":{"timeout":float(timeout)}}
    if token:
        kwargs["token"]=token
    return Client(SPACE_ID,**kwargs)


def generate(
    image: Path,
    output: Path,
    *,
    token: str | None=None,
    seed: int=1993,
    remove_background: bool=True,
    refine: bool=True,
    expansion_weight: float=0.1,
    init_type: str="std",
) -> dict[str,Any]:
    image=Path(image)
    output=Path(output)
    if not image.is_file():
        raise FileNotFoundError(image)
    if init_type not in {"std","thin"}:
        raise ValueError(f"unsupported Unique3D init_type={init_type!r}")

    client=_connect(token)
    api=client.view_api(return_format="dict")
    named=dict(api.get("named_endpoints") or {})
    if ENDPOINT not in named:
        available=sorted(named)
        raise RuntimeError(
            "Unique3D public Space lost its generation endpoint; "
            f"expected={ENDPOINT} available={available}"
        )

    args=(
        handle_file(str(image.resolve())),
        bool(remove_background),
        int(seed),
        False,
        bool(refine),
        float(expansion_weight),
        init_type,
    )

    result=None
    last_error: Exception | None=None
    for attempt in range(1,5):
        try:
            result=client.predict(*args,api_name=ENDPOINT)
            break
        except Exception as exc:
            last_error=exc
            message=f"{type(exc).__name__}: {exc}"
            lower=message.lower()
            if "zerogpu quota" in lower or "exceeded your zerogpu quota" in lower:
                raise
            transient=any(marker in lower for marker in (
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
            ))
            if not transient or attempt>=4:
                raise
            delay=min(18,3*attempt)
            print(
                "HAYUYA_UNIQUE3D_RETRY",
                json.dumps(
                    {
                        "attempt":attempt,
                        "max_attempts":4,
                        "delay_seconds":delay,
                        "error":message[:500],
                    },
                    separators=(",",":"),
                ),
            )
            time.sleep(delay)
            client=_connect(token)

    if result is None:
        raise RuntimeError(
            "Unique3D generation returned no result after retries: "
            +repr(last_error)
        )

    src=_as_path(result)
    if src is None:
        raise RuntimeError(
            "Unique3D endpoint returned no downloadable model: "
            +repr(result)[:1200]
        )

    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,output)
    blob=output.read_bytes()
    if len(blob)<1024:
        raise RuntimeError(f"Unique3D output unexpectedly small: {len(blob)} bytes")
    if output.suffix.lower()==".glb" and blob[:4]!=b"glTF":
        raise RuntimeError("Unique3D output is not a valid GLB container")

    meta={
        "schema":1,
        "generator":"AiuniAI/Unique3D",
        "space":SPACE_ID,
        "endpoint":ENDPOINT,
        "seed":int(seed),
        "remove_background":bool(remove_background),
        "refine":bool(refine),
        "expansion_weight":float(expansion_weight),
        "init_type":init_type,
        "native_model_generated_geometry":True,
        "license":"MIT",
        "production_default":True,
        "path":str(output),
        "bytes":len(blob),
    }
    output.with_suffix(".generation.json").write_text(
        json.dumps(meta,indent=2)+"\n",
        encoding="utf-8",
    )
    print("HAYUYA_UNIQUE3D_NATIVE_PASS",json.dumps(meta,separators=(",",":")))
    return meta
