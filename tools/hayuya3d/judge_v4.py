#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps


@dataclass(frozen=True)
class JudgeV4Thresholds:
    qrealign_full_mean_min: float = 0.55
    qrealign_full_p10_min: float = 0.45
    qrealign_face_mean_min: float = 0.55
    qrealign_face_p10_min: float = 0.42
    dreamsim_full_worst_max: float = 0.50
    dreamsim_face_worst_max: float = 0.45
    face_candidate_detection_fraction_min: float = 0.60
    face_profile_median_error_max: float = 0.22
    face_profile_p90_error_max: float = 0.35
    face_nose_ratio_min: float = 0.65
    face_nose_ratio_max: float = 1.40
    internvl_face_anatomy_min: float = 80.0
    internvl_face_source_fidelity_min: float = 75.0
    internvl_body_anatomy_min: float = 75.0
    internvl_hands_min: float = 65.0
    internvl_material_texture_min: float = 70.0
    internvl_multiview_consistency_min: float = 80.0
    internvl_source_fidelity_min: float = 75.0


@dataclass
class JudgeV4Report:
    schema: int
    method: str
    policy: str
    passed: bool
    hard_fail_reasons: list[str]
    advisories: list[str]
    thresholds: dict
    evidence: dict
    qrealign: dict | None
    face_landmarks: dict | None
    dreamsim: dict | None
    internvl: dict | None


def face_proportion_failures(
    face_landmarks: dict,
    thresholds: JudgeV4Thresholds,
) -> tuple[list[str], dict]:
    """Generic source-relative face proportion gate.

    The gate is derived from the current source face profile on every job.
    It contains no asset coordinates, Monja landmarks, or fixed target face.
    """
    if not face_landmarks.get("face_expected_from_source"):
        return [], {
            "enabled": False,
            "reason": "source face not established",
        }

    reference = dict(face_landmarks.get("reference_profile") or {})
    rows = list(face_landmarks.get("candidate") or [])
    if not rows:
        return ["face_proportion_candidate_missing"], {
            "enabled": True,
            "passed": False,
            "ratios": {},
        }

    features = dict(rows[0].get("features") or {})
    ratio_names = (
        "nose_to_chin",
        "nose_eye_center_offset",
    )
    lo = float(thresholds.face_nose_ratio_min)
    hi = float(thresholds.face_nose_ratio_max)
    failures = []
    ratios = {}

    for name in ratio_names:
        try:
            expected = float(reference.get(name))
            actual = float(features.get(name))
        except (TypeError, ValueError):
            expected = 0.0
            actual = 0.0

        if expected <= 1e-8 or actual <= 1e-8:
            ratios[name] = None
            failures.append(f"face_proportion_missing:{name}")
            continue

        ratio = actual / expected
        ratios[name] = round(float(ratio), 6)
        if not (lo <= ratio <= hi):
            failures.append(
                f"face_{name}_ratio:{ratio:.3f}_outside_{lo:.3f}_{hi:.3f}"
            )

    return failures, {
        "enabled": True,
        "passed": not failures,
        "source_relative": True,
        "ratios": ratios,
        "limits": {
            "min": lo,
            "max": hi,
        },
        "asset_specific_coordinates": False,
    }


