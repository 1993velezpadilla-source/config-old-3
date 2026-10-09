#!/usr/bin/env python3
"""Research-only real Mesa renderer A/B audit for Nacht. Never certifies Android FPS."""
import argparse
import json
from pathlib import Path

FIELDS = ("realVisibleObjects", "realVisibleDrawCalls", "realVisiblePrimitiveIndices")
VARIANTS = {
    "realSourceOriginalBaselineRenderer": "native_source_before_",
    "sourceFarExteriorOnlyRealRenderer": "far_visual_policy_",
    "realActorSpecificSourceDerivedDDSExtension": "far_source_vista_dds_",
}
VIEWS = ("overview", "interior")

def validate(raw):
    exact = {"originalNativeActors": 10793,
             "originalSourceMaterialBindings": 16595,
             "originalLightComponents": 166,
             "validGodotRendererMeasurements": True,
             "androidGPUActualFPSOrMemoryMeasured": False,
             "occludedActorDeletionCertified": False,
             "sourceMaterialAndGLTFActorResourcesPreserved": True}
    for field, expected in exact.items():
        if raw.get(field) != expected:
            raise ValueError(f"{field}: expected {expected}, got {raw.get(field)}")
    result = {}
    for key, prefix in VARIANTS.items():
        samples = raw.get(key)
        if not isinstance(samples, list) or len(samples) != len(VIEWS):
            raise ValueError(f"{key}: expected precisely 2 camera samples")
        result[key] = {}
        for row in samples:
            if not isinstance(row, dict):
                raise ValueError(f"{key}: invalid sample")
            label = row.get("label", "")
            if not isinstance(label, str) or not label.startswith(prefix):
                raise ValueError(f"{key}: bad label {label}")
            view = label[len(prefix):]
            if view not in VIEWS or view in result[key]:
                raise ValueError(f"{key}: unknown or repeated camera {view}")
            if row.get("androidPhysicalDeviceFPSNotKnown") is not True:
                raise ValueError("Desktop Mesa measurements misrepresented as Android")
            if "NOT Android GPU" not in str(row.get("realGodotRenderingBackend", "")):
                raise ValueError("Mesa backend not distinguished from physical GPU")
            if not row.get("cameraPosition"):
                raise ValueError("Actual camera position missing")
            for field in FIELDS:
                if type(row.get(field)) is not int or row[field] <= 0:
                    raise ValueError(f"{key}/{view}: missing real monitor {field}")
            result[key][view] = row
        if set(result[key]) != set(VIEWS):
            raise ValueError(f"{key}: incomplete camera pair")
    for view in VIEWS:
        positions = [result[key][view]["cameraPosition"] for key in VARIANTS]
        if len(set(positions)) != 1:
            raise ValueError(f"Unpaired cameras for {view}: {positions}")
    return result

def delta(before, after):
    return {
        key: {
            "baseline": before[key],
            "optimized": after[key],
            "saved": before[key] - after[key],
            "savedPercent": round(100 * (before[key] - after[key]) / before[key], 5)
        } for key in FIELDS
    }

