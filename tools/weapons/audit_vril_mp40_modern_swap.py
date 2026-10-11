#!/usr/bin/env python3
"""Read the actual MP40 Godot GLB files and assess feasibility in Vril MDL v6.

Read-only. Does NOT modify meshes, animations, copyright-protected assets,
QuakeC gameplay, or Android APKs. A successful audit is not a successful port.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

# Confirmed in NZ:P Android v2.3.14:
# vril-engine/source/platform/android/gl/gl_model.h lines 309-311
VRIL_LIMITS = {"vertices": 2048, "triangles": 2048, "frames": 256}


def glb(path: Path) -> dict:
    with path.open("rb") as f:
        header = f.read(20)
        if len(header) != 20:
            raise ValueError(f"{path}: incomplete GLB header")
        magic, version, total, length, kind = struct.unpack("<4sIIII", header)
        if magic != b"glTF" or version != 2 or kind != 0x4E4F534A:
            raise ValueError(f"{path}: expected glTF 2 binary JSON chunk")
        if total != path.stat().st_size:
            raise ValueError(f"{path}: declared byte count != file size")
        doc = json.loads(f.read(length).decode("utf-8"))
    return doc


def summarize(path: Path) -> dict:
    doc = glb(path)
    accessors = doc.get("accessors", [])
    meshes = []
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            attrs = prim.get("attributes", {})
            pos_idx = attrs.get("POSITION")
            vertex_count = int(accessors[pos_idx]["count"]) if pos_idx is not None else 0
            idx = prim.get("indices")
            index_count = int(accessors[idx]["count"]) if idx is not None else vertex_count
            mode = prim.get("mode", 4)
            triangles = index_count // 3 if mode == 4 else None
            meshes.append({"name": mesh.get("name"), "vertices": vertex_count,
                           "triangles": triangles, "primitive_mode": mode,
                           "skinned": "JOINTS_0" in attrs})
    clips = {}
    for animation in doc.get("animations", []):
        mins, maxs = [], []
        for sampler in animation.get("samplers", []):
            acc = accessors[sampler["input"]]
            if "min" in acc and "max" in acc:
                mins.append(float(acc["min"][0]))
                maxs.append(float(acc["max"][0]))
        clips[str(animation.get("name", ""))] = {
            "duration_seconds": round(max(maxs) - min(mins), 6) if mins else None,
            "channels": len(animation.get("channels", [])),
        }
    return {"file": str(path), "bytes": path.stat().st_size,
            "meshes": meshes, "total_vertices": sum(m["vertices"] for m in meshes),
            "total_triangles": sum(m["triangles"] or 0 for m in meshes),
            "skin_joint_counts": [len(x["joints"]) for x in doc.get("skins", [])],
            "node_names": [str(x.get("name", "")) for x in doc.get("nodes", [])],
            "animations": clips}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("xogot/assets/weapons"))
    parser.add_argument("--output", type=Path, default=Path("build/vril-mp40-feasibility.json"))
    args = parser.parse_args()

    gun_path = args.root / "aether_waw_real/mp40/viewmodel.glb"
    hands_path = args.root / "aether_waw_hands/t4_marine/mp40/viewhands.glb"
    gun, hands = summarize(gun_path), summarize(hands_path)
    clips = gun["animations"]
    gun_nodes, hand_nodes = set(gun["node_names"]), set(hands["node_names"])
    required_gun = ["PSA_viewmodel_mp40_fire", "PSA_viewmodel_mp40_reload",
                    "PSA_viewmodel_mp40_reload_empty"]
    required_hands = ["PSA_viewmodel_mp40_reload_empty", "PSA_HandIdleMP40"]
    missing = ([f"gun:{c}" for c in required_gun if c not in clips]
               + [f"hands:{c}" for c in required_hands if c not in hands["animations"]]
               + [f"gun-bone:{n}" for n in ("j_clip", "j_bolt") if n not in gun_nodes]
               + [f"hands-bone:{n}" for n in ("tag_weapon", "tag_view")
                  if n not in hand_nodes])
    need_vertex_reduction = (gun["total_vertices"] > VRIL_LIMITS["vertices"]
                             or gun["total_triangles"] > VRIL_LIMITS["triangles"])
    combined = {"vertices": gun["total_vertices"] + hands["total_vertices"],
                "triangles": gun["total_triangles"] + hands["total_triangles"]}
    report = {
        "status": "AUDIT_ONLY_NO_APK_NO_MDL",
        "source_branch": "audit/black-pines-mp40-runtime-frame-proof-20261011",
        "vril_mdl6_runtime_limits": VRIL_LIMITS,
        "gun": {k: v for k, v in gun.items() if k != "node_names"},
        "hands": {k: v for k, v in hands.items() if k != "node_names"},
        "missing_expected_source": missing,
        "gun_exceeds_vril_mdl_budget": need_vertex_reduction,
        "combined_undecimated_geometry": combined,
        "combined_exceeds_vril_mdl_budget": (
            combined["vertices"] > VRIL_LIMITS["vertices"]
            or combined["triangles"] > VRIL_LIMITS["triangles"]),
        "direct_glb_swap_works": False,
        "conversion_needs": [
            "Bake the authored gun AND hand skeleton animation to vertex frames.",
            "Solve animated tag_weapon attachment/orientation in source space.",
            "Decimate or explicitly expand/test Android MDL vertex and triangle limits.",
            "Map tactical and empty reloads onto QuakeC frame sequences and durations.",
            "Convert textures to Vril-supported external skin (PCX or TGA).",
            "Render and visually approve hands, magazine, barrel and ADS on Android.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("VRIL_MP40_SOURCE_AUDIT", json.dumps({
        "missing": missing, "gun_vertices": gun["total_vertices"],
        "gun_triangles": gun["total_triangles"], "combined_geometry": combined,
        "vril_limits": VRIL_LIMITS,
        "tactical_reload_s": clips.get("PSA_viewmodel_mp40_reload", {}).get("duration_seconds"),
        "empty_reload_s": clips.get("PSA_viewmodel_mp40_reload_empty", {}).get("duration_seconds"),
        "result": report["status"],
    }))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
