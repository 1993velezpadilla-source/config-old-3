#!/usr/bin/env python3
"""Validate glTF material-to-original-IW3-DDS links without exporting textures.

OpenAssetTools 0.34 glTF exporter writes baseColorTexture + normalTexture
with ../images/<name>.dds URIs. GLB geometry alone cannot render original
textures. This probe checks the real original DDS paths, counts only.
No game images/GLBs exported from private analysis.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import argparse,json,urllib.parse

from iw3_glb_to_iwvm import load_glb


def probe(path:Path, extraction_root:Path):
    descriptor,_=load_glb(path)
    materials=descriptor.get("materials",[])
    textures=descriptor.get("textures",[])
    images=descriptor.get("images",[])
    root=extraction_root.resolve()
    stats=Counter()
    checked=[]
    for m in materials:
        stats["materials"]+=1
        for texture_name in ("baseColorTexture","normalTexture"):
            if texture_name=="baseColorTexture":
                info=(m.get("pbrMetallicRoughness") or {}).get(texture_name)
            else:
                info=m.get(texture_name)
            if not info:continue
            stats["material_texture_references"]+=1
            idx=info.get("index")
            if not isinstance(idx,int) or not 0<=idx<len(textures):
                stats["broken_texture_index"]+=1
                continue
            image_idx=textures[idx].get("source")
            if not isinstance(image_idx,int) or not 0<=image_idx<len(images):
                stats["broken_image_index"]+=1
                continue
            image=images[image_idx]
            uri=image.get("uri","")
            if not isinstance(uri,str) or uri.startswith(("http://","https://","data:")):
                stats["non_local_uri"]+=1
                continue
            uri=urllib.parse.unquote(uri)
            if not uri.lower().endswith((".dds",".png",".jpg",".jpeg")):
                stats["unknown_image_format"]+=1
                continue
            candidate=(path.parent/uri).resolve()
            if not candidate.is_relative_to(root):
                stats["image_outside_original_extraction"]+=1
                continue
            stats["valid_original_material_uri"]+=1
            if candidate.is_file() and candidate.stat().st_size:
                stats["original_texture_file_present"]+=1
                checked.append(candidate.name)
            else:
                stats["texture_file_missing"]+=1
    return {"glb_materials":len(materials),"statistics":dict(stats),
            "textures_retrieved":False,"original_texture_names_not_exported":True,
            "all_references_resolved":stats["material_texture_references"]>0
               and stats["original_texture_file_present"]==stats["material_texture_references"]}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--original-extraction-root",type=Path,required=True)
    ap.add_argument("--glb",type=Path,required=True)
    args=ap.parse_args()
    print(json.dumps(probe(args.glb,args.original_extraction_root),indent=2))


if __name__=="__main__":
    main()
