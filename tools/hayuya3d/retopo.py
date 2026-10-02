#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from material_bridge import _scene_meshes, transfer_best_material

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_MODEL_ROOT = ROOT / ".hayuya" / "models"


@dataclass
class RetopoResult:
    backend: str
    source_mesh: str
    retopo_obj: str
    bridged_glb: str
    target_triangle_faces: int
    target_native_faces: int
    polygon_count: int
    quad_count: int
    triangle_count: int
    ngon_count: int
    quad_fraction: float
    runtime_triangle_equivalent: int
    triangle_target_error_fraction: float
    style: str
    deterministic: bool
    material_method: str
    material_channels: list[str]
    material_dropped_channels: list[str]
    material_rebake_required: list[str]
    material_fallback: bool
    manifest_path: str


def instant_meshes_binary(model_root: Path = DEFAULT_MODEL_ROOT) -> Path | None:
    configured = os.environ.get("HAYUYA_INSTANT_MESHES_BIN")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return path.resolve()
        resolved = shutil.which(configured)
        if resolved:
            return Path(resolved).resolve()

    repo = model_root / "instant_meshes_retopo"
    candidates = [
        repo / "build-hayuya" / "Instant Meshes",
        repo / "build-hayuya" / "Instant Meshes.exe",
        repo / "build" / "Instant Meshes",
        repo / "build" / "Instant Meshes.exe",
        repo / "Instant Meshes",
        repo / "Instant Meshes.exe",
        repo / "InstantMeshes",
        repo / "InstantMeshes.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def retopo_readiness(model_root: Path = DEFAULT_MODEL_ROOT) -> tuple[bool, list[str]]:
    missing: list[str] = []
    repo = model_root / "instant_meshes_retopo"
    if not repo.is_dir():
        missing.append(f"backend repo missing: {repo}")
    binary = instant_meshes_binary(model_root)
    if binary is None:
        missing.append(
            "Instant Meshes binary missing; set HAYUYA_INSTANT_MESHES_BIN "
            "or build .hayuya/models/instant_meshes_retopo"
        )
    return not missing, missing


def build_instant_meshes(
    model_root: Path = DEFAULT_MODEL_ROOT,
    *,
    jobs: int | None = None,
) -> Path:
    repo = model_root / "instant_meshes_retopo"
    if not repo.is_dir():
        raise FileNotFoundError(
            f"Instant Meshes source missing: {repo}. "
            "Run: python tools/hayuya3d/bootstrap.py --backend instant_meshes_retopo"
        )

    build = repo / "build-hayuya"
    build.mkdir(parents=True, exist_ok=True)

    cmake_cmd = [
        "cmake",
        "-S",
        str(repo),
        "-B",
        str(build),
        "-DCMAKE_BUILD_TYPE=Release",
    ]

    # The pinned upstream vendors an old Intel TBB which fails to compile with
    # modern GCC 13+ because -Wchanges-meaning is a default hard diagnostic.
    # Clang builds the same pinned source without altering third-party code.
    requested_cxx = os.environ.get("HAYUYA_INSTANT_MESHES_CXX")
    cxx = requested_cxx or shutil.which("clang++")
    cc = os.environ.get("HAYUYA_INSTANT_MESHES_CC")
    if cxx:
        cxx_path = shutil.which(cxx) or cxx
        cmake_cmd.append(f"-DCMAKE_CXX_COMPILER={cxx_path}")
        using_clang = Path(str(cxx_path)).name.startswith("clang++")
        if cc is None and using_clang:
            cc = shutil.which("clang")
        if cc:
            cc_path = shutil.which(cc) or cc
            cmake_cmd.append(f"-DCMAKE_C_COMPILER={cc_path}")

        # Pinned NanoGUI intentionally forces libc++ under Clang. Because it is a
        # CMake subdirectory, its linker flag does not reliably propagate back to
        # the parent Instant Meshes executable on modern Linux. Force the same C++
        # standard library at the top level so static NanoGUI/TBB objects and the
        # final executable use one ABI (std::__1) consistently.
        if using_clang:
            cmake_cmd.extend([
                "-DCMAKE_CXX_FLAGS=-stdlib=libc++",
                "-DCMAKE_EXE_LINKER_FLAGS=-stdlib=libc++",
            ])

    subprocess.run(cmake_cmd, check=True)
    cmd = ["cmake", "--build", str(build), "--config", "Release"]
    if jobs:
        cmd.extend(["--parallel", str(jobs)])
    else:
        cmd.append("--parallel")
    subprocess.run(cmd, check=True)

    binary = instant_meshes_binary(model_root)
    if binary is None:
        raise RuntimeError("Instant Meshes build completed but binary was not found")
    return binary


def _geometry_only_obj(source_mesh: Path, output: Path) -> Path:
    import trimesh

    # _scene_meshes applies glTF scene-node transforms before returning copies.
    # Retopology must operate in the same world/object space used by Material Bridge.
    meshes = _scene_meshes(source_mesh)
    geometry_only = [
        trimesh.Trimesh(
            vertices=mesh.vertices.copy(),
            faces=mesh.faces.copy(),
            process=False,
        )
        for mesh in meshes
    ]
    merged = trimesh.util.concatenate(geometry_only)
    output.parent.mkdir(parents=True, exist_ok=True)
    merged.export(output)
    return output


def parse_obj_topology(path: Path) -> dict[str, int | float]:
    polygons = 0
    quads = 0
    triangles = 0
    ngons = 0
    runtime_triangles = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            stripped = raw.lstrip()
            if not stripped.startswith("f "):
                continue
            count = len(stripped.split()) - 1
            if count < 3:
                continue
            polygons += 1
            runtime_triangles += max(1, count - 2)
            if count == 4:
                quads += 1
            elif count == 3:
                triangles += 1
            else:
                ngons += 1
    return {
        "polygon_count": polygons,
        "quad_count": quads,
        "triangle_count": triangles,
        "ngon_count": ngons,
        "quad_fraction": float(quads / polygons) if polygons else 0.0,
        "runtime_triangle_equivalent": runtime_triangles,
    }


def retopo_target_native_faces(target_triangle_faces: int, style: str) -> int:
    target_triangle_faces = max(200, int(target_triangle_faces))
    # Pure/mostly quad OBJ faces triangulate to roughly two runtime triangles.
    if style in {"pure_quad", "quad_dominant"}:
        return max(100, target_triangle_faces // 2)
    raise ValueError(f"unknown retopo style: {style}")


def build_instant_meshes_command(
    binary: Path,
    source_obj: Path,
    output_obj: Path,
    *,
    target_triangle_faces: int,
    style: str,
    crease_angle: float,
    smooth_iterations: int = 2,
) -> list[str]:
    native_faces = retopo_target_native_faces(target_triangle_faces, style)
    cmd = [
        str(binary),
        "--output",
        str(output_obj),
        "--faces",
        str(native_faces),
        "--deterministic",
        "--boundaries",
        "--crease",
        str(float(crease_angle)),
        "--smooth",
        str(int(smooth_iterations)),
    ]
    if style == "quad_dominant":
        cmd.append("--dominant")
    cmd.append(str(source_obj))
    return cmd


def run_retopology(
    source_mesh: Path,
    out_dir: Path,
    *,
    target_triangle_faces: int,
    style: str,
    texture_size: int,
    crease_angle: float | None = None,
    model_root: Path = DEFAULT_MODEL_ROOT,
) -> RetopoResult:
    binary = instant_meshes_binary(model_root)
    if binary is None:
        raise RuntimeError(
            "Instant Meshes binary unavailable. Set HAYUYA_INSTANT_MESHES_BIN "
            "or build the optional backend."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    source_obj = _geometry_only_obj(source_mesh, out_dir / "source_geometry.obj")
    retopo_obj = out_dir / "retopo_master.obj"

    if crease_angle is None:
        crease_angle = 55.0 if style == "pure_quad" else 70.0

    cmd = build_instant_meshes_command(
        binary,
        source_obj,
        retopo_obj,
        target_triangle_faces=target_triangle_faces,
        style=style,
        crease_angle=crease_angle,
    )
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    if not retopo_obj.is_file() or retopo_obj.stat().st_size < 128:
        raise RuntimeError("Instant Meshes did not produce a usable OBJ")

    topo = parse_obj_topology(retopo_obj)
    if topo["polygon_count"] <= 0:
        raise RuntimeError("Instant Meshes OBJ has no polygon faces")
    if style == "pure_quad" and topo["quad_fraction"] < 0.85:
        raise RuntimeError(
            f"pure-quad retopo produced only {topo['quad_fraction']:.3f} quad fraction"
        )

    runtime_triangles = int(topo["runtime_triangle_equivalent"])
    triangle_target_error = abs(runtime_triangles - int(target_triangle_faces)) / max(
        1,
        int(target_triangle_faces),
    )

    bridged_glb = out_dir / "retopo_material_bridge.glb"
    bridge = transfer_best_material(
        source_mesh,
        retopo_obj,
        bridged_glb,
        total_samples=180_000,
        max_texture_size=texture_size,
    )

    manifest_path = out_dir / "retopo_manifest.json"
    result = RetopoResult(
        backend="instant_meshes_retopo",
        source_mesh=str(source_mesh),
        retopo_obj=str(retopo_obj),
        bridged_glb=str(bridged_glb),
        target_triangle_faces=int(target_triangle_faces),
        target_native_faces=retopo_target_native_faces(target_triangle_faces, style),
        polygon_count=int(topo["polygon_count"]),
        quad_count=int(topo["quad_count"]),
        triangle_count=int(topo["triangle_count"]),
        ngon_count=int(topo["ngon_count"]),
        quad_fraction=round(float(topo["quad_fraction"]), 6),
        runtime_triangle_equivalent=runtime_triangles,
        triangle_target_error_fraction=round(float(triangle_target_error), 6),
        style=style,
        deterministic=True,
        material_method=bridge.method,
        material_channels=list(bridge.channels or []),
        material_dropped_channels=list(bridge.dropped_channels or []),
        material_rebake_required=list(bridge.rebake_required or []),
        material_fallback=bridge.fallback_used,
        manifest_path=str(manifest_path),
    )
    manifest_path.write_text(
        json.dumps(asdict(result), indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="HAYUYA Instant Meshes retopology challenger.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--target-faces", type=int)
    parser.add_argument("--texture-size", type=int, default=2048)
    parser.add_argument("--style", choices=["pure_quad", "quad_dominant"], default="quad_dominant")
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()

    if args.build:
        binary = build_instant_meshes(args.model_root)
        print(f"HAYUYA_RETOPO_BINARY_READY {binary}")
        return 0

    if args.input is None or args.output is None or args.target_faces is None:
        parser.error("--input, --output and --target-faces are required unless --build is used")

    result = run_retopology(
        args.input,
        args.output,
        target_triangle_faces=args.target_faces,
        style=args.style,
        texture_size=args.texture_size,
        model_root=args.model_root,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
