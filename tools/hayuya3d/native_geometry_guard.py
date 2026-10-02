#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
from pathlib import Path


PROJECTION_PROXY_NODES = {
    "source_visible_front",
    "occluded_low_frequency",
}
PROJECTION_MARKERS = {
    "source_front_projection",
    "front_projection",
    "projection_proxy",
}


class ProjectionProxyRejected(RuntimeError):
    """Raised when a diagnostic front-projection asset enters native 3D ranking."""


def _glb_json(path: Path) -> dict:
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("not a GLB 2.0 file")
    version, total_length = struct.unpack_from("<II", data, 4)
    if version != 2 or total_length > len(data):
        raise ValueError("invalid GLB header")
    offset = 12
    while offset + 8 <= min(total_length, len(data)):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + chunk_length]
        offset += chunk_length
        if chunk_type == 0x4E4F534A:  # JSON
            return json.loads(chunk.decode("utf-8").rstrip("\x00 \t\r\n"))
    raise ValueError("GLB has no JSON chunk")


def _gltf_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inspect_candidate(path: Path) -> dict:
    """Inspect provenance markers without requiring Blender/trimesh.

    This is deliberately a *negative* gate: it rejects the known diagnostic
    front-projection representation, but does not pretend that every other
    container proves good 360 geometry. The normal HAYUYA Judge still decides
    fidelity/quality after this guard.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    payload = None
    parse_error = None
    try:
        if suffix == ".glb":
            payload = _glb_json(path)
        elif suffix == ".gltf":
            payload = _gltf_json(path)
    except Exception as exc:
        parse_error = f"{type(exc).__name__}: {exc}"

    node_names = []
    asset_extras = {}
    if isinstance(payload, dict):
        node_names = [
            str(node.get("name") or "")
            for node in payload.get("nodes", [])
            if isinstance(node, dict)
        ]
        asset = payload.get("asset")
        if isinstance(asset, dict) and isinstance(asset.get("extras"), dict):
            asset_extras = dict(asset["extras"])

    lowered_names = {name.lower() for name in node_names if name}
    filename = path.name.lower()
    extras_text = json.dumps(asset_extras, sort_keys=True).lower()

    proxy_nodes = sorted(PROJECTION_PROXY_NODES & lowered_names)
    marker_hits = sorted(
        marker for marker in PROJECTION_MARKERS
        if marker in filename or marker in extras_text
    )
    is_projection_proxy = bool(proxy_nodes or marker_hits)

    return {
        "schema": 1,
        "policy": "hayuya-native-geometry-provenance-guard-v1",
        "path": str(path),
        "container": suffix.lstrip(".") or "unknown",
        "parse_error": parse_error,
        "node_names": node_names,
        "projection_proxy_nodes": proxy_nodes,
        "projection_marker_hits": marker_hits,
        "is_projection_proxy": is_projection_proxy,
        "native_geometry_required": True,
        "note": (
            "Front-projection assets are diagnostic/reference evidence only and "
            "must never compete as native HAYUYA geometry."
        ),
    }


def assert_native_candidate(path: Path, *, label: str | None = None) -> dict:
    report = inspect_candidate(path)
    if report["is_projection_proxy"]:
        prefix = f"{label}: " if label else ""
        raise ProjectionProxyRejected(
            prefix
            + "diagnostic front-projection asset rejected from native 3D candidate pool "
            + f"(nodes={report['projection_proxy_nodes']}, markers={report['projection_marker_hits']})"
        )
    return report
