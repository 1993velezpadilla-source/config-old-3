import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/maps/compile_xziel_material_table.py"
spec = importlib.util.spec_from_file_location("xzmt", TOOL)
assert spec and spec.loader
xzmt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xzmt)


def test_xzmt_accepts_xzt_and_packs_binding():
    doc = {
        "format": "xziel_material_runtime_manifest_v1",
        "meshCount": 492,
        "textures": [{
            "index": 0,
            "runtimePath": "xziel/maps/xziel_nacht_bo3/textures/t0000.xzt",
        }],
        "bindings": [{
            "meshIndex": 17,
            "materialIndex": 3,
            "diffuseTextureIndex": 0,
            "flags": 0,
        }],
    }
    payload = xzmt.compile_table(doc)
    header = xzmt.HEADER.unpack_from(payload, 0)
    assert header[0] == b"XZMT"
    assert header[1] == 1
    assert header[2] == 492
    assert header[3] == 1
    assert header[4] == 1


def test_xzmt_rejects_duplicate_mesh_material_pair():
    doc = {
        "format": "xziel_material_runtime_manifest_v1",
        "meshCount": 1,
        "textures": [],
        "bindings": [
            {"meshIndex": 0, "materialIndex": 2, "diffuseTextureIndex": xzmt.NO_TEXTURE},
            {"meshIndex": 0, "materialIndex": 2, "diffuseTextureIndex": xzmt.NO_TEXTURE},
        ],
    }
    try:
        xzmt.compile_table(doc)
    except ValueError as exc:
        assert "duplicate mesh/material binding" in str(exc)
    else:
        raise AssertionError("expected duplicate binding rejection")
