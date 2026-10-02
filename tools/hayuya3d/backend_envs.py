#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCK = HERE / "backend_envs.lock.json"
DEFAULT_MODEL_ROOT = ROOT / ".hayuya" / "models"
DEFAULT_ENV_ROOT = ROOT / ".hayuya" / "envs"


@dataclass
class EnvPlan:
    backend: str
    prefix: str
    python: str
    wrapper: str
    env_key: str
    python_version: str
    torch_version: str
    cuda_family: str
    strategy: str
    commands: list[list[str]]
    cuda_home_hint: str | None


def load_lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def env_key(backend: str) -> str:
    return f"HAYUYA_{backend.upper().replace('-', '_')}_PYTHON"


def find_manager() -> str | None:
    configured = os.environ.get("HAYUYA_CONDA")
    if configured:
        resolved = shutil.which(configured) or (
            configured if Path(configured).is_file() else None
        )
        if resolved:
            return str(resolved)
    for name in ("micromamba", "mamba", "conda"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def torch_install_command(python: Path, spec: dict) -> list[str]:
    packages = [f"torch=={spec['version']}"]
    if spec.get("torchvision"):
        packages.append(f"torchvision=={spec['torchvision']}")
    if spec.get("torchaudio"):
        packages.append(f"torchaudio=={spec['torchaudio']}")
    return [
        str(python),
        "-m",
        "pip",
        "install",
        *packages,
        "--index-url",
        spec["index_url"],
    ]


def build_install_plan(
    backend: str,
    spec: dict,
    *,
    manager: str,
    env_root: Path,
    model_root: Path,
) -> EnvPlan:
    prefix = (env_root / backend).resolve()
    python = prefix / "bin" / "python"
    wrapper = prefix / "hayuya-python"
    repo = (model_root / backend).resolve()

    commands: list[list[str]] = [
        [
            manager,
            "create",
            "-y",
            "-p",
            str(prefix),
            f"python={spec['python']}",
            "pip",
        ],
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "setuptools",
            "wheel",
        ],
    ]

    if not spec.get("requirements_include_torch", False):
        commands.append(torch_install_command(python, spec["torch"]))

    for package in spec.get("pre_pip", []):
        commands.append([str(python), "-m", "pip", "install", package])

    strategy = spec["strategy"]
    if strategy == "pip_requirements":
        requirements = repo / spec["requirements"]
        commands.append(
            [str(python), "-m", "pip", "install", "-r", str(requirements)]
        )
    elif strategy == "minimal_pip":
        packages = list(spec.get("pip", []))
        if packages:
            commands.append(
                [str(python), "-m", "pip", "install", *packages]
            )
    elif strategy == "upstream_setup":
        flags = " ".join(
            shlex.quote(str(flag))
            for flag in spec.get("setup_flags", [])
        )
        shell = f"source ./setup.sh {flags}"
        commands.append(
            [
                manager,
                "run",
                "-p",
                str(prefix),
                "bash",
                "-lc",
                shell,
            ]
        )
    else:
        raise ValueError(f"unknown environment strategy: {strategy}")

    commands.append(
        [
            str(python),
            "-c",
            (
                "import json, torch; "
                "print(json.dumps({'torch': torch.__version__, "
                "'cuda': torch.version.cuda, "
                "'cuda_available': bool(torch.cuda.is_available())}))"
            ),
        ]
    )

    return EnvPlan(
        backend=backend,
        prefix=str(prefix),
        python=str(python),
        wrapper=str(wrapper),
        env_key=env_key(backend),
        python_version=str(spec["python"]),
        torch_version=str(spec["torch"]["version"]),
        cuda_family=str(spec["torch"]["cuda_family"]),
        strategy=strategy,
        commands=commands,
        cuda_home_hint=spec.get("cuda_home_hint"),
    )


def wrapper_text(plan: EnvPlan) -> str:
    lines = ["#!/usr/bin/env bash", "set -e"]
    if plan.cuda_home_hint:
        lines.extend([
            f"export CUDA_HOME={shlex.quote(plan.cuda_home_hint)}",
            'export PATH="$CUDA_HOME/bin:$PATH"',
        ])
    lines.append(f"exec {shlex.quote(plan.python)} \"$@\"" )
    return "\n".join(lines) + "\n"


