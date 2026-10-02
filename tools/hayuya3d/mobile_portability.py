#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "mobile_portability.json"

PROFILE_TO_TIER = {
    "preview": "compatibility",
    "mobile": "compatibility",
    "game": "balanced",
    "monster": "high",
    "ultra": "flagship",
}

MODE_BUDGET_KEY = {
    "prop": "prop_lod0_triangles",
    "character": "character_lod0_triangles",
    "architecture": "architecture_piece_lod0_triangles",
}


def load_portability_spec(path: Path = SPEC_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if int(data.get("schema", 0)) != 1:
        raise ValueError("unsupported mobile portability schema")
    return data


def resolve_tier(tier: str, profile_name: str) -> str:
    if tier != "auto":
        return tier
    try:
        return PROFILE_TO_TIER[profile_name]
    except KeyError as exc:
        raise ValueError(f"unknown Hayuya profile: {profile_name}") from exc


def build_portability_plan(
    *,
    mode: str,
    tier: str = "auto",
    profile_name: str = "monster",
) -> dict:
    if mode not in MODE_BUDGET_KEY:
        raise ValueError(f"unsupported portability asset mode: {mode}")

    spec = load_portability_spec()
    resolved = resolve_tier(tier, profile_name)
    tiers = spec["hayuya_house_runtime_tiers"]
    if resolved not in tiers:
        raise ValueError(f"unknown portability tier: {resolved}")

    data = tiers[resolved]
    budget_key = MODE_BUDGET_KEY[mode]
    lod0 = list(data[budget_key])
    ratios = spec["lod_policy"]

    def scaled(ratio: float) -> list[int]:
        return [
            max(4, int(round(lod0[0] * ratio))),
            max(4, int(round(lod0[1] * ratio))),
        ]

    return {
        "knowledge_base": str(SPEC_PATH),
        "tier": resolved,
        "asset_mode": mode,
        "intent": data["intent"],
        "nominal_fps": data["nominal_fps"],
        "frame_budget_ms": data["frame_budget_ms"],
        "runtime_target": {
            "lod0_triangles": lod0,
            "lod1_triangles": scaled(float(ratios["lod1_ratio"])),
            "lod2_triangles": scaled(float(ratios["lod2_ratio"])),
            "lod3_triangles": scaled(float(ratios["lod3_ratio"])),
            "default_texture_edge_px": data["default_texture_edge_px"],
            "exceptional_texture_edge_px": data["exceptional_texture_edge_px"],
            "material_slots_target": data["material_slots_target"],
            "recommended_astc_block": data["recommended_astc_block"],
        },
        "hero_master": {
            "preserve": True,
            "rule": "runtime/mobile budgets never destructively cap the source-faithful hero master",
            "source_texture_edge_px": data.get("hero_source_texture_edge_px"),
        },
        "portable_contract": {
            "container": spec["universal_rules"]["portable_asset_container"],
            "portable_texture_container": spec["universal_rules"]["portable_distribution_texture_container"],
            "android_primary_texture_format": spec["universal_rules"]["android_primary_texture_format"],
            "android_fallback_texture_format": spec["universal_rules"]["android_fallback_texture_format"],
            "mipmaps_required": spec["universal_rules"]["texture_mipmaps_required_for_3d"],
            "simple_collision": spec["universal_rules"]["keep_collision_simpler_than_render_mesh"],
            "dynamic_quality_scaling": spec["universal_rules"]["dynamic_quality_scaling_required_for_long_mobile_sessions"],
            "thermal_validation_minimum_minutes": spec["universal_rules"]["thermal_validation_minimum_minutes"],
        },
        "important": "These are HAYUYA house portability budgets informed by public engine/hardware guidance, not universal engine hard limits. Real-device profiling wins.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve HAYUYA mobile portability targets.")
    parser.add_argument("--mode", choices=sorted(MODE_BUDGET_KEY), required=True)
    parser.add_argument(
        "--tier",
        choices=["auto", "compatibility", "balanced", "high", "flagship"],
        default="auto",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_TO_TIER),
        default="monster",
    )
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    result = build_portability_plan(
        mode=args.mode,
        tier=args.tier,
        profile_name=args.profile,
    )
    payload = json.dumps(result, indent=2) + "\n"
    print(payload, end="")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
