#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/maps/audit_nacht_texture_payload.py"

report = {
    "materials": [
        {
            "material": "wall",
            "channels": {
                "Diffuse": "brick_c",
                "Normal": "brick_n",
            },
            "other_textures": ["brick_s"],
        },
        {
            "material": "utility",
            "channels": {
                "Diffuse": "White",
                "Normal": "_identitynormalmap",
            },
            "other_textures": [],
        },
    ]
}

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    src = td / "materials.json"
    images = td / "images"
    out = td / "audit.json"
    images.mkdir()

    src.write_text(json.dumps(report), encoding="utf-8")
    (images / "brick_c.tga").write_bytes(b"x")
    (images / "brick_n.png").write_bytes(b"x")
    (images / "brick_s.dds").write_bytes(b"x")

    ok = subprocess.run(
        [
            "python3", str(TOOL),
            str(src), str(images), str(out),
            "--strict",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert ok.returncode == 0, ok.stdout
    payload = json.loads(out.read_text())
    assert payload["summary"]["referencedUniqueTextures"] == 5
    assert payload["summary"]["builtinReferences"] == 2
    assert payload["summary"]["externalReferences"] == 3
    assert payload["summary"]["resolvedExternalReferences"] == 3
    assert payload["summary"]["missingExternalReferences"] == 0
    assert payload["summary"]["strictReady"] is True

    (images / "brick_s.dds").unlink()
    bad = subprocess.run(
        [
            "python3", str(TOOL),
            str(src), str(images), str(out),
            "--strict",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert bad.returncode == 2, bad.stdout
    payload = json.loads(out.read_text())
    assert payload["summary"]["missingExternalReferences"] == 1
    assert payload["missing"] == ["brick_s"]

print("XZIEL_NACHT_TEXTURE_PAYLOAD_TEST_OK strict_missing_gate=PASS")