def write_wrapper(plan: EnvPlan) -> Path:
    path = Path(plan.wrapper)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(wrapper_text(plan), encoding="utf-8")
    path.chmod(0o755)
    return path


def write_exports(plans: list[EnvPlan], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Generated by HAYUYA backend_envs.py",
        "# Source this file before running gpu_doctor.py or hayuya.py.",
    ]
    for plan in plans:
        lines.append(
            f"export {plan.env_key}={shlex.quote(plan.wrapper)}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_command(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(shlex.quote(x) for x in command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def execute_plan(
    plan: EnvPlan,
    spec: dict,
    *,
    manager: str,
    model_root: Path,
    force: bool,
) -> None:
    prefix = Path(plan.prefix)
    python = Path(plan.python)
    repo = model_root / plan.backend
    source_required = bool(spec.get("source_required", True))
    if source_required and not repo.is_dir():
        raise FileNotFoundError(
            f"backend source not bootstrapped: {repo}"
        )

    if force and prefix.exists():
        print(f"HAYUYA_ENV_REMOVE {plan.backend} {prefix}", flush=True)
        shutil.rmtree(prefix)

    commands = list(plan.commands)
    if python.is_file() and not force:
        # Reuse an existing prefix but still run install/repair and validation.
        commands = commands[1:]

    for command in commands:
        cwd = repo if (
            spec["strategy"] == "upstream_setup"
            and "setup.sh" in " ".join(command)
        ) else None
        run_command(command, cwd=cwd)

    wrapper = write_wrapper(plan)
    print(
        f"HAYUYA_ENV_READY {plan.backend} python={wrapper} "
        f"torch={plan.torch_version} cuda={plan.cuda_family}",
        flush=True,
    )


def select_backends(
    lock: dict,
    *,
    repeated: list[str],
    csv: str | None,
    include_support: bool,
) -> list[str]:
    available = lock["backends"]
    selected = list(repeated)
    if csv:
        selected.extend(x.strip() for x in csv.split(",") if x.strip())
    if include_support:
        selected.extend(["dinov2", "wonder3d", "triposf", "judge_v4"])

    if not selected:
        selected = list(available)

    out: list[str] = []
    seen: set[str] = set()
    for backend in selected:
        if backend not in available:
            raise ValueError(f"no environment spec for backend: {backend}")
        if backend not in seen:
            seen.add(backend)
            out.append(backend)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or build isolated HAYUYA backend Python/CUDA environments."
    )
    parser.add_argument("--backend", action="append", default=[])
    parser.add_argument("--backends", help="comma-separated backend ids")
    parser.add_argument("--include-support", action="store_true")
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--env-root", type=Path, default=DEFAULT_ENV_ROOT)
    parser.add_argument("--manager", help="conda/mamba/micromamba executable")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--exports",
        type=Path,
        default=DEFAULT_ENV_ROOT / "hayuya_env.sh",
    )
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    lock = load_lock()
    try:
        selected = select_backends(
            lock,
            repeated=args.backend,
            csv=args.backends,
            include_support=args.include_support,
        )
    except ValueError as exc:
        parser.error(str(exc))

    manager = args.manager or find_manager()
    if manager is None:
        if args.execute:
            raise SystemExit(
                "No conda/mamba/micromamba found. Set HAYUYA_CONDA or install one."
            )
        manager = "conda"

    plans = [
        build_install_plan(
            backend,
            lock["backends"][backend],
            manager=manager,
            env_root=args.env_root,
            model_root=args.model_root,
        )
        for backend in selected
    ]

    payload = {
        "schema_version": lock["schema_version"],
        "manager": manager,
        "model_root": str(args.model_root.resolve()),
        "env_root": str(args.env_root.resolve()),
        "backends": [asdict(plan) for plan in plans],
    }
    print(json.dumps(payload, indent=2))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.execute:
        for plan in plans:
            execute_plan(
                plan,
                lock["backends"][plan.backend],
                manager=manager,
                model_root=args.model_root,
                force=args.force,
            )
        export_path = write_exports(plans, args.exports)
        print(f"HAYUYA_ENV_EXPORTS_READY {export_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
