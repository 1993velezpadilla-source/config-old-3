#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


GENERIC_PROFILE={
    "schema":1,
    "name":"generic",
    "legacy_monja_targeting":False,
    "targeted_safety_regions":[],
    "surface_patches":[],
    "headspace_patch":None,
}


def _rect(value,name:str):
    if not isinstance(value,list) or len(value)!=4:
        raise ValueError(f"{name} must contain four normalized values")
    values=[float(v) for v in value]
    x0,y0,x1,y1=values
    if not (0.0<=x0<x1<=1.0 and 0.0<=y0<y1<=1.0):
        raise ValueError(f"{name} is outside normalized [0,1] space: {values}")
    return values


def load_asset_profile(path:Path|None):
    if path is None:
        return dict(GENERIC_PROFILE)
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if int(data.get("schema",0))!=1:
        raise ValueError(f"unsupported HAYUYA asset profile schema: {data.get('schema')}")
    out=dict(GENERIC_PROFILE)
    out.update(data)
    out["name"]=str(out.get("name") or Path(path).stem)
    out["legacy_monja_targeting"]=bool(out.get("legacy_monja_targeting",False))

    safety=[]
    for index,rect in enumerate(out.get("targeted_safety_regions") or []):
        safety.append(_rect(rect,f"targeted_safety_regions[{index}]"))
    out["targeted_safety_regions"]=safety

    patches=[]
    for index,spec in enumerate(out.get("surface_patches") or []):
        if not isinstance(spec,dict):
            raise ValueError(f"surface_patches[{index}] must be an object")
        item=dict(spec)
        item["name"]=str(item.get("name") or f"profile_patch_{index}")
        item["rect_norm"]=_rect(item.get("rect_norm"),f"surface_patches[{index}].rect_norm")
        mode=str(item.get("depth_mode","average"))
        if mode not in {"average","frontmost"}:
            raise ValueError(f"invalid depth_mode for surface_patches[{index}]: {mode}")
        item["depth_mode"]=mode
        item["depth_lift"]=float(item.get("depth_lift",0.00075))
        patches.append(item)
    out["surface_patches"]=patches

    selector=out.get("headspace_patch")
    if selector is not None:
        if not isinstance(selector,dict):
            raise ValueError("headspace_patch must be an object or null")
        selector=dict(selector)
        selector["rect_norm"]=_rect(selector.get("rect_norm"),"headspace_patch.rect_norm")
        selector["grid"]=int(selector.get("grid",1024))
        selector["area_min"]=int(selector.get("area_min",12))
        selector["area_max"]=int(selector.get("area_max",420))
        selector["edge_fill_radius"]=float(selector.get("edge_fill_radius",6.0))
        selector["depth_lift"]=float(selector.get("depth_lift",0.0015))
        selector["dilation_iterations"]=int(selector.get("dilation_iterations",1))
        if selector["grid"]<256:
            raise ValueError("headspace_patch.grid must be >=256")
        if selector["area_min"]<1 or selector["area_max"]<selector["area_min"]:
            raise ValueError("invalid headspace_patch area limits")
        out["headspace_patch"]=selector

    return out
