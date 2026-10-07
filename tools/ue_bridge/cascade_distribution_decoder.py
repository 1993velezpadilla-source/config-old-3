#!/usr/bin/env python3
"""UE Cascade cooked distribution decoder for the Xogot bridge.

The canonicalization model follows the public MIT-licensed
JsonAsAsset/Reflection Cascade decooking implementation and UE4's
ERawDistributionOperation/FDistributionLookupTable layout.

It does not import Unreal assets by itself. It converts cooked lookup-table
authority already extracted by CUE4Parse into a stable engine-neutral shape
that Godot/Xogot can consume and test.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

RDO_UNINITIALIZED = 0
RDO_NONE = 1
RDO_RANDOM = 2
RDO_EXTREME = 3
UNIFORM_OPS = {RDO_RANDOM, RDO_EXTREME}
TABLE_KEYS = {
    "EntryCount",
    "EntryStride",
    "SubEntryStride",
    "Op",
    "TimeScale",
    "TimeBias",
    "Values",
}


class DistributionDecodeError(ValueError):
    pass


def unwrap(value: Any) -> Any:
    if isinstance(value, list):
        return [unwrap(item) for item in value]
    if not isinstance(value, dict):
        return value

    kind = str(value.get("kind", ""))
    if kind == "FScriptStruct":
        return unwrap(value.get("value"))
    if kind == "FStructFallback":
        result: dict[str, Any] = {}
        for item in value.get("properties", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            if name:
                result[name] = unwrap(item.get("value"))
        return result
    if kind == "FPackageIndex":
        return value.get("path")
    if kind.endswith(".UScriptArray"):
        members = value.get("members", {})
        rows = members.get("Properties", []) if isinstance(members, dict) else []
        out = []
        for item in rows:
            if isinstance(item, dict):
                item_members = item.get("members", {})
                if isinstance(item_members, dict):
                    if "GenericValue" in item_members:
                        out.append(unwrap(item_members["GenericValue"]))
                        continue
                    if "Value" in item_members:
                        out.append(unwrap(item_members["Value"]))
                        continue
            out.append(unwrap(item))
        return out

    members = value.get("members", {})
    if isinstance(members, dict) and members:
        if "GenericValue" in members:
            return unwrap(members["GenericValue"])
        if "Value" in members and len(members) <= 4:
            return unwrap(members["Value"])
        return {str(k): unwrap(v) for k, v in members.items()}

    return {str(k): unwrap(v) for k, v in value.items()}


def _as_float_list(values: Any) -> list[float]:
    if not isinstance(values, list):
        raise DistributionDecodeError("Values is not an array")
    result: list[float] = []
    for value in values:
        value = unwrap(value)
        try:
            result.append(float(value))
        except (TypeError, ValueError) as exc:
            raise DistributionDecodeError(f"non-numeric lookup value {value!r}") from exc
    return result


def _table_dict(raw: Any) -> dict[str, Any]:
    table = unwrap(raw)
    if not isinstance(table, dict):
        raise DistributionDecodeError("lookup table is not an object")
    missing = TABLE_KEYS.difference(table)
    if missing:
        raise DistributionDecodeError("lookup table missing " + ",".join(sorted(missing)))
    return table


def infer_dimension(table: dict[str, Any]) -> int:
    op = int(table["Op"])
    entry_stride = int(table["EntryStride"])
    sub_stride = int(table["SubEntryStride"])
    if op in UNIFORM_OPS and sub_stride > 0:
        dimension = sub_stride
    else:
        dimension = entry_stride
    if dimension not in (1, 3):
        raise DistributionDecodeError(
            f"unsupported inferred distribution dimension={dimension} "
            f"entry_stride={entry_stride} sub_stride={sub_stride} op={op}"
        )
    return dimension


def classify_table(raw_table: Any) -> str:
    table = _table_dict(raw_table)
    values = _as_float_list(table["Values"])
    op = int(table["Op"])
    entry_count = int(table["EntryCount"])
    sub_stride = int(table["SubEntryStride"])

    # Reflection's IsConstantDistribution compares total lookup values to the
    # sub-entry stride. Preserve that decision before the uniform checks.
    if sub_stride > 0 and len(values) == sub_stride:
        return "constant"
    if op in UNIFORM_OPS and entry_count == 1:
        return "uniform"
    if op in UNIFORM_OPS:
        return "uniform_curve"
    return "constant_curve"


def _vec(values: list[float], start: int, dimension: int) -> float | list[float]:
    segment = values[start : start + dimension]
    if len(segment) != dimension:
        raise DistributionDecodeError(
            f"lookup value underflow start={start} dimension={dimension} values={len(values)}"
        )
    return segment[0] if dimension == 1 else segment


def decode_lookup_table(raw_table: Any, dimension: int | None = None) -> dict[str, Any]:
    table = _table_dict(raw_table)
    values = _as_float_list(table["Values"])
    op = int(table["Op"])
    entry_count = int(table["EntryCount"])
    entry_stride = int(table["EntryStride"])
    sub_stride = int(table["SubEntryStride"])
    time_scale = float(table["TimeScale"])
    time_bias = float(table["TimeBias"])
    dimension = infer_dimension(table) if dimension is None else int(dimension)
    if dimension not in (1, 3):
        raise DistributionDecodeError(f"dimension must be 1 or 3, got {dimension}")

    kind = classify_table(table)
    result: dict[str, Any] = {
        "kind": kind,
        "dimension": dimension,
        "operation": op,
        "entryCount": entry_count,
        "entryStride": entry_stride,
        "subEntryStride": sub_stride,
        "timeScale": time_scale,
        "timeBias": time_bias,
    }

    if kind == "constant":
        result["value"] = _vec(values, 0, dimension)
        return result

    if kind == "uniform":
        result["min"] = _vec(values, 0, dimension)
        result["max"] = _vec(values, sub_stride, dimension)
        return result

    # Reflection decooking uses reciprocal TimeScale when rebuilding keys.
    key_step = 0.0 if time_scale == 0.0 else 1.0 / time_scale
    keys: list[dict[str, Any]] = []
    for index in range(entry_count):
        base = index * entry_stride
        row: dict[str, Any] = {
            "time": time_bias + index * key_step,
            "interp": "linear",
        }
        if kind == "uniform_curve":
            row["min"] = _vec(values, base, dimension)
            row["max"] = _vec(values, base + sub_stride, dimension)
        else:
            row["value"] = _vec(values, base, dimension)
        keys.append(row)
    result["keys"] = keys
    return result


def iter_lookup_tables(root: Any, path: str = "$") -> Iterable[tuple[str, dict[str, Any]]]:
    """Yield semantic lookup tables once from an already-unwrapped value."""
    decoded_root = unwrap(root)

    def visit(value: Any, current: str) -> Iterable[tuple[str, dict[str, Any]]]:
        if isinstance(value, dict):
            if TABLE_KEYS.issubset(value):
                yield current, value
                return
            for key, child in value.items():
                yield from visit(child, current + "." + str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from visit(child, current + f"[{index}]")

    yield from visit(decoded_root, path)



def raw_distribution_census(root: Any) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    table_wrappers: Counter[str] = Counter()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            kind = str(value.get("kind", ""))
            struct_type = str(value.get("structType", ""))
            label = kind + " " + struct_type
            if "RawDistributionFloat" in label:
                counts["float"] += 1
                decoded = unwrap(value)
                if isinstance(decoded, dict) and isinstance(decoded.get("Table"), dict):
                    table_wrappers["float"] += 1
            if "RawDistributionVector" in label:
                counts["vector"] += 1
                decoded = unwrap(value)
                if isinstance(decoded, dict) and isinstance(decoded.get("Table"), dict):
                    table_wrappers["vector"] += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(root)
    return {
        "wrappers": dict(sorted(counts.items())),
        "withTable": dict(sorted(table_wrappers.items())),
    }


def iter_node_properties(properties: Any) -> Iterable[tuple[str, Any, str]]:
    """Normalize both CUE4Parse property encodings used by particle authority.

    Some graph slices expose properties as [{"name": ..., "value": ...}],
    while the expanded authority used by Nacht stores them as
    {"Lifetime": ..., "StartSize": ...}. Yield one semantic stream for both.
    """
    if isinstance(properties, dict):
        for name, value in properties.items():
            yield str(name), value, "." + str(name)
        return
    if isinstance(properties, list):
        for index, prop in enumerate(properties):
            if not isinstance(prop, dict):
                continue
            name = str(prop.get("name", ""))
            if not name:
                continue
            yield name, prop.get("value"), f"[{index}].{name}"


def census_graphs(graphs: dict[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    dimensions: Counter[str] = Counter()
    operations: Counter[str] = Counter()
    node_types: Counter[str] = Counter()
    property_names: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    systems = graphs.get("systems", [])
    if not isinstance(systems, list):
        systems = []

    for system_index, system in enumerate(systems):
        if not isinstance(system, dict):
            continue
        system_path = str(system.get("objectPath", ""))
        nodes = system.get("nodes", [])
        if not isinstance(nodes, list):
            continue
        for node_index, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("exportType", ""))
            node_path = str(node.get("objectPath", ""))
            properties = node.get("properties", [])
            for property_name, value, property_suffix in iter_node_properties(
                properties
            ):
                for subpath, table in iter_lookup_tables(
                    value,
                    path="$",
                ):
                    semantic_path = (
                        f"systems[{system_index}]"
                        f".nodes[{node_index}]"
                        f".properties{property_suffix}{subpath[1:]}"
                    )
                    try:
                        decoded = decode_lookup_table(table)
                    except DistributionDecodeError as exc:
                        errors.append({
                            "path": semantic_path,
                            "systemPath": system_path,
                            "nodePath": node_path,
                            "nodeType": node_type,
                            "property": property_name,
                            "error": str(exc),
                        })
                        continue
                    counts[decoded["kind"]] += 1
                    dimensions[str(decoded["dimension"])] += 1
                    operations[str(decoded["operation"])] += 1
                    node_types[node_type] += 1
                    property_names[property_name] += 1
                    rows.append({
                        "path": semantic_path,
                        "systemPath": system_path,
                        "nodePath": node_path,
                        "nodeType": node_type,
                        "property": property_name,
                        "decoded": decoded,
                    })

    return {
        "decoder": "xogot-ue-bridge-reflection-compatible-v2",
        "rawDistributionCoverage": raw_distribution_census(graphs),
        "total": len(rows),
        "counts": dict(sorted(counts.items())),
        "dimensions": dict(sorted(dimensions.items())),
        "operations": dict(sorted(operations.items())),
        "nodeTypes": dict(sorted(node_types.items())),
        "properties": dict(sorted(property_names.items())),
        "errors": errors,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    graphs = json.loads(args.graphs.read_text(encoding="utf-8"))
    if not isinstance(graphs, dict):
        raise SystemExit("particle graph root must be a JSON object")

    report = census_graphs(graphs)
    summary = {
        key: report[key]
        for key in (
            "decoder",
            "rawDistributionCoverage",
            "total",
            "counts",
            "dimensions",
            "operations",
            "nodeTypes",
            "properties",
            "errors",
        )
    }
    print("XZOGOT_UE_BRIDGE_CASCADE_CENSUS " + json.dumps(summary, sort_keys=True))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.strict:
        if report["total"] <= 0:
            print("XZOGOT_UE_BRIDGE_CASCADE_FAILURE no_lookup_tables")
            return 2
        if report["errors"]:
            print(
                "XZOGOT_UE_BRIDGE_CASCADE_FAILURE errors="
                + str(len(report["errors"]))
            )
            return 3

    print("XZOGOT_UE_BRIDGE_CASCADE_GREEN total=" + str(report["total"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
