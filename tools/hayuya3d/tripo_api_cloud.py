#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import os
import shutil
import time
from pathlib import Path
from typing import Any, Sequence

import requests

BASE_URL = "https://api.tripo3d.ai/v2/openapi"
TERMINAL = {"success", "failed", "cancelled", "banned", "expired"}
SUPPORTED_SINGLE = {
    "P1-20260311",
    "Turbo-v1.0-20250506",
    "v3.1-20260211",
    "v3.0-20250812",
    "v2.5-20250123",
    "v2.0-20240919",
    "v1.4-20240625",
}
SUPPORTED_MULTIVIEW = {
    "P1-20260311",
    "v3.1-20260211",
    "v3.0-20250812",
    "v2.5-20250123",
    "v2.0-20240919",
}

class TripoAPIError(RuntimeError):
    pass

def _api_key(explicit: str | None = None) -> str:
    key = (explicit or os.getenv("TRIPO_API_KEY") or "").strip()
    if not key:
        raise TripoAPIError("TRIPO_API_KEY is not configured")
    if not key.startswith("tsk_"):
        raise TripoAPIError("TRIPO_API_KEY must start with 'tsk_'")
    return key

def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}

def _json_response(response: requests.Response, *, operation: str) -> dict[str, Any]:
    trace = response.headers.get("X-Tripo-Trace-ID")
    try:
        payload = response.json()
    except Exception as exc:
        raise TripoAPIError(
            f"{operation}: non-JSON response status={response.status_code} trace={trace}: "
            f"{response.text[:500]}"
        ) from exc
    if response.status_code >= 400 or int(payload.get("code", -1)) != 0:
        raise TripoAPIError(
            f"{operation}: status={response.status_code} code={payload.get('code')} "
            f"message={payload.get('message')} suggestion={payload.get('suggestion')} trace={trace}"
        )
    return payload

