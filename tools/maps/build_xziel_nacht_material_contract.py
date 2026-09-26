#!/usr/bin/env python3
"""Normalize the Pavlov/BO3 Nacht material audit into an XZIEL material contract.

This contract is metadata-only. It preserves source texture semantics instead
of forcing Call of Duty/T7 channels into a metallic/roughness model.

Input:
  nacht-material-channel-report.json

Output:
  nacht-xziel-material-contract.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any

IDENTITY_NORMALS = {"flat_normal", "_identitynormalmap", "_normal", ""}
CONSTANTS = {"White", "_black_color", "AICON-Red", "flat_normal", "_identitynormalmap", "_normal"}

def suffix_role(name: str) -> str | None:
    low=name.lower()
    for suffix, role in (
        ("_c","color"),
        ("_n","normal"),
        ("_s","specular_or_aux_s"),
        ("_g","gloss_or_aux_g"),
        ("_r","aux_r"),
    ):
        if low.endswith(suffix):
            return role
    return None

def classify_material(name: str) -> str:
    low=name.lower()
    if "chalk" in low or "decal" in low:
        return "decal"
    if "water" in low:
        return "water"
    if "sky" in low:
        return "sky"
    if "caulk" in low or name.startswith("MasterMat"):
        return "utility"
    return "surface"

def unique(seq):
    out=[]
    seen=set()
    for x in seq:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("report", type=Path)
    ap.add_argument("output", type=Path)
    args=ap.parse_args()

    src=json.loads(args.report.read_text(encoding="utf-8"))
    rows=src.get("materials") or []
    materials=[]
    all_refs=set()
    class_counts=collections.Counter()
    true_normal_count=0
    flat_normal_count=0
    ambiguous_diffuse=[]

    for row in rows:
        name=row["material"]
        channels=dict(row.get("channels") or {})
        extras=list(row.get("other_textures") or [])
        refs=unique(list(channels.values())+extras)
        for ref in refs: all_refs.add(ref)

        diffuse=channels.get("Diffuse")
        normal=channels.get("Normal")
        normal_real=bool(normal and normal not in IDENTITY_NORMALS)
        if normal_real: true_normal_count+=1
        else: flat_normal_count+=1

        inferred=collections.defaultdict(list)
        for ref in refs:
            role=suffix_role(ref)
            if role: inferred[role].append(ref)

        if diffuse and suffix_role(diffuse) not in {None,"color"}:
            ambiguous_diffuse.append({"material":name,"diffuse_field":diffuse,"suffix_role":suffix_role(diffuse)})

        kind=classify_material(name)
        class_counts[kind]+=1
        requirements={
            "baseColor": bool(diffuse),
            "normal": normal_real,
            "alphaBlendOrMaskCandidate": kind=="decal",
            "transparentOrSpecialSurfaceCandidate": kind in {"decal","water"},
            "skySpecialCase": kind=="sky",
            "multilayerTextureInputs": len([r for r in refs if r not in CONSTANTS]) > 2,
        }
        materials.append({
            "name":name,
            "class":kind,
            "sourceChannels":channels,
            "sourceExtraTextures":extras,
            "textureReferences":refs,
            "inferredCandidates":dict(inferred),
            "normalPolicy":{
                "source":normal,
                "isIdentityFallback":not normal_real,
                "runtimeFallback":"flat_normal" if not normal_real else None,
            },
            "requirements":requirements,
            "semanticPolicy":{
                "preserveOriginalChannelNames":True,
                "doNotBlindlyMapSRGToMetallicRoughness":True,
                "note":"T7/ported material suffixes are retained as source semantics; map to an XZIEL shader only after per-family validation.",
            },
        })

    contract={
        "schemaVersion":1,
        "id":"nacht_bo3_reference_materials",
        "source":{
            "map":"Nacht der Untoten / zm_prototype reference",
            "audit":"Pavlov Workshop 2755515831 MAP_FILES via UE Viewer",
            "nonShippingReference":True,
            "containsTexturePayload":False,
        },
        "summary":{
            "materialCount":len(materials),
            "uniqueTextureReferenceCount":len(all_refs),
            "materialClassCounts":dict(class_counts),
            "realNormalMaterialCount":true_normal_count,
            "flatOrIdentityNormalMaterialCount":flat_normal_count,
            "explicitChannelCounts":src.get("channel_counts") or {},
            "sourceSuffixCounts":src.get("texture_suffix_counts") or {},
            "ambiguousDiffuseFieldCount":len(ambiguous_diffuse),
        },
        "runtimeContract":{
            "minimumMaterialTextureSlots":[
                "baseColor",
                "normal",
                "sourceAuxS",
                "sourceAuxG",
                "sourceAuxR",
                "maskOrOpacity",
                "emissive",
            ],
            "allowMultipleExtraTextures":True,
            "preserveSourceTextureNames":True,
            "requireSamplerSemanticMetadata":True,
            "identityNormalFallback":"flat_normal",
            "missingBaseColorFallback":"white",
            "notes":[
                "Do not collapse every material to one color texture.",
                "Do not infer metallic/roughness solely from T7 suffix letters.",
                "Decals/chalk require blend/mask-capable rendering.",
                "Water and sky require dedicated shader-family handling.",
            ],
        },
        "ambiguousDiffuseFields":ambiguous_diffuse,
        "materials":materials,
    }

    errors=[]
    if len(materials)!=src.get("material_count"):
        errors.append("material count changed during normalization")
    raw_refs=set()
    for row in rows:
        raw_refs.update((row.get("channels") or {}).values())
        raw_refs.update(row.get("other_textures") or [])
    if raw_refs != all_refs:
        errors.append("texture reference set changed during normalization")
    contract["validation"]={"ok":not errors,"errors":errors}

    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(contract,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(contract["summary"],indent=2))
    print(json.dumps(contract["validation"],indent=2))
    return 0 if not errors else 3

if __name__=="__main__":
    raise SystemExit(main())
