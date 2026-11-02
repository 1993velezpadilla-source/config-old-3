#!/usr/bin/env python3
"""Locally mount OWNED IW3 XModel GLBs into the experimental Vril data ZIP.

No Activision data belongs in a public git commit/release or public APK.
Invoke locally (or temporary private CI) with a game installation you may use.

Manifest e.g.
[
 {"vril_viewmodel":"models/weapons/mp40/v_mp40.mdl",
  "iw3_glb":"common_mp/model_export/viewmodel_ak47_mp_lod0.glb",
  "scale":1.0}
]
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

from iw3_glb_to_iwvm import convert
MODEL = re.compile(r"^models/weapons/[a-zA-Z0-9_-]+/v_[a-zA-Z0-9_]+\.mdl$")
GLB = re.compile(r"^[a-zA-Z0-9_/-]+\.glb$")


def prepare(zipfile_path:Path, sources:Path, manifest:Path, dry_run=False):
    data=json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data,list) or not data:
        raise ValueError("Need nonempty explicit private weapon model map")
    outputs={}
    evidence=[]
    for rec in data:
        if not isinstance(rec,dict):raise ValueError("Malformed IW3 weapon mapping")
        old=rec.get("vril_viewmodel")
        model=rec.get("iw3_glb")
        scale=float(rec.get("scale",1))
        if not isinstance(old,str) or not MODEL.fullmatch(old):
            raise ValueError("Invalid original NZP Quake viewmodel path")
        if not isinstance(model,str) or not GLB.fullmatch(model):
            raise ValueError("Invalid CoD4 GLB path")
        if ".." in Path(model).parts:raise ValueError("Path traversal in GLB")
        stem=Path(old).stem
        native="models/iw3/"+stem+".iwvm"
        if native in outputs:raise ValueError("Duplicate native gun target")
        candidate=(sources/model).resolve()
        if not candidate.is_relative_to(sources.resolve()):
            raise ValueError("Weapon path escapes private input directory")
        if not candidate.is_file():
            raise ValueError(f"Missing privately supplied GLB: {model}")
        binary,info=convert(candidate,scale=scale)
        outputs[native]=binary
        evidence.append({"target":old,"native_mesh":native,"source_model":Path(model).stem,
                         **info})
    if not dry_run:
        if not zipfile_path.exists():raise ValueError("NZP runtime asset archive missing")
        with zipfile.ZipFile(zipfile_path,"a",compression=zipfile.ZIP_DEFLATED) as z:
            present=set(z.namelist())
            for dest,b in outputs.items():
                if dest in present:raise ValueError("Refusing duplicated source: "+dest)
                z.writestr(dest,b)
        # NZPActivity uses nzp-data.version to decide whether to extract
        # game files. Without a new checksum, installing a new private
        # weapon build over an existing test APK silently retains the old
        # files, so the rendered gun is never found by COM_FOpenFile().
        digest=hashlib.sha256()
        with zipfile_path.open("rb") as package:
            for block in iter(lambda: package.read(1<<20),b""):
                digest.update(block)
        zipfile_path.with_suffix(".version").write_text(
            digest.hexdigest()+"\\n",encoding="ascii")
    return evidence


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--game-data-zip",required=True,type=Path)
    a.add_argument("--glb-dir",required=True,type=Path)
    a.add_argument("--manifest",required=True,type=Path)
    a.add_argument("--report",type=Path)
    a.add_argument("--dry-run",action="store_true")
    args=a.parse_args()
    evidence=prepare(args.game_data_zip,args.glb_dir,args.manifest,args.dry_run)
    report={"weapons_converted":len(evidence),"local_package_only":True,
            "no_native_XAnim_yet":True,"entries":evidence}
    text=json.dumps(report,indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(text,encoding="utf-8")
    print(text)


if __name__=="__main__":
    main()
