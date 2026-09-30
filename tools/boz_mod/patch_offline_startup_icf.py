#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

PATCH = {
    "SplashScreenMinTime": "0",
    "FastLoad": "1",
    "EnableOF": "0",
    "EnableAndroidMarketBilling": "0",
    "ResourceDownloader": "0",
    "BuyWithCODPointsActive": "0",
    "EnableFrontEndMTXStore": "0",
}

SECTION_FOR = {
    "SplashScreenMinTime": "S3E",
    "FastLoad": "GAME",
    "EnableOF": "GAME",
    "EnableAndroidMarketBilling": "GAME",
    "ResourceDownloader": "GAME",
    "BuyWithCODPointsActive": "GAME",
    "EnableFrontEndMTXStore": "GAME",
}

def parse_key(line: str):
    s=line.strip()
    if not s or s.startswith("#") or "=" not in s:
        return None
    return s.split("=",1)[0].strip()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    args=ap.parse_args()

    lines=args.input.read_text(encoding="latin1").splitlines()
    out=[]
    seen=set()
    section=None

    for line in lines:
        s=line.strip()
        if s.startswith("[") and s.endswith("]"):
            section=s[1:-1].strip().upper()
            out.append(line)
            continue

        key=parse_key(line)
        if key in PATCH:
            out.append(f"{key}={PATCH[key]}")
            seen.add(key)
        else:
            out.append(line)

    # Add missing keys to the end in explicit sections. Marmalade accepts
    # repeated section headers and later values override earlier ones.
    missing=[k for k in PATCH if k not in seen]
    if missing:
        by_section={}
        for key in missing:
            by_section.setdefault(SECTION_FOR[key],[]).append(key)
        out.append("")
        out.append("# XZIEL offline-startup diagnostic overrides")
        for sec,keys in by_section.items():
            out.append(f"[{sec}]")
            for key in keys:
                out.append(f"{key}={PATCH[key]}")

    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text("\n".join(out)+"\n",encoding="latin1")

    check=args.output.read_text(encoding="latin1")
    for key,val in PATCH.items():
        needle=f"{key}={val}"
        if needle not in check:
            raise SystemExit(f"missing override {needle}")

    print("XZIEL_BOZ_OFFLINE_STARTUP_PATCH_OK")
    for key,val in PATCH.items():
        print("PATCH",key,val)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
