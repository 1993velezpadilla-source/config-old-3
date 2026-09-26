#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/nacht_reference/pavlov_scene_reference/assets.json"
TOOL = ROOT / "tools/maps/audit_nacht_visual_payload.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(TOOL), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def physical_package(source: str) -> str:
    assert source.startswith("/Game/")
    parts = PurePosixPath(source[len("/Game/"):].strip("/")).parts
    assert len(parts) >= 2
    return "Pavlov/Content/" + PurePosixPath(*parts[:-1]).as_posix() + ".uasset"


assets = json.loads(ASSETS.read_text(encoding="utf-8"))
assert assets["uniqueMeshCount"] == 492
assert len(assets["meshes"]) == 492

selfcheck = run("--self-check")
assert selfcheck.returncode == 0, selfcheck.stdout
assert '"expectedUniqueMeshes": 492' in selfcheck.stdout, selfcheck.stdout
assert '"expectedUniquePackages": 492' in selfcheck.stdout, selfcheck.stdout

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    index = td / "pak-list.txt"
    report = td / "report.json"

    lines = []
    packages = []
    for i, row in enumerate(assets["meshes"]):
        entry = physical_package(row["sourcePath"])
        packages.append(entry.lower())
        display = "../../../" + entry
        if i % 2:
            display = display.replace("/", "\\")
        lines.append(f'"{display}" offset={i * 4096} size=4096')

    assert len(set(packages)) == 492
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok = run("--pak-index", str(index), "--report", str(report), "--strict")
    assert ok.returncode == 0, ok.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["summary"] == {
        "expected": 492,
        "resolved": 492,
        "missing": 0,
        "payloadReady": True,
    }, payload

    index.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    bad = run("--pak-index", str(index), "--report", str(report), "--strict")
    assert bad.returncode == 2, bad.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["summary"]["resolved"] == 491, payload
    assert payload["summary"]["missing"] == 1, payload
    assert payload["summary"]["payloadReady"] is False, payload

print("XZIEL_NACHT_VISUAL_PAYLOAD_TEST_OK packages=492 object_path_mapping=PASS strict_missing_gate=PASS")
