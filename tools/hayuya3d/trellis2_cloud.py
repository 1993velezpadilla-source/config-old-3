#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file


def _named_endpoints(client: Client) -> dict:
    api=client.view_api(print_info=False,return_format="dict")
    return api.get("named_endpoints",{}) if isinstance(api,dict) else {}


def _endpoint(named: dict, preferred: str, contains: str) -> tuple[str,dict]:
    if preferred in named:
        return preferred,named[preferred]
    key=next((k for k in named if contains.lower() in str(k).lower()),None)
    if key is None:
        raise RuntimeError(
            f"TRELLIS.2 endpoint {preferred} unavailable; found {list(named)}"
        )
    return key,named[key]


def _parameter_names(spec: dict) -> list[str]:
    return [
        str(p.get("parameter_name") or "")
        for p in spec.get("parameters",[])
    ]


def _call_named(client: Client, endpoint: str, spec: dict, values: dict[str,Any]):
    params=_parameter_names(spec)
    missing=[name for name in params if name not in values]
    if missing:
        raise RuntimeError(
            f"TRELLIS.2 endpoint {endpoint} has unsupported parameters: {missing}"
        )
    return client.predict(
        *[values[name] for name in params],
        api_name=endpoint,
    )


def _is_zerogpu_quota(exc: Exception) -> bool:
    text=f"{type(exc).__name__}: {exc}".lower()
    return (
        "zerogpu quota" in text
        or "exceeded your zerogpu quota" in text
        or "more quota" in text and "hugging face token" in text
    )


def _retryable(exc: Exception) -> bool:
    text=f"{type(exc).__name__}: {exc}".lower()
    hard=(
        "unsupported parameters",
        "endpoint /",
        "unexpected trellis.2 preprocess signature",
        "produced invalid glb",
        "returned no downloaded glb",
        "greater than maximum value",
        "less than minimum value",
    )
    if any(marker in text for marker in hard):
        return False
    # The public ZeroGPU app frequently surfaces queue/OOM/session failures as
    # a generic AppError with no useful message. Treat remote/runtime failures
    # as retryable, but keep deterministic API-contract failures hard.
    return True


def _retry_call(
    fn,
    *,
    stage: str,
    attempts: int = 3,
    delays: tuple[int,...] = (20,45),
):
    last=None
    for attempt in range(1,attempts+1):
        try:
            print(f"HAYUYA_TRELLIS2_STAGE {stage} attempt={attempt}")
            result=fn()
            print(f"HAYUYA_TRELLIS2_STAGE_PASS {stage} attempt={attempt}")
            return result
        except Exception as exc:
            last=exc
            # Quota exhaustion cannot recover by sleeping for seconds; the
            # provider reports an hours-long reset. Fail fast so the caller can
            # preserve state and choose another execution path.
            if _is_zerogpu_quota(exc):
                print(
                    f"::warning::TRELLIS.2 {stage} blocked by ZeroGPU quota; "
                    "skipping useless short retries"
                )
                raise
            if attempt>=attempts or not _retryable(exc):
                raise
            delay=delays[min(attempt-1,len(delays)-1)]
            print(
                f"::warning::TRELLIS.2 {stage} attempt {attempt}/{attempts} "
                f"failed; retrying in {delay}s: {type(exc).__name__}: {exc}"
            )
            time.sleep(delay)
    raise RuntimeError(f"TRELLIS.2 {stage} exhausted retries: {last}")


def _as_gradio_file_input(value):
    """Convert a Gradio image output back into a valid file input.

    gradio_client 1.x requires local file paths/URLs to be wrapped with
    handle_file() when they are sent into another endpoint. Image outputs are
    commonly returned as local downloaded paths or FileData-like mappings.
    """
    candidates=list(_walk_paths(value))
    for raw in candidates:
        try:
            path=Path(raw)
            if path.is_file():
                return handle_file(str(path.resolve()))
        except Exception:
            pass
        if isinstance(raw,str) and (
            raw.startswith("http://") or raw.startswith("https://")
        ):
            return handle_file(raw)
    raise RuntimeError(
        "TRELLIS.2 preprocess returned no reusable image file: "
        + repr(value)[:500]
    )


def _walk_paths(value):
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
            v=getattr(value,attr,None)
            if isinstance(v,str):
                yield v


def _state_from_generation(result):
    if isinstance(result,dict) and "res" in result and "coords" in result:
        return result
    if isinstance(result,(list,tuple)):
        for value in result:
            state=_state_from_generation(value)
            if state is not None:
                return state
    if isinstance(result,dict):
        for value in result.values():
            state=_state_from_generation(value)
            if state is not None:
                return state
    return None


