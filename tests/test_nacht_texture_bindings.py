import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/maps/compile_nacht_texture_bindings.py"
spec = importlib.util.spec_from_file_location("bind", TOOL)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_prefers_albedo_over_normal_and_specular():
    doc = {
        "textures": [
            {"texturePath": "/T/A", "file": "textures/a.xzt"},
            {"texturePath": "/T/N", "file": "textures/n.xzt"},
            {"texturePath": "/T/S", "file": "textures/s.xzt"},
        ],
        "bindings": [
            {"materialName": "M_Wall", "source": "parameter:NormalTexture", "texturePath": "/T/N"},
            {"materialName": "M_Wall", "source": "parameter:SpecularTexture", "texturePath": "/T/S"},
            {"materialName": "M_Wall", "source": "parameter:AlbedoTexture", "texturePath": "/T/A"},
        ],
    }
    chosen, _ = mod.build_texture_choices(doc)
    assert chosen["m_wall"]["texturePath"] == "/T/A"


def test_semantic_filter_does_not_treat_normal_as_color():
    assert mod.semantic_priority("parameter:NormalTexture") is None
    assert mod.semantic_priority("parameter:SpecularTexture") is None
    assert mod.semantic_priority("parameter:BaseColor") == 2
