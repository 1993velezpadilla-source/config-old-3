#!/usr/bin/env python3
"""Read-only independent PIL RGB audit of six ORIGINAL-source Nacht screenshot PNGs.

Does not use a demo/synthetic screenshot or fabricate frames. Ensures the
source native Godot report agrees with the actual PNG pixel bytes, and preserves
RED visual regressions for a side-by-side inspection. NOT Android benchmark.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageStat

CASES = ("overview", "interior", "source_vista_near_tree")
MAX_MEAN_RGB_PERCENT = 0.25
MAX_CHANGED_PIXELS_PERCENT = 1.0


def only(root, name):
    files = list(root.rglob(name))
    if len(files) != 1 or not files[0].is_file():
        raise ValueError("RED: missing/duplicate original-source visual input " + name)
    return files[0]


def measure(left, right):
    if left.size != right.size or left.size != (960, 540):
        raise ValueError("RED: original vs spatial MultiMesh cameras mismatch")
    a = left.convert("RGB")
    b = right.convert("RGB")
    count = a.width * a.height
    da = ImageChops.difference(a, b)
    data = da.tobytes()
    total_bytes = sum(data)
    significant = 0
    max_rgb_mean = 0
    for i in range(0, len(data), 3):
        rgb = data[i] + data[i + 1] + data[i + 2]
        max_rgb_mean = max(max_rgb_mean, rgb)
        if rgb / (3.0 * 255.0) > 0.03:
            significant += 1
    return {
        "resolution": [a.width, a.height],
        "meanRGBDifferencePercent": 100 * total_bytes / (3 * 255 * count),
        "changedPixelsOverRGB3Percent": significant,
        "changedPixelsOverRGB3PercentPercent": 100 * significant / count,
        "maxRGBMeanPixelChange": max_rgb_mean / (3 * 255),
        "beforeRGBMean8Bit": [round(v, 2) for v in ImageStat.Stat(a).mean],
        "beforeRGBStddev8Bit": [round(v, 2) for v in ImageStat.Stat(a).stddev],
        "distinctRGBColorsBefore": len(a.getcolors(count + 1) or []),
        "differentRGBAOrRGBExactBytes": a.tobytes() != b.tobytes(),
    }, a, b, da


def audit(folder, output):
    report_path = only(folder, "real-original-source-vista-spatial-visual-ab.json")
    source = json.loads(report_path.read_text(encoding="utf-8"))
    if source.get("actorAndSurfaceAuthority") != [10793, 16595]:
        raise ValueError("RED: native full-source GLB actor/surface count missing")
    if "Pavlov UE4.21" not in source.get("source", ""):
        raise ValueError("RED: invalid provenance")
    if "NOT physical Android GPU" not in source.get("renderer", ""):
        raise ValueError("RED: falsely stated mobile GPU")
    batch = source["experimental32mNativeSourceBatch"]
    if batch.get("originalSourceActorsStillPresent") != 10793:
        raise ValueError("RED: original world actors not retained")
    if batch.get("originalVistaActorIDsVerified") != 340:
        raise ValueError("RED: not all original Vista IDs accounted for")
    if batch.get("originalActorsTemporarilyHidden") != 282:
        raise ValueError("RED: different source batch configuration than measured GPU A/B")
    if batch.get("actualOriginalSourceMultimeshNodes") != 90:
        raise ValueError("RED: different original source group count")
    if batch.get("approvedForShipping") is not False:
        raise ValueError("RED: research batch marked shipping")
    for k, expected in (
        ("realOriginalNachtPixelParityTested", True),
        ("allReachable360WindowVisibilityCertified", False),
        ("androidGPUFPSOrVRAMMeasured", False),
        ("approvedToShip", False),
    ):
        if source.get(k) is not expected:
            raise ValueError("RED: invalid visual-only provenance claim " + k)
    original_cases = source.get("cameraCases", [])
    if len(original_cases) != 3 or {c.get("camera") for c in original_cases} != set(CASES):
        raise ValueError("RED: not exactly three source-captured paired camera views")
    results = {}
    failures = list(source.get("errors", []))
    output.mkdir(parents=True, exist_ok=True)
    for camera in CASES:
        left_path = only(folder, camera + "_before_spatial32m.png")
        right_path = only(folder, camera + "_after_spatial32m.png")
        with Image.open(left_path) as left_png, Image.open(right_path) as right_png:
            left_png.load()
            right_png.load()
            measured, left, right, diff = measure(left_png, right_png)
        claimed = next(x for x in original_cases if x["camera"] == camera)
        for field in ("meanRGBDifferencePercent", "changedPixelsOverRGB3PercentPercent"):
            if not math.isclose(measured[field], float(claimed[field]), abs_tol=0.035):
                failures.append(camera + ": native Godot RGB report does not match actual screenshot PNG " + field)
        if measured["changedPixelsOverRGB3Percent"] != int(claimed["changedPixelsOverRGB3Percent"]):
            failures.append(camera + ": actual changed-pixel count disagrees with native Godot")
        if measured["distinctRGBColorsBefore"] < 64:
            failures.append(camera + ": source screenshot too flat to prove material render parity")
        if measured["meanRGBDifferencePercent"] > MAX_MEAN_RGB_PERCENT:
            failures.append(camera + ": mean RGB delta above 0.25 percent")
        if measured["changedPixelsOverRGB3PercentPercent"] > MAX_CHANGED_PIXELS_PERCENT:
            failures.append(camera + ": greater than 1 percent source pixels substantially changed")
        if camera == "source_vista_near_tree" and int(claimed["significantVisiblePixelsBefore"]) < 500:
            failures.append(camera + ": original source tree camera not visibly populated")
        # Make an inspectable 3-panel BEFORE / AFTER / RGB DELTA per CAMERA
        comparison = Image.new("RGB", (960 * 3, 540))
        comparison.paste(left, (0, 0))
        comparison.paste(right, (960, 0))
        comparison.paste(ImageEnhance.Contrast(diff).enhance(6), (960 * 2, 0))
        comparison.save(output / ("original-source-" + camera + "-before-after-diff.png"))
        results[camera] = measured
    final = {
        "source": "Actual full archived Pavlov UE4.21 Native Godot scene, NOT original BO3 T7",
        "renderer": "Actual Godot 4.6.1 OpenGL Mesa llvmpipe; NOT a physical Android GPU",
        "originalSourceActors": 10793,
        "originalSourceMaterialBindings": 16595,
        "originalVistaTreeActors": 340,
        "originalActorsTemporarilyHiddenWithGroupsPresent": 282,
        "originalVistaSourceMultiMeshNodes": 90,
        "independentScreenshotRGBAQuantizedRGB": results,
        "errors": failures,
        "allReachableWindows360Certified": False,
        "physicalAndroidFPSOrVRAMMeasured": False,
        "shippingApproved": False,
    }
    (output / "independent-original-Nacht-Vista-spatial-pixel-audit.json").write_text(
        json.dumps(final, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise ValueError("RED: visual parity must not be certified " + repr(failures))
    return final


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = audit(a.source, a.output)
    print("XZOGOT_NACHT_NATIVE_SOURCE_VISTA_MM_SIX_PNG_INDEPENDENT_RGB_PARITY_GREEN")
    for camera, row in result["independentScreenshotRGBAQuantizedRGB"].items():
        print(camera, "meanRGBDeltaPercent=", round(row["meanRGBDifferencePercent"], 5),
              "changedOver3Percent=", round(row["changedPixelsOverRGB3PercentPercent"], 5))
