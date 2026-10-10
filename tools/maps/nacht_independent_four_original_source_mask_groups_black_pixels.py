#!/usr/bin/env python3
"""Independently measure source-accurate Nacht UE4 mask quartiles from actual native Godot PNGs.

Original scene: archived Pavlov UE4.21 reconstruction, NOT an official BO3 T7
asset collection. 960x540 real Godot Mesa pixels, NOT actual Android FPS.
Never infer approved shader conversion from positive mask-off control.
"""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops

WIDTH, HEIGHT = 960, 540
CAMERA_PIXEL_ROI = (int(WIDTH*0.15), int(HEIGHT*0.12),
                    int(WIDTH*0.85), int(HEIGHT*0.88))


def original_image(folder, title):
    images = list(folder.rglob(title + ".png"))
    if len(images) != 1:
        raise ValueError(f"RED: expected exactly one native Godot image {title}: found {len(images)}")
    with Image.open(images[0]) as stream:
        img = stream.convert("RGB")
        if img.size != (WIDTH, HEIGHT):
            raise ValueError(f"RED: native Godot screenshot size drift in {title}")
        return img


def roi_dark_recovery(before, after):
    # Align the same native Godot ROI/threshold measurement semantics.
    b = before.crop(CAMERA_PIXEL_ROI).tobytes()
    a = after.crop(CAMERA_PIXEL_ROI).tobytes()
    original_dark = sum(max(b[i:i+3]) < 0.045*255 for i in range(0,len(b),3))
    recovered = sum(max(b[i:i+3]) < 0.045*255 and
                    max(a[i:i+3]) >= 0.08*255 for i in range(0,len(b),3))
    return original_dark, recovered


def mean_rgb_percent(before, after):
    d = ImageChops.difference(before, after)
    data = d.tobytes()
    return sum(data) / (len(data)*255)*100


def main(source_folder, output_folder):
    reports = list(source_folder.rglob("partitions.json"))
    if len(reports) != 1:
        raise ValueError("RED: exactly one authentic source native 4-way report required")
    meta = json.loads(reports[0].read_text())
    expected = {
        "fullOriginalActors":10793,
        "fullOriginalSurfaceBindings":16595,
        "allOriginalUsedDDSTextureImages":718,
        "UE421SourceLightComponents":166,
        "sourceMaskedMasterMaterialCount":564,
        "sourceMaskedMasterSurfaceBindings":15339,
        "originalMaterialResourcesRestoredExactly":True,
        "productionShipApproved":False,
        "UEOpacityMaskGraphPartiallyReconstructedNotProven":True,
    }
    for key,value in expected.items():
        if meta.get(key) != value or type(meta.get(key)) is not type(value):
            raise ValueError(f"RED: original source material authority/ship guard {key} drift")
    partitions = meta["fourSourceQuartileAloneAndLeaveOneOutResults"]
    if len(partitions) != 4 or len(meta["excludedOriginalOtherMaskedMaterials"]) != 7:
        raise ValueError("RED: exact four separate 141-material original UE quartiles required")
    if sum(meta["quartileSourceOriginalSurfaceBindings"]) != 15339:
        raise ValueError("RED: native original source surface bindings are not complete")
    original = original_image(source_folder,"black_partition_original_source")
    positive = original_image(source_folder,"black_partition_all_564_unsafe_positive_control")
    restored = original_image(source_folder,"black_partition_original_source_restored")
    black,recovered = roi_dark_recovery(original,positive)
    if black < 10000 or recovered < 5000:
        raise ValueError(f"RED: original full source broad alpha positive control was missing: {black} / {recovered}")
    restoration = mean_rgb_percent(original,restored)
    if restoration > 0.05:
        raise ValueError(f"RED: source opacity original material viewport was not restored: {restoration}")
    output_folder.mkdir(parents=True,exist_ok=True)
    ranking=[]
    for i, row in enumerate(partitions):
        if row["sourcePartition"] != i or row["nativeSourceMaterialsInPartition"] != 141:
            raise ValueError("RED: original source partition identity lost")
        if len(row["originalMaterialPathsInPartition"]) != 141:
            raise ValueError("RED: material paths missing in this 141-source partition")
        if row["originalSourceSurfaceBindingsInPartition"] != meta["quartileSourceOriginalSurfaceBindings"][i]:
            raise ValueError("RED: source quartile surface counts drift")
        alone = original_image(source_folder,f"black_partition_only_group_{i}")
        except_group = original_image(source_folder,f"black_partition_all_except_group_{i}")
        alone_black,alone_recover=roi_dark_recovery(original,alone)
        except_black,except_recover=roi_dark_recovery(original,except_group)
        if alone_black != black or except_black != black:
            raise ValueError("RED: same native original camera baseline mismatch")
        source_row_alone = row["oneOfFourOnlyBlackROI"]["blackRecoveredByDisablingOnlyDiffuseAlphaScissor"]
        source_row_except = row["allOtherThreePartitionsBlackROI"]["blackRecoveredByDisablingOnlyDiffuseAlphaScissor"]
        if abs(alone_recover-source_row_alone)>350 or abs(except_recover-source_row_except)>350:
            raise ValueError(f"RED: independent source PNG measurement and Godot A/B report inconsistent: {i}")
        ranking.append({
            "partition":i,
            "originalDistinctSourceMaterialPaths":141,
            "originalMaterialSurfaceBindings":row["originalSourceSurfaceBindingsInPartition"],
            "aloneSourceDarkPixelsRecovered":alone_recover,
            "allThreeOtherGroupsDarkPixelsRecovered":except_recover,
            "sourceBroadPositiveControlRecovered":recovered,
            "pixelsLostWithoutPartitionRelativeToBroadControl":recovered-except_recover,
            "originalSourceMaterialPaths":row["originalMaterialPathsInPartition"],
            "sourceUEOpacityMaskConnectedGraphNotYetProven":True
        })
    out = {
        "originalSource":"Archived Pavlov UE4.21 Nacht reconstruction; not original BO3 T7",
        "actualGodotRenderer":"4.6.1 Mesa gl_compatibility; NOT physical Android GPU",
        "originalActors":10793,
        "originalMaterialSurfaceBindings":16595,
        "trueSourceMasterMatPaths":564,
        "originalSourceDDSUsed":718,
        "sourceOriginalBlackROIPixels":black,
        "unsafeAll564AlphaOffRecoveredPixels":recovered,
        "materialResourcesRestoredOriginalMeanRGBDifferencePercent":restoration,
        "sourceMaterialGroupsByIsolatedScreenBlackPixelEffect":sorted(
            ranking,key=lambda x:x["aloneSourceDarkPixelsRecovered"],reverse=True),
        "sourceGraphPartialNotOriginalOpacityMaskProof":True,
        "notAllOriginalMaskedMaterialsApprovedOpaque":True,
        "notShippingReady":True,
        "phoneFPSVRAMUnmeasured":True
    }
    (output_folder/"nacht-4-source-mask-groups-independent-black-pixel-ranking.json").write_text(
        json.dumps(out,indent=2)+"\n")
    print("XZOGOT_NACHT_REAL_ORIGINAL_4_SOURCE_MASK_PARTITION_PNG_INDEPENDENT_GREEN",
          "broad unsafe recovered",recovered,"original nearblack",black)
    for r in out["sourceMaterialGroupsByIsolatedScreenBlackPixelEffect"]:
        print("group",r["partition"],"alone",r["aloneSourceDarkPixelsRecovered"],
              "all_except",r["allThreeOtherGroupsDarkPixelsRecovered"],
              "source_bindings",r["originalMaterialSurfaceBindings"])
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    main(args.source,args.output)
