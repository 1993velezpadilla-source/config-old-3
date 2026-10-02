#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)

# Stable MediaPipe face topology indices.
FEATURE_PAIRS = {
    "left_eye_width": (33, 133),
    "right_eye_width": (362, 263),
    "left_eye_height": (159, 145),
    "right_eye_height": (386, 374),
    "mouth_width": (61, 291),
    "mouth_height": (13, 14),
    "face_width": (234, 454),
    "face_height": (10, 152),
    "nose_to_chin": (1, 152),
}


def _ensure_model(path: Path) -> Path:
    if path.is_file() and path.stat().st_size > 1_000_000:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    urllib.request.urlretrieve(MODEL_URL, tmp)
    if tmp.stat().st_size <= 1_000_000:
        raise RuntimeError("downloaded MediaPipe face model is unexpectedly small")
    tmp.replace(path)
    return path


def _distance(a, b) -> float:
    return math.sqrt(
        (float(a.x) - float(b.x)) ** 2
        + (float(a.y) - float(b.y)) ** 2
        + (float(a.z) - float(b.z)) ** 2
    )


def _features(landmarks) -> dict[str, float]:
    if len(landmarks) < 455:
        raise ValueError(f"expected dense face landmarks, got {len(landmarks)}")

    left_center = np.mean(
        [[landmarks[i].x, landmarks[i].y, landmarks[i].z] for i in (33, 133)],
        axis=0,
    )
    right_center = np.mean(
        [[landmarks[i].x, landmarks[i].y, landmarks[i].z] for i in (362, 263)],
        axis=0,
    )
    inter_eye = float(np.linalg.norm(left_center - right_center))
    inter_eye = max(inter_eye, 1e-8)

    out = {"inter_eye": inter_eye}
    for name, (a, b) in FEATURE_PAIRS.items():
        out[name] = _distance(landmarks[a], landmarks[b]) / inter_eye

    nose = np.array([landmarks[1].x, landmarks[1].y, landmarks[1].z], dtype=float)
    eye_mid = (left_center + right_center) * 0.5
    mouth_mid = np.mean(
        [[landmarks[i].x, landmarks[i].y, landmarks[i].z] for i in (61, 291)],
        axis=0,
    )
    face_left = np.array([landmarks[234].x, landmarks[234].y, landmarks[234].z], dtype=float)
    face_right = np.array([landmarks[454].x, landmarks[454].y, landmarks[454].z], dtype=float)
    face_mid = (face_left + face_right) * 0.5

    out["nose_eye_center_offset"] = float(np.linalg.norm(nose - eye_mid)) / inter_eye
    out["mouth_face_center_offset"] = float(np.linalg.norm(mouth_mid - face_mid)) / inter_eye
    out["eye_width_asymmetry"] = abs(
        out["left_eye_width"] - out["right_eye_width"]
    ) / max(out["left_eye_width"], out["right_eye_width"], 1e-8)
    out["eye_height_asymmetry"] = abs(
        out["left_eye_height"] - out["right_eye_height"]
    ) / max(out["left_eye_height"], out["right_eye_height"], 1e-8)
    return out