def _load_rgb(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def _subject_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    h, w = rgb.shape[:2]
    patch = max(4, min(h, w) // 24)
    corners = np.concatenate(
        [
            rgb[:patch, :patch].reshape(-1, 3),
            rgb[:patch, -patch:].reshape(-1, 3),
            rgb[-patch:, :patch].reshape(-1, 3),
            rgb[-patch:, -patch:].reshape(-1, 3),
        ],
        axis=0,
    )
    bg = np.median(corners, axis=0)
    mask = np.linalg.norm(rgb - bg, axis=2) > 22.0
    ys, xs = np.where(mask)
    if len(xs) < max(64, int(h * w * 0.002)):
        return 0, 0, w, h
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return x0, y0, x1, y1


def _normalized_subject(path: Path, output: Path, size: int = 512) -> Path:
    image = _load_rgb(path)
    x0, y0, x1, y1 = _subject_bbox(image)
    crop = image.crop((x0, y0, x1, y1))
    output.parent.mkdir(parents=True, exist_ok=True)
    ImageOps.pad(
        crop,
        (size, size),
        method=Image.Resampling.LANCZOS,
        color=(24, 24, 24),
    ).save(output)
    return output


def _face_crop(path: Path, output: Path, size: int = 512) -> Path:
    image = _load_rgb(path)
    x0, y0, x1, y1 = _subject_bbox(image)
    sw = max(1, x1 - x0)
    sh = max(1, y1 - y0)
    cx = (x0 + x1) * 0.5
    # Deliberately generous head/upper-torso crop. The actual face landmarker
    # and VLM decide whether a coherent face exists; the cropper never "passes"
    # a face on its own.
    half_w = max(sw * 0.32, 24.0)
    top = y0
    bottom = min(y1, y0 + sh * 0.48)
    left = max(0, int(cx - half_w))
    right = min(image.width, int(cx + half_w))
    crop = image.crop((left, int(top), right, max(int(top) + 2, int(bottom))))
    output.parent.mkdir(parents=True, exist_ok=True)
    ImageOps.pad(
        crop,
        (size, size),
        method=Image.Resampling.LANCZOS,
        color=(24, 24, 24),
    ).save(output)
    return output


def _labelled_sheet(
    items: list[tuple[str, Path]],
    output: Path,
    *,
    title: str,
    columns: int,
    cell: int = 320,
) -> Path:
    if not items:
        raise ValueError(f"no items for sheet {title}")
    header = 42
    title_h = 56
    rows = (len(items) + columns - 1) // columns
    canvas = Image.new(
        "RGB",
        (columns * cell, title_h + rows * (cell + header)),
        (18, 18, 20),
    )
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, canvas.width, title_h), fill=(8, 8, 10))
    draw.text((14, 16), title, fill=(255, 255, 255))
    for index, (label, path) in enumerate(items):
        col = index % columns
        row = index // columns
        x = col * cell
        y = title_h + row * (cell + header)
        thumb = ImageOps.pad(
            _load_rgb(path),
            (cell, cell),
            method=Image.Resampling.LANCZOS,
            color=(24, 24, 24),
        )
        canvas.paste(thumb, (x, y))
        draw.rectangle((x, y + cell, x + cell, y + cell + header), fill=(8, 8, 10))
        draw.text((x + 8, y + cell + 12), label, fill=(240, 240, 240))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=95)
    return output


def _stack_boards(
    sections: list[tuple[str, Path]],
    output: Path,
) -> Path:
    loaded = [(title, _load_rgb(path)) for title, path in sections]
    width = max(image.width for _, image in loaded)
    band = 64
    height = sum(image.height + band for _, image in loaded)
    canvas = Image.new("RGB", (width, height), (10, 10, 12))
    draw = ImageDraw.Draw(canvas)
    y = 0
    for title, image in loaded:
        draw.rectangle((0, y, width, y + band), fill=(0, 0, 0))
        draw.text((18, y + 22), title, fill=(255, 255, 255))
        y += band
        if image.width != width:
            image = ImageOps.pad(
                image,
                (width, image.height),
                method=Image.Resampling.LANCZOS,
                color=(10, 10, 12),
            )
        canvas.paste(image, (0, y))
        y += image.height
    output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve detail while bounding multimodal token count.
    if canvas.width > 2400:
        scale = 2400.0 / canvas.width
        canvas = canvas.resize(
            (2400, max(1, int(canvas.height * scale))),
            Image.Resampling.LANCZOS,
        )
    canvas.save(output, quality=95)
    return output


