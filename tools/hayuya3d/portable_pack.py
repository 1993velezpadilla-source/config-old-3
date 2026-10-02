#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from gameprep import GamePrepResult, build_gameprep
from mobile_portability import build_portability_plan
from portable_textures import detect_toolchain, transcode_glb_to_ktx2
from visual_judge import SourceViewScore

TIERS = ("flagship", "high", "balanced", "compatibility")


@dataclass
class PortableTierArtifact:
    tier: str
    directory: str
    portability_plan: dict
    gameprep: dict
    lod_parity: dict
    runtime_budget: dict
    texture_delivery: dict


@dataclass
class PortablePackResult:
    hero_master: str
    tiers: list[PortableTierArtifact]
    manifest: str
    asset_mode: str
    profile_name: str
    complete_lod_chain: bool
    lod_parity_ready: bool
    runtime_budget_ready: bool
    notes: list[str]


def _tier_dir_name(tier: str) -> str:
    return {
        "flagship": "Flagship",
        "high": "High",
        "balanced": "Balanced",
        "compatibility": "Compatibility",
    }[tier]


def build_portable_pack(
    hero_glb: Path,
    out_dir: Path,
    *,
    mode: str,
    profile_name: str,
    anchor_view: SourceViewScore | None = None,
    material_samples: int = 180_000,
    tiers: tuple[str, ...] = TIERS,
    texture_delivery_mode: str = "auto",
) -> PortablePackResult:
    hero_glb = hero_glb.resolve()
    if not hero_glb.is_file():
        raise FileNotFoundError(hero_glb)

    out_dir.mkdir(parents=True, exist_ok=True)
    hero_dir = out_dir / "HeroMaster"
    hero_dir.mkdir(parents=True, exist_ok=True)
    hero_out = hero_dir / "master.glb"
    shutil.copy2(hero_glb, hero_out)

    if texture_delivery_mode not in {"off", "auto", "required"}:
        raise ValueError("texture_delivery_mode must be off, auto or required")

    texture_toolchain = detect_toolchain() if texture_delivery_mode != "off" else None
    if texture_delivery_mode == "required" and (texture_toolchain is None or not texture_toolchain.ready):
        reasons = [] if texture_toolchain is None else texture_toolchain.reasons
        raise RuntimeError("portable texture delivery required but unavailable: " + "; ".join(reasons))

    artifacts: list[PortableTierArtifact] = []
    complete_lod_chain = True
    lod_parity_ready = True
    runtime_budget_ready = True
    notes: list[str] = [
        "HeroMaster/master.glb is an exact preserved copy and is never capped by a mobile runtime tier.",
        "Each runtime tier is independently derived from HeroMaster rather than from a lower-quality tier.",
        "When the pinned KTX toolchain is available, each runtime LOD is physically transcoded to KTX2/Basis Universal inside a sibling ktx2/ GLB using KHR_texture_basisu.",
    ]

    for tier in tiers:
        plan = build_portability_plan(
            mode=mode,
            tier=tier,
            profile_name=profile_name,
        )
        runtime = plan["runtime_target"]
        target_faces = int(runtime["lod0_triangles"][1])
        max_texture_size = int(runtime["exceptional_texture_edge_px"])

        tier_dir = out_dir / _tier_dir_name(tier)
        result: GamePrepResult = build_gameprep(
            hero_glb,
            tier_dir,
            target_faces=target_faces,
            anchor_view=anchor_view,
            material_samples=material_samples,
            max_texture_size=max_texture_size,
        )
        if len(result.lods) < 4:
            complete_lod_chain = False

        try:
            from lod_parity import audit_lod_chain
            parity = audit_lod_chain(
                hero_glb,
                [
                    (lod.name,Path(lod.path))
                    for lod in result.lods
                ],
                mode=mode,
                samples=1600,
            )
            lod_parity = asdict(parity)
            parity_path = tier_dir / "lod_parity.json"
            parity_path.write_text(
                json.dumps(lod_parity,indent=2)+"\n",
                encoding="utf-8",
            )
            lod_parity["report"] = str(parity_path)
            if not parity.ready:
                lod_parity_ready = False
                complete_lod_chain = False
                notes.append(
                    f"{tier} LOD parity blocked runtime readiness: "
                    + "; ".join(parity.errors[:4])
                )
        except Exception as exc:
            lod_parity_ready = False
            complete_lod_chain = False
            lod_parity = {
                "ready":False,
                "lod_count":len(result.lods),
                "items":[],
                "errors":[f"{type(exc).__name__}:{exc}"],
                "report":None,
            }
            notes.append(
                f"{tier} LOD parity unavailable: "
                f"{type(exc).__name__}:{exc}"
            )

        try:
            from runtime_budget_qa import audit_runtime_tier
            runtime_report = audit_runtime_tier(
                [
                    (lod.name,Path(lod.path))
                    for lod in result.lods
                ],
                plan=plan,
                mode=mode,
            )
            runtime_budget = asdict(runtime_report)
            runtime_budget_path = tier_dir / "runtime_budget.json"
            runtime_budget_path.write_text(
                json.dumps(runtime_budget,indent=2)+"\n",
                encoding="utf-8",
            )
            runtime_budget["report"] = str(runtime_budget_path)
            if not runtime_report.ready:
                runtime_budget_ready = False
                notes.append(
                    f"{tier} runtime asset budget blocked readiness: "
                    + "; ".join(runtime_report.errors[:4])
                )
        except Exception as exc:
            runtime_budget_ready = False
            runtime_budget = {
                "ready":False,
                "tier":tier,
                "mode":mode,
                "lod_count":len(result.lods),
                "items":[],
                "errors":[f"{type(exc).__name__}:{exc}"],
                "warnings":[],
                "report":None,
            }
            notes.append(
                f"{tier} runtime asset budget unavailable: "
                f"{type(exc).__name__}:{exc}"
            )

        texture_delivery = {
            "mode": texture_delivery_mode,
            "format": "KTX2 + Basis Universal / KHR_texture_basisu",
            "status": "off" if texture_delivery_mode == "off" else "skipped_unavailable",
            "toolchain": asdict(texture_toolchain) if texture_toolchain is not None else None,
            "artifacts": [],
            "native_gpu_note": "KTX2 Basis Universal is physically embedded in the GLB and may transcode at runtime to GPU-native formats such as ASTC or ETC2. Native ASTC/ETC2 app packages remain engine/build-system responsibilities.",
        }
        if texture_delivery_mode != "off" and texture_toolchain is not None and texture_toolchain.ready:
            texture_delivery["status"] = "ready"
            ktx_dir = tier_dir / "ktx2"
            for lod in result.lods:
                source_lod = Path(lod.path)
                output_lod = ktx_dir / f"{lod.name}.glb"
                artifact = transcode_glb_to_ktx2(
                    source_lod,
                    output_lod,
                    max_texture_size=max_texture_size,
                    toolchain=texture_toolchain,
                )
                texture_delivery["artifacts"].append(asdict(artifact))
        elif texture_delivery_mode == "required":
            raise RuntimeError("portable texture delivery required but toolchain is unavailable")

        tier_manifest = {
            "tier": tier,
            "portability_plan": plan,
            "gameprep": asdict(result),
            "lod_parity": lod_parity,
            "runtime_budget": runtime_budget,
            "texture_delivery": texture_delivery,
        }
        (tier_dir / "tier_manifest.json").write_text(
            json.dumps(tier_manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        artifacts.append(
            PortableTierArtifact(
                tier=tier,
                directory=str(tier_dir),
                portability_plan=plan,
                gameprep=asdict(result),
                lod_parity=lod_parity,
                runtime_budget=runtime_budget,
                texture_delivery=texture_delivery,
            )
        )

    if not complete_lod_chain:
        notes.append(
            "One or more tiers could not emit LOD1-LOD3 because the accepted GLB is skinned. "
            "HAYUYA preserves JOINTS/WEIGHTS instead of destructively simplifying rigged geometry."
        )

    manifest = out_dir / "portable_pack_manifest.json"
    result = PortablePackResult(
        hero_master=str(hero_out),
        tiers=artifacts,
        manifest=str(manifest),
        asset_mode=mode,
        profile_name=profile_name,
        complete_lod_chain=complete_lod_chain,
        lod_parity_ready=lod_parity_ready,
        runtime_budget_ready=runtime_budget_ready,
        notes=notes,
    )
    manifest.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build all HAYUYA mobile portability tiers from one preserved Hero Master."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["prop", "character", "architecture"], required=True)
    parser.add_argument(
        "--profile",
        choices=["preview", "mobile", "game", "monster", "ultra"],
        default="ultra",
    )
    parser.add_argument("--material-samples", type=int, default=180000)
    parser.add_argument(
        "--texture-delivery",
        choices=["off", "auto", "required"],
        default="auto",
        help="physically embed KTX2/Basis Universal textures in runtime GLBs when the pinned toolchain is available",
    )
    args = parser.parse_args()

    result = build_portable_pack(
        args.input,
        args.output,
        mode=args.mode,
        profile_name=args.profile,
        material_samples=args.material_samples,
        texture_delivery_mode=args.texture_delivery,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
