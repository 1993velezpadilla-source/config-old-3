#!/usr/bin/env python3
"""Fetch ORIGINAL CC0 4K Poly Haven materials for Sanctum's opening nave.

Never upscale legacy 128/256px NZ:P WAD textures and call them '4K'. The
physical 4096x4096 originals are kept as build evidence and the Quake BSP
receives separately downsampled 1024px LODs for Android. Full 4K GPU PBR is a
separate engine milestone; these WAD copies are not falsely advertised as it.

Poly Haven asset metadata: https://api.polyhaven.com/files/{asset_id}
Licensed CC0 by Poly Haven / listed original photographers.
"""
import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from PIL import Image, ImageEnhance, ImageStat

# Chosen for old church geometry, NOT generic 256px stone/wood.
ASSETS = {
    "sanctum_floor": ("monastery_stone_floor", .86),
    "sanctum_wall": ("medieval_blocks_03", .80),
    "sanctum_ceiling": ("stone_brick_wall_001", .66),
}

def fetch(url: str) -> bytes:
    parsed=urlparse(url)
    if parsed.scheme!="https" or not parsed.netloc:
        raise RuntimeError("Refusing untrusted material download URL")
    for retry in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent":"XZIEL-Sanctum-CC0-Texture-Build/1.0"}), timeout=50) as fh:
                payload=fh.read(35*1024*1024)
            if not payload:
                raise RuntimeError("Empty asset payload")
            return payload
        except Exception:
            if retry==2: raise
            time.sleep(2*(retry+1))
    raise AssertionError("unreachable")

def material(asset_id: str, original_dir: Path) -> tuple[Image.Image, dict]:
    doc=json.loads(fetch(f"https://api.polyhaven.com/files/{asset_id}"))
    diffuse=doc.get("Diffuse") or doc.get("diffuse")
    if not isinstance(diffuse,dict) or "4k" not in diffuse:
        raise RuntimeError(f"{asset_id}: no authentic 4K diffuse map")
    formats=diffuse["4k"]
    pick=formats.get("jpg") or formats.get("png")
    if not isinstance(pick,dict) or not pick.get("url"):
        raise RuntimeError(f"{asset_id}: missing downloadable 4K source")
    src=fetch(pick["url"])
    im=Image.open(io.BytesIO(src))
    im.load()
    if im.size!=(4096,4096):
        raise RuntimeError(f"{asset_id}: 4K asset is not actually 4096x4096: {im.size}")
    out=original_dir/f"{asset_id}.{'jpg' if 'jpg' in formats and formats.get('jpg') is pick else 'png'}"
    out.write_bytes(src)
    return im.convert("RGB"), {
        "polyhaven_id":asset_id,
        "license":"CC0",
        "source_url":pick["url"],
        "source_bytes":len(src),
        "source_sha256":hashlib.sha256(src).hexdigest(),
        "source_resolution":[4096,4096],
        "source_path":str(out),
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--wad-root",type=Path,required=True)
    parser.add_argument("--4k-evidence",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    args.wad_root.mkdir(parents=True,exist_ok=True)
    args.__dict__["4k_evidence"].mkdir(parents=True,exist_ok=True)
    report={"source_resolution":"4096x4096 ORIGINAL CC0",
            "runtime_bsp_resolution":"1024x1024 MOBILE LOD - NOT NATIVE 4K",
            "materials":{}}
    for target,(asset_id,exposure) in ASSETS.items():
        source,meta=material(asset_id,args.__dict__["4k_evidence"])
        # Quake BSP miptext has no PBR shader. LOD1024 guards memory/battery;
        # 4K untouched masters remain available for future Vulkan/Godot.
        mobile=source.resize((1024,1024),Image.Resampling.LANCZOS)
        mobile=ImageEnhance.Contrast(mobile).enhance(1.06)
        mobile=ImageEnhance.Brightness(mobile).enhance(exposure)
        stats=ImageStat.Stat(mobile)
        if min(stats.stddev)<8.0:
            raise RuntimeError(f"{target}: rejected low-detail flat surface")
        path=args.wad_root/f"{target}.png"
        mobile.save(path,format="PNG",optimize=True)
        meta.update(bsp_footprint_px=[1024,1024],bsp_file=str(path),
                    mobile_png_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    contrast=1.06,exposure=exposure,
                    mobile_stddev=[round(x,2) for x in stats.stddev])
        report["materials"][target]=meta
        print("SANCTUM_TRUE_SOURCE_4K_CC0_TO_MOBILE_LOD_GREEN",target,meta["source_resolution"],flush=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("SANCTUM_CC0_4K_MASTERS_VERIFIED_AND_LOD_GENERATED_GREEN",flush=True)

if __name__=="__main__":
    main()
