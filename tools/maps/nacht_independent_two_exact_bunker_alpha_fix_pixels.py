#!/usr/bin/env python3
"""Independent exact-source native Godot 4.6.1 black wall 2-surface pixel audit.

This checks ONE original source material from TWO exact archived actor IDs.
574-material source screen-owner raster proves which material becomes
visible when everything is opaque but NOT the original authored OpacityMask.
No claim of full-view/window visual parity or Android hardware performance.
"""
import argparse
from pathlib import Path
import json
from PIL import Image,ImageChops,ImageDraw

BASE="interior_central_yaw180","interior_original_yaw0","interior_original_yaw270"
TARGET=("Content/CustomMaps/UGC2755515831/CoD_nacht/MAP_FILES/"
        "t7_concrete_poured_bunker_dirty_01.t7_concrete_poured_bunker_dirty_01")
def one_png(directory,name):
    x=list(directory.rglob(name))
    if len(x)!=1:
        raise ValueError("RED: missing or duplicate real Godot source PNG "+name)
    with Image.open(x[0]) as im:
        if im.size!=(960,540):
            raise ValueError("RED: changed original full-source camera size")
        return im.convert("RGB")

def measure(before,after):
    diff=ImageChops.difference(before,after)
    bb=before.tobytes()
    aa=after.tobytes()
    change=diff.tobytes()
    dark=0
    recovered=0
    changed=0
    left,right=int(960*0.15),int(960*0.85)
    top,bottom=int(540*0.12),int(540*0.88)
    for y in range(540):
        for x in range(960):
            pos=(y*960+x)*3
            if sum(change[pos:pos+3])>int(0.09*255):
                changed+=1
            if left<=x<right and top<=y<bottom and max(bb[pos:pos+3])<int(0.045*255):
                dark+=1
                if max(aa[pos:pos+3])>=int(0.08*255):
                    recovered+=1
    return {
        "originalBlackPixelsAtCenter":dark,
        "blackPixelsRecoveredByExactlyOneOriginalSourceMaterial":recovered,
        "significantlyChangedSourceFullFramePixels":changed,
        "changedSourceFullFramePercent":100*changed/(960*540),
        "colorMeanPercent":100*sum(change)/(len(change)*255)
    }

