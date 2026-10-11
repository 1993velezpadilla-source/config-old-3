#!/usr/bin/env python3
"""Preflight the *actual* Aether MP40 vs NZ:P/Vril Android MDL runtime.

No animation correctness is inferred from clip names or a passing CI job.
This tool never claims an APK or a valid conversion was produced.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path


def inspect_glb(path: Path) -> dict:
    blob = path.read_bytes()
    if len(blob) < 20 or blob[:4] != b"glTF":
        raise ValueError(f"Not a binary glTF: {path}")
    version, total = struct.unpack_from("<II", blob, 4)
    if version != 2 or total != len(blob):
        raise ValueError(f"Invalid GLB v{version} or declared size: {path}")
    chunk_size, chunk_type = struct.unpack_from("<II", blob, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError(f"First chunk is not JSON: {path}")
    doc = json.loads(blob[20:20 + chunk_size])
    nodes = doc.get("nodes", [])
    names = [str(node.get("name", "")) for node in nodes]
    primitives = []
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            if prim.get("mode", 4) != 4:
                raise ValueError(f"Non-triangle mesh: {path}")
            accessor = doc["accessors"][prim["attributes"]["POSITION"]]
            index_accessor = doc["accessors"][prim["indices"]]
            if index_accessor["count"] % 3:
                raise ValueError(f"Unaligned triangle index stream: {path}")
            primitives.append({
                "mesh": mesh.get("name"),
                "render_vertices": int(accessor["count"]),
                "triangles": int(index_accessor["count"] // 3),
                "skinned": "JOINTS_0" in prim["attributes"],
            })
    animations = []
    for clip in doc.get("animations", []):
        times = []
        for samp in clip.get("samplers", []):
            a = doc["accessors"][samp["input"]]
            if "max" in a:
                times.append(float(a["max"][0]))
        animations.append({
            "name": clip.get("name", ""),
            "duration_seconds": round(max(times, default=0.0), 5),
            "channels": len(clip.get("channels", [])),
        })
    return {
        "path": str(path),
        "size_bytes": len(blob),
        "mesh_primitives": primitives,
        "total_render_vertices": sum(p["render_vertices"] for p in primitives),
        "total_triangles": sum(p["triangles"] for p in primitives),
        "skeleton_bones": [len(s["joints"]) for s in doc.get("skins", [])],
        "node_names": names,
        "animations": animations,
        "materials": [m.get("name", "") for m in doc.get("materials", [])],
    }


def inspect_mdl(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 84 or raw[:4] != b"IDPO":
        raise ValueError(f"Not a Quake IDPO MDL: {path}")
    ints = struct.unpack_from("<7i", raw, 48)
    return {
        "path": str(path),
        "format_version": struct.unpack_from("<i", raw, 4)[0],
        "skins": ints[0],
        "skin_width": ints[1],
        "skin_height": ints[2],
        "vertices": ints[3],
        "triangles": ints[4],
        "frames": ints[5],
        "size_bytes": len(raw),
    }


def engine_limits(header_path: Path) -> dict:
    h = header_path.read_text(encoding="utf-8")
    limits = {}
    for key in ("MAXALIASVERTS", "MAXALIASTRIS", "MAXALIASFRAMES"):
        match = re.search(r"^\s*#define\s+" + key + r"\s+(\d+)", h, re.MULTILINE)
        if match is None:
            raise ValueError(f"No {key} in actual Vril Android header")
        limits[key] = int(match.group(1))
    return limits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gun", type=Path, required=True)
    ap.add_argument("--hands", type=Path, required=True)
    ap.add_argument("--legacy-mdl", type=Path, required=True)
    ap.add_argument("--engine-header", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    gun, hands = inspect_glb(a.gun), inspect_glb(a.hands)
    legacy, caps = inspect_mdl(a.legacy_mdl), engine_limits(a.engine_header)
    gun_anims = {x["name"]: x for x in gun["animations"]}
    hands_anims = {x["name"]: x for x in hands["animations"]}
    required_gun = (
        "PSA_viewmodel_mp40_fire",
        "PSA_viewmodel_mp40_reload",
        "PSA_viewmodel_mp40_reload_empty",
    )
    for name in required_gun:
        if name not in gun_anims:
            raise ValueError(f"Required original source gun clip absent: {name}")
    if "PSA_viewmodel_mp40_reload_empty" not in hands_anims:
        raise ValueError("Source hands lack the long reload_empty clip")
    if "j_clip" not in gun["node_names"]:
        raise ValueError("Real animated magazine joint 'j_clip' missing")
    if "tag_weapon" not in hands["node_names"]:
        raise ValueError("Source hand rig tag_weapon missing")

    v = gun["total_render_vertices"] + hands["total_render_vertices"]
    t = gun["total_triangles"] + hands["total_triangles"]
    # GLB counts are rendered vertices (can include UV seam duplicates), so
    # counts after any MDL-index remap must be independently measured.
    limitations = [
        "GLB skeletal animation is not Quake IDPO vertex-frame animation.",
        "The MP40 gun alone has more triangles than stock Vril MAXALIASTRIS."
        if gun["total_triangles"] > caps["MAXALIASTRIS"] else "",
        "The MP40 gun alone has more GLB render vertices than stock Vril MAXALIASVERTS."
        if gun["total_render_vertices"] > caps["MAXALIASVERTS"] else "",
        "The two rigs must be sampled in one camera-space coordinate system;",
        "tag_weapon transform / handedness is NOT yet visually correct in Godot.",
        "Hands and gun use multiple glTF materials; IDPO requires a compatible indexed/atlas skin.",
        "Normal and empty reload duration and sound event frames need their own mapping.",
        "Do NOT release sourced commercial game assets without explicit distribution rights.",
    ]
    result = {
        "schema": 1,
        "kind": "SOURCE_FORMAT_PREFLIGHT_ONLY_NOT_A_CONVERTED_MDL",
        "source": "Existing Aether/WaW source files + NZ:P Android v2.3.14",
        "gun": gun,
        "hands": hands,
        "vril_stock_mp40": legacy,
        "vril_android_limits": caps,
        "combined_source_render_vertices": v,
        "combined_source_triangles": t,
        "gun_reload_seconds": {
            "normal": gun_anims["PSA_viewmodel_mp40_reload"]["duration_seconds"],
            "empty": gun_anims["PSA_viewmodel_mp40_reload_empty"]["duration_seconds"],
        },
        "source_hand_clip_lengths_seconds": {
            k: hands_anims[k]["duration_seconds"]
            for k in ("PSA_MP40ReloadHands", "PSA_viewmodel_mp40_reload_empty")
            if k in hands_anims
        },
        "known_blockers": [x for x in limitations if x],
        "next_required_proof": (
            "Bake skinned gun + 113-bone hands at same timeline, apply correct "
            "tag_weapon orientation, pack skin, use a compatible MDL and patch "
            "Android vertex/triangle limits as needed. Render reload from "
            "real Vril/Android, never gate on static files only."
        ),
        "converted_mdl_created": False,
        "android_apk_built": False,
        "visual_approval": "RED_NOT_TESTED",
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("MP40_VRIL_PREFLIGHT_COMPLETED_WITH_BLOCKERS")
    print(f"legacy={legacy['vertices']} verts / {legacy['triangles']} tris / {legacy['frames']} frames")
    print(f"gun={gun['total_render_vertices']} render verts / {gun['total_triangles']} tris")
    print(f"hands={hands['total_render_vertices']} render verts / {hands['total_triangles']} tris")
    print(f"total={v} render verts / {t} tris")
    print("format_converter=NOT_DONE visual_status=RED apk=NOT_BUILT")
    return 0  # Preflight succeeded, not the feature. Report is deliberately RED.


if __name__ == "__main__":
    raise SystemExit(main())
