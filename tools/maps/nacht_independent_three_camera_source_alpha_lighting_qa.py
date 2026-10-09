#!/usr/bin/env python3
"""Independent Pillow/RGB-byte validation of THREE original Nacht alpha vs light views.

Ten actual Godot 4.6.1 screenshots from unchanged full archived source.
Does NOT claim this diagnostic "unlit" or "opaque all" mode is shippable.
"""
import argparse
import json
from pathlib import Path

from PIL import Image

CAMERAS=("interior_central_yaw180","interior_original_yaw0","interior_original_yaw270")

def one(root, name):
    found=list(root.rglob(name))
    if len(found)!=1 or not found[0].is_file():
        raise ValueError("RED: missing or duplicate actual Godot source PNG "+name)
    with Image.open(found[0]) as src:
        image=src.convert("RGB")
        image.load()
    if image.size!=(960,540):
        raise ValueError("RED: Godot frame changed resolution")
    return image

def pixel_census(a,b,c):
    w,h=a.size
    original=alpha=light=remaining=0
    ar=a.load();br=b.load();cr=c.load()
    for y in range(int(h*.12),int(h*.88)):
        for x in range(int(w*.15),int(w*.85)):
            aa=ar[x,y]
            if max(aa)>=12:
                continue
            original+=1
            if max(br[x,y])>=21:
                alpha+=1
            elif max(cr[x,y])>=21:
                light+=1
            else:
                remaining+=1
    return {
        "sourceDarkROIPixels":original,
        "sourceDarkRevealedByMaskOff":alpha,
        "additionalSourceDarkRevealedByNoLight":light,
        "sourceDarkStillUnlitMaskedOpaque":remaining
    }

def audit(root,output):
    matches=list(root.rglob("alpha-vs-light-three-original-camera.json"))
    if len(matches)!=1:
        raise ValueError("RED: source Godot report not unique")
    d=json.loads(matches[0].read_text())
    expected={
        "nativeMeshActorNodes":10793,
        "nativeOriginalSourceSurfaceBindings":16595,
        "sourceAlphaScissorSurfacesTested":15372,
        "sourceDistinctMaskedMaterialResources":571,
        "originalLightsReconstructed":166,
        "sourceUsedDDSStaged":718,
        "originalSourceAssetFilesUnchanged":True,
        "shippingMaterialBehaviorNotModified":True,
        "originalBlackInteriorVisualArtApproved":False,
        "physicalAndroidFPSMeasured":False
    }
    for k,exp in expected.items():
        if type(d.get(k)) is not type(exp) or d[k]!=exp:
            raise ValueError("RED: source-material or shipping-safety authority changed "+k)
    rows={x["sourceCamera"]:x for x in d["threeRealCameraSourceMaterialAlphaAndLightingExperiments"]}
    if len(rows)!=3 or set(rows)!=set(CAMERAS):
        raise ValueError("RED: 3 original-source camera classifications absent")
    errors=[]
    observed={}
    output.mkdir(parents=True,exist_ok=True)
    for name in CAMERAS:
        a=one(root,name+"_source_as_is.png")
        b=one(root,name+"_only_source_mask_scissor_off.png")
        c=one(root,name+"_same_DDS_no_alpha_no_light.png")
        counted=pixel_census(a,b,c)
        official=rows[name]
        compare={
            "sourceDarkROIPixels":"originalNearBlackCenterROIPixels",
            "sourceDarkRevealedByMaskOff":"blackRecoveredByDisablingOnlyDiffuseAlphaScissor",
            "additionalSourceDarkRevealedByNoLight":"additionalBlackRecoveredBySuppressingLightingButKeepingSourceDDS",
            "sourceDarkStillUnlitMaskedOpaque":"blackRemainingEvenUnlitOpaqueWithSourceDDS"
        }
        for key,original_key in compare.items():
            if abs(counted[key]-int(official[original_key]))>500:
                errors.append(f"{name} Pillow/Godot black recovered pixel count disagreement {key}: {counted[key]} vs {official[original_key]}")
        if counted["sourceDarkRevealedByMaskOff"]<1000:
            errors.append(name+" no visible alpha mask-related loss")
        if counted["additionalSourceDarkRevealedByNoLight"]<1000:
            errors.append(name+" no additional measurable light-related darkness")
        # Keep original pixels in contact sheets, never retouch or draw fake walls.
        from PIL import ImageDraw
        sheet=Image.new("RGB",(960*3,540+44),(22,25,29))
        drawer=ImageDraw.Draw(sheet)
        for i,(label,img) in enumerate([
            ("Original archived Godot DDS",a),
            ("Same DDS + lighting, alpha cutoff OFF (research)",b),
            ("Same DDS unshaded, alpha OFF (research ONLY)",c)
        ]):
            sheet.paste(img,(i*960,44))
            drawer.text((i*960+12,15),label,fill=(255,255,255))
        sheet.save(output/(name+"-actual-DDS-original-mask-light.png"))
        observed[name]=counted
    before=one(root,"interior_central_yaw180_source_as_is.png")
    restored=one(root,"interior_central_yaw180_source_materials_restored.png")
    if before.tobytes()!=restored.tobytes():
        errors.append("source material restore failed exact 8-bit image equality")
    if d["postExperimentOriginalMaterialRestoreRGBDelta"]["changedSignificantPixels"]!=0:
        errors.append("Godot source original 10th image restoration control invalid")
    audit={
        "source":"real archived Pavlov UE4.21 original source, NOT original BO3 T7",
        "realNativeGodotSourceActorCount":10793,
        "originalSourceMaterialBindings":16595,
        "originalMaskedSurfacesSampled":15372,
        "uniqueOriginalMaskedEffectiveMaterials":571,
        "unchangedOriginalGodotDDSFiles":718,
        "originalSourceUE4Lights":166,
        "originalMaterialPtrsRevertedAndSourceImageExact":before.tobytes()==restored.tobytes(),
        "sourceCameraCaseStudy":observed,
        "errors":errors,
        "twoDistinctBlackMechanismsBothMeasurable":not errors,
        "globalAlphaScissorRemovalApproved":False,
        "unshadedProductionLightsApproved":False,
        "allReachableInteriorWindowsCertified":False,
        "originalBlackInteriorArtFixed":False,
        "physicalAndroidGPUFPSMeasured":False,
        "shippingApproved":False
    }
    (output/"Nacht-independent-3-camera-original-mask-vs-light-pixel-diagnosis.json").write_text(json.dumps(audit,indent=2)+"\n")
    if errors:
        raise ValueError("RED: "+repr(errors))
    print("XZOGOT_NACHT_REAL_THREE_CAMERA_ALPHA_AND_LIGHT_SEPARATE_ROOT_CAUSES_INDEPENDENT_GREEN",
          "exact_original_restoration=YES", "source_frames=10", "cameras=3")
    return audit

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    audit(args.source,args.output)
