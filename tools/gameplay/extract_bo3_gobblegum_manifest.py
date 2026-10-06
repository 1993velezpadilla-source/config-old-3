#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

REGISTER_RE = re.compile(
    r'bgb::register\(\s*"(?P<id>[^"]+)"\s*,\s*"(?P<limit_type>[^"]+)"\s*,\s*(?P<limit>[^,\)]+)'
    r'(?:\s*,\s*(?P<enable>[^,\)]+))?(?:\s*,\s*(?P<disable>[^,\)]+))?'
    r'(?:\s*,\s*(?P<validation>[^,\)]+))?(?:\s*,\s*(?P<activation>[^\)]+))?\)',
    re.MULTILINE,
)
FUNC_RE = re.compile(r'(?m)^function\s+(?:private\s+)?([A-Za-z0-9_]+)\s*\(')
USING_RE = re.compile(r'(?m)^#using\s+([^;]+);')
NUMBER_RE = re.compile(r'(?<![A-Za-z0-9_])(-?\d+(?:\.\d+)?)')
STRING_RE = re.compile(r'"([^"\r\n]{1,160})"')

def clean_ref(v: str | None) -> str | None:
    if v is None:
        return None
    v=v.strip()
    if v in {"undefined",""}:
        return None
    if v.startswith("&"):
        v=v[1:]
    return v

def parse_registration(text: str) -> list[dict]:
    rows=[]
    for m in REGISTER_RE.finditer(text):
        raw=m.group("limit").strip()
        try:
            limit=float(raw) if "." in raw else int(raw)
        except Exception:
            limit=raw
        rows.append({
            "id":m.group("id"),
            "limit_type":m.group("limit_type"),
            "limit":limit,
            "enable":clean_ref(m.group("enable")),
            "disable":clean_ref(m.group("disable")),
            "validation":clean_ref(m.group("validation")),
            "activation":clean_ref(m.group("activation")),
        })
    return rows

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-root",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--source-commit",default="")
    ns=ap.parse_args()
    root=ns.source_root
    gum_dir=root/"BO3-GSC/zm/bgbs"
    core=[
        root/"BO3-GSC/zm/_zm_bgb.gsc",
        root/"BO3-GSC/zm/_zm_bgb_machine.gsc",
        root/"BO3-GSC/zm/_zm_bgb_token.gsc",
    ]
    files=sorted(gum_dir.glob("*.gsc"))
    rows=[]
    for p in files:
        text=p.read_text(errors="ignore")
        regs=parse_registration(text)
        rows.append({
            "source_path":p.relative_to(root).as_posix(),
            "sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
            "registrations":regs,
            "functions":FUNC_RE.findall(text),
            "uses":USING_RE.findall(text),
            "numbers":sorted(set(NUMBER_RE.findall(text))),
            "strings":sorted(set(s for s in STRING_RE.findall(text) if len(s)<=100)),
            "bytes":p.stat().st_size,
        })
    core_rows=[]
    for p in core:
        text=p.read_text(errors="ignore")
        core_rows.append({
            "source_path":p.relative_to(root).as_posix(),
            "sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
            "functions":FUNC_RE.findall(text),
            "uses":USING_RE.findall(text),
            "numbers":sorted(set(NUMBER_RE.findall(text))),
            "strings":sorted(set(s for s in STRING_RE.findall(text) if len(s)<=100)),
            "bytes":p.stat().st_size,
        })
    registered=[r for row in rows for r in row["registrations"]]
    by_id={r["id"]:r for r in registered}
    report={
        "schema":1,
        "authority":"BO3 decompiled GSC source",
        "source_repo":"SyndiShanX/COD-GSC-Source",
        "source_commit":ns.source_commit,
        "gum_script_count":len(rows),
        "registered_gum_count":len(by_id),
        "registered_ids":sorted(by_id),
        "limit_type_counts":{},
        "core":core_rows,
        "gums":rows,
    }
    for r in by_id.values():
        k=r["limit_type"]
        report["limit_type_counts"][k]=report["limit_type_counts"].get(k,0)+1
    ns.output.parent.mkdir(parents=True,exist_ok=True)
    ns.output.write_text(json.dumps(report,indent=2)+"\n")
    print("XZOGOT_BO3_GOBBLEGUM_SOURCE",
          "scripts=",len(rows),
          "registered=",len(by_id),
          "limit_types=",report["limit_type_counts"])
    if len(rows) < 60 or len(by_id) < 55:
        raise SystemExit("GobbleGum source coverage unexpectedly incomplete")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