def _crop_top_subject(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    h, w = rgb.shape[:2]
    patch = max(4, min(h, w) // 24)
    corners = np.concatenate([
        rgb[:patch, :patch].reshape(-1, 3),
        rgb[:patch, -patch:].reshape(-1, 3),
        rgb[-patch:, :patch].reshape(-1, 3),
        rgb[-patch:, -patch:].reshape(-1, 3),
    ], axis=0)
    bg = np.median(corners, axis=0)
    mask = np.linalg.norm(rgb - bg, axis=2) > 24.0
    ys, xs = np.where(mask)
    if len(xs) < 64:
        return image
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    sh = y1 - y0 + 1
    sw = x1 - x0 + 1
    head_y1 = min(y1 + 1, y0 + max(int(sh * 0.48), 32))
    cx = (x0 + x1) // 2
    half = max(int(sw * 0.34), 24)
    crop = image.crop((max(0, cx - half), max(0, y0), min(w, cx + half), head_y1))
    return crop.resize((512, 512), Image.Resampling.LANCZOS)


def _detect(detector, path: Path) -> tuple[dict | None, str | None]:
    import mediapipe as mp

    image = Image.open(path).convert("RGB")
    attempts = [image, _crop_top_subject(image)]
    last_error = None
    for attempt_index, pil in enumerate(attempts):
        try:
            arr = np.asarray(pil, dtype=np.uint8)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
            result = detector.detect(mp_image)
            if result.face_landmarks:
                landmarks = result.face_landmarks[0]
                features = _features(landmarks)
                blendshapes = {}
                if result.face_blendshapes:
                    for item in result.face_blendshapes[0]:
                        name = str(getattr(item, "category_name", "") or "")
                        if name:
                            blendshapes[name] = round(float(item.score), 6)
                return {
                    "path": str(path),
                    "attempt": attempt_index,
                    "landmarks": len(landmarks),
                    "features": {k: round(float(v), 6) for k, v in features.items()},
                    "blendshapes": blendshapes,
                }, None
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{exc}"
    return None, last_error or "no_face_detected"


def _profile(rows: list[dict]) -> dict[str, float]:
    keys = sorted(
        set.intersection(*[set(row["features"]) for row in rows])
    )
    return {
        key: float(statistics.median(float(row["features"][key]) for row in rows))
        for key in keys
    }


def _profile_error(reference: dict[str, float], row: dict) -> float:
    errors = []
    for key, expected in reference.items():
        actual = float(row["features"].get(key, expected))
        if key.endswith("asymmetry") or key.endswith("offset"):
            errors.append(abs(actual - expected))
        elif expected > 1e-8 and actual > 1e-8:
            errors.append(abs(math.log(actual / expected)))
    return float(statistics.median(errors)) if errors else float("inf")


def main() -> int:
    p = argparse.ArgumentParser(description="HAYUYA Judge v4 dense face-landmark worker.")
    p.add_argument("--source", type=Path, action="append", default=[])
    p.add_argument("--candidate", type=Path, action="append", default=[])
    p.add_argument(
        "--model",
        type=Path,
        default=Path.home() / ".cache" / "hayuya" / "face_landmarker.task",
    )
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()

    import mediapipe as mp

    model = _ensure_model(a.model)
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=1,
        # Keep Judge aligned with the source-autofix detector. Stylized
        # character faces (white eyes / heavy makeup) can be valid source
        # evidence while scoring below the old 0.45 detector threshold.
        min_face_detection_confidence=0.30,
        min_face_presence_confidence=0.30,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )

    source_rows, candidate_rows = [], []
    source_failures, candidate_failures = [], []
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
        for path in a.source:
            row, error = _detect(detector, path)
            if row:
                source_rows.append(row)
            else:
                source_failures.append({"path": str(path), "error": error})
        for path in a.candidate:
            row, error = _detect(detector, path)
            if row:
                candidate_rows.append(row)
            else:
                candidate_failures.append({"path": str(path), "error": error})

    face_expected = bool(source_rows)
    reference_profile = _profile(source_rows) if source_rows else {}
    candidate_errors = []
    if reference_profile:
        for row in candidate_rows:
            error = _profile_error(reference_profile, row)
            row["profile_error"] = round(error, 6)
            candidate_errors.append(error)

    median_error = (
        float(statistics.median(candidate_errors))
        if candidate_errors else None
    )
    p90_error = None
    if candidate_errors:
        ordered = sorted(candidate_errors)
        p90_error = ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.90))]

    report = {
        "schema": 1,
        "model": str(model),
        "face_expected_from_source": face_expected,
        "source_detected": len(source_rows),
        "source_total": len(a.source),
        "candidate_detected": len(candidate_rows),
        "candidate_total": len(a.candidate),
        "source": source_rows,
        "candidate": candidate_rows,
        "source_failures": source_failures,
        "candidate_failures": candidate_failures,
        "reference_profile": {
            k: round(float(v), 6) for k, v in reference_profile.items()
        },
        "median_profile_error": (
            round(median_error, 6) if median_error is not None else None
        ),
        "p90_profile_error": (
            round(p90_error, 6) if p90_error is not None else None
        ),
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("HAYUYA_JUDGE_V4_FACE " + json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
