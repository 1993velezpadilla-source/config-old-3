#!/usr/bin/env python3
"""Decode true source Godot first70 masked material contributors using 7 A/B bitpasses.

Exact original 10793 mesh actors, 718 original-used DDS, original lighting.
The temporary "made opaque" bitsets are DIAGNOSTIC only. A 7-bit pixel
pattern may be a union of multiple overlapping materials; a candidate is
NOT proven until individually rendered and checked for safe alpha fidelity.
Archive is Pavlov UE4.21 reconstruction, not official BO3 T7.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

W,H=960,540
NAMES=("source_70bitmask_original","source_70bitmask_all70_positive")
BIT_STEM="source_70bitmask_native_bit_"
RESTORE="source_70bitmask_original_restored"
SRC_REPORT="original-first70-sevenbit-id-native-report.json"

def png(root: Path, name):
    found=list(root.rglob(name+".png"))
    if len(found)!=1:
        raise ValueError("RED: exact original Godot scene screenshot missing/duplicated "+name)
    with Image.open(found[0]) as im:
        if im.size!=(W,H):
            raise ValueError("RED: source 960x540 material bit raster changed")
        return np.asarray(im.convert("RGB")).copy()

def recovered(base,after,roi):
    original_near_black=np.max(base,axis=2)<(0.045*255)
    after_not_black=np.max(after,axis=2)>=(0.08*255)
    return original_near_black & after_not_black & roi

def diff_percent(a,b):
    return float(np.mean(np.abs(a.astype(float)-b.astype(float)))/255.0*100)

def classify(root:Path,output:Path):
    reports=list(root.rglob(SRC_REPORT))
    if len(reports)!=1:
        raise ValueError("RED: original Godot full source bit ID result missing")
    data=json.loads(reports[0].read_text())
    expected={
       "originalSourceNativeActors":10793,
       "originalMaterialSurfaceBindings":16595,
       "originalUsedDDS":718,
       "originalUE421LightComponents":166,
       "eligibleMasterMatSourceMaterialCount":564,
       "nonMasterMatMaskedSourceMaterialsProtected":7,
       "sourceMaterialCandidateCount":70,
       "sourceMaterialsOutsideCurrentProbeUntouched":494,
       "sourceSurfaceBindingsInProbe":3431,
       "originalSourceMaterialPointersFullyRestored":True,
       "realSourceAlphaGraphOutputsArePartial":True,
       "productionMaterialShaderFixApproved":False
    }
    for k,v in expected.items():
        if data.get(k)!=v or type(data.get(k)) is not type(v):
            raise ValueError(f"RED: source authority or no-shipping guard drift {k}")
    mapping={int(e["encodedMaterialCode"]):e["exactOriginalUE421MaterialPath"]
             for e in data["sourceMaterialBitIdLookup"]}
    if sorted(mapping)!=list(range(1,71)):
        raise ValueError("RED: original 70 source material 7-bit code identity not bijective")
    if len(set(mapping.values()))!=70:
        raise ValueError("RED: duplicate original source material paths")
    expected_bits=data["sevenOriginalSourceMaterialBitImageReports"]
    if len(expected_bits)!=7 or [e["sourceBitIndex"] for e in expected_bits]!=list(range(7)):
        raise ValueError("RED: missing source bit index identity")
    base=png(root,NAMES[0])
    positive=png(root,NAMES[1])
    restored=png(root,RESTORE)
    roi=np.zeros((H,W),dtype=bool)
    roi[int(H*.12):int(H*.88),int(W*.15):int(W*.85)]=True
    central_black=int((np.max(base,axis=2)<(0.045*255) & roi).sum()) if False else int(((np.max(base,axis=2)<(0.045*255))&roi).sum())
    broad=recovered(base,positive,roi)
    broad_count=int(broad.sum())
    if central_black<50000 or broad_count<11000:
        raise ValueError(f"RED: native positive original 70 materials not recovered: {central_black}/{broad_count}")
    restore_percent=diff_percent(base,restored)
    if restore_percent>0.05:
        raise ValueError(f"RED: original Godot material pointers not visually restored {restore_percent}%")
    original_meta=data["realOriginalDarkRegionRecoveryAll70UnsafeControl"]
    if abs(broad_count-int(original_meta["blackRecoveredByDisablingOnlyDiffuseAlphaScissor"]))>350:
        raise ValueError("RED: Godot vs independent 70 source bit true-original pixel metric")
    bitmask=np.zeros((H,W),dtype=np.uint8)
    bit_counts=[]
    for k in range(7):
        image=png(root,BIT_STEM+str(k))
        recovering=recovered(base,image,roi)
        count=int(recovering.sum())
        compare=int(expected_bits[k]["realOriginalDarkPixelRecovery"]["blackRecoveredByDisablingOnlyDiffuseAlphaScissor"])
        if abs(count-compare)>350:
            raise ValueError(f"RED: original native Godot bitmask source pixel mismatch bit={k} {count}/{compare}")
        bitmask |= (recovering.astype(np.uint8)<<k)
        bit_counts.append(count)
    # Only pixels present in all70 positive mask are eligible for attribution.
    # Additional bit recoveries elsewhere may be real but incomparable to full control.
    encoded=bitmask[broad]
    hist=np.bincount(encoded,minlength=128)
    resolved=sum(int(hist[i]) for i in range(1,71))
    out_of_range=int(hist[0])+int(hist[71:].sum())
    ranked=[]
    for code in sorted(range(1,71),key=lambda k:int(hist[k]),reverse=True):
        path=mapping[code]
        tail=path.rsplit("/",1)[-1]
        suspicious=any(token in tail.lower() for token in (
             "decal","foliage","leaf","leaves","grass","glass","chainlink","water",
             "shadow","caulk","particle","sprite","wire"))
        ranked.append({
            "originalSourceMaterialCode":code,
            "exactArchivedSourceUE421MaterialPath":path,
            "darkSourcePixelsWhose7BitMasksEqualCode":int(hist[code]),
            "materialNameSuggestsPossibleIntentionalTransparency":suspicious,
            "sourceMaterialAlphaOutputVerifiedExact":False,
            "overlappingSourceMaterialsMayCreateFalseCode":True
        })
    if resolved<200 or resolved/broad_count<0.015:
        raise ValueError("RED: single-contributor source image bit raster insufficiently unambiguous")
    result={
        "source":"Pavlov UE4.21 original archived Nacht reconstruction NOT official BO3 T7",
        "renderer":"actual Godot 4.6.1 Mesa OpenGL Compatibility NOT Android",
        "fullOriginalActors":10793,"originalSourceBoundSurfaces":16595,
        "originalUsedDDS":718,"originalUE421Lights":166,
        "originalMasterMatMaterialsConsidered":70,
        "otherSourceMaskedMasterMaterialsUntouched":494,
        "nonMasterMatMaskedMaterialsUntouched":7,
        "sourceOriginalBlackROIPixels":central_black,
        "unsafeFirst70OpaqueBlackPixelsRecovered":broad_count,
        "sevenSourceBitFrameDarkPixelRecoveryCounts":bit_counts,
        "attributableSourceBlackPixelsWith1to70BitSignature":resolved,
        "ambiguousSourceRecoveredBlackPixels":out_of_range,
        "fractionSingleCodePlausible":resolved/broad_count,
        "rankedOriginalSourceAlphaMaterialCandidates":ranked,
        "originalRestoredFramebufferMeanRGBDifferencePercent":restore_percent,
        "MUSTVerifyOneSourceMaterialAtATime":True,
        "bitCodeMayBeOROfOverlappingSourceMaterials":True,
        "blackRegionMayBeIntentionalVoidSkyOrCaulk":True,
        "partialOriginalCookedShaderGraphMissingSourceOpacityMaskProof":True,
        "productionApproved":False,
        "physicalAndroidFPSMeasured":False
    }
    output.mkdir(parents=True,exist_ok=True)
    (output/"nacht-original-first70-bitwise-black-wall-material-suspects.json").write_text(
        json.dumps(result,indent=2)+"\n")
    # Offer the user original zoomable real-source captures and confidence
    # annotations, not a misleading screenshot claiming repaired art.
    top=ranked[:6]
    for i,row in enumerate(top):
        code=row["originalSourceMaterialCode"]
        mask=(bitmask==code)&broad
        original=Image.fromarray(base)
        tint=Image.new("RGB",(W,H),(250,0,200))
        alpha=Image.fromarray((mask.astype(np.uint8)*150))
        original.paste(tint,(0,0),alpha)
        banner=Image.new("RGB",(W,H+52),(20,23,30))
        d=ImageDraw.Draw(banner)
        banner.paste(original,(0,52))
        label=row["exactArchivedSourceUE421MaterialPath"].rsplit("/",1)[-1]
        d.text((15,7),f"ORIGINAL-source bitmask code {code} · candidate {i+1} · pixels {row['darkSourcePixelsWhose7BitMasksEqualCode']}",fill="white")
        d.text((15,28),label[:120],fill="white")
        banner.save(output/f"original-Nacht-source-material-suspect-{i+1:02d}-id{code}-pixel-mask.png")
    print("XZOGOT_NACHT_TRUE_SOURCE_FIRST70_SEVEN_BIT_MATERIAL_PIXEL_RANKING_GREEN")
    print("original_black",central_black,"unsafe_control_recovered",broad_count,
          "plausible_ranked",resolved,"ambiguous",out_of_range)
    for row in top:
        print("suspect",row["originalSourceMaterialCode"],row["darkSourcePixelsWhose7BitMasksEqualCode"],row["exactArchivedSourceUE421MaterialPath"])
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    classify(args.input,args.output)
