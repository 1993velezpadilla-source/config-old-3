#!/usr/bin/env python3
"""Read-only real Mesa drawcall/primitive regression guard across 16 Nacht source camera candidates.

This never claims true physical Android FPS, nor navigable/window viewpoint
certification. Source scenes are Pavlov UE4.21 archival reconstruction.
"""
import argparse
import json
from pathlib import Path

DRAW_REGRESSION_LIMIT = 0.05
PRIMITIVE_REGRESSION_LIMIT = 0.15
CAMERA_IDS = tuple(
    f"{center}_yaw{angle}"
    for center in (
        "interior_original", "interior_central",
        "exterior_south_candidate", "exterior_east_candidate"
    ) for angle in (0, 90, 180, 270)
)


def aggregate(data):
    mandatory = {
        "fullOriginalActors": 10793,
        "originalSourceMaterialBindings": 16595,
        "originalVistaTreeIds": 340,
        "originalActorsRetained": 10793,
        "originalActorsTemporarilyHidden": 282,
        "sourceMultiMeshGroups": 90,
        "sampledCandidateEyeHeightPositions": 4,
        "cardinal360DegreesHeadingsPerSample": 4,
        "noPermanentOriginalSourceDeletes": True,
        "originalWorld3DNavigationAndWindowsNotCertified": True,
        "realPhysicalAndroidGPUFPSOrMemoryMeasured": False,
        "productionShipApproved": False,
    }
    for key, expected in mandatory.items():
        if data.get(key) != expected or type(data[key]) is not type(expected):
            raise ValueError("RED: source evidence authority mismatch: " + key)
    if "NOT physical Android GPU" not in str(data.get("renderer", "")):
        raise ValueError("RED: Mesa source counters misrepresented as Android device")
    rows = data.get("individualPairReports")
    if not isinstance(rows, list) or len(rows) != len(CAMERA_IDS):
        raise ValueError("RED: not 16 paired source camera GPU samples")
    by_name = {x.get("cameraName"): x for x in rows}
    if len(by_name) != 16 or set(by_name) != set(CAMERA_IDS):
        raise ValueError("RED: unmatched/repeated original cameras")
    results = {}
    errors = []
    sums = {
        "sourceOriginalDrawCalls": 0,
        "sourceMultiMeshDrawCalls": 0,
        "sourceOriginalVisiblePrimitiveIndices": 0,
        "sourceMultiMeshVisiblePrimitiveIndices": 0
    }
    for camera in CAMERA_IDS:
        row = by_name[camera]
        vals = {}
        for stat, before_key, after_key, large_limit, sum_before, sum_after in (
            ("drawCalls", "sourceDrawCallsBefore", "sourceDrawCallsAfter",
             DRAW_REGRESSION_LIMIT, "sourceOriginalDrawCalls", "sourceMultiMeshDrawCalls"),
            ("primitiveIndices", "visiblePrimitiveIndicesBefore", "visiblePrimitiveIndicesAfter",
             PRIMITIVE_REGRESSION_LIMIT,
             "sourceOriginalVisiblePrimitiveIndices", "sourceMultiMeshVisiblePrimitiveIndices"),
        ):
            before = row.get(before_key)
            after = row.get(after_key)
            if type(before) is not int or type(after) is not int or before <= 0 or after <= 0:
                raise ValueError(f"RED: missing actual nonzero source {stat} Mesa counters for {camera}")
            saved = before - after
            percent = saved / before
            sums[sum_before] += before
            sums[sum_after] += after
            vals[stat] = {
                "before": before, "after": after,
                "saved": saved, "savedPercent": round(percent * 100, 5),
                "gpuRegressionMoreThanTolerance": percent < -large_limit,
            }
            if percent < -large_limit:
                errors.append(f"{camera}: {stat} increased by {-percent * 100:.3f}%")
        if not row.get("cameraHasSomeSourceSceneDetail"):
            vals["cameraVisibilityUnverified"] = True
        results[camera] = vals
    net_calls = sums["sourceOriginalDrawCalls"] - sums["sourceMultiMeshDrawCalls"]
    net_primitive_indices = (
        sums["sourceOriginalVisiblePrimitiveIndices"] -
        sums["sourceMultiMeshVisiblePrimitiveIndices"]
    )
    if net_calls <= 0:
        errors.append("aggregate selected-camera source draw calls did not improve")
    if net_primitive_indices < 0:
        errors.append("aggregate selected-camera source visible primitive indices regressed")
    return {
        "classification": (
            "MEASURED_MESA_16_CANDIDATE_VIEW_COUNTS_IMPROVED_NOT_ANDROID_FPS"
            if not errors else "MEASURED_MESA_16_CANDIDATE_VIEW_PERFORMANCE_REGRESSION_RED"
        ),
        "source": "Pavlov UE4.21 archival scene, NOT original BO3 T7",
        "sampledCameraCount": len(CAMERA_IDS),
        "sourceOriginalActorCount": 10793,
        "sourceMultiMeshGroups": 90,
        "sourceActorsTemporarilyHiddenNotDeleted": 282,
        "sampledCameraSummedDrawCallsSavedNotFrameFPS": net_calls,
        "sampledCameraSummedPrimitiveIndicesSavedNotFrameFPS": net_primitive_indices,
        "cameraSummedMeasures": sums,
        "pairedCameraDeltas": results,
        "allPlayableViewsAndWindowsCovered": False,
        "physicalAndroidGPUFPSMeasured": False,
        "productionMergeApproved": False,
        "regressions": errors,
    }


