#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_MODEL_ROOT = ROOT / ".hayuya" / "models"


def run_text(cmd: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=30,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 999, "", f"{type(exc).__name__}: {exc}"


def load_lock() -> dict:
    return json.loads((HERE / "backends.lock.json").read_text(encoding="utf-8"))


def load_env_lock() -> dict:
    path = HERE / "backend_envs.lock.json"
    if not path.is_file():
        return {"backends": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def env_key(backend: str) -> str:
    return f"HAYUYA_{backend.upper().replace('-', '_')}_PYTHON"


def resolve_python(backend: str) -> tuple[str, bool]:
    key = env_key(backend)
    configured = os.environ.get(key)
    executable = configured or sys.executable
    exists = bool(shutil.which(executable) or Path(executable).is_file())
    return executable, exists


def gpu_inventory() -> dict:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ]
    code, stdout, stderr = run_text(command)
    gpus = []
    if code == 0:
        for index, line in enumerate(stdout.splitlines()):
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 3:
                try:
                    memory_mb = int(float(parts[1]))
                except Exception:
                    memory_mb = None
                gpus.append({
                    "index": index,
                    "name": parts[0],
                    "memory_total_mb": memory_mb,
                    "driver_version": parts[2],
                })
    return {
        "available": code == 0 and bool(gpus),
        "command_exit": code,
        "gpus": gpus,
        "stderr": stderr or None,
    }


def python_cuda_probe(executable: str) -> dict:
    script = (
        "import json\n"
        "try:\n"
        " import torch\n"
        " ok=bool(torch.cuda.is_available())\n"
        " data={'torch':getattr(torch,'__version__',None),'cuda_available':ok,"
        "'torch_cuda':getattr(torch.version,'cuda',None),'device_count':int(torch.cuda.device_count())}\n"
        " if ok:\n"
        "  data['device_name']=torch.cuda.get_device_name(0)\n"
        "  p=torch.cuda.get_device_properties(0)\n"
        "  data['device_memory_gb']=round(p.total_memory/(1024**3),2)\n"
        " print(json.dumps(data))\n"
        "except Exception as e:\n"
        " print(json.dumps({'error':type(e).__name__+': '+str(e)}))\n"
    )
    code, stdout, stderr = run_text([executable, "-c", script])
    data = {"exit": code}
    if stdout:
        try:
            data.update(json.loads(stdout.splitlines()[-1]))
        except Exception:
            data["stdout"] = stdout
    if stderr:
        data["stderr"] = stderr
    return data


def backend_probe(entry: dict, model_root: Path, env_spec: dict | None = None) -> dict:
    backend = entry["id"]
    repo = model_root / backend
    executable, python_exists = resolve_python(backend)
    result = {
        "id": backend,
        "license": entry.get("license"),
        "expected_sha": entry.get("sha"),
        "min_vram_gb": entry.get("min_vram_gb"),
        "repo_path": str(repo),
        "repo_exists": repo.is_dir(),
        "python_env_key": env_key(backend),
        "python_explicit": bool(os.environ.get(env_key(backend))),
        "python": executable,
        "python_exists": python_exists,
    }

    if repo.is_dir():
        code, stdout, stderr = run_text(["git", "rev-parse", "HEAD"], cwd=repo)
        result["repo_head"] = stdout if code == 0 else None
        result["repo_sha_matches"] = code == 0 and stdout == entry.get("sha")
        if stderr:
            result["git_stderr"] = stderr
    else:
        result["repo_head"] = None
        result["repo_sha_matches"] = False

    if python_exists:
        code, stdout, stderr = run_text([executable, "--version"])
        result["python_version"] = stdout or stderr or None
        result["python_probe_exit"] = code
        result["cuda_probe"] = python_cuda_probe(executable)
    else:
        result["python_version"] = None
        result["python_probe_exit"] = 127
        result["cuda_probe"] = {"error": "python executable missing"}

    required_vram = float(entry.get("min_vram_gb") or 0)
    cuda = result["cuda_probe"]
    result["cuda_ready"] = bool(cuda.get("cuda_available")) or required_vram <= 0

    result["env_contract"] = None
    result["python_version_matches"] = True
    result["torch_version_matches"] = True
    result["cuda_family_matches"] = True
    if env_spec:
        expected_python = str(env_spec.get("python", ""))
        torch_spec = env_spec.get("torch", {})
        expected_torch = str(torch_spec.get("version", ""))
        expected_cuda = str(torch_spec.get("cuda_family", ""))

        actual_python = str(result.get("python_version") or "")
        actual_torch = str(cuda.get("torch") or "")
        actual_cuda = str(cuda.get("torch_cuda") or "")

        result["env_contract"] = {
            "expected_python": expected_python,
            "expected_torch": expected_torch,
            "expected_cuda_family": expected_cuda,
        }
        if expected_python:
            result["python_version_matches"] = actual_python.startswith(
                f"Python {expected_python}"
            )
        if expected_torch:
            result["torch_version_matches"] = (
                actual_torch.split("+", 1)[0] == expected_torch
            )
        if expected_cuda:
            result["cuda_family_matches"] = actual_cuda.startswith(expected_cuda)

    source_required = bool(entry.get("source_required", True))
    result["source_required"] = source_required
    source_ready = bool(
        (result["repo_exists"] and result["repo_sha_matches"])
        if source_required else True
    )
    result["ready"] = bool(
        source_ready
        and result["python_exists"]
        and result["cuda_ready"]
        and result["python_version_matches"]
        and result["torch_version_matches"]
        and result["cuda_family_matches"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a GPU runner for HAYUYA end-to-end execution.")
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--backend", action="append", default=[])
    parser.add_argument("--backends", help="comma-separated backend ids")
    parser.add_argument("--include-support", action="store_true", help="also require DINOv2, Wonder3D and TripoSF")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    lock = load_lock()
    env_lock = load_env_lock()
    meta = {entry["id"]: entry for entry in lock["backends"]}
    env_meta = env_lock.get("backends", {})

    requested = list(args.backend)
    if args.backends:
        requested.extend(x.strip() for x in args.backends.split(",") if x.strip())
    if not requested:
        requested = [
            entry["id"]
            for entry in lock["backends"]
            if entry.get("enabled_by_default")
            and entry.get("license") in {"MIT", "Apache-2.0"}
        ]
    if args.include_support:
        requested.extend(["dinov2", "wonder3d", "triposf", "judge_v4"])

    ordered = []
    seen = set()
    for backend in requested:
        if backend not in meta:
            parser.error(f"unknown backend: {backend}")
        if backend not in seen:
            seen.add(backend)
            ordered.append(backend)

    gpu = gpu_inventory()
    probes = [
        backend_probe(
            meta[backend],
            args.model_root,
            env_meta.get(backend),
        )
        for backend in ordered
    ]

    report = {
        "engine": "HAYUYA GPU DOCTOR",
        "model_root": str(args.model_root.resolve()),
        "controller_python": sys.executable,
        "gpu": gpu,
        "requested_backends": ordered,
        "backends": probes,
        "ready_backends": [item["id"] for item in probes if item["ready"]],
        "not_ready_backends": [item["id"] for item in probes if not item["ready"]],
        "strict_ready": bool(gpu["available"] and all(item["ready"] for item in probes)),
    }

    payload = json.dumps(report, indent=2)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")

    if args.strict and not report["strict_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
