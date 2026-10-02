#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FAMILY_REQUIRED={
    "handgun_semiauto":["trigger","slide","magazine"],
    "revolver":["trigger","cylinder"],
    "shotgun_pump_tube":["trigger","pump","tube"],
    "shotgun_semiauto_tube":["trigger","bolt","tube"],
    "shotgun_break_open":["trigger","barrel_group","break_hinge"],
    "rifle_magazine":["trigger","bolt_or_slide","magazine"],
    "rifle_bolt_action":["trigger","bolt_handle","magazine_or_internal_mag"],
    "lmg_beltfed":["trigger","bolt_or_slide","feed_cover","belt_or_box"],
    "launcher":["trigger"],
}

def _dist(a,b):
    return math.sqrt(sum((float(x)-float(y))**2 for x,y in zip(a,b)))

def _norm(v):
    m=math.sqrt(sum(float(x)*float(x) for x in v))
    return [float(x)/m for x in v] if m>1e-9 else [0.0,0.0,0.0]

def fit(part_map:dict,family:str)->dict:
    comps=list(part_map.get("components") or [])
    required=FAMILY_REQUIRED.get(family,[])
    out={
        "schema":1,
        "weapon_family":family,
        "status":"needs_vision_segmentation",
        "method":"hayuya-geometry-component-fit-v1",
        "required_components":required,
        "components":{},
        "warnings":[],
        "confidence":0.0,
        "mechanical_ready":False,
    }
    if not required:
        out["status"]="unknown_family"
        out["warnings"].append("unsupported_or_unresolved_weapon_family")
        return out
    if len(comps)<2:
        out["warnings"].append("single_connected_component_requires_semantic_segmentation")
        return out

    # Normalize component positions by global centroid/extents. The deterministic
    # geometry pass is deliberately conservative: it proposes candidates but only
    # promotes high-confidence disconnected parts. Vision masks / user confirmation
    # remain authoritative when topology is fused.
    main=max(comps,key=lambda c:int(c.get("face_count",0)))
    center=[float(x) for x in main.get("centroid",[0,0,0])]
    extent=[max(float(x),1e-9) for x in main.get("extent",[1,1,1])]
    long_axis=max(range(3),key=lambda i:extent[i])
    vert_axis=min(range(3),key=lambda i:extent[i]) if family!="revolver" else 1
    candidates=[c for c in comps if not c.get("main_component")]

    def rel(c):
        cc=[float(x) for x in c.get("centroid",[0,0,0])]
        return [(cc[i]-center[i])/extent[i] for i in range(3)]

    def score_mag(c):
        r=rel(c); f=float(c.get("face_fraction",0))
        below=max(0.0,-r[vert_axis])
        near=max(0.0,1.0-abs(r[long_axis]))
        size=1.0 if 0.005<=f<=0.20 else 0.3
        return 0.45*below+0.30*near+0.25*size

    def score_forward(c):
        r=rel(c); f=float(c.get("face_fraction",0))
        along=abs(r[long_axis])
        size=1.0 if 0.01<=f<=0.25 else 0.35
        return 0.65*along+0.35*size

    def score_center_small(c):
        r=rel(c); f=float(c.get("face_fraction",0))
        near=max(0.0,1.0-sum(abs(x) for x in r)/3.0)
        size=1.0 if 0.001<=f<=0.12 else 0.25
        return 0.65*near+0.35*size

    def pick(name,fn,threshold=0.72):
        if not candidates:
            return None
        ranked=sorted(((fn(c),c) for c in candidates),key=lambda x:x[0],reverse=True)
        score,c=ranked[0]
        if score<threshold:
            return None
        axis=[0.0,0.0,0.0]
        axis[long_axis]=1.0
        return {
            "component_id":int(c["component_id"]),
            "target_type":"component",
            "target_name":f"component_{int(c['component_id'])}",
            "confidence":round(float(min(score,0.95)),3),
            "centroid":c.get("centroid"),
            "extent":c.get("extent"),
            "axis":axis,
        }

    mapping={}
    if family in {"handgun_semiauto","rifle_magazine","rifle_bolt_action"}:
        x=pick("magazine",score_mag)
        if x:
            mapping["magazine" if family!="rifle_bolt_action" else "magazine_or_internal_mag"]=x

    if family=="revolver":
        x=pick("cylinder",score_center_small,0.78)
        if x: mapping["cylinder"]=x

    if family=="shotgun_pump_tube":
        x=pick("pump",score_forward,0.76)
        if x: mapping["pump"]=x

    if family=="shotgun_break_open":
        x=pick("barrel_group",score_forward,0.76)
        if x: mapping["barrel_group"]=x

    # Trigger/bolt/hinge inference from pure disconnected topology is too risky.
    # Keep them unresolved until semantic masks, object/bone names or editor
    # confirmation provide real evidence.
    out["components"]=mapping
    detected=set(mapping)
    aliases={
        "bolt_or_slide":{"bolt_or_slide","bolt","slide"},
        "magazine_or_internal_mag":{"magazine_or_internal_mag","magazine"},
        "belt_or_box":{"belt_or_box","magazine"},
    }
    missing=[]
    for req in required:
        if req in detected:
            continue
        if req in aliases and any(x in detected for x in aliases[req]):
            continue
        missing.append(req)

    if mapping:
        out["status"]="partial_fit"
        out["confidence"]=round(sum(v["confidence"] for v in mapping.values())/len(mapping),3)
    if not missing and mapping:
        out["status"]="fit_ready"
        out["mechanical_ready"]=True
    else:
        out["warnings"].append("unresolved_components:"+",".join(missing))
    out["missing_components"]=missing
    return out

def main()->int:
    p=argparse.ArgumentParser(description="Conservative HAYUYA firearm mechanical-part fitter.")
    p.add_argument("--part-map",required=True,type=Path)
    p.add_argument("--family",required=True)
    p.add_argument("--json",required=True,type=Path)
    a=p.parse_args()
    data=json.loads(a.part_map.read_text(encoding="utf-8"))
    out=fit(data,a.family)
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_MECHANICAL_PART_FIT",json.dumps({
        "family":a.family,
        "status":out["status"],
        "confidence":out["confidence"],
        "mapped":sorted(out["components"]),
        "missing":out.get("missing_components",[])
    },separators=(",",":")))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
