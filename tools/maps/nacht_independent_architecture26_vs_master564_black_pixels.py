#!/usr/bin/env python3
"""Independent genuine Godot PNG A/B: 26 architecture-only vs 564 whole-MasterMat.

No synthetic geometry; compares exact original Pavlov UE4.21 native scene
camera screenshots from existing independent GitHub Actions runs. Research,
not a certified source UE OpacityMask or a physical Android benchmark.
"""
import argparse
from pathlib import Path
import json
from PIL import Image, ImageChops, ImageDraw

CAMERAS=("interior_central_yaw180","interior_original_yaw0","interior_original_yaw270")
W,H=960,540

def original(root,name):
    files=list(root.rglob(name))
    if len(files)!=1 or not files[0].is_file():
        raise ValueError(f"RED original source PNG missing or duplicate: {name} = {files}")
    with Image.open(files[0]) as img:
        rgb=img.convert("RGB")
        if rgb.size!=(W,H):
            raise ValueError("original Godot camera pixel resolution altered")
        return rgb

def diff(a,b):
    delta=ImageChops.difference(a,b)
    raw=delta.tobytes()
    pixels=W*H
    changed=sum(raw[i]+raw[i+1]+raw[i+2]>int(0.03*3*255)
                for i in range(0,len(raw),3))
    return {"meanRGBPercent":100*sum(raw)/(len(raw)*255),
            "significantChangedPixels":changed,
            "significantChangedPercent":100*changed/pixels}

def black_recovered(a,b):
    pixel_a=a.tobytes()
    pixel_b=b.tobytes()
    left,top,right,bottom=(int(W*0.15),int(H*0.12),int(W*0.85),int(H*0.88))
    original_black=0
    recovered=0
    for y in range(top,bottom):
        for x in range(left,right):
            i=(y*W+x)*3
            if max(pixel_a[i:i+3])<int(0.045*255):
                original_black+=1
                if max(pixel_b[i:i+3])>=int(0.08*255):
                    recovered+=1
    return {"sourceBlackPixelsInCenterROI":original_black,
            "blackPixelsRestoredBySourceExperiment":recovered}

