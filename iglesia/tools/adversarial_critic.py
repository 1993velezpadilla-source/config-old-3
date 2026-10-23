#!/usr/bin/env python3
"""Adversarial critic for real Iglesia source/build. Assumes nothing is correct.

It searches for actionable defects, not flattering GREEN badges. 'preview'
allows delivery of a playable build while reporting real art/device blockers;
'final' refuses sign-off unless BOTH art and real Android performance are proven.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SCRIPT = ROOT / "scripts"
STYLE = ROOT / "docs" / "NUN_FMF2_VISUAL_CONTRACT.json"

def issue(items, severity, code, evidence, action):
    items.append({"severity":severity,"code":code,"evidence":evidence,"next_action":action})
    print(f"ADVERSARIAL_{severity}_{code}: {evidence} | FIX: {action}")

def run(gate: str, android_probe: str) -> int:
    issues: list[dict] = []
    contract = json.loads(STYLE.read_text(encoding="utf-8"))
    if contract["id"] != "iglesia_nun_fmf2_target_v1":
        issue(issues, "FAIL", "STYLE_CONTRACT_CHANGED",
              "Owner-locked visual source mismatch", "Restore canonical target")
    player = (SCRIPT / "player.gd").read_text(encoding="utf-8")
    hud = (SCRIPT / "hud.gd").read_text(encoding="utf-8")
    level = (SCRIPT / "level.gd").read_text(encoding="utf-8")
    main = (SCRIPT / "main.gd").read_text(encoding="utf-8")
    stage = (ROOT / "tools" / "stage_assets.py").read_text(encoding="utf-8")
    enemy = (SCRIPT / "enemy.gd").read_text(encoding="utf-8")
    if "IGLESIA_MOBILE_TEXTURE_BUDGET" not in (ROOT / "tools" / "optimize_mobile_assets.py").read_text():
        issue(issues, "FAIL", "TEXTURE_LOD_MISSING", "4K originals uploaded straight to mobile",
              "Apply mobile stage-only LOD")
    budget_path = ASSETS / "mobile_texture_budget.json"
    if not budget_path.exists():
        issue(issues, "FAIL", "NO_STAGED_BUDGET", "Mobile texture report absent",
              "Run stage_assets.py with Pillow")
    else:
        data = json.loads(budget_path.read_text(encoding="utf-8"))
        fraction = data["runtime_pixels"]/max(1,data["source_pixels"])
        print(f"ADVERSARIAL_TEXTURE_RATIO {fraction:.3f} "
              f"{data['source_pixels']} -> {data['runtime_pixels']}")
        if data["tier"] == "mobile" and fraction > .40:
            issue(issues,"FAIL","MOBILE_TEXTURE_MEMORY_HIGH",
                  f"Retained {fraction:.1%} of 4K source pixels", "Cap fixture 1024/wall 2048")
        if any(max(t["runtime_dimensions"])>2048 for t in data["textures"]
               if data["tier"]=="mobile"):
            issue(issues,"FAIL","RUNTIME_TEXTURE_OVER_2K",
                  "Unexpected oversized material", "Reduce staged texture, not original ZIP")
    fixture_path = ASSETS / "tripo" / "fixtures_catalog.json"
    if not fixture_path.exists():
        issue(issues,"FAIL","NO_AUTHENTIC_TRIPO_CATALOG",
              "No import evidence", "Restore source-locked chandelier/holder ZIPs")
    else:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        if data["fixture_count"] != 10 or any(
          not v.get("source_geometry_glb_sha256") for v in data["fixtures"]):
            issue(issues,"FAIL","SOURCE_MODEL_UNTRUSTED",
                  "Missing one or more real Tripo GLBs", "Stage all 10 source-locked GLBs")
    if "_gothic_vault_ribs()" not in level or "MultiMesh.new()" not in level:
        issue(issues,"ART_BLOCKER","GOTHIC_ARCH_STRUCTURE_MISSING",
              "Nave interior is plain rectangular hall instead of gothic vaulted chapel",
              "Restore cheaply batched vault ribs, stained glass and candle lit aisle")
    if "shadow_enabled = true" in main:
        issue(issues,"FAIL","FULL_NAVE_SHADOW_OMNI",
              "Dynamic OmniLight renders costly full-scene shadow passes",
              "Disable or bake the wide-area caster")
    if "if index >= 4 or index % 2 != 0:" not in level:
        issue(issues,"FAIL","DYNAMIC_LIGHT_BUDGET",
              "Too many per-pixel dynamic lights for mobile",
              "Use at most four shadowless church practicals")
    if "emulate_mouse_from_touch=false" not in (ROOT/"project.godot").read_text():
        issue(issues,"FAIL","GHOST_FIRE_TOUCH",
              "Touch events can become mouse-left weapon fire",
              "Disable touch->mouse and test explicit FIRE hitbox")
    if "ads_active" not in player or 'buttons["fire"]' not in hud and '"fire"' not in hud:
        issue(issues,"FAIL","HUD_FIRE_ADS_RUNTIME_GAP",
              "Missing input routing", "Restore fire and aim touch controls")
    if "texture_normal" not in hud:
        issue(issues,"FAIL","OFFICIAL_TOUCH_BUTTON_SKINS_ABSENT",
              "HUD dropped approved fire/ADS art","Keep official PNG touchscreen assets")
    if 'nun_mp40_viewmodel.gd' in player or 'nun_mp40_viewmodel.gd' in hud:
        issue(issues,"FAIL","REJECTED_3D_RIG_REFERENCED",
              "Old model or skinned military hands still called by FPS",
              "Only reference weapon_sprite_animator.gd")
    if "stage_mp40()" in stage or "stage_nun_mp40_source()" in stage:
        issue(issues,"FAIL","REJECTED_MILITARY_SOURCE_RESTAGED",
              "CI would re-import the soldier arms or rejected sheet",
              "Remove all legacy MP40 staging calls")
    if "reject_legacy_mp40()" not in stage:
        issue(issues,"FAIL","NO_LEGACY_ART_PURGE",
              "Stale Godot import cache may keep rejected old art",
              "Purge stale mp40/ and mp40_nun/ during source stage")
    spriter = SCRIPT / "weapon_sprite_animator.gd"
    if not spriter.is_file() or "PROFILES :=" not in spriter.read_text(encoding="utf-8"):
        issue(issues,"FAIL","SPRITE_ANIMATOR_ABSENT",
              "No canonical independent PNG state machine","Restore 12/15/24 profile player")
    if "weapon_sprites.render(player, weapon" not in hud:
        issue(issues,"FAIL","SPRITE_PLAYER_NOT_IN_HUD",
              "HUD not drawing new camera-space MP40 frames","Attach PNG animator to actual HUD")
    if "_debug_texture()" in enemy:
        issue(issues,"FAIL","REJECTED_RECTANGULAR_NUN_PRESENT",
              "Old generated block-character zombie still coded",
              "Require only approved 2.5D Nun source PNGs")
    from collections import Counter
    expected_counts = {
        12: {"idle":1,"ads_idle":1,"fire":2,"ads_fire":1,"reload":5,"sprint":1,"equip":1},
        15: {"idle":1,"ads_idle":1,"fire":2,"ads_fire":2,"reload":7,"sprint":1,"equip":1},
        24: {"idle":1,"ads_idle":1,"fire":4,"ads_fire":3,"reload":12,"sprint":1,"equip":2},
    }
    src = json.loads((ASSETS / "SOURCES.json").read_text(encoding="utf-8"))
    if "mp40" in src:
        issue(issues,"FAIL","REJECTED_OLD_MP40_IN_AUTHORITY",
              "Legacy sprite sheet still an approved source", "Remove it from SOURCES.json")
    gun_folder = ASSETS / "weapons" / "mp40_nun_2d"
    sprite_frames = sorted(gun_folder.glob("*.png"))
    for requested, spec in expected_counts.items():
        needed = [f"{role}_{i:02d}.png" for role,num in spec.items()
                  for i in range(num)]
        if len(needed) != requested:
            issue(issues,"FAIL","BAD_SPRITE_BUDGET",
                  f"{requested} frame variant calculates to {len(needed)}",
                  "Correct per-action frame allocations")
        missing_files = [name for name in needed if not (gun_folder/name).is_file()]
        if missing_files:
            issue(issues,"ART_BLOCKER",f"MP40_{requested}_PNG_PENDING",
                  f"{len(missing_files)}/{requested} original hand-drawn frames absent",
                  "Prepare consistent PNGs from the chosen Nun aesthetic; no soldiers")
        else:
            print(f"ADVERSARIAL_MP40_PROFILE_{requested}_FRAMES_PRESENT")
    for filename in sprite_frames:
        with Image.open(filename) as im:
            if im.mode != "RGBA" or im.getchannel("A").getbbox() is None:
                issue(issues,"FAIL","MP40_ALPHA_INVALID",str(filename),
                      "Use transparent RGBA PNGs")
            if im.width>768 or im.height>512:
                issue(issues,"FAIL","MP40_MOBILE_TEXTURE_OVER_BUDGET",
                      f"{filename.name} at {im.size}",
                      "Resize/export viewmodel PNG within 768x512 maximum")
    enemy_folder = ASSETS / "enemies" / "gothic_nun_2d"
    required_nun = ["idle_00.png","walk_00.png","attack_00.png","death_00.png"]
    if any(not (enemy_folder/name).is_file() for name in required_nun):
        issue(issues,"ART_BLOCKER","GOTHIC_NUN_SPRITES_PENDING",
              "No complete approved idle/walk/attack/death source PNG sequences",
              "Bake/draw and integrate the chosen Gothic Nun in 2.5D")
    # One phone screenshot and human approval are needed for visual parity;
    # satisfying frame counts alone does not grant fidelity approval.
    issue(issues,"ART_BLOCKER","ART_VISUAL_FIDELITY_NOT_SIGNED_OFF",
          "Source PNGs must match the selected Nun, pale bare hands and black sleeves",
          "Capture actual Pixel Fold screenshot and request owner art approval")
    # No claim of real hardware performance without an actual device sample.
    probe=Path(android_probe) if android_probe else None
    if probe and probe.exists():
        q=json.loads(probe.read_text(encoding="utf-8"))
        if q.get("device") not in ("Android","android"):
            issue(issues,"NEEDS_DEVICE","PERF_DEVICE_NOT_ANDROID",
                  f"Telemetry from {q.get('device')}", "Run on actual Pixel Fold")
        if q.get("min_sampled_fps",0)<30:
            issue(issues,"PERF_BLOCKER","PIXEL_FOLD_FPS_BELOW_30",
                  f"Lowest sampled FPS {q.get('min_sampled_fps')}",
                  "Reduce view geometry/overdraw; profile frame pacing on device")
        else:
            print("ADVERSARIAL_DEVICE_FPS_SAMPLE",q.get("min_sampled_fps"))
    else:
        issue(issues,"NEEDS_DEVICE","FPS_UNVERIFIED_ON_PIXEL_FOLD",
              "GitHub Actions headless smoke is not an Android FPS test",
              "Collect user://iglesia_mobile_perf_latest.json on Pixel Fold")
    fails=[x for x in issues if x["severity"]=="FAIL"]
    blockers=[x for x in issues if x["severity"] in
              ("FAIL","ART_BLOCKER","PERF_BLOCKER","NEEDS_DEVICE")]
    outcome="RED" if (fails if gate=="preview" else blockers) else "GREEN"
    report={"schema":1,"gate":gate,"outcome":outcome,
            "final_art_approved":False if any(x["severity"]=="ART_BLOCKER" for x in issues) else None,
            "android_performance_verified":not any(x["code"]=="FPS_UNVERIFIED_ON_PIXEL_FOLD" for x in issues),
            "findings":issues,"next_tasks":[x["next_action"] for x in blockers],
            "note":"Automatic critic flags suspected source and structural defects. It cannot certify visual similarity without in-engine screenshots and device review."}
    output=ROOT/"build"/"adversarial_critic.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    md=[f"# Iglesia adversarial critic — {gate}: {outcome}","",
        "No auto-approval of old military hands, mixed sprites or untested phone FPS.",""]
    for x in issues:
        md.append(f"- **{x['severity']} / {x['code']}** — {x['evidence']} → {x['next_action']}")
    (ROOT/"build"/"adversarial_critic.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(f"ADVERSARIAL_CRITIC_{outcome}: {len(issues)} findings, "
          f"{len(fails)} must-fix code/asset failures, "
          f"{len(blockers)} unresolved final release issues")
    return 1 if outcome=="RED" else 0

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--gate",choices=("preview","final"),default="preview")
    parser.add_argument("--android-probe",default="")
    args=parser.parse_args()
    raise SystemExit(run(args.gate,args.android_probe))

if __name__=="__main__":
    main()
