#!/usr/bin/env python3
"""Compare ORIGINAL COD4 gun skeleton joint names to its real XAnim tracks.

Only aggregate match scores are printed. No copyrighted bone names or raw
animation/keyframe bytes leave the private runner. This establishes whether
our original OAT glTF bones can be driven by decoded native IW3 XAnim.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from iw3_glb_to_iwvm import load_glb
from iw3_xanim_bones_v17 import decode
from iw3_match_oat_assets import parse_fields


def bone_names(glb:Path)->set[str]:
    data,_=load_glb(glb)
    nodes=data.get("nodes",[])
    skins=data.get("skins",[])
    result=set()
    for skin in skins:
        for idx in skin.get("joints",[]):
            if not isinstance(idx,int) or not 0<=idx<len(nodes):
                raise ValueError("Corrupt original glTF skeleton joint")
            name=nodes[idx].get("name")
            if isinstance(name,str) and len(name)<128:
                result.add(name.lower())
    return result


def probe(original_glb:Path,original_weapon_file:Path,extracted_animations:Path):
    joints=bone_names(original_glb)
    fields=parse_fields(original_weapon_file)
    source_anims=[]
    # WeaponDef fields such as reloadAnim, fireAnim, adsDownAnim. The asset
    # names come from the user's original COD4 installation, not guesses.
    for key,val in fields.items():
        if "anim" not in key.lower() or not isinstance(val,str) or not val:
            continue
        name=val.replace("\\","/").split("/")[-1]
        if name not in source_anims and len(name)<128:
            source_anims.append(name)
    # OAT exports some IW3 XAnim files with exporter suffixes. Match
    # case-insensitively, just as the verified global 977/977 asset audit:
    # exact asset name or original name followed by a dot-extension.
    animations={p.name.lower():p for p in extracted_animations.rglob("*")
                if p.is_file() and p.parent.name=="xanim"}
    scores=[]
    for name in source_anims:
        key=name.lower()
        source=animations.get(key)
        if source is None:
            source=next((p for label,p in animations.items()
                         if label.startswith(key+".")),None)
        if source is None:
            scores.append((0,0,False))
            continue
        anim=decode(source)
        keys={str(b["name"]).lower() for b in anim["bones"]}
        scores.append((len(joints.intersection(keys)),len(keys),True))
    return {
        "original_gun_skeleton_joint_count":len(joints),
        "original_weapon_anim_references":len(source_anims),
        "original_anim_files_found":sum(x[2] for x in scores),
        "original_anim_files_missing":sum(not x[2] for x in scores),
        "anims_sharing_skeleton_joints":sum(x[0]>0 for x in scores),
        "max_bone_name_overlap":max((x[0] for x in scores),default=0),
        "max_original_animation_bones":max((x[1] for x in scores),default=0),
        "original_materials_published":False,
        "original_bone_names_published":False,
        "live_skeletal_skinning_implemented":False,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--original-glb",type=Path,required=True)
    ap.add_argument("--original-weapondef",type=Path,required=True)
    ap.add_argument("--original-oat-root",type=Path,required=True)
    a=ap.parse_args()
    print(json.dumps(probe(a.original_glb,a.original_weapondef,
                           a.original_oat_root),indent=2))
