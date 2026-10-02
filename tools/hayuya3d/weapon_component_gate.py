#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ALIASES={
    "trigger":["trigger"],
    "slide":["slide","bolt"],
    "bolt":["bolt","slide"],
    "bolt_or_slide":["bolt","slide"],
    "magazine":["magazine","mag","clip"],
    "magazine_release":["magazinerelease","magrelease","magcatch"],
    "cylinder":["cylinder","drum"],
    "hammer":["hammer"],
    "ejector_rod":["ejector","ejectorrod"],
    "pump":["pump","foreend","forend","reload"],
    "tube":["tube","magazinetube","shelltube"],
    "loading_gate":["loadinggate","gate","lifter"],
    "shell_lifter":["shelllifter","lifter"],
    "bolt_handle":["bolthandle","handle"],
    "magazine_or_internal_mag":["magazine","mag","internalmag","floorplate"],
    "feed_cover":["feedcover","topcover","cover"],
    "belt_or_box":["belt","ammobox","boxmag","magazine"],
    "charging_handle":["charginghandle","handle"],
    "break_hinge":["hinge","break","breech"],
    "barrel_group":["barrel","barrels"],
    "breech":["breech","hinge"],
    "barrel":["barrel"],
    "safety":["safety"],
    "selector":["selector"],
    "bolt_release":["boltrelease"],
    "bullet":["bullet","bullets","round","rounds","shell"],
    "control":["control","root"],
}

def norm(v:str)->str:
    return re.sub(r"[^a-z0-9]+","",str(v).lower())

def infer_components(names:list[str])->list[str]:
    normalized=[norm(x) for x in names]
    found=set()
    for component,aliases in ALIASES.items():
        for alias in aliases:
            a=norm(alias)
            if any(a and a in n for n in normalized):
                found.add(component)
                break
    return sorted(found)

def resolve_family(spec:dict,value:str|None):
    target=str(value or "").strip().lower()
    if target in spec.get("families",{}):
        return target
    for fam,data in spec.get("families",{}).items():
        if target in [str(x).lower() for x in data.get("aliases",[])]:
            return fam
    return None

def inspect(report:dict,spec:dict,family_hint:str|None=None)->dict:
    names=[]
    names.extend(report.get("bone_names") or [])
    names.extend(report.get("mesh_names") or [])
    for arm in report.get("armatures") or []:
        names.extend(arm.get("bones") or [])
    components=infer_components(names)
    family=resolve_family(spec,family_hint or report.get("family_guess"))
    expected=[]
    if family:
        expected=list(spec["families"][family].get("expected_components",[]))
    missing=[x for x in expected if x not in components]
    # Some family requirements are conceptual aliases. Allow equivalent parts.
    equivalents={
        "bolt_or_slide":{"bolt_or_slide","bolt","slide"},
        "magazine_or_internal_mag":{"magazine_or_internal_mag","magazine"},
        "belt_or_box":{"belt_or_box","magazine"},
    }
    missing=[
        x for x in missing
        if not (x in equivalents and any(y in components for y in equivalents[x]))
    ]
    passed=bool(family) and not missing
    return {
        "schema":1,
        "family":family,
        "detected_components":components,
        "expected_components":expected,
        "missing_components":missing,
        "passed":passed,
        "one_tap_mechanical_ready":passed,
        "reason":"" if passed else ("unknown_weapon_family" if not family else "missing_required_mechanical_components"),
    }

def main()->int:
    p=argparse.ArgumentParser(description="Infer weapon moving components and gate mechanical animation compatibility.")
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--family")
    p.add_argument("--spec",type=Path,default=Path("hayuya/standards/hayuya_weapon_animation_v1.json"))
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    report=json.loads(a.report.read_text(encoding="utf-8"))
    spec=json.loads(a.spec.read_text(encoding="utf-8"))
    out=inspect(report,spec,a.family)
    payload=json.dumps(out,indent=2)
    print(payload)
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True)
        a.json.write_text(payload+"\n",encoding="utf-8")
    return 0 if out["passed"] else 2

if __name__=="__main__":
    raise SystemExit(main())
