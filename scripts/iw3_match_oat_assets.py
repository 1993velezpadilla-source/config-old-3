#!/usr/bin/env python3
"""Audit real IW3 WeaponDefs and match their references to extracted XModels/XAnims.

Only counts and boolean evidence can be published. Do not upload private
converted meshes, textures, native animations or raw weapon definition data.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

ANIMATION_FIELDS=("reloadAnim","reloadEmptyAnim","reloadStartAnim","reloadEndAnim",
                  "fireAnim","adsUpAnim","adsDownAnim","adsFireAnim",
                  "meleeAnim","raiseAnim","dropAnim")
MESH_FIELDS=("gunModel","gunModel2","handModel","worldModel")


def parse_fields(path: Path) -> dict[str,str]:
    raw=path.read_text(encoding="utf-8-sig",errors="replace").replace("\x00","")
    pairs=raw.split("\\")
    data={}
    # IW3 weapon source is an infostring with a WEAPONFILE prefix.
    if len(pairs)>3:
        for i in range(0,len(pairs)-1):
            k=pairs[i].strip().lstrip("\ufeff")
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,90}",k):
                continue
            value=pairs[i+1].strip()
            if value and "\n" not in value:
                data[k]=value
    else:
        for line in raw.splitlines():
            m=re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:=|\s)\s*(.*?)\s*",line)
            if m:
                data[m[1]]=m[2]
    return data


def report(root: Path) -> dict:
    weapon_defs=[p for p in root.rglob("*")
                 if p.is_file() and p.parent.name=="weapons"]
    xmodels={p.stem.lower() for p in root.rglob("*.glb")}
    glb_sample=sorted(xmodels)[:18]
    anims={p.name.lower() for p in root.rglob("*")
           if p.is_file() and p.parent.name=="xanim"}
    guns=0
    matched=0
    anims_linked=0
    gun_names=set()
    model_references=0
    anim_references=0
    sample=[]
    raw_model_values=[]
    cleaned_models=set()
    cleaned_matches=0
    for p in weapon_defs:
        fields=parse_fields(p)
        model=(fields.get("gunModel") or "").strip()
        if model:
            guns+=1
            key=model.replace("\\\\", "/").split("/")[-1].lower().removesuffix(".glb")
            if len(raw_model_values)<18 and model not in raw_model_values:
                raw_model_values.append(model[:90])
            canonical=key.replace("viewmodel_", "").replace("viewmodel", "")
            cleaned_models.add(canonical)
            if any(canonical and canonical in x for x in xmodels):
                cleaned_matches += 1
            gun_names.add(key)
            model_references+=1
            ok=key in xmodels
            if ok:
                matched+=1
                if len(sample)<10: sample.append(p.name)
        for name in ANIMATION_FIELDS:
            anim=(fields.get(name) or "").strip().lower()
            if not anim: continue
            anim_references+=1
            if anim in anims or any(a.startswith(anim+".") for a in anims):
                anims_linked+=1
    return {
        "source":"OAT 0.34.0 private extraction of user-owned original CoD4 IW3 fastfiles",
        "weapon_definitions":len(weapon_defs),
        "weapon_definitions_with_gunModel":guns,
        "unique_viewmodel_references":len(gun_names),
        "referenced_models_found_as_GLBS":matched,
        "animation_links_attempted":anim_references,
        "animation_links_resolved":anims_linked,
        "individual_matched_weapon_names_sample":sample,
        "debug_weapon_gunModel_values":raw_model_values,
        "debug_GLBS_basename_sample":glb_sample,
        "candidate_substring_matches":cleaned_matches,
        "native_vril_GL_render_tested":False,
        "copyrighted_files_uploaded":False,
    }


def main():
    if len(sys.argv)!=2:
        raise SystemExit("Usage: iw3_match_oat_assets.py <TEMP OAT extracted root>")
    root=Path(sys.argv[1])
    if not root.is_dir(): raise SystemExit("Missing private OAT output")
    print(json.dumps(report(root),indent=2))


if __name__=="__main__":
    main()
