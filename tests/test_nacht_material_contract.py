#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/maps/build_xziel_nacht_material_contract.py"

report = {
    "material_count": 4,
    "channel_counts": {
        "Diffuse": 4,
        "Normal": 4,
        "SpecPower": 1,
        "Opacity": 1,
    },
    "texture_suffix_counts": {
        "_c": 4,
        "_n": 2,
        "_s": 1,
        "_g": 1,
    },
    "unique_texture_refs": 9,
    "materials": [
        {
            "material": "zm_prototype_chalk_decal",
            "channels": {
                "Diffuse": "chalk_buy_arak_c",
                "Normal": "chalk_buy_arak_n",
                "Opacity": "chalk_buy_arak_g",
            },
            "other_textures": ["chalk_buy_arak_s"],
        },
        {
            "material": "zm_prototype_water_surface",
            "channels": {
                "Diffuse": "water_c",
                "Normal": "water_n",
            },
            "other_textures": ["water_g"],
        },
        {
            "material": "zm_prototype_sky",
            "channels": {
                "Diffuse": "sky_c",
                "Normal": "flat_normal",
            },
            "other_textures": [],
        },
        {
            "material": "MasterMatUtility",
            "channels": {
                "Diffuse": "White",
                "Normal": "_identitynormalmap",
                "SpecPower": "utility_s",
            },
            "other_textures": [],
        },
    ],
}

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    src = td / "report.json"
    out = td / "contract.json"
    src.write_text(json.dumps(report), encoding="utf-8")

    proc = subprocess.run(
        ["python3", str(TOOL), str(src), str(out)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["validation"]["ok"] is True
    assert payload["summary"]["materialCount"] == 4
    assert payload["runtimeContract"]["preserveSourceTextureNames"] is True
    assert payload["runtimeContract"]["requireSamplerSemanticMetadata"] is True

    by_name = {row["name"]: row for row in payload["materials"]}
    assert by_name["zm_prototype_chalk_decal"]["class"] == "decal"
    assert by_name["zm_prototype_chalk_decal"]["requirements"]["alphaBlendOrMaskCandidate"] is True
    assert by_name["zm_prototype_water_surface"]["class"] == "water"
    assert by_name["zm_prototype_sky"]["class"] == "sky"
    assert by_name["MasterMatUtility"]["class"] == "utility"
    assert by_name["zm_prototype_sky"]["normalPolicy"]["isIdentityFallback"] is True
    assert by_name["zm_prototype_chalk_decal"]["semanticPolicy"]["doNotBlindlyMapSRGToMetallicRoughness"] is True

print("XZIEL_NACHT_MATERIAL_CONTRACT_TEST_OK semantic_preservation=PASS")
