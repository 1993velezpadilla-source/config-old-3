#!/usr/bin/env python3
"""Fail-closed original Pavlov UE4.21 Nacht 16-camera research shard merge.

Accepts ONLY the existing Godot-produced indoors/outdoors subfolders. Copies
actual PNGs unchanged into a flat original-source directory and combines
the 8+8 camera reports. Does not rerender or make Android GPU claims.
"""
import argparse
import json
import shutil
from pathlib import Path

CAMERAS = {
    "indoors": {"interior_original", "interior_central"},
    "outdoors": {"exterior_south_candidate", "exterior_east_candidate"},
}
SHARED = (
    "fullOriginalActors",
    "originalSourceMaterialBindings",
    "sourceLightsReconstructed",
    "originalVistaTreeIds",
    "originalActorsRetained",
    "originalActorsTemporarilyHidden",
    "sourceMultiMeshGroups",
    "cardinal360DegreesHeadingsPerSample",
    "renderer",
    "source",
    "originalWorld3DNavigationAndWindowsNotCertified",
    "noPermanentOriginalSourceDeletes",
    "realPhysicalAndroidGPUFPSOrMemoryMeasured",
    "productionShipApproved",
)
EXPECTED = {
    "fullOriginalActors": 10793,
    "originalSourceMaterialBindings": 16595,
    "sourceLightsReconstructed": 166,
    "originalVistaTreeIds": 340,
    "originalActorsRetained": 10793,
    "originalActorsTemporarilyHidden": 282,
    "sourceMultiMeshGroups": 90,
    "cardinal360DegreesHeadingsPerSample": 4,
    "originalWorld3DNavigationAndWindowsNotCertified": True,
    "noPermanentOriginalSourceDeletes": True,
    "realPhysicalAndroidGPUFPSOrMemoryMeasured": False,
    "productionShipApproved": False,
}

def merge(source: Path, dest: Path):
    if dest.exists() and list(dest.iterdir()):
        raise ValueError("RED: refusing overwrite of existing source screenshot evidence")
    dest.mkdir(parents=True, exist_ok=True)
    reports = {}
    all_camera_names = set()
    for shard, centers in CAMERAS.items():
        folder = source / ("shard-" + shard)
        if not folder.is_dir():
            raise ValueError("RED: missing original source shard directory " + str(folder))
        report_path = folder / f"nacht-{shard}-8view-report.json"
        if not report_path.is_file():
            raise ValueError("RED: missing actual Godot source shard report " + shard)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("shardName") != shard:
            raise ValueError("RED: switched 8-view shard source identities")
        if report.get("sampledCandidateEyeHeightPositions") != 2 or report.get("pairedBeforeAfterScreenshots") != 16:
            raise ValueError("RED: original source render count changed")
        if report.get("errors") or len(report.get("individualPairReports", [])) != 8:
            raise ValueError("RED: incomplete native source Godot visual report")
        for key, value in EXPECTED.items():
            if type(report.get(key)) is not type(value) or report[key] != value:
                raise ValueError(f"RED: original source or safety policy mismatch {shard}/{key}")
        if "Pavlov UE4.21" not in report.get("source", "") or "NOT physical Android GPU" not in report.get("renderer", ""):
            raise ValueError("RED: archived source and Linux renderer provenance lost")
        camera_names = {
            f"{center}_yaw{degree}" for center in centers for degree in (0, 90, 180, 270)
        }
        actual = {entry.get("cameraName") for entry in report["individualPairReports"]}
        if actual != camera_names or all_camera_names.intersection(camera_names):
            raise ValueError("RED: missing/duplicate original camera pairs")
        all_camera_names.update(camera_names)
        images = list(folder.glob("*_spatial32m.png"))
        if len(images) != 16:
            raise ValueError("RED: actual source 8-view shard does not have 16 PNG frames")
        expected_pngs = {
            f"{name}_{version}_spatial32m.png" for name in camera_names
            for version in ("before", "after")
        }
        if {p.name for p in images} != expected_pngs:
            raise ValueError("RED: source screenshot names do not match the 8 original cameras")
        for png in images:
            if not png.is_file() or png.stat().st_size < 100:
                raise ValueError("RED: original source raster image empty " + str(png))
            shutil.copyfile(png, dest / png.name)
        reports[shard] = report
    if len(all_camera_names) != 16 or len(list(dest.glob("*_spatial32m.png"))) != 32:
        raise ValueError("RED: 16 original positions / 32 PNG pairs not complete")
    indoor, outdoor = reports["indoors"], reports["outdoors"]
    for name in SHARED:
        if indoor.get(name) != outdoor.get(name):
            raise ValueError("RED: 2 scene shards have different source authority " + name)
    combined = dict(indoor)
    del combined["shardName"]
    combined["sampledCandidateEyeHeightPositions"] = 4
    combined["pairedBeforeAfterScreenshots"] = 32
    combined["individualPairReports"] = (
        indoor["individualPairReports"] + outdoor["individualPairReports"]
    )
    combined["viewsWithAtLeast500NonDarkSourcePixels"] = sum(
        d["viewsWithAtLeast500NonDarkSourcePixels"] for d in reports.values()
    )
    if combined["viewsWithAtLeast500NonDarkSourcePixels"] < 12:
        raise ValueError("RED: too few actual visible original scene cameras")
    if len({x["cameraName"] for x in combined["individualPairReports"]}) != 16:
        raise ValueError("RED: source merge lost camera uniqueness")
    combined["shardMergeEvidence"] = {
        "nativeGodotSourceJobs": 2,
        "screenshotsAreExactCopiesOfGodotPNGNotRerendered": True,
        "originalActorsDeleted": 0,
        "navigator360OrWindowReachabilityCertified": False,
        "androidFPSProven": False,
        "productionShippingAllowed": False
    }
    (dest / "nacht-original-vista-360-candidate-visual-sweep.json").write_text(
        json.dumps(combined, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "XZOGOT_NACHT_TWO_REAL_8VIEW_SHARDS_SOURCE_32_PNG_MERGE_GREEN",
        "camera_pairs=16 source_png=32",
        "meaningful_views=" + str(combined["viewsWithAtLeast500NonDarkSourcePixels"])
    )
    return combined

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    merge(args.source, args.output)
