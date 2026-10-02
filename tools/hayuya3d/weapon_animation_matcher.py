#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_family(spec: dict, name: str):
    target=name.strip().lower()
    if target in spec["families"]:
        return target
    for fam,data in spec["families"].items():
        if target in [str(x).lower() for x in data.get("aliases",[])]:
            return fam
    return None


def compatible(spec: dict, weapon: dict, clip: dict):
    family=resolve_family(spec, weapon.get("family",""))
    clip_families=[resolve_family(spec,x) or x for x in clip.get("families",[])]
    components=set(weapon.get("components",[]))
    reasons=[]
    if not family:
        reasons.append("unknown_weapon_family")
    if clip_families and family not in clip_families:
        reasons.append("family_mismatch")
    if family:
        allowed=set(spec["families"][family].get("allowed_events",[]))
        event=clip.get("event")
        if event and event not in allowed:
            reasons.append("event_not_allowed_for_family")
    missing=[x for x in clip.get("requires_components",[]) if x not in components]
    if missing:
        reasons.append("missing_components:"+",".join(missing))
    forbidden=[x for x in clip.get("forbids_components",[]) if x in components]
    if forbidden:
        reasons.append("forbidden_components_present:"+",".join(forbidden))
    return {
        "compatible":not reasons,
        "family":family,
        "event":clip.get("event"),
        "reasons":reasons
    }


def main():
    p=argparse.ArgumentParser(description="HAYUYA weapon animation compatibility gate")
    p.add_argument("--weapon",required=True,type=Path,help="JSON describing family/components")
    p.add_argument("--clip",required=True,type=Path,help="JSON clip metadata")
    p.add_argument("--spec",type=Path,default=Path("hayuya/standards/hayuya_weapon_animation_v1.json"))
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    result=compatible(load(a.spec),load(a.weapon),load(a.clip))
    payload=json.dumps(result,indent=2)
    print(payload)
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True)
        a.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if result["compatible"] else 2


if __name__=="__main__":
    raise SystemExit(main())
