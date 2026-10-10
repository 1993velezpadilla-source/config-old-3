#!/usr/bin/env python3
"""Inventory real archived Pavlov UE4.21 718 source-used compressed DDS.

No resizing, lossy import, texture guessing or "mobile FPS" claims.
DDS header parsing follows standard DDS_HEADER + optional DX10 extension.
Report exact on-disk sum and approximate RGBA8 decoded upper-bound only.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct

DXGI_FORMATS = {
    2:"R32G32B32A32_FLOAT",10:"R16G16B16A16_FLOAT",28:"R8G8B8A8_UNORM",
    29:"R8G8B8A8_UNORM_SRGB",71:"BC1_UNORM",72:"BC1_UNORM_SRGB",
    74:"BC2_UNORM",75:"BC2_UNORM_SRGB",77:"BC3_UNORM",78:"BC3_UNORM_SRGB",
    80:"BC4_UNORM",81:"BC4_SNORM",83:"BC5_UNORM",84:"BC5_SNORM",
    95:"BC6H_UF16",96:"BC6H_SF16",98:"BC7_UNORM",99:"BC7_UNORM_SRGB",
}
def inspect_dds(path):
    with path.open("rb") as f:
        head=f.read(148)
    if len(head)<128 or head[:4]!=b"DDS ":
        raise ValueError("invalid original DDS signature: "+str(path))
    if struct.unpack_from("<I",head,4)[0]!=124:
        raise ValueError("invalid original DDS header size: "+str(path))
    w=struct.unpack_from("<I",head,16)[0]
    h=struct.unpack_from("<I",head,12)[0]
    n=struct.unpack_from("<I",head,28)[0] or 1
    fourcc=head[84:88].decode("ascii",errors="replace").strip("\x00")
    if not 0<w<=32768 or not 0<h<=32768 or not 0<n<=20:
        raise ValueError("bad original DDS dimensions/mips: "+str(path))
    fmt=fourcc or "UNCOMPRESSED"
    if fourcc=="DX10":
        if len(head)<148:
            raise ValueError("truncated original DX10 DDS: "+str(path))
        val=struct.unpack_from("<I",head,128)[0]
        fmt=DXGI_FORMATS.get(val,"DXGI_"+str(val))
    decoded=0
    for i in range(n):
        decoded+=max(1,w>>i)*max(1,h>>i)*4
    return {"width":w,"height":h,"mipCount":n,"format":fmt,
            "fileBytes":path.stat().st_size,"rgba8MipUpperBoundBytes":decoded}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--xzml",type=Path,required=True)
    p.add_argument("--dds",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    rep=json.loads(a.xzml.read_text())
    entries=rep.get("textureAssets",[])
    if not rep.get("ready") or len(entries)!=718:
        raise ValueError("expected 718 exactly authored and genuinely used source texture assets")
    files={}
    for row in entries:
        runtime=str(row.get("runtimeFile",""))
        if not runtime:
            raise ValueError("missing original source DDS runtimeFile")
        name=Path(runtime).stem+".dds"
        if name in files:
            raise ValueError("duplicate source DDS file maps to two original texture identities")
        file=a.dds/name
        if not file.is_file():
            raise ValueError("original source texture DDS missing: "+name)
        files[name]=inspect_dds(file)
    if len(files)!=718:
        raise ValueError("not all 718 original used DDS files audited")
    exact_bytes=sum(r["fileBytes"] for r in files.values())
    predicted_rgba=sum(r["rgba8MipUpperBoundBytes"] for r in files.values())
    formats=Counter(r["format"] for r in files.values())
    dimensions=Counter(str(r["width"])+"x"+str(r["height"]) for r in files.values())
    tier=Counter()
    tier_bytes=Counter()
    for row in files.values():
        largest=max(row["width"],row["height"])
        label= "8K+" if largest>4096 else "4K" if largest>2048 else "2K" if largest>1024 else "1K" if largest>512 else "512px and below"
        tier[label]+=1
        tier_bytes[label]+=row["fileBytes"]
    result={
        "authority":"actual archived Pavlov UE4.21 scene DDS - NOT original BO3 T7",
        "source_used_DDS_assets":718,
        "exact_source_used_compressed_DDS_bytes":exact_bytes,
        "source_compressed_MiB":round(exact_bytes/(1024*1024),3),
        "source_DDS_all_decoded_RGBA8_MIP_upper_bound_bytes":predicted_rgba,
        "source_DDS_decoded_RGBA8_MiB_estimate":round(predicted_rgba/(1024*1024),3),
        "texture_formats":dict(formats),
        "source_dimensions_top":dict(dimensions.most_common(25)),
        "resolution_tiers":dict(tier),
        "source_bytes_by_resolution_tier":dict(tier_bytes),
        "largest_20_compressed_original_assets":[{"runtimeDDS":name,**attrs}
            for name,attrs in sorted(files.items(),key=lambda x:x[1]["fileBytes"],reverse=True)[:20]],
        "unmodified_original_assets":True,
        "RGAB8EstimateIsNotActualAndroidGpuFootprint":True,
        "DDSNativeAndroidSupportNotProven":True,
        "android_astc_etc2_transcode_not_performed":True,
        "mobile_memory_FPS_playable_not_proven":True,
        "mobile_APK_binary_size_measured":False,
        "source_image_count_with_integrity_errors":0,
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print("XZOGOT_NACHT_718_SOURCE_DDS_NATIVE_MOBILE_ASSET_INVENTORY_GREEN",
          "textures",718,"total_compressed_MiB",result["source_compressed_MiB"],
          "RGBA8_upper_bound_MiB",result["source_DDS_decoded_RGBA8_MiB_estimate"],
          "formats",dict(formats),"tiers",dict(tier))
    if exact_bytes>512*1024*1024:
        print("XZOGOT_NACHT_MOBILE_DDS_ASSET_VOLUME_OVER_512_MIB_AMBER",
              "IMPORTANT: need targeted mobile texture transcode/mip streaming, not yet shipped")

if __name__=="__main__":
    main()
