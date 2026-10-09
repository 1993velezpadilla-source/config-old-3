#!/usr/bin/env python3
"""Independent actual-source 16-pose x 2 Godot PNG pixel audit; candidate 360, NOT proven nav.

The real Mesa renders contain full 10,793 original UE4.21 Pavlov archive actors,
574 material paths and 166 source light components. This script ONLY audits
already-generated PNG evidence, never substitutes synthetic art or predicts
mobile FPS, collision/visibility/accessibility, or official BO3 T7 assets.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

CENTERS = (
    "interior_original",
    "interior_central",
    "exterior_south_candidate",
    "exterior_east_candidate",
)
ANGLES = (0, 90, 180, 270)
MAX_MEAN_RGB_PERCENT = 0.25
MAX_SIGNIFICANT_PIXELS_PERCENT = 1.0


def required_unique(root: Path, filename: str) -> Path:
    paths = list(root.rglob(filename))
    if len(paths) != 1:
        raise ValueError(f"RED: no unique original Godot screenshot {filename} ({len(paths)} found)")
    return paths[0]


def measure_image_pair(original_file: Path, batched_file: Path):
    with Image.open(original_file) as original, Image.open(batched_file) as batched:
        a = original.convert("RGB")
        b = batched.convert("RGB")
    if a.size != (960, 540) or b.size != a.size:
        raise ValueError("RED: source camera render dimensions changed")
    diff = ImageChops.difference(a, b)
    count = a.width * a.height
    raw = diff.tobytes()
    changed = sum(1 for i in range(0, len(raw), 3)
                  if (raw[i] + raw[i + 1] + raw[i + 2]) > 0.03 * 3 * 255)
    mean_delta = 100 * sum(raw) / (len(raw) * 255)
    sig_percent = 100 * changed / count
    before_stats = ImageStat.Stat(a)
    # Transparent or empty frames are not evidence of matching visual details.
    distinct = len(a.getcolors(count + 1) or [])
    return {
        "resolution": [a.width, a.height],
        "meanRGBDifferencePercent": mean_delta,
        "changedPixelsOverRGB3PercentPercent": sig_percent,
        "changedPixelsOverRGB3Percent": changed,
        "sourceOriginalRGBStandardDeviation": [round(x, 2) for x in before_stats.stddev],
        "sourceOriginalDistinctRGBColors": distinct,
        "renderedOriginalImageNonempty": distinct >= 64,
    }, a, b


def audit(data_root: Path, outdir: Path):
    info = json.loads(required_unique(
        data_root, "nacht-original-vista-360-candidate-visual-sweep.json"
    ).read_text(encoding="utf-8"))
    asserts = {
        "fullOriginalActors": 10793,
        "originalSourceMaterialBindings": 16595,
        "sourceLightsReconstructed": 166,
        "originalVistaTreeIds": 340,
        "originalActorsRetained": 10793,
        "originalActorsTemporarilyHidden": 282,
        "sourceMultiMeshGroups": 90,
        "sampledCandidateEyeHeightPositions": 4,
        "cardinal360DegreesHeadingsPerSample": 4,
        "pairedBeforeAfterScreenshots": 32,
        "originalWorld3DNavigationAndWindowsNotCertified": True,
        "realPhysicalAndroidGPUFPSOrMemoryMeasured": False,
        "productionShipApproved": False,
        "noPermanentOriginalSourceDeletes": True,
    }
    for key, expected in asserts.items():
        if info.get(key) != expected or type(info[key]) is not type(expected):
            raise ValueError(f"RED: altered actual original source or overclaimed {key}")
    if "Pavlov UE4.21" not in info.get("source", ""):
        raise ValueError("RED: archive provenance lost")
    if "NOT physical Android GPU" not in info.get("renderer", ""):
        raise ValueError("RED: Linux Mesa counters falsely called Android results")
    rows = info.get("individualPairReports")
    if not isinstance(rows, list) or len(rows) != 16:
        raise ValueError("RED: not exactly 16 original-source paired camera screenshots")
    by_name = {}
    errors = list(info.get("errors", []))
    for row in rows:
        name = str(row.get("cameraName", ""))
        if name in by_name:
            errors.append(f"duplicate source camera {name}")
        by_name[name] = row
    wanted = {f"{name}_yaw{angle}" for name in CENTERS for angle in ANGLES}
    if set(by_name) != wanted:
        errors.append("original source camera selection does not cover four cardinal headings at four anchors")
    outdir.mkdir(parents=True, exist_ok=True)
    raw_measurements = {}
    for name in sorted(wanted):
        before = required_unique(data_root, name + "_before_spatial32m.png")
        after = required_unique(data_root, name + "_after_spatial32m.png")
        observed, _, _ = measure_image_pair(before, after)
        raw_measurements[name] = observed
        if name not in by_name:
            continue
        row = by_name[name]
        if not math.isclose(
            observed["meanRGBDifferencePercent"],
            float(row["meanRGBDifferencePercent"]), abs_tol=0.035
        ):
            errors.append(f"{name} Godot and independent PIL mean RGB delta differ")
        if not math.isclose(
            observed["changedPixelsOverRGB3PercentPercent"],
            float(row["changedPixelsOverRGB3PercentPercent"]), abs_tol=0.02
        ):
            errors.append(f"{name} Godot and independent PIL pixel count differ")
        if observed["changedPixelsOverRGB3Percent"] != int(row["changedPixelsOverRGB3Percent"]):
            errors.append(f"{name} raw 8-bit significant changed pixel count not paired")
        if not observed["renderedOriginalImageNonempty"]:
            errors.append(f"{name} screenshot is flat and cannot certify pixels")
        if observed["meanRGBDifferencePercent"] > MAX_MEAN_RGB_PERCENT:
            errors.append(f"{name} original source RGB exceeds visual tolerance")
        if observed["changedPixelsOverRGB3PercentPercent"] > MAX_SIGNIFICANT_PIXELS_PERCENT:
            errors.append(f"{name} too many visibly changed original pixels")
        if not isinstance(row.get("cameraHasSomeSourceSceneDetail"), bool):
            errors.append(f"{name} source camera visibility status absent")
        if row.get("sourceDrawCallsBefore", 0) <= 0 or row.get("sourceDrawCallsAfter", 0) <= 0:
            errors.append(f"{name} missing actual original or 32m MultiMesh draw calls")
    meaningful = sum(1 for row in rows if row.get("cameraHasSomeSourceSceneDetail"))
    if meaningful < 12 or info.get("viewsWithAtLeast500NonDarkSourcePixels") != meaningful:
        errors.append("less than 12/16 genuinely visible scene camera samples")
    # Every anchor in one inspectable original/after RGB contact sheet. Full
    # original PNGs remain in the source artifact, no pixel upscaling/AI art.
    for center in CENTERS:
        canvas = Image.new("RGB", (960 * 2, 540 * 4), (16, 20, 28))
        for angle_i, angle in enumerate(ANGLES):
            name = f"{center}_yaw{angle}"
            before = required_unique(data_root, name + "_before_spatial32m.png")
            after = required_unique(data_root, name + "_after_spatial32m.png")
            _, left, right = measure_image_pair(before, after)
            # Side-by-side pair per source player-height camera direction.
            canvas.paste(left, (0, 540 * angle_i))
            canvas.paste(right, (960, 540 * angle_i))
        canvas.save(outdir / (center + "-actual-original-vs-32m-source-pixels.png"))
    verdict = {
        "status": "PASS_16_CANDIDATE_PAIRED_SOURCE_CAMERA_PIXELS_NOT_360_PLAYER_REACHABILITY"
        if not errors else "RED_16_CANDIDATE_PIXEL_OR_PROVENANCE_REGRESSION",
        "source": "archived Pavlov UE4.21 actual original Godot 10,793 actors; NOT BO3 T7",
        "numberOfOriginalNachtPairedViews": 16,
        "sourceImageCountInspected": 32,
        "originalSourceActorCountUnchanged": 10793,
        "numberOfViewsWithContent": meaningful,
        "actualPixelAudit": raw_measurements,
        "cameraEyeHeightsAndWindowPlayabilityVerified": False,
        "allPlayable360VisibilityCertified": False,
        "physicalAndroidPerformanceProven": False,
        "originalActorsDeleted": 0,
        "approvedForProduction": False,
        "errors": errors,
    }
    (outdir / "original-Nacht-independent-16-cardinal-camera-RGB-audit.json").write_text(
        json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise ValueError("RED: original-source 16-view A/B evidence incomplete: " + repr(errors))
    return verdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    final = audit(args.source, args.output)
    print("XZOGOT_NACHT_ACTUAL_FULL_SOURCE_16_VIEW_32_PNG_INDEPENDENT_RGB_PARITY_GREEN")
    print("views=", final["numberOfOriginalNachtPairedViews"],
          "visibly populated=", final["numberOfViewsWithContent"])


if __name__ == "__main__":
    main()