def _save_generation_checkpoint(result, state, output: Path) -> dict:
    """Persist what the public Gradio API exposes before GLB extraction.

    The official Space keeps gr.State server-side in some API revisions, so a
    client may receive only preview HTML while extract_glb still has access to
    the latent through the same session. Never abort generation merely because
    the hidden state is not serializable client-side.
    """
    checkpoint={}
    if isinstance(state,dict):
        try:
            import numpy as np
            state_path=output.with_suffix(".state.npz")
            payload={}
            for key,value in state.items():
                if isinstance(value,np.ndarray):
                    payload[key]=value
                elif isinstance(value,(int,float,bool,str)):
                    payload[key]=np.asarray(value)
            if payload:
                np.savez_compressed(state_path,**payload)
                checkpoint["state_npz"]=str(state_path)
                checkpoint["state_bytes"]=state_path.stat().st_size
        except Exception as exc:
            checkpoint["state_error"]=f"{type(exc).__name__}: {exc}"
    else:
        checkpoint["state_visibility"]="server_session_only"
        checkpoint["state_persistable"]=False

    try:
        preview=None
        def find_preview(value):
            nonlocal preview
            if preview is not None:
                return
            if isinstance(value,str) and (
                "previewer-container" in value or "<img" in value
            ):
                preview=value
                return
            if isinstance(value,dict):
                for v in value.values():
                    find_preview(v)
            elif isinstance(value,(list,tuple)):
                for v in value:
                    find_preview(v)
        find_preview(result)
        if preview:
            preview_path=output.with_suffix(".preview.html")
            preview_path.write_text(preview,encoding="utf-8")
            checkpoint["preview_html"]=str(preview_path)
            checkpoint["preview_bytes"]=preview_path.stat().st_size
    except Exception as exc:
        checkpoint["preview_error"]=f"{type(exc).__name__}: {exc}"

    meta_path=output.with_suffix(".generation.json")
    meta_path.write_text(json.dumps(checkpoint,indent=2)+"\n",encoding="utf-8")
    checkpoint["metadata"]=str(meta_path)
    print("HAYUYA_TRELLIS2_GENERATION_CHECKPOINT",json.dumps(checkpoint,separators=(",",":")))
    return checkpoint


