#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file


def _named_endpoints(client: Client) -> dict:
    api=client.view_api(print_info=False,return_format="dict")
    return api.get("named_endpoints",{}) if isinstance(api,dict) else {}


def _parameter_names(spec: dict) -> list[str]:
    return [
        str(p.get("parameter_name") or "")
        for p in spec.get("parameters",[])
    ]


def _pick_generate(named: dict) -> tuple[str,dict]:
    if "/generate" in named:
        return "/generate",named["/generate"]
    candidates=[]
    for key,spec in named.items():
        name=str(key).lower()
        params=_parameter_names(spec)
        if "generate" in name and len(params)==1:
            candidates.append((key,spec))
    if not candidates:
        raise RuntimeError(
            "TripoSR CPU Space exposes no single-image generate endpoint; "
            f"found={list(named)}"
        )
    return candidates[0]


def _walk_paths(value: Any):
    if isinstance(value,str):
        yield value
    elif isinstance(value,dict):
        for v in value.values():
            yield from _walk_paths(v)
    elif isinstance(value,(list,tuple)):
        for v in value:
            yield from _walk_paths(v)
    else:
        for attr in ("path","url"):
            raw=getattr(value,attr,None)
            if isinstance(raw,str):
                yield raw


def generate(
    image: Path,
    output: Path,
    *,
    space: str="AleenDG/3DGenTripoSR",
    token: str|None=None,
) -> dict:
    """Free CPU continuity candidate.

    The audited Space runs TripoSR on CPU when CUDA is unavailable and its
    generate(image) function exports OBJ + GLB. HAYUYA never auto-promotes this
    candidate: caller quality/source gates remain authoritative.
    """
    # gradio_client 1.x already owns the httpx timeout argument internally;
    # passing timeout again through httpx_kwargs causes duplicate-key failure.
    kwargs={"verbose":True}
    if token:
        kwargs["token"]=token
    client=Client(space,**kwargs)
    named=_named_endpoints(client)
    endpoint,spec=_pick_generate(named)
    params=_parameter_names(spec)
    if len(params)!=1:
        raise RuntimeError(
            f"Unexpected TripoSR CPU generate signature: {params}"
        )
    print(
        "HAYUYA_TRIPOSR_CPU_SUBMIT",
        f"space={space}",
        f"endpoint={endpoint}",
        f"params={params}",
    )
    result=client.predict(
        handle_file(str(image.resolve())),
        api_name=endpoint,
    )
    candidates=[]
    for raw in _walk_paths(result):
        if not raw.lower().endswith(".glb"):
            continue
        p=Path(raw)
        if p.is_file():
            candidates.append(p)
    if not candidates:
        raise RuntimeError(
            "TripoSR CPU Space returned no downloaded GLB: "
            + repr(result)[:1000]
        )
    src=candidates[-1]
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,output)
    data=output.read_bytes()
    if data[:4]!=b"glTF" or len(data)<1024:
        raise RuntimeError(
            f"TripoSR CPU produced invalid GLB: magic={data[:16]!r} bytes={len(data)}"
        )
    payload={
        "path":str(output),
        "generator":"stabilityai/TripoSR",
        "service_space":space,
        "compute":"public Hugging Face CPU Space",
        "bytes":len(data),
        "quality_role":"continuity_candidate",
        "requires_full_hayuya_gates":True,
    }
    print("HAYUYA_TRIPOSR_CPU_PASS",payload)
    return payload
