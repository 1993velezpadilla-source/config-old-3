import importlib.util
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/maps/compile_xziel_material_table.py"

spec = importlib.util.spec_from_file_location("xzmt", TOOL)
assert spec is not None and spec.loader is not None
xzmt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xzmt)


def test_compile_material_table_v1():
    doc = {
        "format": "xziel_material_runtime_manifest_v1",
        "meshCount": 2,
        "textures": [
            {
                "index": 0,
                "runtimePath": "xziel/maps/nacht/t/t0000.png",
            }
        ],
        "bindings": [
            {
                "meshIndex": 0,
                "materialIndex": 0,
                "diffuseTextureIndex": 0,
                "flags": 0,
            },
            {
                "meshIndex": 1,
                "materialIndex": 3,
                "diffuseTextureIndex": xzmt.NO_TEXTURE,
                "flags": 0,
            },
        ],
    }

    payload = xzmt.compile_table(doc)
    magic, version, meshes, textures, bindings, string_bytes, reserved = (
        xzmt.HEADER.unpack_from(payload, 0)
    )

    assert magic == b"XZMT"
    assert version == 1
    assert meshes == 2
    assert textures == 1
    assert bindings == 2
    assert string_bytes == len("xziel/maps/nacht/t/t0000.png")
    assert reserved == 0

    at = xzmt.HEADER.size
    offset, length = xzmt.TEXTURE.unpack_from(payload, at)
    assert offset == 0
    assert length == string_bytes

    at += xzmt.TEXTURE.size
    assert xzmt.BINDING.unpack_from(payload, at) == (0, 0, 0, 0)
    at += xzmt.BINDING.size
    assert xzmt.BINDING.unpack_from(payload, at) == (
        1, 3, xzmt.NO_TEXTURE, 0
    )


def test_reject_duplicate_mesh_material_binding():
    doc = {
        "format": "xziel_material_runtime_manifest_v1",
        "meshCount": 1,
        "textures": [],
        "bindings": [
            {
                "meshIndex": 0,
                "materialIndex": 0,
                "diffuseTextureIndex": xzmt.NO_TEXTURE,
            },
            {
                "meshIndex": 0,
                "materialIndex": 0,
                "diffuseTextureIndex": xzmt.NO_TEXTURE,
            },
        ],
    }

    try:
        xzmt.compile_table(doc)
    except ValueError as exc:
        assert "duplicate mesh/material binding" in str(exc)
    else:
        raise AssertionError("expected duplicate binding rejection")