def generate(
    image: Path,
    output: Path,
    *,
    token: str | None = None,
    quality: str = "high",
    seed: int = 1993,
    space: str = "microsoft/TRELLIS.2",
) -> dict:
    """
    Generate one modern full-PBR candidate through Microsoft's public TRELLIS.2
    Space. The caller owns fallback policy; this function never hides failure.
    """
    kwargs={"verbose":True,"httpx_kwargs":{"timeout":180.0}}
    if token:
        kwargs["token"]=token
    client=Client(space,**kwargs)
    named=_named_endpoints(client)

    if "/start_session" in named:
        try:
            _retry_call(
                lambda: client.predict(api_name="/start_session"),
                stage="start_session",
                attempts=2,
                delays=(8,),
            )
        except Exception as exc:
            print(
                "::warning::TRELLIS.2 start_session failed; continuing with "
                f"Gradio session state: {type(exc).__name__}: {exc}"
            )

    preprocess_ep,preprocess_spec=_endpoint(
        named,"/preprocess_image","preprocess_image"
    )
    preprocess_params=_parameter_names(preprocess_spec)
    if len(preprocess_params)!=1:
        raise RuntimeError(
            f"Unexpected TRELLIS.2 preprocess signature: {preprocess_params}"
        )
    processed=_retry_call(
        lambda: client.predict(
            handle_file(str(image.resolve())),
            api_name=preprocess_ep,
        ),
        stage="preprocess_image",
    )
    processed_input=_as_gradio_file_input(processed)
    print(
        "HAYUYA_TRELLIS2_PREPROCESS_CHAIN",
        "output_type="+type(processed).__name__,
        "reupload=handle_file",
    )

    generate_ep,generate_spec=_endpoint(
        named,"/image_to_3d","image_to_3d"
    )
    # Microsoft's official TRELLIS.2 app exposes 512 / 1024 / 1536 and
    # defaults to 1024. Ultra first attempts 1536, but an upstream Space/OOM
    # failure must degrade inside TRELLIS.2 before HAYUYA considers another
    # generator. This avoids silently falling back to a lower-fidelity model.
    resolution_candidates=(
        ["1536","1024","512"]
        if quality=="ultra"
        else ["1024","512"]
    )
    generation=None
    resolution=None
    resolution_failures=[]
    for candidate_resolution in resolution_candidates:
        generate_values={
            "image":processed_input,
            "input":processed_input,
            "seed":int(seed),
            "resolution":candidate_resolution,
            "ss_guidance_strength":7.5,
            "ss_guidance_rescale":0.7,
            "ss_sampling_steps":12,
            "ss_rescale_t":5.0,
            "shape_slat_guidance_strength":7.5,
            "shape_slat_guidance_rescale":0.5,
            "shape_slat_sampling_steps":12,
            "shape_slat_rescale_t":3.0,
            "tex_slat_guidance_strength":1.0,
            "tex_slat_guidance_rescale":0.0,
            "tex_slat_sampling_steps":12,
            "tex_slat_rescale_t":3.0,
        }
        try:
            generation=_retry_call(
                lambda values=generate_values: _call_named(
                    client,generate_ep,generate_spec,values
                ),
                stage=f"image_to_3d_{candidate_resolution}",
            )
            resolution=candidate_resolution
            if resolution_failures:
                print(
                    "HAYUYA_TRELLIS2_RESOLUTION_RECOVERED",
                    f"selected={resolution}",
                    "failed="+",".join(x["resolution"] for x in resolution_failures),
                )
            break
        except Exception as exc:
            resolution_failures.append({
                "resolution":candidate_resolution,
                "error":f"{type(exc).__name__}: {exc}",
            })
            print(
                "::warning::TRELLIS.2 resolution "
                f"{candidate_resolution} unavailable; trying lower official "
                f"resolution: {type(exc).__name__}: {exc}"
            )
    if generation is None or resolution is None:
        raise RuntimeError(
            "TRELLIS.2 failed all official resolutions: "
            + "; ".join(
                f"{x['resolution']}={x['error']}"
                for x in resolution_failures
            )
        )
    state=_state_from_generation(generation)
    checkpoint=_save_generation_checkpoint(generation,state,output)
    if state is None:
        print(
            "HAYUYA_TRELLIS2_STATE",
            "visibility=server_session_only",
            "continuing_extract_same_session=true",
        )

    extract_ep,extract_spec=_endpoint(named,"/extract_glb","extract_glb")
    texture_size=4096 if quality in {"high","ultra"} else 2048

    # The public TRELLIS.2 Space hard-caps GLB extraction at 500k faces.
    # Keep that provider constraint explicit instead of repeatedly submitting an
    # invalid 1-2M request. HAYUYA's Hero Master target stays separate and is
    # fulfilled by downstream open geometry enhancement / dense challengers.
    provider_extract_cap=500_000
    if quality=="ultra":
        hero_target_faces=2_000_000
        hero_min_faces=1_000_000
    elif quality=="high":
        hero_target_faces=1_250_000
        hero_min_faces=650_000
    else:
        hero_target_faces=500_000
        hero_min_faces=0
    faces=min(hero_target_faces,provider_extract_cap)

    extract_values={
        "state":state,
        "output_buf":state,
        "decimation_target":faces,
        "texture_size":texture_size,
    }
    # Gradio session state is sometimes intentionally hidden from the public
    # signature. In that case the same Client session carries it implicitly.
    for param in _parameter_names(extract_spec):
        if param in {"state","output_buf"} and extract_values[param] is None:
            raise RuntimeError(
                "TRELLIS.2 exposed state as an API parameter but generation "
                "did not return a serializable state"
            )
    extracted=_retry_call(
        lambda: _call_named(client,extract_ep,extract_spec,extract_values),
        stage=f"extract_glb_{faces}f_{texture_size}px",
    )

    candidates=[]
    for value in _walk_paths(extracted):
        path=Path(value)
        if value.lower().endswith(".glb") and path.is_file():
            candidates.append(path)
    if not candidates:
        raise RuntimeError(
            f"TRELLIS.2 extraction returned no downloaded GLB: {extracted!r}"
        )

    source=candidates[-1]
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,output)
    data=output.read_bytes()
    if data[:4]!=b"glTF" or len(data)<1024:
        raise RuntimeError(
            f"TRELLIS.2 produced invalid GLB: magic={data[:16]!r} bytes={len(data)}"
        )
    return {
        "path":str(output),
        "generator":"microsoft/TRELLIS.2-4B",
        "space":space,
        "resolution":int(resolution),
        "resolution_fallbacks":resolution_failures,
        "generation_checkpoint":checkpoint,
        "texture_size":texture_size,
        "faces_target":faces,
        "provider_extract_cap_faces":provider_extract_cap,
        "hero_master_target_faces":hero_target_faces,
        "hero_master_min_faces":hero_min_faces,
        "hero_master_requires_refinement":hero_target_faces>faces,
        "hero_master_policy":"dense-first-fidelity-before-retopo",
        "bytes":len(data),
    }
