#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

UA="HAYUYA/1.0 (asset research; GitHub Actions)"
WIKI="https://en.wikipedia.org/w/api.php"

FAMILY_PATTERNS=[
    ("shotgun_pump_tube",[
        r"pump[- ]action",r"pump shotgun",r"slide[- ]action"
    ]),
    ("shotgun_break_open",[
        r"break[- ]action",r"double[- ]barrel",r"over[- ]and[- ]under",r"side[- ]by[- ]side"
    ]),
    ("shotgun_semiauto_tube",[
        r"semi[- ]automatic shotgun",r"self[- ]loading shotgun",r"autoloading shotgun"
    ]),
    ("revolver",[r"revolver",r"rotating cylinder"]),
    ("rifle_bolt_action",[r"bolt[- ]action",r"turn[- ]bolt",r"straight[- ]pull"]),
    ("lmg_beltfed",[r"belt[- ]fed",r"machine gun"]),
    ("launcher",[r"rocket launcher",r"grenade launcher"]),
    ("handgun_semiauto",[r"semi[- ]automatic pistol",r"self[- ]loading pistol",r"automatic pistol"]),
    ("rifle_magazine",[r"assault rifle",r"carbine",r"submachine gun",r"semi[- ]automatic rifle"]),
]

def wiki(params:dict)->dict:
    q=urllib.parse.urlencode({**params,"format":"json","formatversion":2})
    req=urllib.request.Request(WIKI+"?"+q,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=12) as res:
        return json.loads(res.read().decode("utf-8"))

def search_title(query:str)->list[dict]:
    data=wiki({
        "action":"query","list":"search","srsearch":query,"srlimit":5,
        "srprop":"snippet|titlesnippet"
    })
    return data.get("query",{}).get("search",[]) or []

def page_extract(title:str)->dict:
    data=wiki({
        "action":"query","prop":"extracts|info","inprop":"url",
        "exintro":1,"explaintext":1,"redirects":1,"titles":title
    })
    pages=data.get("query",{}).get("pages",[]) or []
    return pages[0] if pages else {}

def infer_family(text:str)->tuple[str,float,list[str]]:
    t=text.lower()
    hits=[]
    for fam,patterns in FAMILY_PATTERNS:
        score=sum(1 for p in patterns if re.search(p,t,re.I))
        if score:
            hits.append((score,fam,patterns))
    if not hits:
        return "auto",0.0,[]
    hits.sort(reverse=True)
    top=hits[0]
    confidence=min(0.97,0.68+0.10*top[0])
    if len(hits)>1 and hits[1][0]==top[0]:
        confidence=max(0.45,confidence-0.22)
    matched=[p for p in top[2] if re.search(p,t,re.I)]
    return top[1],round(confidence,3),matched

def research(query:str,asset_profile:str,weapon_family:str)->dict:
    out={
        "schema":1,
        "query":query,
        "asset_profile":asset_profile,
        "requested_weapon_family":weapon_family,
        "adapter":"wikipedia_mediawiki",
        "sources":[],
        "inferred_weapon_family":"auto",
        "confidence":0.0,
        "matched_patterns":[],
        "summary":"",
        "warnings":[],
    }
    if not query.strip():
        out["warnings"].append("empty_query")
        return out
    try:
        hits=search_title(query)
        if not hits:
            out["warnings"].append("no_search_results")
            return out
        page=page_extract(str(hits[0].get("title") or query))
        extract=str(page.get("extract") or "")
        fullurl=str(page.get("fullurl") or "")
        title=str(page.get("title") or hits[0].get("title") or query)
        out["sources"].append({
            "title":title,
            "url":fullurl,
            "kind":"secondary_reference",
        })
        out["summary"]=extract[:5000]
        if asset_profile=="weapon.firearm":
            fam,conf,patterns=infer_family(title+"\n"+extract)
            out["inferred_weapon_family"]=fam
            out["confidence"]=conf
            out["matched_patterns"]=patterns
            if weapon_family and weapon_family!="auto" and fam!="auto" and fam!=weapon_family:
                out["warnings"].append(
                    f"explicit_family_conflicts_with_online_research:{weapon_family}!={fam}"
                )
            if fam=="auto":
                out["warnings"].append("weapon_family_not_resolved_from_research")
        else:
            out["confidence"]=0.7 if extract else 0.0
    except Exception as exc:
        out["warnings"].append(f"research_error:{type(exc).__name__}:{exc}")
    return out

def main()->int:
    p=argparse.ArgumentParser(description="HAYUYA online asset identity/mechanism research.")
    p.add_argument("--query",required=True)
    p.add_argument("--asset-profile",default="auto")
    p.add_argument("--weapon-family",default="auto")
    p.add_argument("--json",type=Path,required=True)
    a=p.parse_args()
    out=research(a.query,a.asset_profile,a.weapon_family)
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_RESEARCH",json.dumps({
        "query":out["query"],
        "family":out["inferred_weapon_family"],
        "confidence":out["confidence"],
        "sources":len(out["sources"]),
        "warnings":out["warnings"]
    },separators=(",",":")))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
