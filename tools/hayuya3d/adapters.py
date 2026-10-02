#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_MODEL_ROOT = ROOT / ".hayuya" / "models"


@dataclass
class Candidate:
    backend: str
    model_path: Path
    preview_path: Path | None = None
    notes: str = ""


def backend_python(backend: str) -> str:
    key = f"HAYUYA_{backend.upper().replace('-', '_')}_PYTHON"
    return os.environ.get(key, sys.executable)


def run_checked(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def require_backend(backend: str, model_root: Path) -> Path:
    path = model_root / backend
    if not path.exists():
        raise FileNotFoundError(
            f"Hayuya backend '{backend}' is not bootstrapped at {path}. "
            f"Run: python tools/hayuya3d/bootstrap.py --backend {backend}"
        )
    return path


def generate_triposg(
    image: Path,
    out_dir: Path,
    *,
    faces: int,
    seed: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> Candidate:
    repo = require_backend("triposg", model_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "triposg.glb"
    cmd = [
        backend_python("triposg"),
        "-m",
        "scripts.inference_triposg",
        "--image-input",
        str(image.resolve()),
        "--output-path",
        str(model_path.resolve()),
        "--seed",
        str(seed),
        "--num-inference-steps",
        "50",
        "--guidance-scale",
        "7.0",
        "--faces",
        str(faces),
    ]
    run_checked(cmd, cwd=repo)
    if not model_path.is_file():
        raise RuntimeError(f"TripoSG did not create {model_path}")
    return Candidate("triposg", model_path, notes="Rectified-flow high fidelity shape candidate")


def generate_triposr(
    image: Path,
    out_dir: Path,
    *,
    texture_size: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> Candidate:
    repo = require_backend("triposr", model_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        backend_python("triposr"),
        "run.py",
        str(image.resolve()),
        "--output-dir",
        str(out_dir.resolve()),
        "--model-save-format",
        "glb",
        "--bake-texture",
        "--texture-resolution",
        str(texture_size),
        "--render",
    ]
    run_checked(cmd, cwd=repo)
    model_path = out_dir / "0" / "mesh.glb"
    preview_path = out_dir / "0" / "render_000.png"
    if not model_path.is_file():
        raise RuntimeError(f"TripoSR did not create {model_path}")
    return Candidate(
        "triposr",
        model_path,
        preview_path if preview_path.is_file() else None,
        "Fast LRM sanity/baseline candidate",
    )


def generate_instantmesh(
    image: Path,
    out_dir: Path,
    *,
    seed: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> Candidate:
    repo = require_backend("instantmesh", model_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        backend_python("instantmesh"),
        "run.py",
        "configs/instant-mesh-large.yaml",
        str(image.resolve()),
        "--output_path",
        str(out_dir.resolve()),
        "--diffusion_steps",
        "75",
        "--seed",
        str(seed),
        "--view",
        "6",
        "--export_texmap",
        "--save_video",
    ]
    run_checked(cmd, cwd=repo)

    stem = image.stem
    model_path = out_dir / "instant-mesh-large" / "meshes" / f"{stem}.obj"
    preview_path = out_dir / "instant-mesh-large" / "videos" / f"{stem}.mp4"
    if not model_path.is_file():
        raise RuntimeError(f"InstantMesh did not create {model_path}")
    return Candidate(
        "instantmesh",
        model_path,
        preview_path if preview_path.is_file() else None,
        "Zero123++ six-view + LRM/FlexiCubes candidate",
    )


def generate_trellis2(
    image: Path,
    out_dir: Path,
    *,
    seed: int,
    resolution: int,
    faces: int,
    texture_size: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> Candidate:
    repo = require_backend("trellis2", model_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "trellis2.glb"
    cmd = [
        backend_python("trellis2"),
        str((HERE / "trellis2_adapter.py").resolve()),
        "--backend-root",
        str(repo.resolve()),
        "--input",
        str(image.resolve()),
        "--output",
        str(model_path.resolve()),
        "--seed",
        str(seed),
        "--resolution",
        str(resolution),
        "--faces",
        str(max(faces, 100_000)),
        "--texture-size",
        str(texture_size),
    ]
    run_checked(cmd, cwd=repo)
    if not model_path.is_file():
        raise RuntimeError(f"TRELLIS.2 did not create {model_path}")
    return Candidate("trellis2", model_path, notes="O-Voxel full-PBR ultra candidate")


def generate_trellis(
    images: list[Path],
    out_dir: Path,
    *,
    seed: int,
    texture_size: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> Candidate:
    repo = require_backend("trellis", model_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "trellis_multiview.glb"
    cmd = [
        backend_python("trellis"),
        str((HERE / "trellis_adapter.py").resolve()),
        "--backend-root",
        str(repo.resolve()),
        "--output",
        str(model_path.resolve()),
        "--seed",
        str(seed),
        "--texture-size",
        str(min(texture_size, 2048)),
        "--multiimage-mode",
        "multidiffusion",
    ]
    for image in images:
        cmd.extend(["--input", str(image.resolve())])
    run_checked(cmd, cwd=repo)
    if not model_path.is_file():
        raise RuntimeError(f"TRELLIS did not create {model_path}")
    return Candidate(
        "trellis",
        model_path,
        notes=f"TRELLIS native multi-image fusion candidate ({len(images)} source views)",
    )


def generate_spar3d(
    image: Path,
    out_dir: Path,
    *,
    texture_size: int,
    faces: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> Candidate:
    repo = require_backend("spar3d", model_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        backend_python("spar3d"),
        "run.py",
        str(image.resolve()),
        "--output-dir",
        str(out_dir.resolve()),
        "--texture-resolution",
        str(min(texture_size, 2048)),
        "--low-vram-mode",
    ]
    # SPAR3D exposes remeshing only when optional remesh dependencies are installed,
    # so keep the core path dependency-light and let Hayuya's later GamePrep stage
    # handle target face budgets.
    run_checked(cmd, cwd=repo)
    model_path = out_dir / "0" / "mesh.glb"
    if not model_path.is_file():
        raise RuntimeError(f"SPAR3D did not create {model_path}")
    return Candidate(
        "spar3d",
        model_path,
        notes="Point-cloud-conditioned backside-aware single-image candidate",
    )


PSHUMAN_REQUIRED_ASSETS = (
    "smpl_related/smpl_data/smplx_faces.npy",
    "smpl_related/smpl_data/smplx_verts.npy",
    "smpl_related/smpl_data/smpl_verts.npy",
    "smpl_related/smpl_data/smpl_faces.npy",
    "smpl_related/smpl_data/smplx_to_smpl.pkl",
    "smpl_related/HPS/pixie_data/pixie_model.tar",
    "smpl_related/HPS/pixie_data/SMPLX_NEUTRAL_2020.npz",
)


def pshuman_readiness(model_root: Path = DEFAULT_MODEL_ROOT) -> tuple[bool, list[str]]:
    repo = model_root / "pshuman"
    missing: list[str] = []
    if not repo.is_dir():
        return False, [f"backend repo missing: {repo}"]
    for rel in PSHUMAN_REQUIRED_ASSETS:
        if not (repo / rel).is_file():
            missing.append(rel)
    # PIXIE and SMPLX reconstruction also need the model directory supplied by
    # the PSHuman/ECON auxiliary bundle.
    if not (repo / "smpl_related" / "models").is_dir():
        missing.append("smpl_related/models/")
    return not missing, missing


def generate_pshuman(
    image: Path,
    out_dir: Path,
    *,
    seed: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> Candidate:
    repo = require_backend("pshuman", model_root)
    ready, missing = pshuman_readiness(model_root)
    if not ready:
        raise RuntimeError(
            "PSHuman auxiliary human-model assets are incomplete; missing: "
            + ", ".join(missing)
        )

    from viewforge import _native_foreground_rgba

    out_dir.mkdir(parents=True, exist_ok=True)
    input_dir = out_dir / "input"
    result_dir = out_dir / "results"
    mv_dir = out_dir / "multiview"
    input_dir.mkdir(parents=True, exist_ok=True)

    staged = input_dir / "source.png"
    _native_foreground_rgba(image).save(staged, format="PNG")

    cmd = [
        backend_python("pshuman"),
        "inference.py",
        "--config",
        "configs/inference-768-6view.yaml",
        "pretrained_model_name_or_path=pengHTYX/PSHuman_Unclip_768_6views",
        "validation_dataset.crop_size=740",
        "with_smpl=false",
        f"validation_dataset.root_dir={input_dir.resolve()}",
        f"save_dir={mv_dir.resolve()}",
        f"recon_opt.res_path={result_dir.resolve()}",
        f"seed={seed}",
        "num_views=7",
        "save_mode=rgb",
    ]
    run_checked(cmd, cwd=repo)

    case_dir = result_dir / "source"
    model_path = case_dir / "result_clr_scale4_source.obj"
    preview_path = case_dir / "result_clr_scale4_source.mp4"
    if not model_path.is_file():
        # Keep this deterministic but tolerate upstream scale changes.
        matches = sorted(case_dir.glob("result_clr_scale*_source.obj"))
        if len(matches) == 1:
            model_path = matches[0]
        else:
            raise RuntimeError(
                f"PSHuman did not create expected textured mesh under {case_dir}"
            )

    return Candidate(
        "pshuman",
        model_path,
        preview_path if preview_path.is_file() else None,
        "40GB+ human-specialist challenger; SMPL-free multiview model with gated PIXIE/SMPLX reconstruction assets",
    )


def refine_triposf(
    mesh_path: Path,
    out_dir: Path,
    *,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> Candidate:
    repo = require_backend("triposf", model_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    config = repo / "configs" / "TripoSFVAE_1024.yaml"
    cmd = [
        backend_python("triposf"),
        "inference.py",
        "--mesh-path",
        str(mesh_path.resolve()),
        "--output-dir",
        str(out_dir.resolve()),
        "--config",
        str(config.resolve()),
    ]
    run_checked(cmd, cwd=repo)
    reconstructed = out_dir / f"{mesh_path.stem}_reconstruction.obj"
    if not reconstructed.is_file():
        raise RuntimeError(f"TripoSF did not create {reconstructed}")
    return Candidate(
        "triposf_refine",
        reconstructed,
        notes="SparseFlex 1024^3 geometry refinement challenger; materials require later bridge",
    )


REFINERS = {
    "triposf": refine_triposf,
}


GENERATORS = {
    "triposg": generate_triposg,
    "triposr": generate_triposr,
    "instantmesh": generate_instantmesh,
    "trellis2": generate_trellis2,
    "trellis": generate_trellis,
    "spar3d": generate_spar3d,
    "pshuman": generate_pshuman,
}
