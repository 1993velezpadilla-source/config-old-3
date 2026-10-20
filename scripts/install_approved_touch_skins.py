#!/usr/bin/env python3
"""Restore the APPROVED September-29 XZIEL touch skins in native VRIL APK.

Exactly the assets already restored for XOGOT's latest_12 HUD are reused;
we must not accidentally replace them with the unrelated Nieobie glyph pack.
Special case: original Sep-29 FIRE WebP was corrupted, so the already
approved `hud_fire.png` fallback is authoritative. Likewise the approved
Jump PNG fallback fills a role not in the original 12-pack.

Outputs go under gfx/xziel/skin_*.png and coexist with original icons for
other gameplay, HUD editor, missing-texture fallback and weapon cards.
"""
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image, ImageStat

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"xogot/assets/hud/latest_12"
MAPPING={
    "ads":"hud_ads.webp",
    "adsfire":"hud_ads_fire.webp",
    "fire":"hud_fire.png",
    "reload":"hud_reload.webp",
    "jump":"hud_jump.png",
    "grenade":"hud_grenade.webp",
    "knife":"hud_knife.webp",
    "slide":"hud_slide.webp",
    "swap":"hud_swap.webp",
    "sprint":"hud_sprint.webp",
    "claw":"hud_claw.webp",
    "crouch":"hud_crouch.webp",
    "prone":"hud_prone.webp",
}
def main(out:Path):
    manifest=json.loads((SOURCE/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("set_name")!="xziel_hud_zombies_mobile_v1" or manifest.get("status")!="latest-approved":
        raise RuntimeError("Unexpected HUD source: refusing to invent/replace user-approved skins")
    if manifest.get("fire_fallback",{}).get("file")!="hud_fire.png":
        raise RuntimeError("Refusing corrupt Sep-29 FIRE skin")
    if manifest.get("jump_fallback",{}).get("file")!="hud_jump.png":
        raise RuntimeError("Approved Jump fallback missing")
    out.mkdir(parents=True,exist_ok=True)
    report={"source_set":manifest["set_name"],"status":"approved-real-user-artwork","skins":{}}
    for role,filename in MAPPING.items():
        source=SOURCE/filename
        if not source.is_file():
            raise FileNotFoundError("APPROVED_SKIN_MISSING: "+str(source))
        with Image.open(source) as im:
            rgba=im.convert("RGBA")
            # Preserve the user's authored sprite, only convert WebP to PNG.
            # No circles, labels, or decorative lookalikes get created here.
            if not 32<=rgba.width<=4096 or not 32<=rgba.height<=4096:
                raise RuntimeError("Invalid skin dimensions "+role+" "+str(rgba.size))
            if rgba.getbbox() is None:
                raise RuntimeError("Approved skin is fully transparent: "+role)
            # Prevent regression to blank/solid-color button art.
            extrema=rgba.getextrema()
            if max(c[1]-c[0] for c in extrema)<12:
                raise RuntimeError("Approved skin appears flat/invalid: "+role)
            dest=out/("skin_"+role+".png")
            rgba.save(dest,format="PNG",optimize=True)
            assert dest.stat().st_size>350, "Tiny/empty sprite: "+role
            report["skins"][role]={
                "source":str(source.relative_to(ROOT)),
                "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
                "png_sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),
                "resolution":[rgba.width,rgba.height],
                "bytes":dest.stat().st_size
            }
            print("APPROVED_NATIVE_SKIN_GREEN",role,source.name,
                  rgba.width,rgba.height,dest.stat().st_size)
    (out/"approved_hud_manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("XZIEL_LATEST12_APPROVED_NATIVE_HUD_GREEN",len(MAPPING))
if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: install_approved_touch_skins.py <nzp/gfx/xziel-dir>")
    main(Path(sys.argv[1]))
