#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from gradio_client import Client, handle_file


def _named_endpoints(client):
    api = client.view_api(print_info=False, return_format="dict")
    return api.get("named_endpoints", {})


def _parameter_names(spec):
    return [p.get("parameter_name") for p in spec.get("parameters", [])]


def _find_preprocess_endpoint(named):
    ranked = []
    for name, spec in named.items():
        lname = name.lower()
        params = _parameter_names(spec)
        score = 0
        if "preprocess" in lname:
            score += 10
        if len(params) == 1 and params[0] in {"image", "image_prompt"}:
            score += 3
        if score:
            ranked.append((score, name, spec))
    if not ranked:
        raise RuntimeError(f"AniGen preprocess endpoint not found: {list(named)}")
    ranked.sort(reverse=True, key=lambda x: x[0])
    return ranked[0][1], ranked[0][2]


def _find_generation_endpoint(named):
    preferred = []
    for name, spec in named.items():
        params = set(_parameter_names(spec))
        score = 0
        lname = name.lower()
        if "image_to_3d" in lname:
            score += 10
        if "ss_model_name" in params:
            score += 5
        if "slat_model_name" in params:
            score += 5
        if "texture_size" in params:
            score += 3
        if "seed" in params:
            score += 1
        if score:
            preferred.append((score, name, spec))
    if not preferred:
        raise RuntimeError(f"AniGen generation endpoint not found: {list(named)}")
    preferred.sort(reverse=True, key=lambda x: x[0])
    return preferred[0][1], preferred[0][2]


def _retry(call, stage, attempts=5):
    delays = (20, 40, 70, 100)
    last = None
    for i in range(1, attempts + 1):
        try:
            return call()
        except Exception as exc:
            last = exc
            text = f"{type(exc).__name__}: {exc}".lower()
            print(f"::warning::AniGen {stage} attempt {i}/{attempts}: {type(exc).__name__}: {exc}")
            if "zerogpu quota" in text or "quota" in text and "exceeded" in text:
                raise RuntimeError(f"AniGen {stage} blocked by upstream GPU quota: {exc}")
            if i < attempts:
                time.sleep(delays[min(i - 1, len(delays) - 1)])
    raise RuntimeError(f"AniGen {stage} failed after {attempts} attempts: {last}")


def _path_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("path", "name"):
            raw = value.get(key)
            if isinstance(raw, str):
                return raw
    path = getattr(value, "path", None)
    if isinstance(path, str):
        return path
    return None


def _copy_glb(value, dst: Path, label: str):
    raw = _path_value(value)
    if not raw:
        raise RuntimeError(f"AniGen returned no {label} path: {value!r}")
    src = Path(raw)
    if not src.is_file():
        raise RuntimeError(f"AniGen {label} path is not local: {raw}")
    data = src.read_bytes()
    if len(data) < 1024 or data[:4] != b"glTF":
        raise RuntimeError(f"AniGen {label} is not a valid GLB: {raw}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


@dataclass
class AniGenResult:
    mesh: str
    skeleton: str | None
    processed_image: str | None
    space: str
    endpoint: str
    ss_model: str
    slat_model: str
    ss_steps: int
    slat_steps: int
    joints_density: int
    texture_size: int
    seed: int


def generate(
    image: Path,
    output_dir: Path,
    *,
    space: str = "VAST-AI/AniGen",
    ss_model: str = "ss_flow_solo",
    slat_model: str = "slat_flow_auto",
    ss_steps: int = 25,
    slat_steps: int = 25,
    joints_density: int = 1,
    texture_size: int = 2048,
    seed: int = 42,
) -> AniGenResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    kwargs = {"verbose": True, "httpx_kwargs": {"timeout": 240.0}}
    token = os.environ.get("HF_TOKEN", "").strip()
    if token:
        kwargs["token"] = token
    client = Client(space, **kwargs)
    named = _named_endpoints(client)

    preprocess_endpoint, preprocess_spec = _find_preprocess_endpoint(named)
    preprocess_params = _parameter_names(preprocess_spec)
    if len(preprocess_params) != 1:
        raise RuntimeError(
            f"Unexpected AniGen preprocess signature {preprocess_endpoint}: {preprocess_params}"
        )
    raw_image = handle_file(str(image.resolve()))
    processed = _retry(
        lambda: client.predict(raw_image, api_name=preprocess_endpoint),
        stage="preprocess_image",
        attempts=3,
    )

    endpoint, spec = _find_generation_endpoint(named)
    params = _parameter_names(spec)

    values = {
        "image": processed,
        "image_prompt": processed,
        "seed": int(seed),
        "ss_model_name": ss_model,
        "slat_model_name": slat_model,
        "ss_guidance_strength": 7.5,
        "ss_sampling_steps": int(ss_steps),
        "slat_guidance_strength": 3.0,
        "slat_sampling_steps": int(slat_steps),
        "joints_density": int(joints_density),
        "texture_size": int(texture_size),
    }
    missing = [p for p in params if p not in values]
    if missing:
        raise RuntimeError(f"Unhandled AniGen parameters for {endpoint}: {missing}")
    args = [values[p] for p in params]

    result = _retry(
        lambda: client.predict(*args, api_name=endpoint),
        stage="image_to_3d",
        attempts=5,
    )
    if not isinstance(result, (list, tuple)) or not result:
        raise RuntimeError(f"Unexpected AniGen response: {result!r}")

    mesh = _copy_glb(result[0], output_dir / "anigen_mesh.glb", "mesh")
    skeleton = None
    if len(result) > 1 and _path_value(result[1]):
        skeleton = _copy_glb(result[1], output_dir / "anigen_skeleton.glb", "skeleton")

    processed_image = None
    if len(result) > 2:
        raw = _path_value(result[2])
        if raw and Path(raw).is_file():
            ext = Path(raw).suffix or ".png"
            processed = output_dir / ("anigen_processed" + ext)
            shutil.copy2(raw, processed)
            processed_image = str(processed)

    payload = AniGenResult(
        mesh=str(mesh),
        skeleton=str(skeleton) if skeleton else None,
        processed_image=processed_image,
        space=space,
        endpoint=f"{preprocess_endpoint} -> {endpoint}",
        ss_model=ss_model,
        slat_model=slat_model,
        ss_steps=int(ss_steps),
        slat_steps=int(slat_steps),
        joints_density=int(joints_density),
        texture_size=int(texture_size),
        seed=int(seed),
    )
    (output_dir / "anigen_result.json").write_text(
        json.dumps(asdict(payload), indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    p = argparse.ArgumentParser(description="HAYUYA AniGen joint shape+skeleton+skin challenger.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--space", default="VAST-AI/AniGen")
    p.add_argument("--ss-model", default="ss_flow_solo", choices=["ss_flow_solo", "ss_flow_duet", "ss_flow_epic"])
    p.add_argument("--slat-model", default="slat_flow_auto", choices=["slat_flow_auto", "slat_flow_control"])
    p.add_argument("--ss-steps", type=int, default=25)
    p.add_argument("--slat-steps", type=int, default=25)
    p.add_argument("--joints-density", type=int, default=1)
    p.add_argument("--texture-size", type=int, default=2048)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()

    result = generate(
        a.input,
        a.output_dir,
        space=a.space,
        ss_model=a.ss_model,
        slat_model=a.slat_model,
        ss_steps=a.ss_steps,
        slat_steps=a.slat_steps,
        joints_density=a.joints_density,
        texture_size=a.texture_size,
        seed=a.seed,
    )
    print("HAYUYA_ANIGEN_RESULT", json.dumps(asdict(result), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