def _run_worker(
    python: str,
    script: Path,
    args: list[str],
    output: Path,
    log: Path,
    *,
    timeout: int = 5400,
) -> dict:
    command = [python, str(script), *args, "--output", str(output)]
    proc = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(proc.stdout or "", encoding="utf-8")
    if proc.returncode != 0:
        tail = (proc.stdout or "")[-4000:]
        raise RuntimeError(
            f"{script.name} failed exit={proc.returncode}: {tail}"
        )
    if not output.is_file():
        raise RuntimeError(f"{script.name} produced no report: {output}")
    return json.loads(output.read_text(encoding="utf-8"))


def _split_qrealign(report: dict, full_paths: list[Path], face_paths: list[Path]) -> tuple[dict, dict]:
    rows = report.get("images") or []
    by_path = {str(Path(row["path"])): float(row["score"]) for row in rows}

    def summarize(paths: list[Path]) -> dict:
        values = [by_path[str(path)] for path in paths if str(path) in by_path]
        if len(values) != len(paths):
            raise RuntimeError(
                f"Q-ReAlign coverage incomplete {len(values)}/{len(paths)}"
            )
        ordered = sorted(values)
        p10 = ordered[max(0, int(math.floor((len(ordered) - 1) * 0.10)))]
        return {
            "count": len(values),
            "mean": round(sum(values) / len(values), 6),
            "minimum": round(ordered[0], 6),
            "p10": round(p10, 6),
            "maximum": round(ordered[-1], 6),
        }

    return summarize(full_paths), summarize(face_paths)


def _internvl_failures(report: dict, t: JudgeV4Thresholds) -> list[str]:
    failures: list[str] = []
    passes = report.get("passes") or []
    if len(passes) < 2:
        return ["internvl_order_swap_evidence_missing"]
    floors = {
        "face_anatomy": t.internvl_face_anatomy_min,
        "face_source_fidelity": t.internvl_face_source_fidelity_min,
        "body_anatomy": t.internvl_body_anatomy_min,
        "hands": t.internvl_hands_min,
        "material_texture": t.internvl_material_texture_min,
        "multiview_consistency": t.internvl_multiview_consistency_min,
        "source_fidelity": t.internvl_source_fidelity_min,
    }
    for index, item in enumerate(passes):
        verdict = item.get("verdict") or {}
        if not verdict.get("pass"):
            failures.append(f"internvl_pass_{index}_rejected")
        issues = [str(x) for x in (verdict.get("critical_issues") or []) if str(x).strip()]
        if issues:
            failures.append(
                f"internvl_pass_{index}_critical:" + "|".join(issues[:8])
            )
        scores = verdict.get("scores") or {}
        for key, floor in floors.items():
            try:
                score = float(scores[key])
            except Exception:
                failures.append(f"internvl_pass_{index}_{key}_missing")
                continue
            if score < floor:
                failures.append(
                    f"internvl_pass_{index}_{key}:{score:.1f}<{floor:.1f}"
                )
    return failures