def audit(source):
    rows = validate(source)
    original = rows["realSourceOriginalBaselineRenderer"]
    lod = rows["sourceFarExteriorOnlyRealRenderer"]
    dds = rows["realActorSpecificSourceDerivedDDSExtension"]
    comparisons = {
        view: {
            "sourceToFarLOD": delta(original[view], lod[view]),
            "sourceToFarLODPlusVistaDDS": delta(original[view], dds[view]),
            "farLODToAdditionalDDS": delta(lod[view], dds[view]),
        } for view in VIEWS
    }
    regressions = []
    for view, samples in comparisons.items():
        for stage in ("sourceToFarLOD", "sourceToFarLODPlusVistaDDS"):
            for field, d in samples[stage].items():
                if d["saved"] < 0:
                    regressions.append({
                        "camera": view, "variant": stage,
                        "monitor": field, "increase": -d["saved"]
                    })
    overview = comparisons["overview"]["sourceToFarLOD"]
    better = (overview["realVisibleDrawCalls"]["saved"] > 0 or
              overview["realVisiblePrimitiveIndices"]["saved"] > 0)
    classification = ("REGRESSION_NEEDS_REVIEW" if regressions else
                      "RENDER_COUNTER_REDUCTION_MEASURED_NOT_FPS" if better else
                      "NO_DRAW_CALL_OR_PRIMITIVE_IMPROVEMENT_PROVEN")
    return {
        "researchOnly": True,
        "originalUE421ActorCount": 10793,
        "realMesaGodotPairedCameras": 2,
        "comparisons": comparisons,
        "overviewRenderSubmissionReductionObserved": better,
        "classification": classification,
        "regressions": regressions,
        "physicalAndroidFPSMeasured": False,
        "physicalAndroidGPUVRAMMeasured": False,
        "unusedActorDeletionSafetyProven": False,
        "actualGeometryLODProven": False,
        "multiFrameConfidenceProven": False,
        "originalFullResolutionDDSReleasedFromGPU": False,
        "caveat": "One Mesa Compatibility snapshot per viewpoint and variant; no device FPS, GPU VRAM, frame-time statistics or deletion proof."
    }

def fixture(improvement=10, mismatch=False):
    raw = dict(originalNativeActors=10793, originalSourceMaterialBindings=16595,
               originalLightComponents=166, validGodotRendererMeasurements=True,
               androidGPUActualFPSOrMemoryMeasured=False,
               occludedActorDeletionCertified=False,
               sourceMaterialAndGLTFActorResourcesPreserved=True)
    for key, prefix in VARIANTS.items():
        raw[key] = []
        for view in VIEWS:
            count = (100 if key == "realSourceOriginalBaselineRenderer" or view == "interior"
                     else 100 - improvement)
            raw[key].append(dict(
                label=prefix+view, cameraPosition="(0,1,2)" if view == "overview" else "(4,5,6)",
                androidPhysicalDeviceFPSNotKnown=True,
                realGodotRenderingBackend="Mesa OpenGL Compatibility (Xvfb), NOT Android GPU",
                realVisibleObjects=count, realVisibleDrawCalls=count,
                realVisiblePrimitiveIndices=count*100))
    if mismatch:
        raw["sourceFarExteriorOnlyRealRenderer"][0]["cameraPosition"] = "unpaired"
    return raw

def selftest():
    assert audit(fixture())["classification"] == "RENDER_COUNTER_REDUCTION_MEASURED_NOT_FPS"
    assert audit(fixture(0))["classification"] == "NO_DRAW_CALL_OR_PRIMITIVE_IMPROVEMENT_PROVEN"
    assert audit(fixture(-10))["classification"] == "REGRESSION_NEEDS_REVIEW"
    for source in (fixture(mismatch=True), fixture()):
        if not source["sourceFarExteriorOnlyRealRenderer"][0]["cameraPosition"] == "unpaired":
            source["androidGPUActualFPSOrMemoryMeasured"] = True
        try:
            audit(source)
        except ValueError:
            continue
        raise AssertionError("A false certification or unpaired camera was allowed")
    print("XZOGOT_NACHT_RENDERER_METRICS_AUDIT_SELFTEST_GREEN")

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--input", type=Path)
    cli.add_argument("--output", type=Path)
    cli.add_argument("--self-test", action="store_true")
    args = cli.parse_args()
    if args.self_test:
        selftest()
        return
    if args.input is None or args.output is None:
        cli.error("--input and --output are required")
    output = audit(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print("XZOGOT_NACHT_RENDERER_METRICS_AUDIT", output["classification"])
    if output["regressions"]:
        raise SystemExit("RED: measured draw/object/primitive regression; investigate")

if __name__ == "__main__":
    main()
