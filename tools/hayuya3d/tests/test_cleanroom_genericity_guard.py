from __future__ import annotations

from pathlib import Path
import ast

HERE = Path(__file__).resolve().parents[1]

CORE_MODULES = (
    "cleanroom_engine_router.py",
    "triposg_cloud.py",
    "hunyuan3d_cloud.py",
    "native_face_repair.py",
    "regional_fusion.py",
    "face_geometry_tournament.py",
)

# Runtime core must never acquire fixture-specific identity, paths or filenames.
# Workflows/tests may reference named fixtures; engine code may not.
BANNED_RUNTIME_LITERALS = (
    "monji-murgucol",
    "murgucol",
    "detail-01.webp",
    "primary.webp",
    "view-01.webp",
    "view-02.webp",
    "view-03.webp",
    "hayuya/assets/monji",
)


def _string_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.append(node.value)
    return values


def test_cleanroom_runtime_has_no_fixture_specific_literals() -> None:
    violations: list[str] = []
    for name in CORE_MODULES:
        path = HERE / name
        assert path.is_file(), path
        for value in _string_literals(path):
            low = value.lower()
            for banned in BANNED_RUNTIME_LITERALS:
                if banned in low:
                    violations.append(f"{name}: {banned!r} in {value[:160]!r}")
    assert not violations, "\n".join(violations)


def test_face_repair_contract_is_source_driven_not_named_asset_driven() -> None:
    path = HERE / "native_face_repair.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    funcs = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    fn = funcs["prepare_source_face_repair_challenger"]
    arg_names = [arg.arg for arg in [*fn.args.args, *fn.args.kwonlyargs]]
    assert "base_mesh" in arg_names
    assert "detail_image" in arg_names
    assert "selected_backends" in arg_names
    assert "derive_head_from_full_source" in arg_names

    # Generic engine function should not accept a fixture/job/name selector.
    forbidden_args = {"monji", "monja", "asset_name", "job_id", "fixture"}
    assert forbidden_args.isdisjoint(arg_names)


def test_cleanroom_router_contract_accepts_arbitrary_input_path() -> None:
    path = HERE / "cleanroom_engine_router.py"
    source = path.read_text(encoding="utf-8")
    # The CLI contract must remain path/provider based rather than fixture based.
    assert 'add_argument("--input"' in source
    assert 'add_argument("--providers"' in source
    for banned in BANNED_RUNTIME_LITERALS:
        assert banned not in source.lower()
