#!/usr/bin/env python3
"""Fail-closed research audit of actual Godot Mesa native Vista MultiMesh measurements."""
import argparse
import json
from pathlib import Path
from nacht_renderer_ab_audit import audit as validate_first_three, FIELDS

def classify(report):
    prior = validate_first_three(report)
    rows = report.get("realOriginalVistaSourceMultimesh32mRenderer")
    props = report.get("researchVistaSpatialMultimeshOriginalActorsPreserved")
    if not isinstance(rows, list) or len(rows) != 2 or not isinstance(props, dict):
        raise ValueError("RED: no 32m research batch GPU samples")
    if props.get("originalSourceActorsStillPresent") != 10793:
        raise ValueError("RED: original actors deleted or not present")
    if props.get("originalVistaActorIDsVerified") != 340:
        raise ValueError("RED: original Vista actor IDs not fully accounted for")
    if props.get("originalMeshTransformsPreserved") is not True:
        raise ValueError("RED: original native actor geometry/transform mutated")
    if props.get("approvedForShipping") is not False:
        raise ValueError("RED: source research mistakenly certified as shipping")
    if props.get("originalCollisionNavigationChanged") is not False:
        raise ValueError("RED: original collision/nav mutated")
    if props.get("androidFPSNotMeasured") is not True:
        raise ValueError("RED: research Mesa counters conflated with Android")
    if props.get("originalActorsTemporarilyHidden", 0) < 100:
        raise ValueError("RED: fewer than 100 genuine source instances batched")
    if props.get("cellSizeMeters") != 32:
        raise ValueError("RED: not the 32m researched spatial batching policy")
    samples = {}
    for row in rows:
        view = row.get("label", "").replace("spatial32m_vista_original_multimesh_", "")
        if view not in ("overview", "interior") or view in samples:
            raise ValueError("RED: duplicated/missing original paired cameras")
        reference = next(
            r for r in report["realSourceOriginalBaselineRenderer"]
            if r["label"] == "native_source_before_" + view)
        if row.get("cameraPosition") != reference["cameraPosition"]:
            raise ValueError("RED: source and batched camera mismatch")
        if "NOT Android GPU" not in str(row.get("realGodotRenderingBackend", "")):
            raise ValueError("RED: invalid GPU backend provenance")
        for field in FIELDS:
            if type(row.get(field)) is not int or row[field] <= 0:
                raise ValueError("RED: invalid GPU monitor " + field)
        samples[view] = row
    if len(samples) != 2:
        raise ValueError("RED: incomplete matched cameras")
    results = {}
    regressions = []
    improvements = []
    for view in ("overview", "interior"):
        baseline = next(r for r in report["realSourceOriginalBaselineRenderer"]
                        if r["label"] == "native_source_before_" + view)
        lod = next(r for r in report["realActorSpecificSourceDerivedDDSExtension"]
                   if r["label"] == "far_source_vista_dds_" + view)
        rows_by_target = {}
        for name, original in (("originalToMultimesh", baseline),
                               ("farDDS_ToMultimesh", lod)):
            delta = {}
            for field in FIELDS:
                saved = original[field] - samples[view][field]
                delta[field] = {"before": original[field], "after": samples[view][field],
                                "saved": saved, "savedPercent": round(
                                    100 * saved / original[field], 5)}
                if saved < 0 and field in ("realVisibleDrawCalls",
                                           "realVisiblePrimitiveIndices"):
                    regressions.append(f"{view}/{name}/{field} increased by {-saved}")
                elif saved > 0:
                    improvements.append(f"{view}/{name}/{field} saved {saved}")
            rows_by_target[name] = delta
        results[view] = rows_by_target
    # Fail without measured draw savings at both cameras. No fake improvement.
    calls_lower_at_both = all(results[view]["originalToMultimesh"]
                              ["realVisibleDrawCalls"]["saved"] > 0
                              for view in ("overview", "interior"))
    state = ("RENDERED_TRIANGLE_OR_CALL_REGRESSION_RED" if regressions else
             "ACTUAL_MESA_REDUCED_CALLS_BOTH_CAMERAS_NOT_ANDROID"
             if calls_lower_at_both else
             "NO_MEASURED_DRAW_CALL_SAVINGS_BOTH_CAMERAS_RED")
    return {
        "status": state, "validPairedMesaCounters": True,
        "actualPhysicalAndroidGPUFPSMeasured": False,
        "sourceActorCountUnmodified": props["originalSourceActorsStillPresent"],
        "comparison": results, "regressions": regressions, "improvements": improvements,
        "cullingParityCertified": False, "productionMergeApproved": False,
        "visualScreenPixelParityForBatchingCertified": False,
        "warning": "Mesa llvmpipe comparison only. Instancing may change culling/shadow silhouettes; requires screenshots & real Android device."
    }

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = classify(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("XZOGOT_NACHT_REAL_GPU_BATCHING_DELTA_CLASSIFICATION", report["status"])
    for view, r in report["comparison"].items():
        d = r["originalToMultimesh"]
        print(view, "real_drawcall_saved=", d["realVisibleDrawCalls"]["saved"],
              "primitives_saved=", d["realVisiblePrimitiveIndices"]["saved"])
    if report["regressions"] or not report["status"].startswith("ACTUAL_MESA_REDUCED"):
        raise SystemExit("RED: cannot approve source instancing performance improvement")
