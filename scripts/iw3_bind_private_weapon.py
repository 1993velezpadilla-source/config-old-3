#!/usr/bin/env python3
"""Associate extracted REAL IW3 gunModel and WeaponDef pose with an NZ:P slot.

Private runner or locally-owned game data only. This tool writes a mapping
JSON and a copy of the matching original .weapon definition, WITHOUT placing
CoD4 content into the open-source repository or a public APK.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil

from iw3_match_oat_assets import parse_fields, model_key

QUAKE_MODEL = re.compile(r"^models/weapons/[a-zA-Z0-9_-]+/v_[a-zA-Z0-9_]+\.mdl$")


def bind_weapon(oat_root: Path, glb_name: str, quake_model: str,
                private_dir: Path) -> dict:
    if not QUAKE_MODEL.fullmatch(quake_model):
        raise ValueError("Expected existing NZ:P first-person Quake MDL path")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+_lod0\.glb", glb_name):
        raise ValueError("Expected an extracted original OAT LOD0 viewmodel filename")
    wanted = model_key(glb_name)
    candidates = []
    for asset in oat_root.rglob("*"):
        if not asset.is_file() or asset.parent.name != "weapons":
            continue
        fields = parse_fields(asset)
        if model_key(fields.get("gunModel", "")) == wanted:
            # Prefer weapon definition names belonging to real game guns,
            # not default camera, debug, character or other test assets.
            rank = sum(t in asset.name.lower() for t in ("default", "camera", "none"))
            candidates.append((rank, asset.name.lower(), asset, fields))
    if not candidates:
        raise ValueError(f"No original IW3 WeaponDef uses {wanted}")
    _, _, source, fields = sorted(candidates, key=lambda entry: entry[:2])[0]
    private_dir.mkdir(parents=True, exist_ok=True)
    destination = private_dir/"current.weapon"
    shutil.copyfile(source, destination)
    mapping = [{"definition": destination.name, "viewmodel": quake_model}]
    out = private_dir/"pose_mapping.json"
    out.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    return {
        "matched": True,
        "gunModel": wanted,
        "source_weapon_identifier": source.name,
        "numeric_pose_fields": sum(k in fields for k in (
            "standMoveF", "standMoveR", "standMoveU", "standRotP",
            "standRotY", "standRotR", "duckedOfsF", "proneOfsF")),
        "private_definition_dir": str(private_dir),
        "private_mapping": str(out),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original-oat-dir", type=Path, required=True)
    ap.add_argument("--original-glb-filename", required=True)
    ap.add_argument("--nzp-viewmodel", default="models/weapons/m1911/v_colt.mdl")
    ap.add_argument("--private-output-dir", type=Path, required=True)
    args = ap.parse_args()
    result=bind_weapon(args.original_oat_dir,args.original_glb_filename,
                       args.nzp_viewmodel,args.private_output_dir)
    # Print only source type/count; do not log raw original .weapon content.
    print(json.dumps({k:v for k,v in result.items()
                      if not k.startswith("private_")},indent=2))


if __name__=="__main__":
    main()
