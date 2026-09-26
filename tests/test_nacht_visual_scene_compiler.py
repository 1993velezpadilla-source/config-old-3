#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "assets/nacht_reference/pavlov_scene_reference"
TOOL = ROOT / "tools/maps/compile_nacht_visual_scene.py"


def make_glb(path: Path) -> None:
    doc = {
        "asset": {"version": "2.0"},
        "meshes": [{"primitives": [{}]}],
    }
    payload = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    total = 12 + 8 + len(payload)
    raw = (
        struct.pack("<III", 0x46546C67, 2, total)
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
    )
    path.write_bytes(raw)


assets = json.loads((REF / "assets.json").read_text(encoding="utf-8"))
assert assets["uniqueMeshCount"] == 492
assert len(assets["meshes"]) == 492

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    meshes = td / "meshes"
    meshes.mkdir()
    for row in assets["meshes"]:
        name = row["sourcePath"].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        make_glb(meshes / f"{name}.glb")

    out = td / "xziel.visual.scene.json"
    proc = subprocess.run(
        [
            "python3", str(TOOL),
            "--mesh-root", str(meshes),
            "--output", str(out),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format"] == "xziel_visual_scene_v1"
    assert payload["summary"]["requiredMeshCount"] == 492
    assert payload["summary"]["resolvedMeshCount"] == 492
    assert payload["summary"]["sceneInstanceCount"] == 10791
    assert payload["summary"]["referencedMeshCount"] == 492
    assert payload["summary"]["geometryReady"] is True
    assert payload["summary"]["visualParityReady"] is False
    assert len(payload["meshes"]) == 492
    assert len(payload["instances"]) == 10791

    victim = meshes / (
        assets["meshes"][-1]["sourcePath"].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        + ".glb"
    )
    victim.unlink()
    bad = subprocess.run(
        [
            "python3", str(TOOL),
            "--mesh-root", str(meshes),
            "--output", str(out),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert bad.returncode != 0, bad.stdout
    assert "missing exported GLBs" in bad.stdout, bad.stdout

print("XZIEL_NACHT_VISUAL_SCENE_TEST_OK meshes=492 instances=10791 missing_asset_gate=PASS")
