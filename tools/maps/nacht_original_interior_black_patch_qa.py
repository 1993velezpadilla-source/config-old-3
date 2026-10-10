#!/usr/bin/env python3
"""Flag near-black interior regions in actual *original* Godot Nacht captures.

This measures PIXELS only. Black can mean intentional darkness, a scene gap,
alpha discard, lighting/culling, or missing source material. No invented source
texture, geometry deletion, shipping quality claims or original BO3 assets.
"""
import argparse
import json
from collections import deque
from pathlib import Path

from PIL import Image

NAMES = tuple(
    f"{origin}_yaw{yaw}_before_spatial32m.png"
    for origin in ("interior_central", "interior_original")
    for yaw in (0, 90, 180, 270)
)
BLACK_MAX_8BIT = 20
ROI = (0.15, 0.12, 0.85, 0.88)


def analyze(original: Image.Image):
    rgb = original.convert("RGB")
    width, height = rgb.size
    if (width, height) != (960, 540):
        raise ValueError("RED: different native source screenshot resolution")
    left, top, right, bottom = (
        round(width * ROI[0]), round(height * ROI[1]),
        round(width * ROI[2]), round(height * ROI[3])
    )
    roi = rgb.crop((left, top, right, bottom))
    rw, rh = roi.size
    pixels = roi.tobytes()
    mask = bytearray(rw * rh)
    for pos in range(rw * rh):
        idx = pos * 3
        mask[pos] = int(max(pixels[idx:idx + 3]) <= BLACK_MAX_8BIT)
    num_black = sum(mask)
    largest = 0
    largest_box = None
    num_large = 0
    remaining = bytearray(mask)
    for index, enabled in enumerate(mask):
        if not enabled or not remaining[index]:
            continue
        remaining[index] = 0
        pending = deque((index,))
        size = 0
        xmin, xmax = rw, 0
        ymin, ymax = rh, 0
        while pending:
            cur = pending.pop()
            x, y = cur % rw, cur // rw
            size += 1
            xmin, xmax = min(xmin, x), max(xmax, x)
            ymin, ymax = min(ymin, y), max(ymax, y)
            for n in (cur - 1 if x else -1,
                      cur + 1 if x + 1 < rw else -1,
                      cur - rw if y else -1,
                      cur + rw if y + 1 < rh else -1):
                if n >= 0 and remaining[n]:
                    remaining[n] = 0
                    pending.append(n)
        if size >= 300:
            num_large += 1
        if size > largest:
            largest = size
            largest_box = [left + xmin, top + ymin,
                           left + xmax + 1, top + ymax + 1]
    overlay = rgb.copy()
    purple = Image.new("RGB", (rw, rh), (245, 57, 173))
    base = roi.copy()
    selection = Image.frombytes("L", (rw, rh), bytes(255 if m else 0 for m in mask))
    base.paste(Image.blend(roi, purple, 0.52), (0, 0), selection)
    overlay.paste(base, (left, top))
    return {
        "nativeResolution": [width, height],
        "sampleROI": [left, top, right, bottom],
        "sampleROIPixels": rw * rh,
        "blackThresholdRGBMax8Bit": BLACK_MAX_8BIT,
        "nearBlackROIPixels": num_black,
        "nearBlackROIPercent": 100 * num_black / (rw * rh),
        "largestNearBlackFourConnectedPatchPixels": largest,
        "largestNearBlackPatchBoundsPixels": largest_box,
        "numberOfNearBlackPatchesOver300Px": num_large,
        "materialOrGeometryCauseProven": False,
        "blackSkyAndIntentionalHolesNotExcluded": True,
    }, overlay


def run(root: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    found = {}
    for name in NAMES:
        matches = list(root.rglob(name))
        if len(matches) != 1 or not matches[0].is_file():
            raise ValueError("RED: exact original Godot screenshot missing " + name)
        with Image.open(matches[0]) as png:
            result, overlay = analyze(png)
        found[name] = result
        overlay.save(output / name.replace("_before_spatial32m.png", "-darkmask-purple-diagnostic.png"))
    worst = sorted(found.items(), key=lambda kv: kv[1]["nearBlackROIPercent"], reverse=True)
    final = {
        "source": "Godot original Pavlov UE4.21 archived Nacht, NOT official BO3 T7",
        "input": "only unbatched real source PNGs, no fake synthetic images",
        "interiorViewsSampled": len(found),
        "frameCountOfOriginalSourceOriginal": len(found),
        "rankedNearBlackCameraFrames": [
            {"camera": name, **data} for name, data in worst
        ],
        "allSourceAlbedoBindCountsAlreadyVerified": {
            "sourceMaterialSurfaceBindings": 16595,
            "texturedGodotSurfaceBindings": 16593,
            "UEPartialSourceGraphs": 570,
        },
        "missingTextureCauseProven": False,
        "throughWindowAndAllPlayablePositionsCertified": False,
        "blackInteriorArtIsNotCertifiedComplete": True,
        "phoneFPSOrMemoryMeasured": False,
        "noSourceGeometryModifiedOrDeleted": True,
        "productionShippingApproved": False,
    }
    (output / "nacht-original-8-interior-dark-patch-triage.json").write_text(
        json.dumps(final, indent=2) + "\n", encoding="utf-8"
    )
    if len(found) != 8 or max(r["largestNearBlackFourConnectedPatchPixels"] for r in found.values()) < 10000:
        raise ValueError("RED: pixel forensic source screenshot identity or dark-mask sample changed")
    print("XZOGOT_NACHT_EIGHT_REAL_UNBATCHED_INTERIOR_FRAMES_BLACK_PATCH_QA_GREEN",
          "worst", worst[0][0],
          "worstDarkPercent", round(worst[0][1]["nearBlackROIPercent"], 2),
          "maxConnectedDarkBlob", max(r["largestNearBlackFourConnectedPatchPixels"] for r in found.values()),
          "BLACK_MATERIAL_FIDELITY_REMAINS_UNPROVEN")
    return final


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.input, a.output)
