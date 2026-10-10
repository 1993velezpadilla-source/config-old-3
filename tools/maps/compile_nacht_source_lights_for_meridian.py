#!/usr/bin/env python3
"""Adapt exactly archived Nacht UE4.21 environment/light authorities to Godot.

The staged gameplay pipeline uses nacht-environment-report.json + nacht-lights.json
rather than xzen-report.json. Both are source CUE4Parse outputs. This bridge
retains IDs, actor world positions, rotations, colors, zero intensities and
source-authored spot cone values; it refuses missing or mismatched authority.
Not an original BO3 T7 provenance or visual-pixel equivalence claim.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

SUPPORTED={"point","spot","directional","sky"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--environment",type=Path,required=True)
    p.add_argument("--source-lights",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    env=json.loads(a.environment.read_text())
    orig=json.loads(a.source_lights.read_text())
    rows=env.get("lights",[])
    originals=orig.get("lights",[])
    if len(rows)!=166 or len(originals)!=166:
        raise ValueError(f"original Nacht staged source light coverage env={len(rows)} raw={len(originals)} expected=166")
    indexed={str(x.get("id","")):x for x in originals}
    if len(indexed)!=166 or "" in indexed:
        raise ValueError("duplicate/empty CUE4Parse light source IDs")
    adapted=[]
    type_count=Counter()
    spot_adjust=0
    for row in rows:
        iid=str(row.get("id",""))
        if iid not in indexed:
            raise ValueError("environment source light missing exact raw UE ID: "+iid)
        kind=str(row.get("componentType",""))
        if kind not in SUPPORTED:
            raise ValueError("unhandled original UE source light class "+kind)
        raw=indexed[iid]
        info=dict(row)
        if kind=="spot":
            props=raw.get("properties",{})
            for key in ("outerConeAngleDegrees","innerConeAngleDegrees"):
                if key in row:
                    continue
                if key not in props:
                    raise ValueError(f"authored {key} missing for source spot light {iid}")
                info[key]=props[key]
            spot_adjust+=1
        if len(info.get("worldPositionMeters",[]))!=3:
            raise ValueError("source light world translation absent "+iid)
        if "intensity" not in info or "color" not in info:
            raise ValueError("source light authored intensity/color missing "+iid)
        type_count[kind]+=1
        adapted.append(info)
    if set(indexed)!={str(x["id"]) for x in adapted}:
        raise ValueError("original UE4.21 source/raw light IDs not identical")
    output={
        "format":"XZOGOT_NACHT_ORIGINAL_UE421_SOURCE_LIGHT_ADAPTER_V1",
        "authority":"original archived Pavlov UE4.21 source env/raw lights, NOT original BO3 T7",
        "lights":adapted,
        "lightCount":166,
        "sourceGame":"UE4.21",
        "sourceLightCounts":dict(type_count),
        "spotConesCopiedFromOriginalUEProperties":spot_adjust,
        "sourcePositionOffsetsInvented":0,
        "sourceIntensitiesInvented":0,
        "claimsIdenticalRenderedLighting":False,
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(output,indent=2)+"\n")
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps({
        "total_original_light_identities":len(indexed),
        "env_and_raw_source_ids_identical":True,
        "type_counts":dict(type_count),
        "spot_source_cones_preserved":spot_adjust,
        "zero_source_intensities":sum(abs(float(x["intensity"]))<1e-8 for x in adapted),
        "all_source_world_positions_preserved":True,
        "visual_equivalence_proven":False,
    },indent=2)+"\n")
    print("XZOGOT_NACHT_166_SOURCE_UE_LIGHTS_EXACT_AUTHORITY_ADAPTER_GREEN",
          "source_lights",len(adapted),"types",dict(type_count),
          "real_spot_cones",spot_adjust)


if __name__=="__main__":
    main()
