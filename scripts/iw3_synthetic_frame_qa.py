#!/usr/bin/env python3
"""Screenshot smoke: reject giant central diagnostic geometry and blank frames.

Checks screenshots of *synthetic-only* test, never validates COD4 appearance.
The native first-person mesh is separately asserted from Android logcat.
"""
from __future__ import annotations
import argparse,json
from PIL import Image

def audit(path):
    with Image.open(path) as src:
        src.load()
        im=src.convert("RGB")
        w,h=im.size
        if w<640 or h<360:raise ValueError("Invalid Android gameplay screenshot")
        # The old 4x4 prism appeared as a huge opaque pink/red square
        # around the crosshair. No test geometry should occupy that much.
        mid=im.crop((int(w*.15),int(h*.12),int(w*.77),int(h*.88)))
        total=mid.width*mid.height
        pink=0
        colors=set()
        step=max(1,int(total**.5)//130)
        for y in range(0,mid.height,step):
            for x in range(0,mid.width,step):
                r,g,b=mid.getpixel((x,y))
                if r>170 and g<90 and b<145 and r>g*2:
                    pink+=1
                colors.add((r//12,g//12,b//12))
        sampled=len(range(0,mid.height,step))*len(range(0,mid.width,step))
        ratio=pink/sampled
        return {"width":w,"height":h,"center_saturated_red_fraction":round(ratio,6),
                "scene_palette_bins":len(colors),
                "old_center_occluding_quad_rejected":ratio<.085,
                "nonblank_gameplay":len(colors)>50}
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("screenshot")
    a=p.parse_args()
    out=audit(a.screenshot)
    print(json.dumps(out,indent=2))
    assert out["old_center_occluding_quad_rejected"],"Large center red weapon placeholder still obscures screen"
    assert out["nonblank_gameplay"],"Android screenshot is blank or monochromatic"
