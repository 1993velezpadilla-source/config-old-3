#!/usr/bin/env python3
"""Generate a CTW3D patch-profile template from elf_probe JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PREFIX = "Java_com_rockstargames_oswrapper_GameNative_"
DRAW = PREFIX + "implOnDrawFrame"
SETUP = PREFIX + "implOnInitialSetup"
AXES = PREFIX + "implOnGamepadAxesChanged"

TARGET_KEYS = (
    "camera_update",
    "projection_setup",
    "world_stream_update",
    "sector_visibility",
    "lod_test",
    "player_render",
)


def _jni_rva(report: dict, name: str) -> int | None:
    details = report.get("symbols", {}).get("known_jni_details", {})
    item = details.get(name)
    if not item or not item.get("present"):
        return None
    value = item.get("value")
    return int(value) if value is not None else None


def summarize_xrefs(xref_report: dict | None) -> dict:
    groups = (xref_report or {}).get("groups", {})
    out = {}
    for group in ("camera", "streaming", "lod_culling", "player_render"):
        by_func = {}
        for item in groups.get(group, []):
            rva = item.get("function_rva")
            name = item.get("function")
            if rva is None:
                continue
            key = (name, int(rva))
            entry = by_func.setdefault(key, {
                "function": name,
                "rva": int(rva),
                "hits": 0,
                "strings": [],
                "call_sites": [],
            })
            entry["hits"] += 1
            text = item.get("string")
            if text and text not in entry["strings"]:
                entry["strings"].append(text)
            pc = item.get("pc_rva")
            if pc is not None and pc not in entry["call_sites"]:
                entry["call_sites"].append(pc)

        ranked = sorted(
            by_func.values(),
            key=lambda x: (-x["hits"], x["rva"]),
        )
        out[group] = ranked[:32]
    return out


def make_profile(report: dict, xref_report: dict | None = None) -> dict:
    if report.get("elf", {}).get("machine") != "AArch64":
        raise ValueError("report is not for an AArch64 libGame.so")

    draw_rva = _jni_rva(report, DRAW)
    setup_rva = _jni_rva(report, SETUP)
    axes_rva = _jni_rva(report, AXES)

    if draw_rva is None or setup_rva is None:
        raise ValueError("report is missing required CTW GameNative JNI RVAs")

    candidates = report.get("symbols", {}).get("candidate_groups", {})
    candidate_summary = {}
    for group in ("camera", "streaming", "lod_culling", "player_render"):
        entries = candidates.get(group, [])
        candidate_summary[group] = [
            {
                "name": item.get("name"),
                "rva": item.get("value"),
                "size": item.get("size"),
            }
            for item in entries[:64]
            if item.get("source") == "symbol"
        ]

    return {
        "schema": 1,
        "game": "GTA Chinatown Wars Android",
        "abi": "arm64-v8a",
        "fingerprint": {
            "file_size": report.get("file_size"),
            "sha256": report.get("sha256"),
            "text_sha256": report.get("text", {}).get("sha256"),
            "gnu_build_id": report.get("elf", {}).get("build_id"),
            "jni_rvas": {
                "implOnDrawFrame": draw_rva,
                "implOnInitialSetup": setup_rva,
                "implOnGamepadAxesChanged": axes_rva,
            },
        },
        "patch_targets_rva": {key: None for key in TARGET_KEYS},
        "camera_defaults": {
            "initial_mode": "third_person",
            "toggle_button": 13,
            "right_stick_look": True,
            "fov_degrees": 70.0,
            "near_clip": 0.05,
        },
        "world_distance_defaults": {
            "far_clip_multiplier": 2.0,
            "stream_radius_multiplier": 2.0,
            "lod_distance_multiplier": 2.0,
            "requires_coordinated_patch": True,
        },
        "candidate_symbols": candidate_summary,
        "candidate_xref_functions": summarize_xrefs(xref_report),
        "status": "template_needs_verified_internal_rvas",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("elf_report", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--xrefs", type=Path, help="Optional aarch64_xref JSON report")
    args = ap.parse_args()

    try:
        report = json.loads(args.elf_report.read_text(encoding="utf-8"))
        xrefs = (
            json.loads(args.xrefs.read_text(encoding="utf-8"))
            if args.xrefs is not None else None
        )
        profile = make_profile(report, xrefs)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
