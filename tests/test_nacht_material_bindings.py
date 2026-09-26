import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/maps/compile_nacht_material_bindings.py"

spec = importlib.util.spec_from_file_location(
    "nacht_material_bindings", TOOL
)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_primitive_material_rows_preserves_scene_order_and_names():
    doc = {
        "scene": 0,
        "scenes": [{"nodes": [1, 0]}],
        "nodes": [
            {
                "mesh": 0,
                "children": [2],
            },
            {
                "mesh": 1,
            },
            {
                "mesh": 2,
            },
        ],
        "meshes": [
            {
                "primitives": [
                    {"material": 1},
                    {},
                ],
            },
            {
                "primitives": [
                    {"material": 0},
                ],
            },
            {
                "primitives": [
                    {"material": 2},
                ],
            },
        ],
        "materials": [
            {"name": "Mat_A"},
            {"name": "Mat_B"},
            {},
        ],
    }

    rows = mod.primitive_material_rows(doc)

    assert [row["submeshIndex"] for row in rows] == [0, 1, 2, 3]
    assert [row["materialIndex"] for row in rows] == [
        0,
        1,
        mod.NO_MATERIAL,
        2,
    ]
    assert [row["materialName"] for row in rows] == [
        "Mat_A",
        "Mat_B",
        None,
        "MaterialSlot_2",
    ]
    assert [row["sourceNodeIndex"] for row in rows] == [1, 0, 0, 2]
