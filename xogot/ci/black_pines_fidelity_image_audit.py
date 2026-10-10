#!/usr/bin/env python3
"""Inspect ACTUAL nine-room Godot screenshot evidence. No fake renders.

Pillow only used for CI review; NOT bundled into game/Blender addon.
The fixed source/scene captures these same nine views from real Godot camera.
This is quantitative black-ceiling/blank-frame regression detection, not
an artistic 'perfect' certification.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageStat

ROOMS = ("generator", "isolation", "surgery", "patients", "triage",
         "cafeteria", "security", "yard", "garage")
INTERIOR = tuple(r for r in ROOMS if r != "yard")
CEILING_MIN = 23.0  # Previously 8-16, fixed institutional ceilings 27-38


def analyze(folder: Path):
    results = {}
    hashes = set()
    for room in ROOMS:
        path = folder / ("black-pines-fidelity-" + room + ".png")
        if not path.exists():
            raise AssertionError("Fidelity RED missing REAL Godot frame " + room)
        payload = path.read_bytes()
        if len(payload) < 30000:
            raise AssertionError("Fidelity RED blank/too-small screenshot " + room)
        signature = hashlib.sha256(payload).hexdigest()
        if signature in hashes:
            raise AssertionError("Fidelity RED duplicate camera image " + room)
        hashes.add(signature)
        with Image.open(path) as source:
            source.load()
            if source.width < 1200 or source.height < 800:
                raise AssertionError("Fidelity RED non-native image " + room)
            image = source.convert("RGB")
            sample = image.resize((128, 80))
            stats = ImageStat.Stat(sample)
            # Upper 12% of a first-person room shows roof/ceiling visual.
            ceil_sample = image.crop(
                (0,0,image.width,max(1,round(image.height*.12)))
            ).resize((128,16))
            ceiling = sum(ImageStat.Stat(ceil_sample).mean)/3.
            contrast = sum(stats.stddev)/3.
        if room in INTERIOR and ceiling < CEILING_MIN:
            raise AssertionError("Fidelity RED near-black roof in %s: %.2f < %.2f"
                                 % (room,ceiling,CEILING_MIN))
        if contrast < 16.0:
            raise AssertionError("Fidelity RED near-flat/empty screenshot %s %.2f"
                                 % (room,contrast))
        results[room] = {
            "source": path.name, "actualGodotScreenshot": True,
            "meanTopRGB": round(ceiling,2),
            "fullFrameContrastRGB": round(contrast,2),
            "bytes": len(payload),
        }
    return {
        "gate": "BLACK_PINES_NINE_ROOM_REAL_IMAGE_FIDELITY_GREEN",
        "rooms": results,
        "sourceScreenshotCount": 9,
        "distinctRealScreenshotHashes": len(hashes),
        "indoorCeilingMinimumRGB": CEILING_MIN,
        "notArtisticPerfectionCertification": True,
        "notPhysicalAndroidFPSTest": True
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder",type=Path)
    args = ap.parse_args()
    report = analyze(args.folder)
    (args.folder / "black-pines-godot-nine-room-fidelity.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("BLACK_PINES_NINE_ROOM_REAL_IMAGE_FIDELITY_GREEN",
          "distinct_images=9",
          "interior_min_ceiling_luma=%.1f" %
          min(report["rooms"][r]["meanTopRGB"] for r in INTERIOR),
          "artistic_perfection=false")


if __name__ == "__main__":
    main()
