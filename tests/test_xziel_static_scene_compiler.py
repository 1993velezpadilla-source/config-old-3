#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/maps/compile_xziel_static_scene.py"
HEADER = struct.Struct("<4s7IfI")
MESH = struct.Struct("<II")
INSTANCE = struct.Struct("<I16f")


def matrix(tx: float) -> list[float]:
    return [
        1.0, 0.0, 0.0, tx,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


scene = {
    "format": "xziel_visual_scene_v1",
    "meshes": [
        {"index": 0, "sourceBasename": "wall_a"},
        {"index": 1, "sourceBasename": "prop_b"},
    ],
    "instances": [
        {"meshIndex": 0, "matrixRowMajor": matrix(1.0)},
        {"meshIndex": 1, "matrixRowMajor": matrix(2.0)},
        {"meshIndex": 0, "matrixRowMajor": matrix(3.0)},
    ],
}

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    source = td / "visual.json"
    output = td / "scene.xzsc"
    report = td / "report.json"

    source.write_text(
        json.dumps(scene),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "python3",
            str(TOOL),
            str(source),
            str(output),
            "--runtime-map-id",
            "unit_map",
            "--report",
            str(report),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout

    raw = output.read_bytes()
    header = HEADER.unpack_from(raw, 0)

    assert header[0] == b"XZSC"
    assert header[1] == 1
    assert header[3] == 2
    assert header[4] == 3
    assert header[5] == MESH.size
    assert header[6] == INSTANCE.size
    assert abs(header[8] - 39.3700787402) < 0.001

    payload = json.loads(
        report.read_text(encoding="utf-8")
    )
    assert payload["meshCount"] == 2
    assert payload["instanceCount"] == 3

    bad = dict(scene)
    bad["instances"] = [
        {
            "meshIndex": 0,
            "matrixRowMajor": matrix(0.0),
        }
    ]
    source.write_text(
        json.dumps(bad),
        encoding="utf-8",
    )
    rejected = subprocess.run(
        [
            "python3",
            str(TOOL),
            str(source),
            str(output),
            "--runtime-map-id",
            "unit_map",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert rejected.returncode != 0
    assert "meshes are referenced" in rejected.stdout

print(
    "XZIEL_STATIC_SCENE_COMPILER_TEST_OK "
    "mesh_paths=SAFE zero_omission=PASS"
)
