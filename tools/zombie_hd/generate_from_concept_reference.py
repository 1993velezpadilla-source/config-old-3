#!/usr/bin/env python3
"""Bake *generated* zombie concept art onto original NZ:P Quake UV atlas layout.

PROVENANCE: assets/zombie_hd/concept_diffuse_reference.b64 is compressed from
the actual image shown to the user earlier, not from original PCX upscaling.
Uses original PCX only for UV-layout orientation and alignment.
This is an experimental painted atlas, not a precise 3D projection bake.
"""
import argparse,base64,hashlib,io,json
from pathlib import Path
from zipfile import ZipFile
import cv2
import numpy as np
from PIL import Image,ImageDraw

def create(source,art,index,SZ=1024):
    scale=SZ/128
    original=cv2.cvtColor(np.asarray(source.resize((SZ,SZ),Image.Resampling.LANCZOS)),cv2.COLOR_RGB2BGR)
    # Restore reference's original crop coordinates from the compressed material
    # library (112x148 to 528x635); preserve face/cloth details spatially.
    ref=cv2.cvtColor(np.asarray(art.resize((528,635),Image.Resampling.LANCZOS)),cv2.COLOR_RGB2BGR)
    face_transform=np.asarray([[-.355,0,41+.355*349],[0,-.230,102+.230*80]],dtype=np.float32)*scale
    face=cv2.warpAffine(ref,face_transform,(SZ,SZ),
            flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT)
    Y,X=np.mgrid[0:SZ,0:SZ].astype(np.float32)
    U=X/scale;V=Y/scale
    face_mask=np.clip((1-(((U-33)/28)**4+((V-104)/21)**4))/.45,0,1).astype(np.float32)
    coat=ref[20:274,132:332]
    trousers=ref[335:602,6:116]
    arms=ref[345:585,130:220]
    def material(im,n):
        # Crop from GENERATED costume concept, NEVER resized original Quake PCX
        m=cv2.resize(im,(256,256),interpolation=cv2.INTER_CUBIC)
        m=np.roll(m,n*83,axis=0)
        m=np.roll(m,n*51,axis=1)
        return cv2.resize(m,(SZ,SZ),interpolation=cv2.INTER_CUBIC)
    jacket=material(coat,index)
    pants=material(trousers,index+3)
    gloves=material(arms,index+7)
    base=np.where(((V>.42*128)&(U>.49*128))[...,None],pants,jacket).astype(np.float32)
    base=np.where(((U<.29*128)&(V<.38*128))[...,None],gloves,base)
    gray=cv2.cvtColor(original,cv2.COLOR_BGR2GRAY).astype(np.float32)
    edge=np.clip((gray-cv2.GaussianBlur(gray,(0,0),8))/30,-1,1)[...,None]
    base=np.clip(base*(.91+.10*edge),0,255)
    base=base*.77+original*.23
    hole=(U>=77)&(U<=91)&(V<=31)
    base[hole]=0
    base=base*(1-face_mask[...,None])+face.astype(np.float32)*face_mask[...,None]
    result=Image.fromarray(cv2.cvtColor(base.clip(0,255).astype(np.uint8),cv2.COLOR_BGR2RGB))
    mae=float(np.abs(np.asarray(result.resize((128,128),Image.Resampling.BOX),dtype=np.float32)-
           np.asarray(source,dtype=np.float32)).mean())
    assert mae>16,(index,mae,"generated art not demonstrably different from stock texture")
    return result,mae

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--pack",type=Path,required=True)
    parser.add_argument("--concept-base64",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    b64=args.concept_base64.read_text().strip()
    art_bytes=base64.b64decode(b64,validate=True)
    art=Image.open(io.BytesIO(art_bytes)).convert("RGB")
    assert art.size==(112,148),("Generated source art unexpectedly sized",art.size)
    directory=args.out/"models/ai"
    directory.mkdir(parents=True,exist_ok=True)
    contact=Image.new("RGB",(1072,4*565),(24,23,22))
    d=ImageDraw.Draw(contact)
    manifest=[]
    with ZipFile(args.pack) as archive:
        for idx in range(4):
            oldname=f"nzp/models/ai/zfull.mdl_{idx}.pcx"
            original=Image.open(io.BytesIO(archive.read(oldname))).convert("RGB")
            result,mae=create(original,art,idx)
            filename=f"xziel_zombie_hd_{idx}.png"
            target=directory/filename
            result.save(target,format="PNG",optimize=True)
            assert Image.open(target).size==(1024,1024)
            manifest.append({"model_skin":idx,"source":oldname,
                "generated_png":filename,"measured_128px_MAE_from_stock":round(mae,2),
                "sha256":hashlib.sha256(target.read_bytes()).hexdigest()})
            y=idx*565
            contact.paste(original.resize((500,500),Image.Resampling.NEAREST),(20,y+52))
            contact.paste(result.resize((500,500)),(546,y+52))
            d.text((24,y+15),f"ORIGINAL 128 SKIN {idx}   ->   ACTUAL GENERATED CONCEPT TEXTURE (UV EXPERIMENT)",fill=(230,220,195))
    preview=args.out/"XZIEL-CONCEPT-ACTUAL-UV-vs-STOCK.png"
    contact.save(preview)
    metadata={"model":"stock UV layout; experimental hand-projected",
              "art":"genuine generated visual concept (compressed material reference)",
              "reference_sha256":hashlib.sha256(art_bytes).hexdigest(),
              "reference_size":list(art.size),
              "source_is_original_zombie_pcx_upscale":False,
              "screen_test":"not yet verified on Android",
              "skins":manifest}
    (args.out/"zombie-concept-manifest.json").write_text(json.dumps(metadata,indent=2)+"\n")
    print("XZIEL_GENERATED_CONCEPT_ART_USED_FOR_TRUE_NEW_UV_SKINS",metadata)

if __name__=="__main__":main()
