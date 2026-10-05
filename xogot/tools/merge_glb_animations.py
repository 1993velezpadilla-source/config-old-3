#!/usr/bin/env python3
"""Losslessly append animation channels from one GLB onto a validated base GLB.

Geometry, skins, materials, textures, images, nodes, and all existing binary
payload bytes from the base file are preserved byte-for-byte. Only new
animation buffer data and JSON animation/accessor/bufferView records are added.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import struct
from pathlib import Path
from typing import Any

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


def align4(n: int) -> int:
    return (n + 3) & ~3


def read_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise RuntimeError(f"invalid GLB header: {path}")
    magic, version, declared = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or declared != len(data):
        raise RuntimeError(f"invalid GLB envelope: {path}")
    pos = 12
    doc = None
    blob = None
    while pos + 8 <= len(data):
        size, kind = struct.unpack_from("<II", data, pos)
        chunk = data[pos + 8 : pos + 8 + size]
        if kind == JSON_CHUNK:
            doc = json.loads(chunk.decode("utf-8").rstrip("\x00 \t\r\n"))
        elif kind == BIN_CHUNK:
            blob = bytes(chunk)
        pos += 8 + size
    if doc is None or blob is None:
        raise RuntimeError(f"GLB missing JSON/BIN chunks: {path}")
    return doc, blob


def write_glb(path: Path, doc: dict[str, Any], blob: bytes) -> None:
    json_bytes = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    json_bytes += b" " * (align4(len(json_bytes)) - len(json_bytes))
    blob += b"\x00" * (align4(len(blob)) - len(blob))
    total = 12 + 8 + len(json_bytes) + 8 + len(blob)
    out = bytearray(struct.pack("<4sII", b"glTF", 2, total))
    out += struct.pack("<II", len(json_bytes), JSON_CHUNK)
    out += json_bytes
    out += struct.pack("<II", len(blob), BIN_CHUNK)
    out += blob
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)


def parents(doc: dict[str, Any]) -> list[int | None]:
    nodes = doc.get("nodes", [])
    out: list[int | None] = [None] * len(nodes)
    for pi, node in enumerate(nodes):
        for ci in node.get("children", []) or []:
            if 0 <= int(ci) < len(out):
                out[int(ci)] = pi
    return out


def lineage(doc: dict[str, Any], index: int, parent_map: list[int | None]) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[int] = set()
    i: int | None = index
    while i is not None and i not in seen:
        seen.add(i)
        names.append(str(doc["nodes"][i].get("name", "")))
        i = parent_map[i]
    names.reverse()
    return tuple(names)


def build_target_node_map(base: dict[str, Any], anim: dict[str, Any]) -> dict[int, int]:
    base_parents = parents(base)
    anim_parents = parents(anim)
    by_name: dict[str, list[int]] = {}
    for i, node in enumerate(base.get("nodes", [])):
        name = str(node.get("name", ""))
        if name:
            by_name.setdefault(name, []).append(i)

    result: dict[int, int] = {}
    target_nodes = {
        int(ch["target"]["node"])
        for a in anim.get("animations", [])
        for ch in a.get("channels", [])
        if "node" in ch.get("target", {})
    }
    for src_i in sorted(target_nodes):
        src_name = str(anim["nodes"][src_i].get("name", ""))
        candidates = by_name.get(src_name, [])
        if not candidates:
            raise RuntimeError(f"animation target node missing in base: {src_name!r}")
        if len(candidates) == 1:
            result[src_i] = candidates[0]
            continue

        src_path = lineage(anim, src_i, anim_parents)
        best: tuple[int, int] | None = None
        for base_i in candidates:
            base_path = lineage(base, base_i, base_parents)
            score = 0
            for a_name, b_name in zip(reversed(src_path), reversed(base_path)):
                if a_name != b_name:
                    break
                score += 1
            pair = (score, base_i)
            if best is None or pair > best:
                best = pair
        if best is None or best[0] <= 0:
            raise RuntimeError(f"ambiguous animation target node: {src_name!r}")
        result[src_i] = best[1]
    return result


def read_accessor(doc: dict[str, Any], blob: bytes, index: int) -> list[list[float]]:
    acc = doc["accessors"][index]
    if "bufferView" not in acc:
        raise RuntimeError(f"sparse/no-buffer accessor unsupported for animation validation: {index}")
    bv = doc["bufferViews"][int(acc["bufferView"])]
    component = int(acc["componentType"])
    component_fmt = {
        5120: ("b", 1),
        5121: ("B", 1),
        5122: ("h", 2),
        5123: ("H", 2),
        5125: ("I", 4),
        5126: ("f", 4),
    }
    dims = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    if component not in component_fmt or acc["type"] not in dims:
        raise RuntimeError(f"unsupported animation accessor: {acc}")
    fmt, item_size = component_fmt[component]
    width = dims[acc["type"]]
    count = int(acc["count"])
    offset = int(bv.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
    packed = item_size * width
    stride = int(bv.get("byteStride", packed))
    rows: list[list[float]] = []
    for i in range(count):
        row_off = offset + i * stride
        values = struct.unpack_from("<" + fmt * width, blob, row_off)
        rows.append([float(x) for x in values])
    return rows


def animation_motion(doc: dict[str, Any], blob: bytes, prefix: str) -> dict[str, dict[str, float | int]]:
    out: dict[str, dict[str, float | int]] = {}
    for anim in doc.get("animations", []):
        name = str(anim.get("name", "Animation"))
        if prefix and prefix.lower() not in name.lower():
            continue
        varying = 0
        sampled = 0
        max_range = 0.0
        for channel in anim.get("channels", []):
            path = channel.get("target", {}).get("path")
            if path not in ("translation", "rotation", "scale"):
                continue
            sampler = anim["samplers"][int(channel["sampler"])]
            rows = read_accessor(doc, blob, int(sampler["output"]))
            if len(rows) < 2:
                continue
            sampled += 1
            width = len(rows[0])
            for j in range(width):
                values = [row[j] for row in rows]
                span = max(values) - min(values)
                max_range = max(max_range, span)
                if span > 1e-5:
                    varying += 1
        out[name] = {
            "sampled_channels": sampled,
            "varying_channels": varying,
            "max_component_range": max_range,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--animations", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--prefix", default="CMU_")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    base_doc, base_blob = read_glb(args.base)
    anim_doc, anim_blob = read_glb(args.animations)

    selected = [
        copy.deepcopy(a)
        for a in anim_doc.get("animations", [])
        if args.prefix.lower() in str(a.get("name", "")).lower()
    ]
    if not selected:
        raise RuntimeError(f"no animations matched prefix {args.prefix!r}")

    # Prove we never mutate base scene/geometry sections.
    immutable_keys = ("nodes", "meshes", "skins", "materials", "textures", "images", "samplers")
    immutable_before = {k: copy.deepcopy(base_doc.get(k)) for k in immutable_keys}

    node_map = build_target_node_map(base_doc, {"nodes": anim_doc.get("nodes", []), "animations": selected})

    append_offset = align4(len(base_blob))
    merged_blob = base_blob + b"\x00" * (append_offset - len(base_blob)) + anim_blob

    base_views = base_doc.setdefault("bufferViews", [])
    view_offset = len(base_views)
    for view in anim_doc.get("bufferViews", []):
        v = copy.deepcopy(view)
        if int(v.get("buffer", 0)) != 0:
            raise RuntimeError("animation GLB must use buffer 0")
        v["buffer"] = 0
        v["byteOffset"] = append_offset + int(v.get("byteOffset", 0))
        base_views.append(v)

    base_accessors = base_doc.setdefault("accessors", [])
    accessor_offset = len(base_accessors)
    for accessor in anim_doc.get("accessors", []):
        a = copy.deepcopy(accessor)
        if "bufferView" in a:
            a["bufferView"] = int(a["bufferView"]) + view_offset
        if "sparse" in a:
            sparse = a["sparse"]
            sparse["indices"]["bufferView"] = int(sparse["indices"]["bufferView"]) + view_offset
            sparse["values"]["bufferView"] = int(sparse["values"]["bufferView"]) + view_offset
        base_accessors.append(a)

    incoming_names = {str(a.get("name", "")) for a in selected}
    base_anims = [
        a for a in base_doc.get("animations", [])
        if str(a.get("name", "")) not in incoming_names
    ]
    for anim in selected:
        for sampler in anim.get("samplers", []):
            sampler["input"] = int(sampler["input"]) + accessor_offset
            sampler["output"] = int(sampler["output"]) + accessor_offset
        for channel in anim.get("channels", []):
            target = channel.get("target", {})
            if "node" in target:
                target["node"] = node_map[int(target["node"])]
        base_anims.append(anim)
    base_doc["animations"] = base_anims

    if not base_doc.get("buffers"):
        raise RuntimeError("base GLB has no buffers")
    if len(base_doc["buffers"]) != 1:
        raise RuntimeError("base GLB must contain exactly one GLB buffer")
    base_doc["buffers"][0]["byteLength"] = len(merged_blob)

    for key, before in immutable_before.items():
        if base_doc.get(key) != before:
            raise RuntimeError(f"base immutable section changed: {key}")

    write_glb(args.output, base_doc, merged_blob)
    final_doc, final_blob = read_glb(args.output)
    motion = animation_motion(final_doc, final_blob, args.prefix)
    expected = sorted(incoming_names)
    missing = [name for name in expected if name not in motion]
    valid = (
        not missing
        and len(expected) == len(selected)
        and all(
            int(metric["varying_channels"]) >= 3
            and float(metric["max_component_range"]) > 1e-4
            for metric in motion.values()
        )
    )
    if not valid:
        raise RuntimeError(f"merged animation motion invalid missing={missing} motion={motion}")

    if args.report:
        report = json.loads(args.report.read_text())
        report["output_bytes"] = args.output.stat().st_size
        report["output_actions"] = [str(a.get("name", "Animation")) for a in final_doc.get("animations", [])]
        report["missing_cmu_actions"] = [
            token
            for token in ("104_41", "105_25", "74_01", "139_19", "02_05", "111_19", "111_03", "90_16", "140_01")
            if not any(token.lower() in name.lower() for name in report["output_actions"])
        ]
        report["raw_glb_animation_motion"] = motion
        report["raw_glb_animation_motion_valid"] = valid and not report["missing_cmu_actions"]
        report["animation_merge_mode"] = "lossless_base_glb_plus_animation_payload"
        report["geometry_conserved"] = True
        args.report.write_text(json.dumps(report, indent=2) + "\n")

    print("XZOGOT_GLTF_ANIMATION_MERGE_GREEN", len(selected), args.output.stat().st_size)
    print("XZOGOT_GLTF_ANIMATION_MOTION_GREEN", json.dumps(motion, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
