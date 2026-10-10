#!/usr/bin/env python3
"""Inventory real archived Pavlov material/texture authority without guessing.

Read the SAME material/texture manifests already consumed by Xogot's
xziel_benchmark_loader.gd. Report exact paths, schemas and linkage readiness.
Do not treat .dds existence as a binding. Does not export copyrighted assets.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path

REQUIRED = (
    "material-binding-manifest.json",
    "xzml-report.json",
    "xzmi-report.json",
    "complete-xztx-report.json",
)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args=p.parse_args()
    paths={name:[] for name in REQUIRED}
    dds_samples=[]
    textures=0
    for base,dirs,files in os.walk(args.root):
        for fname in files:
            if fname in paths:
                paths[fname].append(Path(base)/fname)
            if fname.lower().endswith(".dds"):
                textures+=1
                if len(dds_samples)<12:
                    dds_samples.append(str((Path(base)/fname).relative_to(args.root)))
    report={"authority":"archived Pavlov UE4.21 - not original BO3 T7",
            "source_dds_files":textures,
            "source_dds_samples":dds_samples,
            "manifests":{}, "failures":[]}
    for name, candidates in paths.items():
        manifests=[]
        for file in candidates:
            d=json.loads(file.read_text(encoding="utf-8"))
            info={"path":str(file.relative_to(args.root)),
                  "size_bytes":file.stat().st_size,
                  "top_keys":sorted(d),
                  "summary":d.get("summary",{}),
                  "ready":d.get("ready"),
                  "counts":{},"samples":{}}
            for field in ("meshes","materials","instanceOverrides","textureAssets",
                          "materialPaths","textures","instances","bindings"):
                value=d.get(field)
                if isinstance(value,list):
                    info["counts"][field]=len(value)
                    if value and field in ("meshes","materials","textureAssets","instanceOverrides"):
                        info["samples"][field]=value[:2]
            manifests.append(info)
        report["manifests"][name]=manifests
        if not manifests:
            report["failures"].append("MISSING: "+name)
    out=args.out
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,default=str)+"\n")
    print("XZOGOT_NACHT_ARCHIVED_AUTHORITY_MANIFEST_INVENTORY",
          "dds",textures,
          "manifest_counts",{k:len(v) for k,v in report["manifests"].items()})
    for name,files in report["manifests"].items():
        for row in files:
            print("XZOGOT_NACHT_AUTHORITY_MANIFEST_PATH",name,row["path"],
                  "counts",json.dumps(row["counts"]), "top_keys",row["top_keys"])
    if report["failures"]:
        print("XZOGOT_NACHT_ARCHIVED_AUTHORITY_MANIFEST_INCOMPLETE",
              json.dumps(report["failures"]))
    else:
        print("XZOGOT_NACHT_ARCHIVED_SOURCE_MATERIAL_AND_TEXTURE_METADATA_GREEN")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
