#!/usr/bin/env python3
"""Standalone Tripo3D API probe.

Independent from Hayuya. Uses the public Tripo3D v2 OpenAPI only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

API_BASE = "https://api.tripo3d.ai/v2/openapi"
DEFAULT_MODEL = "v2.5-20250123"
DEFAULT_TIMEOUT = 900


def headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "tripo3d-light-standalone/1.0",
    }


def require_key() -> str:
    key = os.getenv("TRIPO_API_KEY", "").strip()
    if not key:
        raise SystemExit("TRIPO_API_KEY is missing. Dry-run still works without a key.")

    # Be forgiving when a dashboard/user copies an entire Authorization value
    # instead of only the raw tsk_... token.
    if key.lower().startswith("bearer "):
        key = key[7:].strip()

    # GitHub Secrets stores literal characters, so strip accidental wrapping
    # quotes without ever printing the secret itself.
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {"'", '"'}:
        key = key[1:-1].strip()

    if not key:
        raise SystemExit("TRIPO_API_KEY became empty after normalization.")
    return key


def infer_type(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower().lstrip(".")
    if suffix == "jpeg":
        return "jpg"
    if suffix in {"jpg", "png"}:
        return suffix
    return "jpg"


def payload_for(image_url: str, model_version: str, face_limit: int | None) -> dict:
    if not image_url.startswith(("https://", "http://")):
        raise SystemExit("--image-url must be an http(s) URL")
    payload = {
        "type": "image_to_model",
        "model_version": model_version,
        "file": {"type": infer_type(image_url), "url": image_url},
        "texture": True,
        "pbr": True,
        "export_uv": True,
    }
    if face_limit is not None:
        payload["face_limit"] = face_limit
    return payload


def request_json(method: str, url: str, *, api_key: str, **kwargs) -> tuple[requests.Response, dict]:
    response = requests.request(method, url, headers=headers(api_key), timeout=60, **kwargs)
    trace = response.headers.get("X-Tripo-Trace-ID", "<none>")
    print(f"HTTP {response.status_code} trace={trace}")
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text[:1000]}
    return response, body


def auth_check(api_key: str) -> int:
    response, body = request_json("GET", f"{API_BASE}/user/balance", api_key=api_key)
    if response.status_code != 200 or body.get("code") != 0:
        print(json.dumps(body, indent=2))
        return 2
    data = body.get("data", {})
    print("AUTH_OK")
    print(json.dumps({"balance": data.get("balance"), "frozen": data.get("frozen")}, indent=2))
    return 0


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with destination.open("wb") as fh:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    fh.write(chunk)
    print(f"DOWNLOADED {destination} ({destination.stat().st_size} bytes)")


def generate(api_key: str, payload: dict, out_dir: Path, timeout_seconds: int) -> int:
    response, body = request_json("POST", f"{API_BASE}/task", api_key=api_key, json=payload)
    if response.status_code != 200 or body.get("code") != 0:
        print("SUBMIT_FAILED")
        print(json.dumps(body, indent=2))
        return 3

    task_id = body.get("data", {}).get("task_id")
    if not task_id:
        print("SUBMIT_FAILED: no task_id")
        return 3
    print(f"TASK_ID={task_id}")

    deadline = time.monotonic() + timeout_seconds
    last = None
    result = None
    while time.monotonic() < deadline:
        response, body = request_json("GET", f"{API_BASE}/task/{task_id}", api_key=api_key)
        if response.status_code != 200 or body.get("code") != 0:
            print(json.dumps(body, indent=2))
            return 4
        data = body.get("data", {})
        status = data.get("status", "unknown")
        progress = data.get("progress")
        marker = (status, progress)
        if marker != last:
            print(f"STATUS={status} PROGRESS={progress}")
            last = marker
        if status == "success":
            result = data
            break
        if status in {"failed", "cancelled", "unknown", "banned", "expired"}:
            print(f"GENERATION_{status.upper()}")
            return 5
        time.sleep(2)

    if result is None:
        print("GENERATION_TIMEOUT")
        return 6

    out_dir.mkdir(parents=True, exist_ok=True)
    safe_meta = {
        "task_id": result.get("task_id", task_id),
        "status": result.get("status"),
        "progress": result.get("progress"),
        "output_keys": sorted((result.get("output") or {}).keys()),
    }
    (out_dir / "result.json").write_text(json.dumps(safe_meta, indent=2), encoding="utf-8")

    output = result.get("output") or {}
    candidates = [
        ("pbr_model", "model-pbr.glb"),
        ("model", "model.glb"),
        ("base_model", "base-model.glb"),
        ("rendered_image", "preview.png"),
    ]
    downloaded = set()
    for key, filename in candidates:
        url = output.get(key)
        if not url or url in downloaded:
            continue
        try:
            download_file(url, out_dir / filename)
            downloaded.add(url)
        except Exception as exc:
            print(f"DOWNLOAD_WARNING {key}: {exc}")

    if not any(out_dir.glob("*.glb")):
        print("GENERATION_OK_BUT_NO_GLB_DOWNLOADED")
        return 7
    print("GENERATION_OK")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Standalone Tripo3D image-to-model probe")
    p.add_argument("--image-url")
    p.add_argument("--model-version", default=DEFAULT_MODEL)
    p.add_argument("--face-limit", type=int)
    p.add_argument("--out-dir", default="output")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--auth-check", action="store_true")
    group.add_argument("--generate", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.auth_check:
        return auth_check(require_key())
    if not args.image_url:
        raise SystemExit("--image-url is required for --dry-run and --generate")
    payload = payload_for(args.image_url, args.model_version, args.face_limit)
    if args.dry_run:
        print("DRY_RUN_OK")
        print(json.dumps(payload, indent=2))
        return 0
    return generate(require_key(), payload, Path(args.out_dir), args.timeout)


if __name__ == "__main__":
    sys.exit(main())