def _file_type(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return "jpg" if suffix in {"jpg", "jpeg"} else (suffix or "jpg")

def upload_image(
    image: Path,
    *,
    api_key: str | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    image = Path(image).resolve()
    if not image.is_file():
        raise FileNotFoundError(image)
    key = _api_key(api_key)
    s = session or requests.Session()
    mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    with image.open("rb") as fh:
        response = s.post(
            f"{BASE_URL}/upload",
            headers=_headers(key),
            files={"file": (image.name, fh, mime)},
            timeout=(20, 180),
        )
    payload = _json_response(response, operation="upload")
    data = payload.get("data") or {}
    token = data.get("image_token") or data.get("file_token")
    if not token:
        raise TripoAPIError(
            f"upload: no image/file token in response keys={sorted(data)}"
        )
    return {"type": _file_type(image), "file_token": str(token)}

def create_task(
    task_data: dict[str, Any],
    *,
    api_key: str | None = None,
    session: requests.Session | None = None,
) -> str:
    key = _api_key(api_key)
    s = session or requests.Session()
    response = s.post(
        f"{BASE_URL}/task",
        headers={**_headers(key), "Content-Type": "application/json"},
        json=task_data,
        timeout=(20, 180),
    )
    payload = _json_response(
        response, operation=f"create_task:{task_data.get('type')}"
    )
    task_id = (payload.get("data") or {}).get("task_id")
    if not task_id:
        raise TripoAPIError("create_task: response contained no task_id")
    return str(task_id)

def get_task(
    task_id: str,
    *,
    api_key: str | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    key = _api_key(api_key)
    s = session or requests.Session()
    response = s.get(
        f"{BASE_URL}/task/{task_id}",
        headers=_headers(key),
        timeout=(20, 120),
    )
    payload = _json_response(response, operation=f"get_task:{task_id}")
    data = payload.get("data") or {}
    if not data:
        raise TripoAPIError(f"get_task:{task_id}: empty data")
    return data

def wait_for_task(
    task_id: str,
    *,
    api_key: str | None = None,
    session: requests.Session | None = None,
    timeout_s: float = 1800.0,
    min_poll_s: float = 2.0,
    max_poll_s: float = 30.0,
) -> dict[str, Any]:
    s = session or requests.Session()
    deadline = time.monotonic() + timeout_s
    poll = min_poll_s
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Tripo task {task_id} exceeded {timeout_s:.0f}s")
        task = get_task(task_id, api_key=api_key, session=s)
        status = str(task.get("status") or "").lower()
        print(
            "HAYUYA_TRIPO_TASK",
            json.dumps(
                {
                    "task_id": task_id,
                    "status": status,
                    "progress": task.get("progress"),
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
        if status in TERMINAL:
            if status != "success":
                raise TripoAPIError(
                    f"Tripo task {task_id} ended with status={status}"
                )
            return task
        left = task.get("running_left_time")
        if isinstance(left, (int, float)) and left > 0:
            poll = max(min_poll_s, min(max_poll_s, float(left) * 0.5))
        time.sleep(poll)
        poll = min(max_poll_s, max(min_poll_s, poll * 1.5))

def _output_urls(task: dict[str, Any]) -> list[tuple[str, str]]:
    output = task.get("output") or {}
    ordered: list[tuple[str, str]] = []
    for key in ("pbr_model", "model", "base_model"):
        value = output.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            ordered.append((key, value))
    return ordered

def download_best_model(
    task: dict[str, Any],
    output: Path,
    *,
    session: requests.Session | None = None,
) -> tuple[str, str]:
    urls = _output_urls(task)
    if not urls:
        raise TripoAPIError(
            "task output has no downloadable model URL: "
            f"keys={sorted((task.get('output') or {}).keys())}"
        )
    kind, url = urls[0]
    s = session or requests.Session()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with s.get(url, stream=True, timeout=(20, 300)) as response:
        response.raise_for_status()
        with output.open("wb") as fh:
            shutil.copyfileobj(response.raw, fh, length=1024 * 1024)
    blob = output.read_bytes()
    if len(blob) < 1024 or blob[:4] != b"glTF":
        raise TripoAPIError(
            f"downloaded {kind} is not a valid GLB (bytes={len(blob)})"
        )
    return kind, url

def _base_task_options(
    *,
    model_version: str,
    seed: int,
    texture: bool,
    pbr: bool,
    texture_quality: str,
    face_limit: int | None,
    geometry_quality: str | None,
    quad: bool,
    auto_size: bool,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "model_version": model_version,
        "model_seed": int(seed),
        "texture_seed": int(seed),
        "texture": bool(texture),
        "pbr": bool(pbr),
        "texture_quality": texture_quality,
    }

    # Tripo P1 is a separate low-poly family. Its API explicitly rejects
    # quad/smart-low-poly/generate-parts/geometry-quality and caps face_limit
    # at 20k. Keep one adapter while emitting only provider-valid parameters.
    if model_version == "P1-20260311":
        if face_limit is not None:
            data["face_limit"] = max(48, min(int(face_limit), 20_000))
        return data

    max_faces = {
        "v3.1-20260211": 2_000_000,
        "v3.0-20250812": 2_000_000,
        "v2.5-20250123": 500_000,
        "v2.0-20240919": 500_000,
    }.get(model_version)
    if face_limit is not None and max_faces is not None:
        data["face_limit"] = max(500, min(int(face_limit), max_faces))
    if geometry_quality and model_version in {
        "v3.1-20260211",
        "v3.0-20250812",
    }:
        data["geometry_quality"] = geometry_quality
    if quad:
        data["quad"] = True
    if auto_size:
        data["auto_size"] = True
    return data

def generate(
    image: Path,
    out: Path,
    *,
    token: str | None = None,
    seed: int = 1993,
    api_key: str | None = None,
    model_version: str | None = None,
    texture: bool = True,
    pbr: bool = True,
    texture_quality: str = "standard",
    face_limit: int | None = 2_000_000,
    geometry_quality: str | None = "detailed",
    quad: bool = False,
    auto_size: bool = False,
    timeout_s: float = 1800.0,
) -> dict[str, Any]:
    del token
    version = (
        model_version
        or os.getenv("HAYUYA_TRIPO_MODEL_VERSION")
        or "v3.1-20260211"
    )
    if version not in SUPPORTED_SINGLE:
        raise TripoAPIError(
            f"unsupported Tripo single-image model_version={version}"
        )
    key = _api_key(api_key)
    session = requests.Session()
    task_data: dict[str, Any] = {
        "type": "image_to_model",
        "file": upload_image(Path(image), api_key=key, session=session),
        **_base_task_options(
            model_version=version,
            seed=seed,
            texture=texture,
            pbr=pbr,
            texture_quality=texture_quality,
            face_limit=face_limit,
            geometry_quality=geometry_quality,
            quad=quad,
            auto_size=auto_size,
        ),
    }
    task_id = create_task(task_data, api_key=key, session=session)
    task = wait_for_task(
        task_id, api_key=key, session=session, timeout_s=timeout_s
    )
    artifact_kind, artifact_url = download_best_model(
        task, Path(out), session=session
    )
    return {
        "generator": "Tripo API",
        "provider": "tripoapi",
        "task_id": task_id,
        "model_version": version,
        "textured": bool(texture or pbr),
        "pbr": bool(pbr),
        "multi_view": False,
        "seed": int(seed),
        "artifact_kind": artifact_kind,
        "artifact_url": artifact_url,
        "path": str(Path(out).resolve()),
    }

def generate_multiview(
    images: Sequence[Path | None],
    out: Path,
    *,
    seed: int = 1993,
    api_key: str | None = None,
    model_version: str | None = None,
    texture: bool = True,
    pbr: bool = True,
    texture_quality: str = "standard",
    face_limit: int | None = 2_000_000,
    geometry_quality: str | None = "detailed",
    quad: bool = False,
    auto_size: bool = False,
    timeout_s: float = 1800.0,
) -> dict[str, Any]:
    if len(images) != 4:
        raise ValueError(
            "Tripo multiview requires exactly four slots: front,left,back,right"
        )
    version = (
        model_version
        or os.getenv("HAYUYA_TRIPO_MULTIVIEW_MODEL_VERSION")
        or os.getenv("HAYUYA_TRIPO_MODEL_VERSION")
        or "v3.1-20260211"
    )
    if version not in SUPPORTED_MULTIVIEW:
        raise TripoAPIError(
            f"unsupported Tripo multiview model_version={version}"
        )
    key = _api_key(api_key)
    session = requests.Session()
    files = [
        {}
        if image is None
        else upload_image(Path(image), api_key=key, session=session)
        for image in images
    ]
    task_data: dict[str, Any] = {
        "type": "multiview_to_model",
        "files": files,
        **_base_task_options(
            model_version=version,
            seed=seed,
            texture=texture,
            pbr=pbr,
            texture_quality=texture_quality,
            face_limit=face_limit,
            geometry_quality=geometry_quality,
            quad=quad,
            auto_size=auto_size,
        ),
    }
    task_id = create_task(task_data, api_key=key, session=session)
    task = wait_for_task(
        task_id, api_key=key, session=session, timeout_s=timeout_s
    )
    artifact_kind, artifact_url = download_best_model(
        task, Path(out), session=session
    )
    return {
        "generator": "Tripo API",
        "provider": "tripoapi",
        "task_id": task_id,
        "model_version": version,
        "textured": bool(texture or pbr),
        "pbr": bool(pbr),
        "multi_view": True,
        "view_order": ["front", "left", "back", "right"],
        "seed": int(seed),
        "artifact_kind": artifact_kind,
        "artifact_url": artifact_url,
        "path": str(Path(out).resolve()),
    }
