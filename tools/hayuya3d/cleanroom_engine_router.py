#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import traceback
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
HAYUYA3D = Path(__file__).resolve().parent

@dataclass
class Candidate:
    name: str
    ok: bool
    path: str | None
    faces: int | None
    vertices: int | None
    bytes: int
    score: float
    error: str | None
    meta: dict[str, Any]

def _load_mesh_stats(path: Path) -> tuple[int | None, int | None, dict[str, Any]]:
    try:
        from mesh_gate import inspect as inspect_mesh
        report = inspect_mesh(path, require_normals=False)
        return int(report.faces), int(report.vertices), {
            "watertight": getattr(report, "watertight", None),
            "components": getattr(report, "components", None),
        }
    except Exception as exc:
        return None, None, {"mesh_gate_error": f"{type(exc).__name__}: {exc}"}

def _score(path: Path, faces: int | None, vertices: int | None, meta: dict[str, Any]) -> float:
    # Provider-neutral structural score. Visual fidelity stays under Hayuya Judge.
    score = 0.0
    size = path.stat().st_size
    if size >= 1024:
        score += 10.0
    if faces:
        score += min(45.0, 10.0 + (faces / 2_000_000.0) * 35.0)
    if vertices:
        score += min(15.0, (vertices / 1_000_000.0) * 15.0)
    if meta.get("textured"):
        score += 15.0
    if meta.get("pbr"):
        score += 10.0
    if meta.get("multi_view"):
        score += 5.0
    return round(score, 4)

def _run_tripsg(image: Path, out: Path, token: str | None, seed: int) -> dict[str, Any]:
    mod = importlib.import_module("triposg_cloud")
    return mod.generate(image, out, token=token, seed=seed, apply_texture=True)

def _run_trellis2(image: Path, out: Path, token: str | None, seed: int) -> dict[str, Any]:
    mod = importlib.import_module("trellis2_cloud")
    return mod.generate(image, out, token=token, seed=seed, quality="ultra")

def _run_hunyuan(image: Path, out: Path, token: str | None, seed: int) -> dict[str, Any]:
    mod = importlib.import_module("hunyuan3d_cloud")
    return mod.generate_textured_material_donor(image, out, token=token, seed=seed)

def _run_sf3d(image: Path, out: Path, token: str | None, seed: int) -> dict[str, Any]:
    # Local official Stability-AI/stable-fast-3d checkout only.
    root = os.getenv("HAYUYA_SF3D_ROOT")
    if not root:
        raise RuntimeError("HAYUYA_SF3D_ROOT is not configured")
    rootp = Path(root).resolve()
    run_py = rootp / "run.py"
    if not run_py.is_file():
        raise FileNotFoundError(run_py)
    import subprocess, sys
    tmp = out.parent / "_sf3d"
    tmp.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(run_py), str(image.resolve()),
        "--output-dir", str(tmp.resolve()),
        "--texture-resolution", "4096",
        "--remesh_option", "Triangle",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    p = subprocess.run(cmd, cwd=rootp, env=env, text=True, capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError("SF3D failed: " + (p.stderr or p.stdout)[-3000:])
    glbs = sorted(tmp.rglob("*.glb"), key=lambda x: x.stat().st_mtime)
    if not glbs:
        raise RuntimeError("SF3D returned no GLB")
    out.write_bytes(glbs[-1].read_bytes())
    return {
        "generator": "Stability-AI/stable-fast-3d",
        "textured": True,
        "pbr": True,
        "multi_view": False,
        "seed": seed,
        "stdout_tail": p.stdout[-1000:],
    }

PROVIDERS: dict[str, Callable[[Path, Path, str | None, int], dict[str, Any]]] = {
    "triposg": _run_tripsg,
    "trellis2": _run_trellis2,
    "hunyuan": _run_hunyuan,
    "sf3d": _run_sf3d,
}

def run_candidate(name: str, image: Path, out_dir: Path, token: str | None, seed: int) -> Candidate:
    out = out_dir / f"{name}.glb"
    try:
        meta = PROVIDERS[name](image, out, token, seed) or {}
        if not out.is_file():
            candidate_path = Path(str(meta.get("path") or ""))
            if candidate_path.is_file():
                out.write_bytes(candidate_path.read_bytes())
        if not out.is_file():
            raise RuntimeError(f"{name} produced no file")
        blob = out.read_bytes()
        if len(blob) < 1024 or blob[:4] != b"glTF":
            raise RuntimeError(f"{name} invalid GLB magic/size")
        faces, vertices, audit = _load_mesh_stats(out)
        meta = {**meta, **audit}
        return Candidate(
            name=name,
            ok=True,
            path=str(out),
            faces=faces,
            vertices=vertices,
            bytes=len(blob),
            score=_score(out, faces, vertices, meta),
            error=None,
            meta=meta,
        )
    except Exception as exc:
        return Candidate(
            name=name,
            ok=False,
            path=None,
            faces=None,
            vertices=None,
            bytes=0,
            score=0.0,
            error=f"{type(exc).__name__}: {exc}",
            meta={"traceback": traceback.format_exc(limit=8)},
        )

def main() -> int:
    parser = argparse.ArgumentParser(description="HAYUYA clean-room image-to-3D tournament router")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--providers", default="triposg,trellis2,hunyuan,sf3d")
    parser.add_argument("--seed", type=int, default=1993)
    parser.add_argument("--hf-token", default=os.getenv("HF_TOKEN"))
    parser.add_argument("--winner", default="winner.glb")
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"missing input: {args.input}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(HAYUYA3D)
    if str(HAYUYA3D) not in os.sys.path:
        os.sys.path.insert(0, str(HAYUYA3D))

    requested = [x.strip() for x in args.providers.split(",") if x.strip()]
    unknown = [x for x in requested if x not in PROVIDERS]
    if unknown:
        parser.error(f"unknown providers: {unknown}")

    results = [run_candidate(p, args.input, args.output_dir, args.hf_token, args.seed) for p in requested]
    passing = [r for r in results if r.ok]
    passing.sort(key=lambda r: (r.score, r.faces or 0, r.bytes), reverse=True)

    manifest = {
        "schema": 1,
        "method": "hayuya-cleanroom-blackbox-tournament-v1",
        "input": str(args.input),
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "providers": requested,
        "results": [asdict(r) for r in results],
        "winner": asdict(passing[0]) if passing else None,
        "note": (
            "Provider ranking is structural only. Final promotion still requires "
            "HAYUYA visual Judge / source-fidelity / material / rig acceptance."
        ),
    }

    (args.output_dir / "cleanroom_tournament.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    if not passing:
        print("HAYUYA_CLEANROOM_NO_WINNER", json.dumps(manifest, separators=(",", ":")))
        return 2

    winner_src = Path(passing[0].path or "")
    winner_dst = args.output_dir / args.winner
    winner_dst.write_bytes(winner_src.read_bytes())
    print(
        "HAYUYA_CLEANROOM_WINNER",
        json.dumps(
            {
                "provider": passing[0].name,
                "score": passing[0].score,
                "faces": passing[0].faces,
                "bytes": passing[0].bytes,
                "path": str(winner_dst),
            },
            separators=(",", ":"),
        ),
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
