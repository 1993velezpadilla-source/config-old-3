#!/usr/bin/env python3
"""Decode Godot 4.6.1 actual original-native 574 material-ID black-pixel buffer.

Each of two real native 960x540 source cameras has original, opaque-presence,
two 6-bit base4 RGB ID passes, and original material restoration control.
The recovered owner is the front-most surface in the temporary fully-opaque
diagnostic, which is NOT necessarily the UE4 material whose source alpha
mask discarded the original wall pixel. Candidate rankings require followup
per-material isolation. Not a shipping shader or physical Android GPU proof.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

CAMERAS=("interior_central_yaw180","interior_original_yaw270")
SUFFIXES={
    "original":"_real_original_source_material.png",
    "presence":"_original_source_solid_presence.png",
    "lo":"_original_material_id_low6.png",
    "hi":"_original_material_id_high6.png",
}
SHAPE=(540,960)
BLACK_THRESHOLD=12
PRESENCE_THRESHOLD=90

def get_image(root, name):
    files=list(root.rglob(name))
    if len(files)!=1:
        raise ValueError(f"RED: missing or duplicated exact native Godot source camera {name}: {files}")
    with Image.open(files[0]) as im:
        if im.size!=(960,540):
            raise ValueError("RED: exact native original camera not 960x540")
        return np.asarray(im.convert("RGB")).copy()

def fit_four_palette_levels(sample: np.ndarray):
    # The shader is truly unshaded; only original source surfaces are visible.
    # Godot's sRGB transfer / tonemap may differ from literal input albedo,
    # so learn the FOUR most common separated observed encoded peaks rather
    # than assuming alpha / color profiles.
    hist=np.bincount(sample.astype(np.uint8),minlength=256).astype(float)
    smooth=np.convolve(hist,np.ones(7)/7.0,"same")
    peaks=[]
    for _ in range(4):
        idx=int(smooth.argmax())
        if smooth[idx]<max(4.0, float(hist.sum())*0.00005):
            raise ValueError("RED: four encoded source tone clusters not observed")
        peaks.append(idx)
        smooth[max(idx-17,0):min(idx+18,256)]=0.0
    peaks=sorted(peaks)
    if min(np.diff(peaks))<16:
        raise ValueError("RED: material palette peaks are not distinguishable")
    return np.asarray(peaks,dtype=float)

def decode_pass(img: np.ndarray, centers: list[np.ndarray]):
    digits=[]
    conf=np.ones(SHAPE,bool)
    center_distances=[]
    for channel in range(3):
        vals=img[:,:,channel].astype(float)
        diffs=np.abs(vals[:,:,None]-centers[channel][None,None,:])
        dig=diffs.argmin(axis=2).astype(np.int32)
        min_dist=diffs.min(axis=2)
        conf &= min_dist<=11.0
        center_distances.append(min_dist)
        digits.append(dig)
    return digits[0]+digits[1]*4+digits[2]*16,conf,center_distances

def run(root: Path, output: Path):
    files=list(root.rglob("source-574-material-owner-blackwall.json"))
    if len(files)!=1:
        raise ValueError("RED: original full-source material palette authority JSON unavailable")
    source=json.loads(files[0].read_text())
    require={
        "originalSourceActorCount":10793,
        "originalSourceSurfaceBindings":16595,
        "originalDistinctEffectiveMaterials":574,
        "originalLightCount":166,
        "originalUsedDDS":718,
        "originalShaderMaterialPointersFullyRestored":True,
        "sourceOpaqueIDPassDiagnosticOnly":True,
        "productionBlackWallFixApproved":False,
    }
    for key,want in require.items():
        if source.get(key)!=want or type(source.get(key)) is not type(want):
            raise ValueError(f"RED: tampered original UE4.21 material authority {key}")
    lookup={r["sourceMaterialID"]:r for r in source["sourceMaterialIDLookup"]}
    bindings={r["sourceMaterialID"]:r for r in source["sourceMaterialOriginalSurfaceCounts"]}
    if set(lookup)!=set(range(1,575)) or len(bindings)!=574:
        raise ValueError("RED: original 574 source material IDs not unique or complete")
    if sum(r["originalSourceSurfaceBindings"] for r in bindings.values())!=16595:
        raise ValueError("RED: reconstructed original source material binding count not exact")
    output.mkdir(parents=True,exist_ok=True)
    report={}
    totals=Counter()
    for camera in CAMERAS:
        image={key:get_image(root,camera+suffix) for key,suffix in SUFFIXES.items()}
        base=image["original"]
        presence=image["presence"]
        solid=np.max(presence,axis=2)>PRESENCE_THRESHOLD
        nearblack=np.max(base,axis=2)<BLACK_THRESHOLD
        roi=np.zeros(SHAPE,bool)
        roi[int(540*0.12):int(540*0.88),int(960*0.15):int(960*0.85)]=True
        candidate=nearblack & solid & roi
        # Original scene must include true black geometry-backed pixels;
        # do not classify empty night sky as a missing material.
        if int(candidate.sum())<1000:
            raise ValueError("RED: original scene has insufficient black solid geometry to attribute "+camera)
        calibration=solid & roi
        center_levels=[]
        for ch in range(3):
            center_levels.append(fit_four_palette_levels(
                image["lo"][:,:,ch][calibration]))
        low,low_conf,_=decode_pass(image["lo"],center_levels)
        high,high_conf,_=decode_pass(image["hi"],center_levels)
        material_id=low+64*high
        trusted=(candidate & low_conf & high_conf & (material_id>=1)
                 & (material_id<=574))
        all_valid=trusted.sum()
        if int(all_valid)<100 or float(all_valid)/float(candidate.sum())<0.03:
            raise ValueError("RED: source opaque ID material chromatic decoding lacks confidence "+camera+
                             f" valid={all_valid} possible={candidate.sum()}")
        material_pixels=Counter(int(i) for i in material_id[trusted])
        totals.update(material_pixels)
        ranked=[]
        for uid,count in material_pixels.most_common(50):
            row=lookup[uid]
            ranked.append({
                "sourceMaterialID":uid,
                "originalSourceMaterialPath":row["originalSourceMaterialPath"],
                "originalUEBlendMode":row["sourceUEBlendMode"],
                "originalGraphStatus":row["sourceUEGraphStatus"],
                "originalSourceSurfaceBindings":bindings[uid]["originalSourceSurfaceBindings"],
                "highConfidenceBlackOpaqueDiagnosticPixels":count,
                "caution":"opaque categorical diagnostic only: screen surface owner candidate, NOT proven original UE opacity source"
            })
        report[camera]={
            "originalDarkPixelsInsideCenterROI":int((nearblack&roi).sum()),
            "darkPixelsBackedByActualOpaqueSourceGeometry":int(candidate.sum()),
            "highConfidenceOriginalSourceMaterialOwnerPixels":int(all_valid),
            "conservativeHighConfidenceDecodedFraction":float(all_valid)/float(candidate.sum()),
            "fourRGBLevelsLearnedFromActualGodotSourceImages":[c.tolist() for c in center_levels],
            "originalOpaqueMaterialCandidatesRanked":ranked,
        }
        collage=Image.new("RGB",(960*4,540+36),(16,20,25))
        d=ImageDraw.Draw(collage)
        for k,kind in enumerate(("original","presence","lo","hi")):
            collage.paste(Image.fromarray(image[kind]),(k*960,36))
            d.text((k*960+15,13),kind.upper()+" – original source / diagnostic",fill=(250,250,250))
        collage.save(output/f"{camera}-original-opaque-presence-source-material-ID-two-passes.png")
    aggregate=[]
    for uid,count in totals.most_common(100):
        row=lookup[uid]
        aggregate.append({
            "sourceMaterialID":uid,
            "originalSourceMaterialPath":row["originalSourceMaterialPath"],
            "originalUEBlendMode":row["sourceUEBlendMode"],
            "originalGraphStatus":row["sourceUEGraphStatus"],
            "blackPixelsVisibleAfterForcingAllSourceGeometryOpaque":count,
            "notProvenThatThisMaterialHadDiscardedAlphaOriginally":True,
        })
    result={
        "originalSource": "Pavlov UE4.21 reconstructed Nacht NOT original BO3 T7",
        "actorCount":10793,
        "originalSourceSurfaceBindings":16595,
        "originalEffectiveMaterialPaths":574,
        "originalDDSTextures":718,
        "realEyeHeightCameraCount":2,
        "originalSourceScreenMaterialAttribution":report,
        "rankedOpaqueDiagnosticScreenSurfaceOwners":aggregate,
        "materialOwnerIsNotProofOfUEOpacityMaskFault":True,
        "sourceShaderGraphStillPartial":True,
        "originalSourceActorOrMaterialChangedPermanently":False,
        "productionFixCertified":False,
        "phoneFPSOrWindowLOSProven":False,
    }
    path=output/"nacht-real-original-574-source-material-screen-pixel-attribution.json"
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("XZOGOT_NACHT_574_TRUE_ORIGINAL_SOURCE_MATERIAL_ID_BLACK_WALL_SCREEN_ATTRIBUTION_GREEN")
    for camera,entry in report.items():
        print(camera,entry["highConfidenceOriginalSourceMaterialOwnerPixels"],
              "high-confidence source material-owner pixels")
        for row in entry["originalOpaqueMaterialCandidatesRanked"][:12]:
            print(row["highConfidenceBlackOpaqueDiagnosticPixels"], row["originalSourceMaterialPath"])
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    run(a.input,a.output)
