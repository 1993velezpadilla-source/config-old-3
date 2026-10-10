#!/usr/bin/env python3
"""Download verified CC0 GLB hospital assets for Blender's offline author pass."""
import argparse
import hashlib
import json
import struct
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

def fetch(manifest_file,output,report_file):
    manifest=json.loads(Path(manifest_file).read_text())
    rows=manifest["assetSet"]
    if len(rows)!=4 or manifest.get("license")!="CC0-1.0":
        raise RuntimeError("BLACK_PINES_CC0_RED unauthorized manifest")
    target=Path(output)
    target.mkdir(parents=True,exist_ok=True)
    entries=[]
    for row in rows:
        u=urlparse(row["source"])
        if (u.scheme,u.netloc)!=("https","cdn.3dassets.dev") or not u.path.endswith("/model.glb"):
            raise RuntimeError("BLACK_PINES_CC0_RED source not allowlisted")
        req=urllib.request.Request(row["source"],headers={"User-Agent":"BlackPinesCC0GameAsset/1.0"})
        with urllib.request.urlopen(req,timeout=45) as response:
            raw=response.read(300001)
        if not 1000<len(raw)<300001:
            raise RuntimeError("BLACK_PINES_CC0_RED model size invalid: "+row["id"])
        magic,version,claimed=struct.unpack_from("<4sII",raw,0)
        if magic!=b"glTF" or version!=2 or claimed!=len(raw):
            raise RuntimeError("BLACK_PINES_CC0_RED not authentic glTF 2 binary: "+row["id"])
        digest=hashlib.sha256(raw).hexdigest()
        if row.get("sha256") and row["sha256"]!=digest:
            raise RuntimeError("BLACK_PINES_CC0_RED model changed since approval: "+row["id"])
        (target/(row["id"]+".glb")).write_bytes(raw)
        entries.append({"id":row["id"],"sha256":digest,"bytes":len(raw),"license":"CC0-1.0","assetPage":row["page"]})
        print("BLACK_PINES_CC0_DOWNLOADED id=",row["id"]," bytes=",len(raw)," sha256=",digest,flush=True)
    if report_file:
        p=Path(report_file)
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps({"assetSet":entries,"license":"CC0-1.0"},indent=2)+"\n")
    print("BLACK_PINES_CC0_FOUR_REAL_GLBS_GREEN count=4 valid_GLTF2=true license=CC0-1.0",flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--report",default="")
    args=p.parse_args()
    fetch(args.manifest,args.out,args.report)
