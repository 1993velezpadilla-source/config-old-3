#!/usr/bin/env python3
"""Install a REAL converted animated Hotstrike zombie into NZ:P Android data.

Not an FBX converter: requires a retargeted Quake MDL based on the actual
author mesh, never the 8,284-face stock benchmark. Verify APK after Gradle
with scripts/guard_hotstrike_real_zombie.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from guard_hotstrike_real_zombie import (
    mdl_header, sha, verify_author_source, verify_real_conversion,
    verify_png, ProvenanceError,
)

TARGET = "nzp/models/ai/zfull.mdl"
TEXTURES = tuple(f"nzp/models/ai/xziel_zombie_hd_{i}.png" for i in range(4))
PROOF = "nzp/models/ai/xziel_hotstrike_import_provenance.json"


def install(source, stock, mdl_path, png_path, game_data_path):
    source_info = verify_author_source(source)
    base = stock.read_bytes()
    actual = mdl_path.read_bytes()
    image = png_path.read_bytes()
    geometry = verify_real_conversion(actual, base)
    image_info = verify_png(image)
    if not game_data_path.is_file():
        raise ProvenanceError("Missing game data zip: " + str(game_data_path))
    game_data_path.parent.mkdir(parents=True, exist_ok=True)
    tmpname = None
    try:
        with tempfile.NamedTemporaryFile(prefix="real-zombie-", suffix=".zip",
                                         dir=game_data_path.parent, delete=False) as handle:
            tmpname = Path(handle.name)
        with ZipFile(game_data_path) as original, ZipFile(tmpname, "w", allowZip64=True) as output:
            if original.namelist().count(TARGET) != 1:
                raise ProvenanceError("Expected exactly one stock zfull.mdl in prepared game archive")
            if original.read(TARGET) != base:
                raise ProvenanceError("Stock model changed before real import; refusing mismatch")
            for entry in original.infolist():
                if entry.filename in (TARGET, PROOF, *TEXTURES):
                    continue
                if entry.is_dir():
                    output.writestr(entry, b"")
                else:
                    with original.open(entry) as inp, output.open(entry, "w") as out:
                        shutil.copyfileobj(inp, out, 1024*1024)
            output.writestr(TARGET, actual)
            for p in TEXTURES:
                output.writestr(p, image)
            report = {
                "status": "REAL_MODEL_STAGED_NOT_DEVICE_VERIFIED",
                "author": "Hotstrike Studio, Free Stylized Dark Fantasy Zombie",
                "author_source_zip_sha256": source_info["sha256"],
                "converted_model_sha256": sha(actual),
                "texture_sha256": sha(image),
                "converted_geometry": geometry,
                "converted_texture": image_info,
                "note": "Further APK parity and Pixel Fold 3D animation/hitbox validation required",
            }
            output.writestr(PROOF, json.dumps(report, indent=2)+"\n")
        with ZipFile(tmpname) as check:
            if check.testzip() is not None:
                raise ProvenanceError("Broken rebuilt ZIP")
            if check.namelist().count(TARGET) != 1:
                raise ProvenanceError("New model duplicate in final game ZIP")
            if check.read(TARGET) != actual:
                raise ProvenanceError("Model lost during ZIP packaging")
            for name in TEXTURES:
                if check.namelist().count(name) != 1 or check.read(name) != image:
                    raise ProvenanceError("One of 4 zombie skin slots is missing or stale: "+name)
        os.replace(tmpname, game_data_path)
        tmpname = None
        checksum = sha(game_data_path.read_bytes())
        (game_data_path.parent / "nzp-data.version").write_text(checksum+"\n")
        print("XZIEL_REAL_ZOMBIE_STAGED_NOT_DEVICE_GREEN", json.dumps(report))
        return report
    finally:
        if tmpname is not None:
            tmpname.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-zip",type=Path,required=True)
    p.add_argument("--stock-mdl",type=Path,required=True)
    p.add_argument("--converted-mdl",type=Path,required=True)
    p.add_argument("--diffuse-png",type=Path,required=True)
    p.add_argument("--game-data",type=Path,required=True)
    args=p.parse_args()
    try:
        install(args.source_zip,args.stock_mdl,args.converted_mdl,
                args.diffuse_png,args.game_data)
    except (ProvenanceError,OSError,ValueError) as exc:
        p.exit(1, "XZIEL_REAL_ZOMBIE_STAGE_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    main()