def run(root,owner_root,out):
    reports=list(root.rglob("two-exact-original-source-bunker-blackwall.json"))
    ranks=list(owner_root.rglob("nacht-real-original-574-source-material-screen-pixel-attribution.json"))
    if len(reports)!=1 or len(ranks)!=1:
        raise ValueError("RED missing original Godot source A/B report or independent material identity")
    d=json.loads(reports[0].read_text())
    r=json.loads(ranks[0].read_text())
    for key,want in {
        "realNativeOriginalSourceActorNodes":10793,
        "originalMaterialSurfaceBindings":16595,
        "sourceOriginalBoundDDS":718,
        "originalSourceLightComponents":166,
        "originalTargetSurfaceBindingsChangedTemporarily":2,
        "otherOriginalMaterialSurfaceBindingsUntouched":16593,
        "exactSourceBunkerMaterialPath":TARGET,
        "exactOriginalSourceMeshActorsOnly":["ue_instance_010576","ue_instance_010730"],
        "originalShaderResourceRestorationVerified":True,
        "otherSourceAlphaFoliageWindowsDecalMaterialsUnmodified":True,
        "productionBlackInteriorFixApproved":False,
    }.items():
        if d.get(key)!=want:
            raise ValueError("RED: original source 2 surface authority mismatch "+key)
    if r.get("actorCount")!=10793 or r.get("originalEffectiveMaterialPaths")!=574:
        raise ValueError("RED: full source per-pixel material ID 574 authority lost")
    high_rank=r["rankedOpaqueDiagnosticScreenSurfaceOwners"]
    source=[x for x in high_rank if x["sourceMaterialID"]==28]
    if len(source)!=1 or source[0]["originalSourceMaterialPath"]!=TARGET or source[0]["blackPixelsVisibleAfterForcingAllSourceGeometryOpaque"]<50000:
        raise ValueError("RED: selected bunker material not real original black wall owner")
    out.mkdir(parents=True,exist_ok=True)
    result=[]
    for camera in BASE:
        before=one_png(root,camera+"_bunker_original_DDS.png")
        after=one_png(root,camera+"_ONLY_bunker_2_surfaces_opaque_preview.png")
        row=measure(before,after)
        row["camera"]=camera
        godot_row=next(x for x in d["threeEyeHeightOriginalVsTwoSurfaceMaskDisabled"]
                       if x["cameraName"]==camera)
        if abs(row["blackPixelsRecoveredByExactlyOneOriginalSourceMaterial"]-
               godot_row["blackRecoveredByDisablingOnlyDiffuseAlphaScissor"])>300:
            raise ValueError("RED: source Godot original vs independent actual PNG dark-wall values inconsistent")
        merged=Image.new("RGB",(1920,576),(15,18,22))
        drawer=ImageDraw.Draw(merged)
        merged.paste(before,(0,36))
        merged.paste(after,(960,36))
        drawer.text((20,12),"ORIGINAL: original 718 DDS / 10793 objects",fill=(245,245,245))
        drawer.text((980,12),"EXACT concrete original only: 2 surface alpha off (RESEARCH)",fill=(245,245,245))
        merged.save(out/(camera+"-original-vs-exact-2-bunker-wall-source-DDS.png"))
        result.append(row)
    rest=measure(
        one_png(root,"interior_central_yaw180_bunker_original_DDS.png"),
        one_png(root,"interior_central_yaw180_bunker_source_original_restored.png"))
    if rest["significantlyChangedSourceFullFramePixels"]!=0 or rest["colorMeanPercent"]>0.01:
        raise ValueError("RED: original Godot 2-surface source materials not restored bitwise")
    total=sum(x["blackPixelsRecoveredByExactlyOneOriginalSourceMaterial"] for x in result)
    verdict={
        "originalMaterialID":28,
        "exactOriginalSourceMaterialPath":TARGET,
        "provenIndependentOpaqueDiagnosticBlackPixels":source[0]["blackPixelsVisibleAfterForcingAllSourceGeometryOpaque"],
        "originalSourceActorsUntouched":10793,
        "originalDDSUntouched":718,
        "exactOnlySourceActorIDs":["ue_instance_010576","ue_instance_010730"],
        "sourceMaterialSurfaceBindingsChangedReversibly":2,
        "originalOtherMaterialSourceBindingsUntouched":16593,
        "actualCameraResults":result,
        "sumRecoveredBlackPixelsAcrossThreeDifferentFramesNotUniquePixels":total,
        "originalMaterialRestorationRGB":rest,
        "notAllSourceOriginalOpacityMaskGraphEdgesRecovered":True,
        "allPlayerViewpointsAndWindowsNotCertified":True,
        "productionBlackInteriorFixApproved":False,
        "mobileFPSUnmeasured":True
    }
    (out/"nacht-two-source-bunker-black-pixels-independent-result.json").write_text(
        json.dumps(verdict,indent=2)+"\n")
    print("XZOGOT_NACHT_EXACT_SOURCE_BUNKER_MATERIAL_ONLY_3_CANDIDATE_CAMERA_PIXEL_AUDIT",total)
    for x in result:
        print(x["camera"],"recover",x["blackPixelsRecoveredByExactlyOneOriginalSourceMaterial"],
              "original",x["originalBlackPixelsAtCenter"])
    if total<1000 or result[0]["blackPixelsRecoveredByExactlyOneOriginalSourceMaterial"]<500:
        raise ValueError("RED: exact source #28 bunker material does not meaningfully recover interior darkness")
    print("XZOGOT_NACHT_SOURCE_BUNKER_CONCRETE_TWO_SURFACES_BLACK_PIXEL_RECOVERY_GREEN")
    return verdict

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--owners",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    run(a.source,a.owners,a.output)