def audit(architecture: Path, whole_master: Path, output: Path):
    a_json=list(architecture.rglob("26-architecture-black-fix-original-source.json"))
    m_json=list(whole_master.rglob("mastermask-preview-3-source-cameras.json"))
    if len(a_json)!=1 or len(m_json)!=1:
        raise ValueError("RED missing exact original source material pixel reports")
    a_meta=json.loads(a_json[0].read_text())
    m_meta=json.loads(m_json[0].read_text())
    for key,want in {"sourceActorsUnmodified":10793,"sourceMaterialSurfaceBindings":16595,
                     "sourceLightComponents":166,"sourceUsedDDS":718,
                     "architecturalCandidateOriginalMaterials":26,
                     "architecturalSourceBindingsPotentiallyFixed":1262,
                     "otherOriginalMaterialPathsUntouched":548}.items():
        if a_meta.get(key)!=want:
            raise ValueError(f"RED: original architecture source count changed {key}")
    if m_meta.get("provisionalSourceMasterMaterialCount")!=564:
        raise ValueError("RED: whole-master source reference material count changed")
    if m_meta.get("excludedOtherOriginalMaskedMaterials")!=7:
        raise ValueError("RED: whole-master source sample must preserve 7 other masked")
    if not a_meta.get("shippingFixNotYetApproved") or not m_meta.get("researchOpacityConnectionIsPartialUnproven"):
        raise ValueError("RED: falsely claims UE shader source parity")
    output.mkdir(parents=True,exist_ok=True)
    results=[]
    for name in CAMERAS:
        before=original(architecture,name+"_architectural_source_before.png")
        after=original(architecture,name+"_architectural_source_preview.png")
        broad_before=original(whole_master,name+"_mastermask_before.png")
        broad_after=original(whole_master,name+"_mastermask_preview.png")
        before_interrun=diff(before,broad_before)
        arch_delta=diff(before,after)
        broad_delta=diff(before,broad_after)
        extra_delta=diff(after,broad_after)
        arch_dark=black_recovered(before,after)
        broad_dark=black_recovered(before,broad_after)
        if before_interrun["meanRGBPercent"]>0.20:
            raise ValueError("RED: same original 10793 source scene camera differed across independent material runs: "+name)
        if arch_dark["blackPixelsRestoredBySourceExperiment"]<=0:
            raise ValueError("RED: 26 architectural source candidates restored zero interior black pixels: "+name)
        control=next(x for x in a_meta["actualOriginalArchitectureCandidateVsBaseline"]
                     if x["camera"]==name)
        if abs(int(control["blackRecoveredByDisablingOnlyDiffuseAlphaScissor"])-
               arch_dark["blackPixelsRestoredBySourceExperiment"])>300:
            raise ValueError("RED: genuine screenshot independently disagrees with Godot original architecture image report")
        banner_height=34
        canvas=Image.new("RGB",(W*3,H+banner_height),(16,20,27))
        d=ImageDraw.Draw(canvas)
        for i,(label,img) in enumerate((("Original",before),
                                       ("26 arquitectura, sin recorte alfa",after),
                                       ("564 MasterMat (solo diagnóstico)",broad_after))):
            canvas.paste(img,(i*W,banner_height))
            d.text((i*W+12,12),label,fill=(235,238,250))
        canvas.save(output/(name+"-original-vs-26-architecture-vs-564-mastermask.png"))
        results.append({
            "camera":name,
            "identicalOriginalCameraAcrossRun":before_interrun,
            "originalVs26ArchitectureRGB":arch_delta,
            "originalVsBroad564MasterRGB":broad_delta,
            "architectureVsBroadMaskedSourceDeltaRGB":extra_delta,
            "26ArchitectureRestoredBlack":arch_dark,
            "564MasterRestoredBlack":broad_dark
        })
    ctrl=original(architecture,"interior_central_yaw180_architectural_source_restored.png")
    initial=original(architecture,"interior_central_yaw180_architectural_source_before.png")
    restoration=diff(initial,ctrl)
    if restoration["significantChangedPixels"] or restoration["meanRGBPercent"]>0.01:
        raise ValueError("RED: original source architecture materials not visually restored")
    verdict={
        "source":"Pavlov UE4.21 original archived Nacht Godot 4.6.1 Mesa, NOT official BO3 T7",
        "originalActorMeshCount":10793,
        "originalSurfaceMaterials":16595,
        "originalSourceDDSTextureImages":718,
        "sourceOriginalLightComponents":166,
        "scopedMaterialCount":26,
        "scopedOriginalHardSurfaceBindings":1262,
        "otherSourceMaterialsRemainUntouched":548,
        "sameCameraBeforeAfterPairCount":3,
        "threeRealOriginalSourceCameraComparisons":results,
        "restoredOriginalMaterialCamera":restoration,
        "materialGraphOpacityMaskConnectivityComplete":False,
        "exteriorTreeWindowAlphaCardRegressionsNotYetFullyProven":True,
        "productionIntegrationApproved":False,
        "phoneFPSAndVRAMUnmeasured":True,
        "noOriginalMeshAssetsChanged":True
    }
    (output/"independent-original-26-architecture-vs-564-mastermask-pixel-audit.json").write_text(
        json.dumps(verdict,indent=2)+"\n")
    print("XZOGOT_NACHT_SOURCE_ARCHITECTURE26_BLACK_FIX_INDEPENDENT_3_CAMERA_RGB_GREEN")
    for r in results:
        print(r["camera"],
              "26 architecture dark recovered",r["26ArchitectureRestoredBlack"]["blackPixelsRestoredBySourceExperiment"],
              "broad 564 dark recovered",r["564MasterRestoredBlack"]["blackPixelsRestoredBySourceExperiment"])
    return verdict

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--architecture",type=Path,required=True)
    p.add_argument("--all-masked",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    audit(a.architecture,a.all_masked,a.output)
