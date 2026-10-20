#!/usr/bin/env python3
"""Fail-closed release readiness gate for Sanctum of Ash.

A successful static route check or Android build is not evidence of live
zombie navigation, physical pew collision, or active 2D Colt rendering.
"""
import argparse
import json
from pathlib import Path

def assess(nav, art, material):
    issues = []
    if nav.get("ai_live_gameplay_proof") != "VERIFIED_ON_ANDROID":
        issues.append("LIVE_ZOMBIE_NAVIGATION_NOT_VERIFIED")
    if "visual-only" in nav.get("pew_hulls", "").lower():
        issues.append("PEW_COLLISION_VISUAL_ONLY")
    if art.get("status") != "ACTIVE_NATIVE_RENDERER_VERIFIED":
        issues.append("COLT_2D_ART_NOT_ACTIVE")
    if "NOT NATIVE 4K" in material.get("runtime_bsp_resolution", ""):
        issues.append("BSP_RUNTIME_TEXTURES_NOT_4K")
    return issues

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--navigation", type=Path, required=True)
    p.add_argument("--art", type=Path, required=True)
    p.add_argument("--materials", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--require-release", action="store_true")
    a = p.parse_args()
    nav = json.loads(a.navigation.read_text())
    art = json.loads(a.art.read_text())
    material = json.loads(a.materials.read_text())
    blockers = assess(nav, art, material)
    report = {"release_ready": not blockers, "blockers": blockers,
              "note": "Static tests and a green APK do not prove live gameplay."}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n")
    print("SANCTUM_RELEASE_READINESS", json.dumps(report))
    if a.require_release and blockers:
        raise SystemExit("RELEASE_BLOCKED: " + ", ".join(blockers))

if __name__ == "__main__":
    main()
