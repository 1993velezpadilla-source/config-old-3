#!/usr/bin/env python3
"""Lossless helpers for normalizing CUE4Parse Cascade diagnostic values.

The UEParticleGraphExtract authority intentionally preserves CUE4Parse's
FScriptStruct/FStructFallback/FPackageIndex shapes.  Godot-facing compilers
should consume explicit Python primitives and source object references instead
of parsing debug strings or guessing values.

This module is deliberately renderer-agnostic: normalization never invents a
distribution constant, curve key, material, mesh, lifetime, size, velocity, or
spawn rate.  Unknown shapes stay represented as tagged dictionaries so callers
can keep visualRuntimeReady false until semantics are implemented.
"""

from __future__ import annotations

from typing import Any


def canonical_ue_object_path(raw: Any) -> str:
    value = "" if raw is None else str(raw).strip().replace("\\", "/")
    if "'" in value and value.endswith("'"):
        value = value.split("'", 1)[1][:-1]
    if value.startswith("Content/"):
        value = "/Game/" + value[len("Content/") :]
    elif value.startswith("Game/"):
        value = "/" + value
    return value


def normalize_cue4parse_value(value: Any) -> Any:
    """Convert diagnostic authority into deterministic JSON-like primitives.

    Supported source shapes:
      * FScriptStruct -> tagged struct with normalized inner value
      * FStructFallback -> tagged struct + property-name dictionary
      * FPackageIndex -> canonical UE object reference
      * scalar/list/dict -> recursively normalized

    No text representation is interpreted as data.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, list):
        return [normalize_cue4parse_value(item) for item in value]

    if not isinstance(value, dict):
        return {
            "kind": "opaque_python_value",
            "type": type(value).__name__,
            "text": str(value),
        }

    kind = str(value.get("kind", ""))

    if kind == "FPackageIndex":
        return {
            "kind": "object_ref",
            "index": value.get("index"),
            "path": canonical_ue_object_path(value.get("path")),
        }

    if kind == "FScriptStruct":
        return {
            "kind": "script_struct",
            "structType": value.get("structType"),
            "value": normalize_cue4parse_value(value.get("value")),
        }

    if kind == "FStructFallback":
        properties: dict[str, Any] = {}
        ordered: list[dict[str, Any]] = []
        for raw in value.get("properties", []):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name", ""))
            normalized = normalize_cue4parse_value(raw.get("value"))
            ordered.append(
                {
                    "name": name,
                    "valueType": raw.get("valueType"),
                    "value": normalized,
                }
            )
            if name:
                properties[name] = normalized
        return {
            "kind": "struct",
            "properties": properties,
            "orderedProperties": ordered,
        }

    # Preserve unknown tagged/structured values losslessly.  This is important
    # for Cascade types that are not yet implemented (curves, seeded modules,
    # mesh/beam payloads, etc.): callers can inspect the source authority while
    # still refusing to claim semantic support.
    return {
        str(key): normalize_cue4parse_value(item)
        for key, item in value.items()
    }


def struct_properties(value: Any) -> dict[str, Any]:
    """Return named properties from a normalized struct, if present."""
    normalized = normalize_cue4parse_value(value)
    while isinstance(normalized, dict) and normalized.get("kind") == "script_struct":
        normalized = normalized.get("value")
    if isinstance(normalized, dict) and normalized.get("kind") == "struct":
        props = normalized.get("properties", {})
        return props if isinstance(props, dict) else {}
    return {}


def object_ref_path(value: Any) -> str:
    """Return a canonical object path only for an explicit source ref."""
    normalized = normalize_cue4parse_value(value)
    if isinstance(normalized, dict) and normalized.get("kind") == "object_ref":
        return canonical_ue_object_path(normalized.get("path"))
    return ""
