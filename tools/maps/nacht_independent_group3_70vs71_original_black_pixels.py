#!/usr/bin/env python3
"""Independently compare original 141 source MasterMat candidates split as 70/71.

Uses the five actual Godot 4.6.1 Mesa screenshots from run 38022699414,
never synthetic screenshots nor stock textures. The result identifies which
half removes black original-source pixels when opacity scissor is temporarily
disabled; this is NOT evidence all transparent cutouts can safely be opaque.
"""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

W, H = 960, 540
ORIGINAL="source_group3_twohalves_original"
BOTH="source_group3_twohalves_all141_positive"
HALVES=("source_group3_twohalves_only_0","source_group3_twohalves_only_1")
RESTORED="source_group3_twohalves_original_restored"

def image(source,stem):
    matches=list(source.rglob(stem+".png"))
    if len(matches)!=1:
        raise ValueError("RED: expected ONE genuine source image for "+stem+" got "+str(len(matches)))
    with Image.open(matches[0]) as png:
        if png.size!=(W,H):
            raise ValueError("RED: original Godot framebuffer resolution drift")
        return png.convert("RGB")

def stats(a,b):
    bgr=a.tobytes()
    aft=b.tobytes()
    roi_black=0
    roi_fixed=0
    for y in range(int(H*.12),int(H*.88)):
        for x in range(int(W*.15),int(W*.85)):
            k=(y*W+x)*3
            if max(bgr[k:k+3])<0.045*255:
                roi_black+=1
                if max(aft[k:k+3])>=0.08*255:
                    roi_fixed+=1
    delta=ImageChops.difference(a,b).tobytes()
    return {"sourceNearBlackCenterROIPixels":roi_black,
            "sourceBlackPixelsRecoveredWhenAlphaScissorDisabled":roi_fixed,
            "meanRGBPercent":100.0*sum(delta)/(len(delta)*255)}

def test(source,output):
    reports=list(source.rglob("source-group3-70vs71-analysis.json"))
    if len(reports)!=1:
        raise ValueError("RED: missing unique native-source 70/71 Godot research report")
    r=json.loads(reports[0].read_text())
    expect={"originalSourceMeshActors":10793,"originalMaterialSurfaceBindings":16595,
            "originalSourceLightComponents":166,"originalUsedDDS":718,
            "originalSource564MasterMatAvailable":564,
            "originalSevenNonMasterMaskedProtected":7,
            "quartile3OriginalSourceMaterialCount":141,
            "quartile3OriginalSourceBoundSurfaces":5068,
            "allOriginalSourceMaterialPointersRestored":True,
            "productionMaterialShaderFixNotApproved":True}
    for k,v in expect.items():
        if k not in r or r[k]!=v or type(r[k]) is not type(v):
            raise ValueError("RED: original UE4 source authority or shipping policy changed: "+k)
    two=r["twoOriginalMaterialHalves"]
    if len(two)!=2 or [e["sourceHalf"] for e in two]!=[0,1] or [len(e["originalMaterialPaths"]) for e in two]!=[70,71]:
        raise ValueError("RED: source material halves do not have exact 70/71 immutable identities")
    if sum(e["originalSourceBindings"] for e in two)!=5068:
        raise ValueError("RED: original source 5068 material-bound surfaces changed")
    images={key:image(source,key) for key in (ORIGINAL,BOTH,*HALVES,RESTORED)}
    original=images[ORIGINAL]
    both=stats(original,images[BOTH])
    restored=stats(original,images[RESTORED])
    if both["sourceNearBlackCenterROIPixels"]<50000 or both["sourceBlackPixelsRecoveredWhenAlphaScissorDisabled"]<11000:
        raise ValueError("RED: independent full 141-source MasterMat positive control did not reproduce black recovery")
    if restored["meanRGBPercent"]>.05:
        raise ValueError("RED: source materials not restored to original 960x540 RGB")
    outcomes=[]
    for i in (0,1):
        point=stats(original,images[HALVES[i]])
        got=point["sourceBlackPixelsRecoveredWhenAlphaScissorDisabled"]
        godot=int(two[i]["darkROIOriginalVsOnlyThisHalf"]["blackRecoveredByDisablingOnlyDiffuseAlphaScissor"])
        if abs(got-godot)>350:
            raise ValueError(f"RED: actual original Godot source black pixel count diverged in half {i}: {got}/{godot}")
        if point["sourceNearBlackCenterROIPixels"]!=both["sourceNearBlackCenterROIPixels"]:
            raise ValueError("RED: source-camera original exposure or masks not matched")
        outcomes.append({
            "half":i,"originalSourceMaterialPathCount":len(two[i]["originalMaterialPaths"]),
            "originalSourceSurfaceBindings":two[i]["originalSourceBindings"],
            "blackROIPixelsRecoveredByHalf":got,
            "sourceMaterialNames":two[i]["originalMaterialPaths"],
            "sourceGraphHasIncompleteOpacityOutput":True,
        })
    if max(x["blackROIPixelsRecoveredByHalf"] for x in outcomes)<250:
        raise ValueError("RED: neither masked source-material half can reproduce genuine black wall recovery")
    output.mkdir(parents=True,exist_ok=True)
    canvas=Image.new("RGB",(W*2, H*2+42*2),(22,23,29))
    d=ImageDraw.Draw(canvas)
    for k,(name,label) in enumerate([
        (ORIGINAL,"ORIGINAL — before source alpha experiment"),
        (HALVES[0],"SOURCE group 3, first 70 materials ONLY"),
        (HALVES[1],"SOURCE group 3, last 71 materials ONLY"),
        (BOTH,"ALL 141 — known unsafe positive control")]):
        x=(k%2)*W
        y=(k//2)*(H+42)
        canvas.paste(images[name],(x,y+42))
        d.text((x+15,y+14),label,fill=(245,245,245))
    canvas.save(output/"nacht-real-source-group3-70-vs-71-black-wall-original-pixel-comparison.png")
    out={
        "originalScene":"Pavlov UE4.21 archive (NOT official BO3 T7)",
        "nativeRenderer":"Godot 4.6.1 Mesa Linux software GPU (NOT physical Android)",
        "originalActorNodes":10793,"originalBoundSourceSurfaces":16595,
        "originalUsedDDS":718,"originalLightComponents":166,
        "originalSourceMaterialGroup3Count":141,
        "originalSourceScreenROIAlmostBlackPixels":both["sourceNearBlackCenterROIPixels"],
        "unsafeAll141ControlBlackPixelsRecovered":both["sourceBlackPixelsRecoveredWhenAlphaScissorDisabled"],
        "genuineOriginalMaterialHalfComparisons":outcomes,
        "originalViewportAfterMaterialRestorationMeanRGBPercent":restored["meanRGBPercent"],
        "sourceGraphOpacityMaskNotProven":True,
        "windowsVegetationCutoutsNotCertified":True,
        "productionShaderOrMaterialFixApproved":False,
        "realAndroidFPSMeasured":False
    }
    (output/"original-70-vs-71-source-material-half-independent-real-pixel-audit.json").write_text(
        json.dumps(out,indent=2)+"\n")
    print("XZOGOT_NACHT_SOURCE_141_MASK_70_VS_71_INDEPENDENT_REAL_PIXELS_GREEN")
    print("positive",out["unsafeAll141ControlBlackPixelsRecovered"])
    for item in outcomes:
        print("source half",item["half"],"original materials",item["originalSourceMaterialPathCount"],
              "actual black recovered",item["blackROIPixelsRecoveredByHalf"])
    return out

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    test(args.source,args.output)
