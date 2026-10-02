#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from adapters import DEFAULT_MODEL_ROOT, GENERATORS
from native_geometry_guard import assert_native_candidate
from native_360_geometry_gate import assert_native_volumetric


HEAD_DONOR_PRIORITY = ("trellis2", "triposg", "spar3d", "triposr")


@dataclass
class SourceFaceRepairResult:
    attempted: bool
    ready: bool
    source_detail: str
    base_mesh: str
    backend: str | None
    staged_source: str | None
    donor_mesh: str | None
    candidate_mesh: str | None
    fusion: dict | None
    error: str | None = None
    backend_attempts: list[dict] | None = None
    method: str = "hayuya-source-derived-native-face-repair-v1"


def available_head_donor_backends(
    selected_backends: list[str] | tuple[str, ...],
    model_root: Path,
) -> list[str]:
    """Return usable donor generators in deterministic capability order."""
    selected = {str(x) for x in selected_backends}
    root = Path(model_root)
    return [
        backend
        for backend in HEAD_DONOR_PRIORITY
        if (
            backend in selected
            and backend in GENERATORS
            and (root / backend).is_dir()
        )
    ]


def select_head_donor_backend(
    selected_backends: list[str] | tuple[str, ...],
    model_root: Path,
) -> str | None:
    """Compatibility helper returning the first usable donor backend."""
    available = available_head_donor_backends(
        selected_backends,
        model_root,
    )
    return available[0] if available else None


def _stage_source(
    detail_image: Path,
    output: Path,
    *,
    derive_head_from_full_source: bool = False,
) -> Path:
    """Stage current-source head evidence without inventing identity pixels."""
    output.parent.mkdir(parents=True, exist_ok=True)

    if derive_head_from_full_source:
        from source_autofix import _foreground_head_zoom

        recovered = _foreground_head_zoom(Path(detail_image), output)
        if recovered is None or not output.is_file():
            raise RuntimeError(
                "could not derive grounded head evidence from the current "
                "full-body source"
            )
        return output

    try:
        from viewforge import _native_foreground_rgba

        image = _native_foreground_rgba(Path(detail_image))
    except Exception:
        from PIL import Image

        image = Image.open(detail_image).convert("RGBA")
    image.save(output, format="PNG")
    return output


