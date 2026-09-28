#!/usr/bin/env python3
"""Rank interesting libGame.so symbols/strings for CTW 3D-camera work.

Works on an extracted user-owned arm64 libGame.so. It does not patch anything.
The report is used to turn binary discovery into a repeatable gate instead of
hard-coding guessed offsets.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

GROUPS = {
    "camera": re.compile(r"cam|camera|view|lookat|frustum|projection|fov|nearclip|farclip", re.I),
    "streaming": re.compile(r"stream|sector|worldblock|world|visible|visibility|cull|lod|distance", re.I),
    "player": re.compile(r"player|ped|weapon|skeleton|skin|render.*ped|draw.*ped", re.I),
}

def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return p.stdout if p.returncode == 0 else ""

def unique(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out

def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("usage: scan_libgame.py <libGame.so> [report.json]")
        return 2

    so = Path(sys.argv[1]).expanduser().resolve()
    if not so.is_file():
        print(f"DISCOVERY_RED: not found: {so}")
        return 2

    symbol_text = run(["readelf", "-Ws", str(so)])
    string_text = run(["strings", "-a", "-n", "5", str(so)])

    symbols = unique(
        line.strip() for line in symbol_text.splitlines()
        if any(rx.search(line) for rx in GROUPS.values())
    )
    strings = unique(
        line.strip() for line in string_text.splitlines()
        if any(rx.search(line) for rx in GROUPS.values())
    )

    report = {"file": so.name, "groups": {}}
    for group, rx in GROUPS.items():
        report["groups"][group] = {
            "symbols": [x for x in symbols if rx.search(x)][:500],
            "strings": [x for x in strings if rx.search(x)][:500],
        }

    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_text(json.dumps(report, indent=2), encoding="utf-8")

    total = sum(len(v["symbols"]) + len(v["strings"]) for v in report["groups"].values())
    print(f"DISCOVERY_GREEN candidates={total}")
    for group, data in report["groups"].items():
        print(f"{group}: symbols={len(data['symbols'])} strings={len(data['strings'])}")
        for line in data["symbols"][:8]:
            print(f"  S {line}")
        for line in data["strings"][:8]:
            print(f"  T {line}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
