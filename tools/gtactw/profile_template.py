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


def make_profile(report: dict) -> dict:
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
        "status": "template_needs_verified_internal_rvas",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("elf_report", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    try:
        report = json.loads(args.elf_report.read_text(encoding="utf-8"))
        profile = make_profile(report)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
