#!/usr/bin/env python3
"""Resolve UE material output pins through cooked expression graphs.

This is the material half of the UE -> Xogot authority bridge. It consumes the
UEMaterialAudit JSON produced from CUE4Parse and follows FExpressionInput
connections from a concrete base UMaterial into parameter expressions. For a
MaterialInstanceConstant it then binds those source parameter names to the
instance's effective texture/scalar/color overrides.

No filename heuristics are used to decide material semantics.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

OUTPUT_PINS = (
    "BaseColor",
    "EmissiveColor",
    "Opacity",
    "OpacityMask",
    "Normal",
    "Roughness",
    "Metallic",
    "Specular",
)


class MaterialGraphError(ValueError):
    pass


def canonical_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    quote = text.find("'")
    if quote >= 0 and text.endswith("'"):
        text = text[quote + 1 : -1]
    if text.startswith("Content/"):
        text = "/Game/" + text[len("Content/") :]
    elif text.startswith("Game/"):
        text = "/" + text
    return text.lower()


def property_map(rows: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", ""))
        if name:
            result[name] = row.get("value")
    return result


def parameter_name(expression: dict[str, Any]) -> str:
    props = property_map(expression.get("properties", []))
    raw = props.get("ParameterName")
    if raw is None:
        return ""
    if isinstance(raw, dict):
        # Diagnostic FName/FStructFallback representations occasionally wrap
        # the printable name. Search only explicit value/text fields.
        for key in ("Text", "PlainText", "value", "Value"):
            if key in raw and raw[key] is not None:
                return str(raw[key])
    return str(raw)


def expression_kind(export_type: str) -> str | None:
    token = export_type.lower()
    if "texturesampleparameter" in token:
        return "texture"
    if "scalarparameter" in token:
        return "scalar"
    if "vectorparameter" in token:
        return "vector"
    if "staticboolparameter" in token or "staticswitchparameter" in token:
        return "switch"
    return None


def _expression_aliases(expression: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    object_path = str(expression.get("objectPath", "")).strip()
    if object_path:
        aliases.add(canonical_path(object_path))
        tail = object_path.rsplit(":", 1)[-1].rsplit(".", 1)[-1]
        if tail:
            aliases.add(tail.lower())
    reference = str(expression.get("reference", "")).strip()
    if reference:
        aliases.add(canonical_path(reference))
        tail = reference.rsplit(":", 1)[-1].rsplit(".", 1)[-1]
        if tail:
            aliases.add(tail.lower())
    return {alias for alias in aliases if alias}


def expression_index(base_material: dict[str, Any]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for raw in base_material.get("expressionGraph", []):
        if not isinstance(raw, dict) or not raw.get("loaded", False):
            continue
        for alias in _expression_aliases(raw):
            buckets.setdefault(alias, []).append(raw)

    result: dict[str, dict[str, Any]] = {}
    for alias, rows in buckets.items():
        unique = {
            canonical_path(row.get("objectPath")): row
            for row in rows
        }
        if len(unique) == 1:
            result[alias] = next(iter(unique.values()))
    return result


def _resolve_input_expression(
    raw_input: Any,
    index: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(raw_input, dict):
        return None
    if raw_input.get("kind") != "FExpressionInput":
        return None

    direct = raw_input.get("resolvedExpression")
    if isinstance(direct, dict):
        return direct

    for key in ("expressionPath", "expressionName"):
        raw = str(raw_input.get(key, "")).strip()
        if not raw:
            continue
        candidates = [
            canonical_path(raw),
            raw.rsplit(":", 1)[-1].rsplit(".", 1)[-1].lower(),
        ]
        for candidate in candidates:
            if candidate and candidate in index:
                return index[candidate]
    return None


def _resolved_expression_inputs(
    value: Any,
    index: dict[str, dict[str, Any]],
):
    if isinstance(value, dict):
        if value.get("kind") == "FExpressionInput":
            expression = _resolve_input_expression(value, index)
            if isinstance(expression, dict):
                yield expression
        for child in value.values():
            yield from _resolved_expression_inputs(child, index)
    elif isinstance(value, list):
        for child in value:
            yield from _resolved_expression_inputs(child, index)


def collect_parameters(
    expression: dict[str, Any],
    *,
    index: dict[str, dict[str, Any]] | None = None,
    _seen: set[str] | None = None,
) -> list[dict[str, str]]:
    index = {} if index is None else index
    seen = set() if _seen is None else _seen
    object_path = str(expression.get("objectPath", ""))
    identity = canonical_path(object_path) or f"id:{id(expression)}"
    if identity in seen:
        return []
    seen.add(identity)

    result: list[dict[str, str]] = []
    export_type = str(expression.get("exportType", ""))
    kind = expression_kind(export_type)
    name = parameter_name(expression)
    if kind and name:
        result.append({
            "kind": kind,
            "parameter": name,
            "exportType": export_type,
            "objectPath": object_path,
        })

    for child in _resolved_expression_inputs(
        expression.get("properties", []),
        index,
    ):
        result.extend(
            collect_parameters(
                child,
                index=index,
                _seen=seen,
            )
        )

    unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in result:
        unique[(row["kind"], row["parameter"].lower())] = row
    return list(unique.values())


def output_pin_parameters(base_material: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    props = property_map(base_material.get("rawMaterialProperties", []))
    index = expression_index(base_material)
    result: dict[str, list[dict[str, str]]] = {}
    for pin in OUTPUT_PINS:
        raw_input = props.get(pin)
        expression = _resolve_input_expression(raw_input, index)
        if not isinstance(expression, dict):
            continue
        rows = collect_parameters(expression, index=index)
        if rows:
            result[pin] = rows
    return result



def base_parameter_candidates(base_material: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for expression in base_material.get("expressionGraph", []):
        if not isinstance(expression, dict) or not expression.get("loaded", False):
            continue
        kind = expression_kind(str(expression.get("exportType", "")))
        name = parameter_name(expression)
        if kind and name:
            result.append({
                "kind": kind,
                "parameter": name,
                "exportType": str(expression.get("exportType", "")),
                "objectPath": str(expression.get("objectPath", "")),
            })
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in result:
        unique[(row["kind"], row["parameter"].lower())] = row
    return list(unique.values())


def unresolved_output_inputs(base_material: dict[str, Any]) -> dict[str, str]:
    props = property_map(base_material.get("rawMaterialProperties", []))
    index = expression_index(base_material)
    result: dict[str, str] = {}
    for pin in OUTPUT_PINS:
        raw_input = props.get(pin)
        if not isinstance(raw_input, dict):
            continue
        if raw_input.get("kind") != "FExpressionInput":
            continue
        if _resolve_input_expression(raw_input, index) is not None:
            continue
        expression_name = str(
            raw_input.get("expressionName")
            or raw_input.get("expressionPath")
            or ""
        )
        if expression_name:
            result[pin] = expression_name
    return result

def _override_map(rows: Any, name_key: str = "name", value_key: str = "value") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get(name_key, ""))
        if not name:
            continue
        result[name.lower()] = row.get(value_key)
    return result


def _texture_override_map(rows: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("parameter", ""))
        path = row.get("objectPath")
        if name and path:
            result[name.lower()] = str(path)
    return result


def resolve_instance(materials_root: dict[str, Any], instance_path: str) -> dict[str, Any]:
    rows = materials_root.get("materials", [])
    if not isinstance(rows, list):
        raise MaterialGraphError("materials root has no materials array")

    by_path = {
        canonical_path(row.get("objectPath")): row
        for row in rows
        if isinstance(row, dict) and row.get("objectPath")
    }
    wanted = canonical_path(instance_path)
    instance = by_path.get(wanted)
    if instance is None:
        raise MaterialGraphError(f"material instance not found: {instance_path}")

    base_path = str(instance.get("semanticBaseMaterialPath") or instance.get("objectPath") or "")
    base = by_path.get(canonical_path(base_path))
    if base is None:
        raise MaterialGraphError(
            f"base material not present in authority: {base_path}"
        )
    if str(base.get("exportType", "")) != "Material":
        raise MaterialGraphError(
            f"semantic base is not a UMaterial: {base.get('exportType')}"
        )

    pins = output_pin_parameters(base)
    unresolved_pins = unresolved_output_inputs(base)
    parameter_candidates = base_parameter_candidates(base)
    textures = _texture_override_map(instance.get("textures", []))
    scalars = _override_map(instance.get("scalars", []))
    colors = _override_map(instance.get("colors", []))
    switches = _override_map(instance.get("switches", []))

    resolved_pins: dict[str, list[dict[str, Any]]] = {}
    for pin, parameters in pins.items():
        bound: list[dict[str, Any]] = []
        for row in parameters:
            kind = row["kind"]
            key = row["parameter"].lower()
            value: Any = None
            if kind == "texture":
                value = textures.get(key)
            elif kind == "scalar":
                value = scalars.get(key)
            elif kind == "vector":
                value = colors.get(key)
            elif kind == "switch":
                value = switches.get(key)
            bound.append({**row, "boundValue": value})
        resolved_pins[pin] = bound

    candidate_bindings: list[dict[str, Any]] = []
    for row in parameter_candidates:
        kind = row["kind"]
        key = row["parameter"].lower()
        value: Any = None
        if kind == "texture":
            value = textures.get(key)
        elif kind == "scalar":
            value = scalars.get(key)
        elif kind == "vector":
            value = colors.get(key)
        elif kind == "switch":
            value = switches.get(key)
        candidate_bindings.append({**row, "boundValue": value})

    graph_status = "exact"
    if unresolved_pins:
        graph_status = "partial"
    elif not resolved_pins:
        graph_status = "missing"

    return {
        "instancePath": str(instance.get("objectPath", instance_path)),
        "baseMaterialPath": str(base.get("objectPath", base_path)),
        "blendMode": instance.get("blendMode"),
        "shadingModel": instance.get("shadingModel"),
        "graphStatus": graph_status,
        "exactPinBindings": graph_status == "exact",
        "unresolvedOutputInputs": unresolved_pins,
        "pins": resolved_pins,
        "parameterCandidates": candidate_bindings,
        "instanceTextures": instance.get("textures", []),
        "instanceScalars": instance.get("scalars", []),
        "instanceColors": instance.get("colors", []),
        "instanceSwitches": instance.get("switches", []),
    }


def census(materials_root: dict[str, Any]) -> dict[str, Any]:
    rows = materials_root.get("materials", [])
    if not isinstance(rows, list):
        raise MaterialGraphError("materials root has no materials array")

    by_path = {
        canonical_path(row.get("objectPath")): row
        for row in rows
        if isinstance(row, dict) and row.get("objectPath")
    }
    stats: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    resolved: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("exportType", "")) != "MaterialInstanceConstant":
            continue
        stats["instances"] += 1
        base_path = str(row.get("semanticBaseMaterialPath") or "")
        base = by_path.get(canonical_path(base_path))
        if base is None:
            stats["missingBase"] += 1
            failures.append({
                "materialPath": str(row.get("objectPath", "")),
                "error": "base material missing",
                "baseMaterialPath": base_path,
            })
            continue
        stats["basePresent"] += 1
        pins = output_pin_parameters(base)
        if pins:
            stats["baseGraphPinsResolved"] += 1
        resolved.append({
            "materialPath": row.get("objectPath"),
            "baseMaterialPath": base.get("objectPath"),
            "pins": pins,
        })

    return {
        "decoder": "xogot-ue-bridge-material-graph-v1",
        "stats": dict(sorted(stats.items())),
        "failures": failures,
        "rows": resolved,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--target")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = json.loads(args.materials.read_text(encoding="utf-8"))
    if not isinstance(root, dict):
        raise SystemExit("material authority root must be a JSON object")

    report: dict[str, Any]
    if args.target:
        try:
            report = resolve_instance(root, args.target)
        except MaterialGraphError as exc:
            print("XZOGOT_UE_BRIDGE_MATERIAL_FAILURE " + str(exc))
            return 2
        print("XZOGOT_UE_BRIDGE_MATERIAL_TARGET " + json.dumps(report, sort_keys=True))
        if args.strict:
            texture_bindings = [
                row for row in report.get("parameterCandidates", [])
                if row.get("kind") == "texture" and row.get("boundValue")
            ]
            if report.get("blendMode") == "BLEND_Additive" and not texture_bindings:
                print("XZOGOT_UE_BRIDGE_MATERIAL_FAILURE additive_texture_candidates_unresolved")
                return 3
            if report.get("graphStatus") == "missing":
                print("XZOGOT_UE_BRIDGE_MATERIAL_FAILURE base_graph_missing")
                return 4
    else:
        report = census(root)
        print(
            "XZOGOT_UE_BRIDGE_MATERIAL_CENSUS "
            + json.dumps(
                {
                    "decoder": report["decoder"],
                    "stats": report["stats"],
                    "failureCount": len(report["failures"]),
                },
                sort_keys=True,
            )
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print("XZOGOT_UE_BRIDGE_MATERIAL_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
