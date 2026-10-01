#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file


def _named_endpoints(client: Client) -> dict:
    api = client.view_api(print_info=False, return_format="dict")
    return api.get("named_endpoints", {}) if isinstance(api, dict) else {}



def _initialize_gradio_session(client: Client) -> dict:
    """Run the Space load/start_session hook even when Gradio hides it as unnamed.

    The public TripoSG app creates TMP_DIR/<session_hash> only from demo.load().
    API clients do not reliably execute that browser load event, so direct calls
    to image_to_3d can fail while trying to export into a missing session dir.
    """
    report={"attempted":False,"method":None,"fn_index":None,"ok":False}
    named=_named_endpoints(client)
    if "/start_session" in named:
        report.update(attempted=True,method="named",fn_index=None)
        client.predict(api_name="/start_session")
        report["ok"]=True
        return report

    endpoints=getattr(client,"endpoints",[]) or []
    for ep in endpoints:
        dep=getattr(ep,"dependency",{}) or {}
        targets=dep.get("targets") or []
        is_load=any(
            isinstance(t,(list,tuple)) and len(t)>=2 and str(t[1]).lower()=="load"
            for t in targets
        )
        if is_load and not dep.get("inputs") and not dep.get("outputs"):
            report.update(
                attempted=True,
                method="unnamed_load_fn_index",
                fn_index=int(getattr(ep,"fn_index")),
            )
            client.predict(fn_index=int(getattr(ep,"fn_index")))
            report["ok"]=True
            return report
    return report


def _prepare_local_segmented_image(image: Path, work_dir: Path) -> tuple[Path | None, dict]:
    """Reuse a trustworthy alpha matte locally and avoid a redundant ZeroGPU call."""
    try:
        from PIL import Image
        im=Image.open(image).convert("RGBA")
        alpha=im.getchannel("A")
        lo, hi=alpha.getextrema()
        hist=alpha.histogram()
        total=max(1,sum(hist))
        nonopaque=sum(hist[:250])
        fraction=float(nonopaque)/float(total)
        useful=bool(lo < 250 and hi > 5 and fraction >= 0.0001)
        report={
            "mode":"RGBA",
            "size":[int(im.width),int(im.height)],
            "alpha_min":int(lo),
            "alpha_max":int(hi),
            "nonopaque_fraction":fraction,
            "useful_alpha":useful,
        }
        if not useful:
            return None, report
        work_dir.mkdir(parents=True, exist_ok=True)
        out=work_dir/"triposg_local_segmented.png"
        im.save(out, format="PNG")
        return out, report
    except Exception as exc:
        return None, {"useful_alpha":False,"error":f"{type(exc).__name__}: {exc}"}

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


def texture_existing_mesh(
    image: Path,
    mesh: Path,
    output: Path,
    *,
    token: str | None = None,
    seed: int = 1993,
    space: str = "VAST-AI/TripoSG",
) -> dict:
    """Texture an existing HAYUYA mesh through TripoSG without replacing geometry."""
    if not image.is_file():
        raise FileNotFoundError(image)
    if not mesh.is_file():
        raise FileNotFoundError(mesh)

    kwargs = {"verbose": True, "httpx_kwargs": {"timeout": 240.0}}
    if token:
        kwargs["token"] = token
    client = Client(space, **kwargs)
    named = _named_endpoints(client)

    try:
        session_init = _initialize_gradio_session(client)
        print("HAYUYA_TRIPOSG_TEXTURE_SESSION_INIT", session_init)
    except Exception as exc:
        session_init = {
            "attempted": True,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(
            "::warning::TripoSG texture session initialization failed: "
            + session_init["error"]
        )

    tex_ep, tex_spec = _pick_endpoint(named, "/run_texture", "texture")
    tex_values = {
        "image": handle_file(str(image.resolve())),
        "mesh_path": handle_file(str(mesh.resolve())),
        "mesh": handle_file(str(mesh.resolve())),
        "model": handle_file(str(mesh.resolve())),
        "seed": int(seed),
    }
    textured = _call_named(client, tex_ep, tex_spec, tex_values)
    chosen = _extract_downloaded_glb(textured)

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chosen, output)
    blob = output.read_bytes()
    if blob[:4] != b"glTF" or len(blob) < 1024:
        raise RuntimeError(
            f"TripoSG texture output invalid: magic={blob[:16]!r} bytes={len(blob)}"
        )

    payload = {
        "path": str(output),
        "generator": "VAST-AI/TripoSG",
        "service_space": space,
        "mode": "texture_existing_mesh",
        "source_mesh": str(mesh),
        "reference_image": str(image),
        "seed": int(seed),
        "geometry_authority": "HAYUYA native refined mesh",
        "geometry_replacement_allowed": False,
        "bytes": len(blob),
        "session_init": session_init,
    }
    print("HAYUYA_TRIPOSG_TEXTURE_PASS", payload)
    return payload


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

    try:
        session_init=_initialize_gradio_session(client)
        print("HAYUYA_TRIPOSG_SESSION_INIT", session_init)
    except Exception as exc:
        session_init={"attempted":True,"ok":False,"error":f"{type(exc).__name__}: {exc}"}
        print(
            "::warning::TripoSG session initialization failed: "
            +session_init["error"]
        )

    local_segmented, local_segmentation = _prepare_local_segmented_image(
        image,
        output.parent,
    )
    if local_segmented is not None:
        segmented_input=handle_file(str(local_segmented.resolve()))
        segmentation_mode="local_alpha_reuse"
        print(
            "HAYUYA_TRIPOSG_LOCAL_SEGMENTATION_REUSE",
            local_segmentation,
        )
    else:
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
        segmentation_mode="public_space_rmbg"

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
        "session_init": session_init,
        "segmentation_mode": segmentation_mode,
        "local_segmentation": local_segmentation,
    }
    print("HAYUYA_TRIPOSG_CLOUD_PASS", payload)
    return payload