def run_judge_v4(
    *,
    final_glb: Path,
    source_images: list[Path],
    detail_images: list[Path],
    turntable_frames: list[Path],
    out_dir: Path,
    candidate_face_frames: list[Path] | None = None,
    policy: str = "required",
    python_executable: str | None = None,
    thresholds: JudgeV4Thresholds | None = None,
    tier: str = "pro",
) -> JudgeV4Report:
    t = thresholds or JudgeV4Thresholds()
    if tier not in {"core","pro"}:
        raise ValueError(f"unsupported Judge v4 tier: {tier}")
    qrealign_model=(
        "q-future/Q-ReAlign-Pro-9B"
        if tier=="pro" else "q-future/Q-ReAlign-Mini-0.8B"
    )
    internvl_model=(
        "OpenGVLab/InternVL3_5-8B-HF"
        if tier=="pro" else "OpenGVLab/InternVL3_5-1B-HF"
    )
    failures: list[str] = []
    advisories: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = [Path(p) for p in source_images if Path(p).is_file()]
    details = [Path(p) for p in detail_images if Path(p).is_file()]
    turns = [Path(p) for p in turntable_frames if Path(p).is_file()]
    provided_face_frames = [
        Path(p) for p in (candidate_face_frames or [])
        if Path(p).is_file()
    ]

    if not final_glb.is_file():
        failures.append("final_glb_missing")
    if not sources:
        failures.append("source_evidence_missing")
    if len(turns) < 24:
        failures.append(f"turntable_coverage:{len(turns)}<24")

    evidence_dir = out_dir / "evidence"
    normalized_source = [
        _normalized_subject(path, evidence_dir / "source_full" / f"{i:02d}.png")
        for i, path in enumerate(sources[:12])
    ]
    normalized_turns = [
        _normalized_subject(path, evidence_dir / "turn_full" / f"{i:02d}.png")
        for i, path in enumerate(turns[:24])
    ]

    requested_face_indices = (0, 1, 2, 3, 4, 20, 21, 22, 23)
    if provided_face_frames:
        # A material-faithful renderer may provide dedicated head closeups.
        # Keep the canonical front/quarter ordering so all face metrics remain
        # directly comparable with the historical turntable path.
        selected = list(provided_face_frames[:len(requested_face_indices)])
        candidate_face_indices = list(requested_face_indices[:len(selected)])
        candidate_faces = [
            _normalized_subject(
                path,
                evidence_dir / "candidate_face" / f"{index:02d}.png",
            )
            for index, path in zip(candidate_face_indices, selected)
        ]
    else:
        candidate_face_indices = [
            index
            for index in requested_face_indices
            if index < len(turns)
        ]
        candidate_faces = [
            _face_crop(
                turns[index],
                evidence_dir / "candidate_face" / f"{index:02d}.png",
            )
            for index in candidate_face_indices
        ]

    source_faces: list[Path] = []
    for index, path in enumerate(details[:8]):
        source_faces.append(
            _normalized_subject(
                path,
                evidence_dir / "source_face" / f"detail_{index:02d}.png",
            )
        )
    for index, path in enumerate(sources[:6]):
        source_faces.append(
            _face_crop(
                path,
                evidence_dir / "source_face" / f"crop_{index:02d}.png",
            )
        )

    source_sheet = _labelled_sheet(
        [(f"SOURCE {i+1}", path) for i, path in enumerate([*sources[:8], *details[:4]])],
        out_dir / "source_sheet.jpg",
        title="SOURCE REFERENCES — REAL INPUT EVIDENCE",
        columns=4,
        cell=320,
    )
    turn_sheet = _labelled_sheet(
        [(f"TURN {i*15:03d}", path) for i, path in enumerate(turns[:24])],
        out_dir / "turntable_sheet.jpg",
        title="CANDIDATE TURNTABLE — 24 FIXED VIEWS",
        columns=6,
        cell=280,
    )
    face_sheet = _labelled_sheet(
        [(f"FACE VIEW {index*15:03d}", path) for index, path in zip(candidate_face_indices, candidate_faces)],
        out_dir / "face_sheet.jpg",
        title="CANDIDATE FACE CLOSEUPS — FRONT / QUARTERS",
        columns=3,
        cell=420,
    )
    board_a = _stack_boards(
        [
            ("SOURCE REFERENCES", source_sheet),
            ("CANDIDATE TURNTABLE", turn_sheet),
            ("CANDIDATE FACE CLOSEUPS", face_sheet),
        ],
        out_dir / "board_source_first.jpg",
    )
    board_b = _stack_boards(
        [
            ("CANDIDATE TURNTABLE", turn_sheet),
            ("SOURCE REFERENCES", source_sheet),
            ("CANDIDATE FACE CLOSEUPS", face_sheet),
        ],
        out_dir / "board_candidate_first.jpg",
    )

    evidence = {
        "final_glb": str(final_glb),
        "source_images": [str(x) for x in sources],
        "detail_images": [str(x) for x in details],
        "turntable_frames": [str(x) for x in turns[:24]],
        "candidate_face_render_inputs": [str(x) for x in provided_face_frames],
        "candidate_face_crops": [str(x) for x in candidate_faces],
        "source_face_crops": [str(x) for x in source_faces],
        "source_sheet": str(source_sheet),
        "turntable_sheet": str(turn_sheet),
        "face_sheet": str(face_sheet),
        "boards": [str(board_a), str(board_b)],
    }

    python = (
        python_executable
        or os.environ.get("HAYUYA_JUDGE_V4_PYTHON")
        or ""
    )
    if not python:
        failures.append("judge_v4_python_missing")

    qrealign = None
    face_landmarks = None
    dreamsim = None
    internvl = None
    detected_source_faces: list[Path] = []

    if python:
        here = Path(__file__).resolve().parent
        try:
            face_landmarks = _run_worker(
                python,
                here / "judge_v4_face_worker.py",
                [
                    *sum((["--source", str(p)] for p in source_faces), []),
                    *sum((["--candidate", str(p)] for p in candidate_faces), []),
                ],
                out_dir / "face_landmarks.json",
                out_dir / "face_landmarks.log",
                timeout=900,
            )
            detected_source_faces = [
                Path(str(item["path"]))
                for item in (face_landmarks.get("source") or [])
                if item.get("path")
            ]
            if face_landmarks.get("face_expected_from_source"):
                total = max(1, int(face_landmarks.get("candidate_total") or 0))
                detected = int(face_landmarks.get("candidate_detected") or 0)
                fraction = detected / total
                if fraction < t.face_candidate_detection_fraction_min:
                    failures.append(
                        f"face_detection_coverage:{fraction:.3f}<"
                        f"{t.face_candidate_detection_fraction_min:.3f}"
                    )
                first_candidate = str(candidate_faces[0]) if candidate_faces else ""
                detected_paths = {
                    str(item.get("path"))
                    for item in (face_landmarks.get("candidate") or [])
                }
                if first_candidate and first_candidate not in detected_paths:
                    failures.append("front_face_not_detected")
                med = face_landmarks.get("median_profile_error")
                p90 = face_landmarks.get("p90_profile_error")
                if med is None or float(med) > t.face_profile_median_error_max:
                    failures.append(
                        f"face_geometry_median_error:{med}>"
                        f"{t.face_profile_median_error_max}"
                    )
                if p90 is None or float(p90) > t.face_profile_p90_error_max:
                    failures.append(
                        f"face_geometry_p90_error:{p90}>"
                        f"{t.face_profile_p90_error_max}"
                    )
                proportion_failures, proportion_gate = face_proportion_failures(
                    face_landmarks,
                    t,
                )
                face_landmarks["proportion_gate"] = proportion_gate
                failures.extend(proportion_failures)
            else:
                advisories.append(
                    "MediaPipe did not establish a human-like source face; "
                    "face acceptance remains governed by VLM/Q-ReAlign/DreamSim."
                )
        except Exception as exc:
            failures.append(f"face_landmark_worker:{type(exc).__name__}:{exc}")

        try:
            all_q_images = [*normalized_turns, *candidate_faces]
            qrealign = _run_worker(
                python,
                here / "judge_v4_qrealign_worker.py",
                [
                    *sum((["--image", str(p)] for p in all_q_images), []),
                    "--model",
                    qrealign_model,
                ],
                out_dir / "qrealign.json",
                out_dir / "qrealign.log",
            )
            full_q, face_q = _split_qrealign(
                qrealign,
                normalized_turns,
                candidate_faces,
            )
            qrealign["full_summary"] = full_q
            qrealign["face_summary"] = face_q
            if full_q["mean"] < t.qrealign_full_mean_min:
                failures.append(
                    f"qrealign_full_mean:{full_q['mean']:.3f}<"
                    f"{t.qrealign_full_mean_min:.3f}"
                )
            if full_q["p10"] < t.qrealign_full_p10_min:
                failures.append(
                    f"qrealign_full_p10:{full_q['p10']:.3f}<"
                    f"{t.qrealign_full_p10_min:.3f}"
                )
            if face_q["mean"] < t.qrealign_face_mean_min:
                failures.append(
                    f"qrealign_face_mean:{face_q['mean']:.3f}<"
                    f"{t.qrealign_face_mean_min:.3f}"
                )
            if face_q["p10"] < t.qrealign_face_p10_min:
                failures.append(
                    f"qrealign_face_p10:{face_q['p10']:.3f}<"
                    f"{t.qrealign_face_p10_min:.3f}"
                )
        except Exception as exc:
            failures.append(f"qrealign_worker:{type(exc).__name__}:{exc}")

        try:
            dreamsim = _run_worker(
                python,
                here / "judge_v4_dreamsim_worker.py",
                [
                    *sum((["--source-full", str(p)] for p in normalized_source), []),
                    *sum((["--candidate-full", str(p)] for p in normalized_turns), []),
                    *sum((
                        ["--source-face", str(p)]
                        for p in detected_source_faces
                    ), []),
                    *sum((["--candidate-face", str(p)] for p in candidate_faces), []),
                ],
                out_dir / "dreamsim.json",
                out_dir / "dreamsim.log",
            )
            full_worst = float(dreamsim["full"]["worst_best_distance"])
            if full_worst > t.dreamsim_full_worst_max:
                failures.append(
                    f"dreamsim_full_worst:{full_worst:.3f}>"
                    f"{t.dreamsim_full_worst_max:.3f}"
                )
            if dreamsim.get("face"):
                face_worst = float(dreamsim["face"]["worst_best_distance"])
                if face_worst > t.dreamsim_face_worst_max:
                    failures.append(
                        f"dreamsim_face_worst:{face_worst:.3f}>"
                        f"{t.dreamsim_face_worst_max:.3f}"
                    )
        except Exception as exc:
            failures.append(f"dreamsim_worker:{type(exc).__name__}:{exc}")

        try:
            internvl = _run_worker(
                python,
                here / "judge_v4_internvl_worker.py",
                [
                    "--board",
                    str(board_a),
                    "--board",
                    str(board_b),
                    "--model",
                    internvl_model,
                ],
                out_dir / "internvl.json",
                out_dir / "internvl.log",
            )
            failures.extend(_internvl_failures(internvl, t))
        except Exception as exc:
            failures.append(f"internvl_worker:{type(exc).__name__}:{exc}")

    # De-duplicate while preserving evidence order.
    failures = list(dict.fromkeys(failures))
    passed = not failures
    report = JudgeV4Report(
        schema=4,
        method=(
            "fail-closed multi-eye visual acceptance: 24-view render evidence + "
            + (
                "Q-ReAlign-Pro-9B"
                if tier=="pro"
                else "Q-ReAlign-Mini-0.8B"
            )
            + " + MediaPipe dense face geometry + DreamSim + "
            + (
                "dual-order InternVL3.5-8B-HF"
                if tier=="pro"
                else "dual-order InternVL3.5-1B-HF"
            )
            + f" [tier={tier}]"
        ),
        policy=policy,
        passed=passed,
        hard_fail_reasons=failures,
        advisories=advisories,
        thresholds=asdict(t),
        evidence=evidence,
        qrealign=qrealign,
        face_landmarks=face_landmarks,
        dreamsim=dreamsim,
        internvl=internvl,
    )
    (out_dir / "judge_v4.json").write_text(
        json.dumps(asdict(report), indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    p = argparse.ArgumentParser(description="HAYUYA fail-closed final visual Judge v4.")
    p.add_argument("--final-glb", type=Path, required=True)
    p.add_argument("--source", type=Path, action="append", default=[])
    p.add_argument("--detail", type=Path, action="append", default=[])
    p.add_argument("--turntable", type=Path, action="append", default=[])
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--policy", choices=["required", "auto"], default="required")
    p.add_argument("--python")
    p.add_argument("--tier", choices=["core","pro"], default="pro")
    a = p.parse_args()

    report = run_judge_v4(
        final_glb=a.final_glb,
        source_images=a.source,
        detail_images=a.detail,
        turntable_frames=a.turntable,
        out_dir=a.output_dir,
        policy=a.policy,
        python_executable=a.python,
        tier=a.tier,
    )
    print("HAYUYA_JUDGE_V4 " + json.dumps(asdict(report), separators=(",", ":")))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