def _self_test():
    base = {
        "fullOriginalActors": 10793,
        "originalSourceMaterialBindings": 16595,
        "originalVistaTreeIds": 340,
        "originalActorsRetained": 10793,
        "originalActorsTemporarilyHidden": 282,
        "sourceMultiMeshGroups": 90,
        "sampledCandidateEyeHeightPositions": 4,
        "cardinal360DegreesHeadingsPerSample": 4,
        "noPermanentOriginalSourceDeletes": True,
        "originalWorld3DNavigationAndWindowsNotCertified": True,
        "realPhysicalAndroidGPUFPSOrMemoryMeasured": False,
        "productionShipApproved": False,
        "renderer": "Godot 4.6.1 Mesa llvmpipe NOT physical Android GPU",
        "individualPairReports": [
            {
                "cameraName": n,
                "sourceDrawCallsBefore": 300, "sourceDrawCallsAfter": 298,
                "visiblePrimitiveIndicesBefore": 120000,
                "visiblePrimitiveIndicesAfter": 119700,
                "cameraHasSomeSourceSceneDetail": True
            } for n in CAMERA_IDS
        ]
    }
    if aggregate(base)["regressions"]:
        raise AssertionError("positive source test mislabeled RED")
    regressed = json.loads(json.dumps(base))
    regressed["individualPairReports"][0]["sourceDrawCallsAfter"] = 360
    if not aggregate(regressed)["regressions"]:
        raise AssertionError("real Mesa camera draw-call regression must fail")
    fake_android = json.loads(json.dumps(base))
    fake_android["realPhysicalAndroidGPUFPSOrMemoryMeasured"] = True
    try:
        aggregate(fake_android)
    except ValueError:
        pass
    else:
        raise AssertionError("physical Android claim fabricated")
    print("XZOGOT_NACHT_SOURCE_16_VIEW_MESA_PER_CAMERA_GPU_AUDIT_UNIT_GREEN")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.self_test:
        _self_test()
        return
    if args.source is None or args.output is None:
        parser.error("requires --source and --output")
    source = json.loads(args.source.read_text(encoding="utf-8"))
    report = aggregate(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "XZOGOT_NACHT_REAL_16_CAMERA_MESA_GPU_PER_VIEW_AUDIT ",
        report["classification"],
        " summed_draw_calls_saved=", report["sampledCameraSummedDrawCallsSavedNotFrameFPS"],
        " summed_primitive_indices_saved=",
        report["sampledCameraSummedPrimitiveIndicesSavedNotFrameFPS"]
    )
    if report["regressions"]:
        raise ValueError("RED: actual Godot Mesa native source spatial batch regression " +
                         repr(report["regressions"]))


if __name__ == "__main__":
    main()
