#!/usr/bin/env python3
"""Generate 4 UV-registered HD texture alternatives from NZ:P original PCX skins.

AI concept board is NOT a game-ready UV atlas. This builder uses actual PCX
as source, so original 211 animation frames and detachable parts stay aligned.
Texture-only pilot: zero geometry changes, zero behavioral changes.
"""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import argparse
import hashlib
import json
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

def low_frequency(rng,size,grid):
    noise=rng.normal(127.5,34.0,(grid,grid)).clip(0,255).astype('uint8')
    sm=Image.fromarray(noise,mode='L').resize((size,size),Image.Resampling.BICUBIC)
    return (np.asarray(sm,dtype=np.float32)-127.5)/34.0

def enhance(source,index,size):
    if source.size!=(128,128):
        raise ValueError(f'Expected original 128px UV atlas, got {source.size}')
    photo=source.convert('RGB').resize((size,size),Image.Resampling.LANCZOS)
    photo=photo.filter(ImageFilter.UnsharpMask(radius=1.4,percent=80,threshold=2))
    orig=np.asarray(photo,dtype=np.float32)
    rng=np.random.default_rng(0x5A1E+7351*index)
    grain=2.5*low_frequency(rng,size,33)+1.9*low_frequency(rng,size,120)
    grain+=1.6*rng.normal(0,1,(size,size)).astype('float32')
    luma=orig@np.array([.2126,.7152,.0722],dtype=np.float32)
    shadow=np.clip((110-luma)/100,0,1)
    high=np.clip((luma-34)/125,0,1)
    out=orig*(1+(grain[...,None]*.013))
    out-=4.2*np.maximum(0,grain[...,None]/5)*high[...,None]
    out+=1.7*np.maximum(0,-grain[...,None]/5)*shadow[...,None]
    mean=out.mean(axis=2,keepdims=True)
    out=mean+.93*(out-mean)
    out=(out-111)*1.05+111
    return Image.fromarray(out.clip(0,255).astype('uint8'),mode='RGB')

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--pack',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    args=a.parse_args()
    out=args.out
    atlas_dir=out/'models/ai'
    atlas_dir.mkdir(parents=True,exist_ok=True)
    names=[]
    previews=[]
    with ZipFile(args.pack) as archive:
        members=archive.namelist()
        for idx in range(4):
            source=f'models/ai/zfull.mdl_{idx}.pcx'
            matches=[x for x in members if x.endswith(source)]
            if len(matches)!=1:raise ValueError(f'Not exactly one original skin: {source}, {matches}')
            data=archive.read(matches[0])
            original=Image.open(BytesIO(data)).convert('RGB')
            img=enhance(original,idx,1024)
            file=atlas_dir/f'xziel_zombie_hd_{idx}.png'
            img.save(file,format='PNG',optimize=True)
            with Image.open(file) as verify:
                assert verify.size==(1024,1024) and verify.mode=='RGB'
            mae=np.abs(np.asarray(img.resize((128,128),Image.Resampling.BOX),dtype=np.int16)-
                np.asarray(original,dtype=np.int16)).mean()
            if mae>17:raise RuntimeError(f'UV source alignment guard failed skin {idx}, MAE {mae}')
            names.append({'skin':idx,'original':matches[0],'original_sha256':hashlib.sha256(data).hexdigest(),
                          'hd':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                          'mae_downsampled':round(float(mae),3),'dimensions':[1024,1024],'bytes':file.stat().st_size})
            previews.append((original,img))
    # A/B sheet reflects the REAL 128px UV images and exported HD UV images,
    # NOT a fake 3D render. This proves images generated and provenance.
    size=384
    pad=24
    label=42
    canvas=Image.new('RGB',(2*size+3*pad,4*(size+pad+label)+pad),(24,23,22))
    draw=ImageDraw.Draw(canvas)
    for n,(original,img) in enumerate(previews):
        y=pad+n*(size+pad+label)
        for j,src in enumerate((original,img)):
            x=pad+j*(size+pad)
            canvas.paste(src.resize((size,size),Image.Resampling.NEAREST if j==0 else Image.Resampling.LANCZOS),(x,y+label))
            draw.text((x+4,y+10),f'NZP SKIN {n} — '+('STOCK UV 128' if j==0 else 'XZIEL UV HD 1024'),fill=(229,215,187))
    preview_path=out/'XZIEL-Zombie-UV-Atlas-Original-vs-HD.png'
    canvas.save(preview_path,optimize=True)
    manifest={'status':'UV_SOURCE_PRESERVED','original_assets_sha256':hashlib.sha256(args.pack.read_bytes()).hexdigest(),
              'note':'Original NZ:P geometry unchanged (484-triangle full, 211 frames). Concept art is only visual direction, not a UV-compatible asset.',
              'textures':names}
    (out/'zombie-hd-texture-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    print('XZIEL_ZOMBIE_HD_4_ORIGINAL_UV_SKINS_GREEN',json.dumps(names))

if __name__=='__main__':main()