def generate_source_head_donor(
    detail_image: Path,
    out_dir: Path,
    *,
    backend: str,
    seed: int,
    hero_faces: int,
    trellis2_resolution: int,
    texture_size: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
    generator_override: Callable | None = None,
    derive_head_from_full_source: bool = False,
) -> Path:
    """Generate real native 3D from the current source's head evidence.

    The donor is never a billboard/front projection. It is an ordinary native
    image-to-3D result and is rejected if provenance says otherwise.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    staged = _stage_source(
        Path(detail_image),
        out_dir / "source_head_rgba.png",
        derive_head_from_full_source=bool(derive_head_from_full_source),
    )

    if generator_override is not None:
        candidate = generator_override(
            backend=backend,
            image=staged,
            out_dir=out_dir / "generator",
            seed=int(seed),
            hero_faces=int(hero_faces),
            trellis2_resolution=int(trellis2_resolution),
            texture_size=int(texture_size),
            model_root=Path(model_root),
        )
    elif backend == "trellis2":
        candidate = GENERATORS[backend](
            staged,
            out_dir / "generator",
            seed=int(seed),
            resolution=int(trellis2_resolution),
            faces=max(100_000, int(hero_faces)),
            texture_size=int(texture_size),
            model_root=Path(model_root),
        )
    elif backend == "triposg":
        candidate = GENERATORS[backend](
            staged,
            out_dir / "generator",
            faces=max(100_000, int(hero_faces)),
            seed=int(seed),
            model_root=Path(model_root),
        )
    elif backend == "spar3d":
        candidate = GENERATORS[backend](
            staged,
            out_dir / "generator",
            texture_size=int(texture_size),
            faces=max(100_000, int(hero_faces)),
            model_root=Path(model_root),
        )
    elif backend == "triposr":
        candidate = GENERATORS[backend](
            staged,
            out_dir / "generator",
            texture_size=int(texture_size),
            model_root=Path(model_root),
        )
    else:
        raise ValueError(f"unsupported source head donor backend: {backend}")

    donor = Path(candidate.model_path)
    if not donor.is_file():
        raise RuntimeError(f"source head donor did not create a mesh: {donor}")
    assert_native_candidate(donor, label=f"source_head_donor:{backend}")
    assert_native_volumetric(donor, label=f"source_head_donor:{backend}")
    return donor


def prepare_source_face_repair_challenger(
    base_mesh: Path,
    detail_image: Path,
    out_dir: Path,
    *,
    selected_backends: list[str] | tuple[str, ...],
    seed: int,
    hero_faces: int,
    trellis2_resolution: int,
    texture_size: int,
    model_root: Path = DEFAULT_MODEL_ROOT,
    up_axis: str | int | None = None,
    require_rebake: bool = True,
    generator_override: Callable | None = None,
    derive_head_from_full_source: bool = False,
) -> SourceFaceRepairResult:
    """Create a judged face-repair challenger from the current source image.

    This is the reusable version of the successful Monja workflow:
      source photo -> automatic head evidence -> native head donor -> seam-safe
      head wrap on the already-valid full 3D body.

    No Monja coordinates, silhouettes, landmarks, or cached masks are consumed.
    """


    base_mesh = Path(base_mesh)
    detail_image = Path(detail_image)
    out_dir = Path(out_dir)

    try:
        assert_native_candidate(base_mesh, label="source_face_repair_base")
        assert_native_volumetric(base_mesh, label="source_face_repair_base")
    except Exception as exc:
        return SourceFaceRepairResult(
            attempted=True,
            ready=False,
            source_detail=str(detail_image),
            base_mesh=str(base_mesh),
            backend=None,
            staged_source=None,
            donor_mesh=None,
            candidate_mesh=None,
            fusion=None,
            error=f"{type(exc).__name__}:{exc}",
            backend_attempts=[],
        )

    backends = available_head_donor_backends(
        list(selected_backends),
        Path(model_root),
    )
    if not backends:
        return SourceFaceRepairResult(
            attempted=False,
            ready=False,
            source_detail=str(detail_image),
            base_mesh=str(base_mesh),
            backend=None,
            staged_source=None,
            donor_mesh=None,
            candidate_mesh=None,
            fusion=None,
            error="no selected native head-donor backend is bootstrapped",
            backend_attempts=[],
        )

    from regional_fusion import prepare_head_wrap_challenger

    attempts: list[dict] = []
    last_donor: Path | None = None
    last_fusion: dict | None = None
    last_candidate: Path | None = None

    for index, backend in enumerate(backends):
        donor_dir = out_dir / f"donor_{index:02d}_{backend}"
        staged_source = donor_dir / "source_head_rgba.png"
        try:
            donor = generate_source_head_donor(
                detail_image,
                donor_dir,
                backend=backend,
                seed=int(seed) + index * 101,
                hero_faces=int(hero_faces),
                trellis2_resolution=int(trellis2_resolution),
                texture_size=int(texture_size),
                model_root=Path(model_root),
                generator_override=generator_override,
                derive_head_from_full_source=bool(
                    derive_head_from_full_source
                ),
            )
            last_donor = donor
        except Exception as exc:
            attempts.append(
                {
                    "backend": backend,
                    "stage": "native_head_donor",
                    "ready": False,
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )
            continue

        try:
            fusion = prepare_head_wrap_challenger(
                base_mesh,
                donor,
                out_dir / f"fusion_{index:02d}_{backend}",
                texture_size=int(texture_size),
                require_rebake=bool(require_rebake),
                up_axis=up_axis,
                donor_scope="head",
            )
            fusion_payload = asdict(fusion)
            last_fusion = fusion_payload
            candidate = fusion.output_glb or fusion.raw_output_glb
            last_candidate = Path(candidate) if candidate else None

            if not fusion.ready_for_judge or not candidate:
                attempts.append(
                    {
                        "backend": backend,
                        "stage": "head_wrap",
                        "ready": False,
                        "donor_mesh": str(donor),
                        "candidate_mesh": str(candidate) if candidate else None,
                        "error": (
                            fusion.error
                            or "source-derived head wrap is not Judge-eligible"
                        ),
                    }
                )
                continue

            candidate_path = Path(candidate)
            assert_native_candidate(
                candidate_path,
                label=f"source_face_repair_output:{backend}",
            )
            assert_native_volumetric(
                candidate_path,
                label=f"source_face_repair_output:{backend}",
            )

            attempts.append(
                {
                    "backend": backend,
                    "stage": "output_gate",
                    "ready": True,
                    "donor_mesh": str(donor),
                    "candidate_mesh": str(candidate_path),
                    "error": None,
                }
            )
            return SourceFaceRepairResult(
                attempted=True,
                ready=True,
                source_detail=str(detail_image),
                base_mesh=str(base_mesh),
                backend=backend,
                staged_source=str(staged_source),
                donor_mesh=str(donor),
                candidate_mesh=str(candidate_path),
                fusion=fusion_payload,
                error=None,
                backend_attempts=attempts,
            )
        except Exception as exc:
            attempts.append(
                {
                    "backend": backend,
                    "stage": "fusion_or_output_gate",
                    "ready": False,
                    "donor_mesh": str(donor),
                    "candidate_mesh": (
                        str(last_candidate)
                        if last_candidate is not None
                        else None
                    ),
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )
            continue

    errors = [
        f"{item['backend']}@{item['stage']}:{item.get('error')}"
        for item in attempts
        if not item.get("ready")
    ]
    return SourceFaceRepairResult(
        attempted=True,
        ready=False,
        source_detail=str(detail_image),
        base_mesh=str(base_mesh),
        backend=None,
        staged_source=None,
        donor_mesh=str(last_donor) if last_donor is not None else None,
        candidate_mesh=(
            str(last_candidate)
            if last_candidate is not None
            else None
        ),
        fusion=last_fusion,
        error=(
            "all selected native head-donor backends were rejected: "
            + " | ".join(errors)
        ),
        backend_attempts=attempts,
    )

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a generic source-derived native face-repair challenger."
    )
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--detail", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--backend", action="append", default=[])
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--seed", type=int, default=1993)
    parser.add_argument("--hero-faces", type=int, default=500000)
    parser.add_argument("--trellis2-resolution", type=int, default=1024)
    parser.add_argument("--texture-size", type=int, default=4096)
    parser.add_argument("--allow-unrebaked", action="store_true")
    args = parser.parse_args()

    result = prepare_source_face_repair_challenger(
        args.base,
        args.detail,
        args.output_dir,
        selected_backends=args.backend,
        seed=args.seed,
        hero_faces=args.hero_faces,
        trellis2_resolution=args.trellis2_resolution,
        texture_size=args.texture_size,
        model_root=args.model_root,
        require_rebake=not args.allow_unrebaked,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "source_face_repair.json").write_text(
        json.dumps(asdict(result), indent=2) + "\n",
        encoding="utf-8",
    )
    print("HAYUYA_SOURCE_FACE_REPAIR", json.dumps(asdict(result), separators=(",", ":")))
    return 0 if result.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
