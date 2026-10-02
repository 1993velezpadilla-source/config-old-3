#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from adapters import DEFAULT_MODEL_ROOT, GENERATORS, REFINERS, pshuman_readiness
from qa import export_glb, rank_candidates
from reference_pool import infer_detail_region_hint, order_for_multiview_coverage, split_reference_roles
from mobile_portability import build_portability_plan
from native_geometry_guard import ProjectionProxyRejected, assert_native_candidate
from native_360_geometry_gate import Native360GeometryRejected, assert_native_character_360


@dataclass(frozen=True)
class Profile:
    # Runtime triangle budget used only after the fidelity-approved Hero Master
    # exists. Never feed this value into high-end reconstruction backends.
    faces: int
    # Dense reconstruction target. Monster/Ultra intentionally preserve a
    # Tripo-class Hero Master before retopology/LOD generation.
    hero_faces: int
    texture_size: int
    trellis2_resolution: int
    backends: tuple[str, ...]
    multi_anchor: bool
    multiview_group_size: int


PROFILES = {
    "preview": Profile(
        faces=30_000,
        hero_faces=30_000,
        texture_size=1024,
        trellis2_resolution=512,
        backends=("triposr", "triposg"),
        multi_anchor=False,
        multiview_group_size=4,
    ),
    "mobile": Profile(
        faces=35_000,
        hero_faces=120_000,
        texture_size=2048,
        trellis2_resolution=512,
        backends=("trellis", "triposg", "triposr"),
        multi_anchor=False,
        multiview_group_size=5,
    ),
    "game": Profile(
        faces=80_000,
        hero_faces=400_000,
        texture_size=2048,
        trellis2_resolution=1024,
        backends=("triposg", "trellis", "instantmesh", "triposr"),
        multi_anchor=True,
        multiview_group_size=6,
    ),
    "monster": Profile(
        faces=250_000,
        hero_faces=1_500_000,
        texture_size=4096,
        trellis2_resolution=1024,
        backends=("trellis2", "triposg", "trellis", "instantmesh", "triposr"),
        multi_anchor=True,
        multiview_group_size=6,
    ),
    "ultra": Profile(
        faces=500_000,
        hero_faces=2_000_000,
        texture_size=4096,
        trellis2_resolution=1536,
        backends=("trellis2", "triposg", "trellis", "instantmesh", "triposr"),
        multi_anchor=True,
        multiview_group_size=8,
    ),
}


def load_lock() -> dict:
    return json.loads((HERE / "backends.lock.json").read_text(encoding="utf-8"))


def backend_meta(lock: dict) -> dict[str, dict]:
    return {x["id"]: x for x in lock["backends"]}


def validate_inputs(inputs: list[Path]) -> list[Path]:
    if not inputs:
        raise ValueError("Hayuya Monster requires at least one source photo")

    out: list[Path] = []
    seen_paths: set[Path] = set()
    seen_content: set[str] = set()
    for p in inputs:
        p = p.resolve()
        if p in seen_paths:
            # Do not let accidental duplicate CLI args overweight one image in the Judge.
            continue
        seen_paths.add(p)

        if not p.is_file():
            raise FileNotFoundError(p)
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError(f"unsupported image format: {p}")
        if p.stat().st_size < 512:
            raise ValueError(f"image is unexpectedly small: {p}")

        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        if digest in seen_content:
            # Copied/renamed duplicate files should not count as extra evidence.
            continue
        seen_content.add(digest)
        out.append(p)

    if not out:
        raise ValueError("no unique valid source photos remain")
    return out


def infer_asset_mode(primary: Path) -> str:
    parts = {part.lower() for part in primary.parts}
    stem_tokens = set(primary.stem.lower().replace("-", "_").split("_"))
    tokens = parts | stem_tokens

    character_tokens = {
        "character", "characters", "zombie", "zombies", "human", "humans",
        "humanoid", "humanoids", "npc", "npcs", "llorona",
    }
    architecture_tokens = {
        "architecture", "building", "buildings", "church", "churches", "iglesia",
    }
    if tokens & character_tokens:
        return "character"
    if tokens & architecture_tokens:
        return "architecture"
    return "prop"


ASSET_PROFILE_IDS = {
    "auto", "character.humanoid", "character.creature", "weapon.firearm",
    "weapon.melee", "prop.mechanical", "vehicle", "foliage.grass",
    "foliage.tree", "prop.static", "environment.modular",
}


def infer_asset_profile(primary: Path, mode: str = "auto") -> str:
    raw_parts = [part.lower() for part in primary.parts]
    tokens = set(raw_parts)
    for part in [*raw_parts, primary.stem.lower()]:
        tokens.update(part.replace("-", "_").replace(".", "_").split("_"))

    if tokens & {"pistol","handgun","revolver","shotgun","rifle","smg","lmg","gun","firearm","sniper","launcher","p90"}:
        return "weapon.firearm"
    if tokens & {"sword","knife","machete","axe","bat","club","melee"}:
        return "weapon.melee"
    if tokens & {"grass","turf"}:
        return "foliage.grass"
    if tokens & {"tree","trees","bush","bushes","plant","plants","foliage"}:
        return "foliage.tree"
    if tokens & {"car","cars","truck","vehicle","vehicles","van","bike","motorcycle"}:
        return "vehicle"
    if tokens & {"door","fan","gear","machine","mechanical","hinge","elevator"}:
        return "prop.mechanical"
    if tokens & {"monster","creature","animal","quadruped"}:
        return "character.creature"
    if tokens & {"character","characters","zombie","zombies","human","humans","humanoid","humanoids","npc","npcs","llorona"}:
        return "character.humanoid"
    if mode == "character":
        return "character.humanoid"
    if mode == "architecture":
        return "environment.modular"
    return "prop.static"


def load_asset_profile_spec(asset_profile: str) -> dict:
    path = ROOT / "hayuya" / "standards" / "hayuya_asset_profiles_v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for profile in data.get("profiles", []):
        if profile.get("id") == asset_profile:
            return profile
    if asset_profile == "auto":
        return {
            "id": "auto",
            "label": "Auto",
            "animation_systems": [],
            "preferred_pipeline": [],
            "required_qa": ["mesh_gate", "texture_clarity"],
        }
    raise ValueError(f"unknown asset profile: {asset_profile}")


def is_head_detail_evidence(
    path: Path,
    *,
    semantic_head_inputs: list[Path] | set[Path] | None = None,
) -> bool:
    semantic={
        Path(item).resolve()
        for item in (semantic_head_inputs or [])
    }
    return (
        Path(path).resolve() in semantic
        or infer_detail_region_hint(Path(path))=="head"
    )


def face_seed_hypothesis_count(
    profile_name: str,
    detail_inputs: list[Path],
    *,
    semantic_head_inputs: list[Path] | set[Path] | None = None,
) -> int:
    has_face_reference=any(
        is_head_detail_evidence(
            path,
            semantic_head_inputs=semantic_head_inputs,
        )
        for path in detail_inputs
    )
    if not has_face_reference:
        return 1
    if profile_name=="ultra":
        return 3
    if profile_name=="monster":
        return 2
    return 1


def reclassify_semantic_face_closeups(
    geometry_inputs: list[Path],
    real_detail_inputs: list[Path],
    source_autofix_result,
    *,
    min_face_box_fraction: float = 0.08,
) -> tuple[list[Path], list[Path], list[Path]]:
    """Move obvious unnamed face close-ups out of the geometry reference pool.

    Filename routing remains conservative by default. During execution, however,
    source-autofix already has grounded face evidence. A direct, semantically
    confirmed face occupying a large image fraction is better treated as local
    head evidence when another real geometry source remains available.
    """
    geometry=[Path(path).resolve() for path in geometry_inputs]
    details=[Path(path).resolve() for path in real_detail_inputs]
    if source_autofix_result is None or len(geometry)<=1:
        return geometry,details,[]

    geometry_set=set(geometry)
    candidates=[]
    for item in list(getattr(source_autofix_result,"sources",[]) or []):
        try:
            source=Path(getattr(item,"source")).resolve()
        except Exception:
            continue
        fraction=getattr(item,"face_box_fraction",None)
        if (
            source not in geometry_set
            or not bool(getattr(item,"direct_face_detected",False))
            or not bool(
                getattr(item,"semantic_face_or_head_confirmed",False)
            )
            or fraction is None
            or float(fraction)<float(min_face_box_fraction)
        ):
            continue
        candidates.append((source,float(fraction)))

    if not candidates:
        return geometry,details,[]

    # Move the strongest close-ups first but always preserve >=1 real geometry
    # source. An all-close-up job still needs one primary reconstruction anchor.
    index={path:i for i,path in enumerate(geometry)}
    candidates.sort(key=lambda item:(-item[1],index[item[0]]))
    move_limit=max(0,len(geometry)-1)
    moved=[path for path,_fraction in candidates[:move_limit]]
    moved_set=set(moved)

    geometry=[path for path in geometry if path not in moved_set]
    for path in moved:
        if path not in details:
            details.append(path)
    return geometry,details,moved


def native_conform_mutation_blockers(gltf_audit) -> list[str]:
    """Return GLB features that a trimesh vertex round-trip must not touch."""
    blockers: list[str] = []
    if not bool(getattr(gltf_audit, "valid_glb", True)):
        blockers.append("invalid_glb")
    errors = list(getattr(gltf_audit, "errors", None) or [])
    if errors:
        blockers.append("gltf_audit_errors=" + str(len(errors)))

    skins = int(getattr(gltf_audit, "skin_count", 0) or 0)
    animations = int(getattr(gltf_audit, "animation_count", 0) or 0)
    morph_targets = int(getattr(gltf_audit, "morph_target_count", 0) or 0)
    if skins:
        blockers.append(f"skins={skins}")
    if animations:
        blockers.append(f"animations={animations}")
    if morph_targets:
        blockers.append(f"morph_targets={morph_targets}")
    return blockers


def needs_texture_superres(
    profile_name: str,
    base_color_min_edge: int | None,
    target_edge: int,
) -> bool:
    if profile_name not in {"monster", "ultra"}:
        return False
    edge=int(base_color_min_edge or 0)
    return edge>0 and edge<int(target_edge)


def texture_refinement_regressions(source, challenger) -> list[str]:
    """Reject a resolution-only win when stronger fidelity evidence regresses."""
    reasons=[]

    # Image rewriting must not alter geometry/topology at all.
    for name in ("vertices","faces","components"):
        a=getattr(source,name,None)
        b=getattr(challenger,name,None)
        if a is not None and b is not None and a!=b:
            reasons.append(f"geometry_changed:{name}:{a}->{b}")
    a_bbox=getattr(source,"bbox",None)
    b_bbox=getattr(challenger,"bbox",None)
    if a_bbox is not None and b_bbox is not None and list(a_bbox)!=list(b_bbox):
        reasons.append("geometry_changed:bbox")

    source_channels=set(getattr(source,"pbr_channels",None) or [])
    challenger_channels=set(getattr(challenger,"pbr_channels",None) or [])
    missing_channels=sorted(source_channels-challenger_channels)
    if missing_channels:
        reasons.append("missing_pbr_channels:"+",".join(missing_channels))

    # These metrics are monotonic evidence. Missing challenger evidence is also
    # a regression when the incumbent had it.
    for name in (
        "score",
        "production_score",
        "head_texture_detail_score",
        "head_texel_density_score",
        "visual_score",
        "appearance_score",
        "appearance_face_detail_score",
        "appearance_face_detail_min_score",
    ):
        a=getattr(source,name,None)
        b=getattr(challenger,name,None)
        if a is None:
            continue
        if b is None:
            reasons.append(f"missing_evidence:{name}")
            continue
        if float(b)+1e-6<float(a):
            reasons.append(f"regressed:{name}:{float(a):.3f}->{float(b):.3f}")

    source_edge=int(getattr(source,"base_color_min_edge",0) or 0)
    challenger_edge=int(getattr(challenger,"base_color_min_edge",0) or 0)
    if source_edge>0 and challenger_edge<source_edge:
        reasons.append(
            f"basecolor_resolution_regressed:{source_edge}->{challenger_edge}"
        )
    return reasons


def head_composite_regressions(source, challenger) -> list[str]:
    """Protect evidence that a head-shape fusion is not allowed to damage."""
    reasons=[]

    source_channels=set(getattr(source,"pbr_channels",None) or [])
    challenger_channels=set(getattr(challenger,"pbr_channels",None) or [])
    missing_channels=sorted(source_channels-challenger_channels)
    if missing_channels:
        reasons.append("missing_pbr_channels:"+",".join(missing_channels))

    for name in (
        "head_texel_density_score",
        "head_texture_detail_score",
        "appearance_face_detail_min_score",
    ):
        before=getattr(source,name,None)
        after=getattr(challenger,name,None)
        if before is None:
            continue
        if after is None:
            reasons.append(f"missing_evidence:{name}")
            continue
        if float(after)+1e-6<float(before):
            reasons.append(
                f"regressed:{name}:{float(before):.3f}->{float(after):.3f}"
            )

    before_edge=int(getattr(source,"base_color_min_edge",0) or 0)
    after_edge=int(getattr(challenger,"base_color_min_edge",0) or 0)
    if before_edge>0 and after_edge<before_edge:
        reasons.append(
            f"basecolor_resolution_regressed:{before_edge}->{after_edge}"
        )
    return reasons


def _strict_metric_improvement(
    source,
    challenger,
    metric: str,
) -> list[str]:
    before=getattr(source,metric,None)
    after=getattr(challenger,metric,None)
    if before is None:
        if after is None:
            return [f"missing_target_evidence:{metric}"]
        return []
    if after is None:
        return [f"missing_target_evidence:{metric}"]
    if float(after)<=float(before)+1e-6:
        return [
            f"target_not_improved:{metric}:"
            f"{float(before):.3f}->{float(after):.3f}"
        ]
    return []


def _appearance_detail_score(item, source: str) -> float | None:
    wanted=str(source)
    wanted_name=Path(wanted).name
    for detail in getattr(item,"appearance_details",None) or []:
        if not isinstance(detail,dict):
            continue
        actual=str(detail.get("source") or "")
        if actual!=wanted and Path(actual).name!=wanted_name:
            continue
        try:
            score=float(detail.get("score"))
        except (TypeError,ValueError):
            return None
        if math.isfinite(score):
            return score
    return None


def local_detail_composite_regressions(
    source,
    challenger,
    detail_source: str,
) -> list[str]:
    reasons=texture_refinement_regressions(source,challenger)
    before=_appearance_detail_score(source,detail_source)
    after=_appearance_detail_score(challenger,detail_source)
    if before is None:
        if after is None:
            reasons.append(
                "missing_target_detail_evidence:"
                +Path(detail_source).name
            )
    elif after is None:
        reasons.append(
            "missing_target_detail_evidence:"
            +Path(detail_source).name
        )
    elif after<=before+1e-6:
        reasons.append(
            "target_detail_not_improved:"
            f"{Path(detail_source).name}:"
            f"{before:.3f}->{after:.3f}"
        )
    return reasons


def accessory_composite_regressions(
    source,
    challenger,
    detail_source: str,
) -> list[str]:
    """Allow a proven accessory geometry replacement without sacrificing other evidence."""
    reasons=[]

    source_channels=set(getattr(source,"pbr_channels",None) or [])
    challenger_channels=set(getattr(challenger,"pbr_channels",None) or [])
    missing_channels=sorted(source_channels-challenger_channels)
    if missing_channels:
        reasons.append(
            "missing_pbr_channels:"+",".join(missing_channels)
        )

    for name in (
        "score",
        "production_score",
        "visual_score",
        "appearance_score",
        "material_score",
        "texture_resolution_score",
        "head_texture_detail_score",
        "head_texel_density_score",
        "appearance_face_detail_score",
        "appearance_face_detail_min_score",
    ):
        before=getattr(source,name,None)
        after=getattr(challenger,name,None)
        if before is None:
            continue
        if after is None:
            reasons.append(f"missing_evidence:{name}")
            continue
        if float(after)+1e-6<float(before):
            reasons.append(
                f"regressed:{name}:{float(before):.3f}->{float(after):.3f}"
            )

    before_edge=int(getattr(source,"base_color_min_edge",0) or 0)
    after_edge=int(getattr(challenger,"base_color_min_edge",0) or 0)
    if before_edge>0 and after_edge<before_edge:
        reasons.append(
            f"basecolor_resolution_regressed:{before_edge}->{after_edge}"
        )

    before=_appearance_detail_score(source,detail_source)
    after=_appearance_detail_score(challenger,detail_source)
    if before is None:
        if after is None:
            reasons.append(
                "missing_target_detail_evidence:"
                +Path(detail_source).name
            )
    elif after is None:
        reasons.append(
            "missing_target_detail_evidence:"
            +Path(detail_source).name
        )
    elif after<=before+1e-6:
        reasons.append(
            "target_detail_not_improved:"
            f"{Path(detail_source).name}:"
            f"{before:.3f}->{after:.3f}"
        )
    return reasons


def make_reference_groups(inputs: list[Path], group_size: int) -> list[list[Path]]:
    """
    Split an arbitrary reference pool into backend-sized groups without dropping evidence.

    The first source is the continuity anchor and appears in every group. Every other
    source appears in exactly one group. The global Judge still evaluates every
    candidate against the complete reference pool.
    """
    if group_size < 2:
        raise ValueError("multiview group size must be >= 2")
    if len(inputs) <= group_size:
        return [list(inputs)]

    primary = inputs[0]
    payload = group_size - 1
    groups: list[list[Path]] = []
    others = order_for_multiview_coverage(inputs[1:])
    for i in range(0, len(others), payload):
        groups.append([primary, *others[i:i + payload]])
    return groups


def limit_anchor_refs(inputs: list[Path], budget: int | None) -> list[Path]:
    """
    budget=None or <=0 means every real source can spawn a single-image hypothesis.
    A positive budget is an explicit user/CI cost control, never a hidden fidelity cap.
    """
    if budget is None or budget <= 0 or budget >= len(inputs):
        return list(inputs)
    if budget == 1:
        return [inputs[0]]

    # Deterministically sample across the entire ordered reference pool.
    picks = [0]
    remaining = budget - 1
    span = len(inputs) - 1
    for i in range(1, remaining + 1):
        idx = round(i * span / remaining)
        picks.append(min(len(inputs) - 1, idx))
    deduped: list[Path] = []
    seen: set[int] = set()
    for idx in picks:
        if idx not in seen:
            seen.add(idx)
            deduped.append(inputs[idx])
    return deduped


def _viewforge_strategy(count: int) -> str:
    if count == 1:
        return "single-source expansion: synthesize only missing coverage"
    if count == 2:
        return "multi-source fusion: preserve both real anchors and synthesize only missing coverage"
    return (
        f"reference-pool fusion: preserve all {count} real sources, group only where a backend "
        "needs bounded batches, and synthesize only uncovered viewpoints"
    )


def make_job_plan(
    inputs: list[Path],
    *,
    profile_name: str,
    mode: str,
    seed: int,
    selected_backends: list[str],
    model_root: Path,
    multiview_group_size: int | None = None,
    anchor_hypothesis_budget: int | None = None,
    appearance_mode: str = "auto",
    viewforge_mode: str = "auto",
    geometry_refine_mode: str = "auto",
    native_silhouette_conform_mode: str = "auto",
    native_face_repair_mode: str = "auto",
    gameprep_mode: str = "auto",
    character_specialist_mode: str = "off",
    mesh_doctor_mode: str = "auto",
    retopo_mode: str = "auto",
    texture_superres_mode: str = "auto",
    portable_target: str = "auto",
    portable_pack_mode: str = "auto",
    texture_delivery_mode: str = "auto",
    asset_profile: str | None = None,
    animation_requested: bool = False,
    source_autofix_mode: str = "auto",
    derived_detail_inputs: list[Path] | None = None,
    geometry_inputs_override: list[Path] | None = None,
    real_detail_inputs_override: list[Path] | None = None,
    semantic_head_detail_inputs: list[Path] | None = None,
) -> dict:
    profile = PROFILES[profile_name]
    primary_for_profile = (
        list(geometry_inputs_override or [])[0]
        if geometry_inputs_override
        else inputs[0]
    )
    resolved_asset_profile = asset_profile or infer_asset_profile(
        primary_for_profile,
        mode,
    )
    if resolved_asset_profile == "auto":
        resolved_asset_profile = infer_asset_profile(inputs[0], mode)
    asset_spec = load_asset_profile_spec(resolved_asset_profile)
    portability_plan = build_portability_plan(
        mode=mode,
        tier=portable_target,
        profile_name=profile_name,
    )
    roles = split_reference_roles(inputs)
    geometry_inputs = list(
        geometry_inputs_override
        if geometry_inputs_override is not None
        else roles.geometry
    )
    real_detail_inputs = list(
        real_detail_inputs_override
        if real_detail_inputs_override is not None
        else roles.detail
    )
    derived_detail_inputs = list(derived_detail_inputs or [])
    semantic_head_detail_inputs = list(semantic_head_detail_inputs or [])
    detail_inputs = [*real_detail_inputs, *derived_detail_inputs]
    group_size = multiview_group_size or profile.multiview_group_size
    groups = make_reference_groups(geometry_inputs, group_size) if len(geometry_inputs) > 1 else [list(geometry_inputs)]
    anchor_refs = (
        limit_anchor_refs(geometry_inputs, anchor_hypothesis_budget)
        if profile.multi_anchor
        else [geometry_inputs[0]]
    )
    face_seed_count=face_seed_hypothesis_count(
        profile_name,
        detail_inputs,
        semantic_head_inputs=semantic_head_detail_inputs,
    )

    return {
        "engine": "HAYUYA MONSTER",
        "schema": 2,
        "inputs": [str(p) for p in inputs],
        "input_count": len(inputs),
        "reference_pool": {
            "logical_limit": None,
            "all_real_sources_are_authoritative": True,
            "duplicate_paths_are_deduplicated": True,
            "duplicate_file_content_is_deduplicated": True,
            "ordered_primary_source": str(geometry_inputs[0]),
            "geometry_sources": [str(p) for p in geometry_inputs],
            "geometry_source_count": len(geometry_inputs),
            "detail_sources": [str(p) for p in detail_inputs],
            "detail_source_count": len(detail_inputs),
            "real_detail_sources": [str(p) for p in real_detail_inputs],
            "real_detail_source_count": len(real_detail_inputs),
            "derived_detail_sources": [str(p) for p in derived_detail_inputs],
            "derived_detail_source_count": len(derived_detail_inputs),
            "semantic_head_detail_sources": [
                str(p) for p in semantic_head_detail_inputs
            ],
            "semantic_head_detail_source_count": len(
                semantic_head_detail_inputs
            ),
            "derived_details_are_auxiliary_evidence": True,
            "detail_policy": "manual detail/close-up references are optional; source-autofix crops are derived from real geometry sources and never count as independent photos",
        },
        "mode": mode,
        "profile": profile_name,
        "asset_profile": resolved_asset_profile,
        "asset_pipeline": {
            "label": asset_spec.get("label", resolved_asset_profile),
            "animation_requested": bool(animation_requested),
            "animation_systems": asset_spec.get("animation_systems", []),
            "preferred_pipeline": asset_spec.get("preferred_pipeline", []),
            "required_qa": asset_spec.get("required_qa", []),
            "policy": "asset-type-specific postprocess; never force humanoid rigging or incompatible mechanical animation onto unrelated geometry",
        },
        "mobile_portability": portability_plan,
        "portable_pack": {
            "mode": portable_pack_mode,
            "texture_delivery_mode": texture_delivery_mode,
            "tiers": ["flagship", "high", "balanced", "compatibility"],
            "policy": "derive every runtime tier independently from the preserved Hero Master; never cascade quality loss from one tier into the next",
        },
        "seed": seed,
        "targets": {
            "faces": profile.faces,
            "runtime_faces": profile.faces,
            "hero_faces": profile.hero_faces,
            "texture_size": profile.texture_size,
            "trellis2_resolution": profile.trellis2_resolution,
        },
        "hero_master": {
            "enabled": profile.hero_faces > profile.faces,
            "policy": "reconstruct dense first; fidelity-gate the Hero Master before retopology, LODs, rigging or mobile optimization",
            "runtime_faces": profile.faces,
            "hero_faces": profile.hero_faces,
            "preserve_regions": ["face", "hands", "cloth_edges", "accessories"],
        },
        "source_autofix": {
            "mode": source_autofix_mode,
            "single_photo_first": True,
            "manual_face_closeup_required": False,
            "auto_face_zoom": True,
            "auto_character_hint_from_face": True,
            "derived_detail_sources": [str(p) for p in derived_detail_inputs],
            "policy": "derived crops stay tied to their original real source and are auxiliary evidence only",
        },
        "viewforge": {
            "mode": viewforge_mode,
            "auto_activation": "one real geometry source + bootstrapped Wonder3D",
            "strategy": _viewforge_strategy(len(geometry_inputs)),
            "canonical_views": [
                "front",
                "front_45_right",
                "right",
                "back_45_right",
                "back",
                "back_45_left",
                "left",
                "front_45_left",
            ],
            "normal_support": ["wonder3d"],
            "sparse_view_support": ["instantmesh/zero123++"],
            "real_sources_override_synthetic_views": True,
            "wonder3d_rgb_normal_stage": True,
            "single_source_trellis_fusion": "real primary anchor + up to five non-front synthetic Wonder3D RGB views",
            "synthetic_views_never_enter_real_source_judge": True,
        },
        "native_silhouette_conform": {
            "mode": native_silhouette_conform_mode,
            "input_geometry": "native generator/Judge champion only",
            "source_target": "current real source image mask",
            "auto_activation": "single real geometry source after first full ranking",
            "multi_reference_policy": "auto skips multi-reference jobs; required may create a primary-source challenger but the full Judge still scores every real source",
            "topology_policy": "vertex-position challenger only; no projection shell and no source_visible_front/occluded_low_frequency nodes",
            "asset_specific_coordinates": False,
            "promotion_policy": "never overwrite the native generator result; add a challenger and require it to win the same full Judge",
        },
        "native_face_repair": {
            "mode": native_face_repair_mode,
            "asset_scope": "character-only",
            "activation": "character mode only; props and architecture are never routed through head/face donor generation",
            "input_geometry": "current native Judge champion",
            "source_target": "current source-derived head/face evidence",
            "donor_policy": "generate one native 3D head donor from the current source crop using an already-selected bootstrapped backend",
            "fusion_policy": "seam-safe head wrap on preserved full-body topology with adaptive displacement guards",
            "asset_specific_coordinates": False,
            "projection_proxy_created": False,
            "promotion_policy": "face repair is only a challenger; complete Judge must promote it",
        },
        "multi_reference": {
            "enabled": len(geometry_inputs) > 1,
            "backend_group_size": group_size,
            "group_count": len(groups),
            "groups": [[str(p) for p in group] for group in groups],
            "single_image_anchor_hypotheses": [str(p) for p in anchor_refs],
            "anchor_hypothesis_budget": anchor_hypothesis_budget,
            "all_geometry_sources_always_used_by_judge": True,
            "detail_sources_reserved_for_material_and_local_detail_validation": True,
            "detail_sources_enter_judge_v3_when_appearance_is_active": True,
        },
        "candidate_backends": selected_backends,
        "face_seed_tournament": {
            "enabled": face_seed_count>1,
            "trellis2_seed_count": face_seed_count,
            "activation": "Monster/Ultra + explicit head/face detail evidence",
            "policy": "extra high-end stochastic hypotheses are judged against the same geometry and face evidence; no seed is auto-promoted",
        },
        "character_specialist": {
            "mode": character_specialist_mode,
            "backend": "PSHuman 768 6-view",
            "activation": "explicit non-off opt-in + --allow-restricted + character mode + complete PSHuman auxiliary assets + >=40GB VRAM",
            "policy": "specialist is one additional candidate and must win the same real-source Judge; never auto-promoted",
            "auxiliary_asset_gate": "smpl_related + PIXIE/SMPLX assets must exist; Hayuya does not auto-download separately licensed body-model data"
        },
        "mesh_doctor": {
            "mode": mesh_doctor_mode,
            "activation": "audit provisional champion before retopology; safe repair challenger only when structural defects are detected",
            "safe_repairs": ["duplicate faces", "degenerate faces", "unreferenced vertices", "winding/normals", "small simple holes for props/architecture"],
            "audit_only": ["tiny disconnected components"],
            "policy": "never delete tiny accessories automatically; repaired/material-restored GLB must re-enter the complete real-source Judge",
            "rig_policy": "audit rigged glTF but skip topology-changing repair until JOINTS/WEIGHTS transfer exists"
        },
        "retopology": {
            "mode": retopo_mode,
            "backend": "Instant Meshes field-aligned retopology",
            "activation": "unrigged provisional champion + bootstrapped/built Instant Meshes binary",
            "style": "pure_quad for prop/architecture; quad_dominant for unrigged character",
            "policy": "preserve retopo_master.obj as editable topology, restore PBR through Material Bridge v2, then re-enter the complete real-source Judge; never overwrite the source candidate blindly",
            "rig_policy": "skip any glTF with skins until skin-weight-preserving retopology transfer exists"
        },
        "texture_superres": {
            "mode": texture_superres_mode,
            "backend": "Real-ESRGAN NCNN Vulkan",
            "activation": "Monster/Ultra provisional champion only when weakest embedded baseColor is below the profile target and the optional executable is available",
            "policy": "rewrite only embedded baseColor image payloads, preserve geometry/skin/animation buffers byte-for-byte, add as a separate challenger, and require the complete Judge to choose it",
            "model": "realesrgan-x4plus"
        },
        "geometry_refinement": {
            "mode": geometry_refine_mode,
            "backend": "TripoSF SparseFlex 1024^3",
            "activation": "monster/ultra execution when bootstrapped and VRAM budget >=12GB",
            "policy": "refined topology is a challenger; real-source geometry evidence must improve before it is marked preferred",
            "asset_promotion": "when refined geometry wins, Material Bridge v2 transfers/reprojects the strongest available material evidence and the bridged GLB must win the full final Judge",
            "material_bridge_v2": "packed PBR atlas + nearest-surface UV projection preserves baseColor/metallic/roughness/normal/AO/emissive when source UV/PBR exists; automatic v1 base-color fallback otherwise"
        },
        "gameprep": {
            "mode": gameprep_mode,
            "activation": "auto for mobile/game/monster/ultra after final champion",
            "outputs": ["master.glb", "LOD0.glb", "LOD1.glb", "LOD2.glb", "LOD3.glb", "collision_convex.glb", "8-frame turntable", "gameprep_manifest.json"],
            "lod_material_policy": "master keeps original materials; simplified LODs reuse one Material Bridge v2 transfer context so PBR/UV survives when source material supports it, with v1 base-color fallback"
        },
        "judge": {
            "version": "v3-auto" if appearance_mode != "off" else "v2",
            "production_subscore": {
                "geometry_capacity_weight": 0.42,
                "topology_health_weight": 0.33,
                "material_readiness_weight": 0.18,
                "bbox_health_weight": 0.07,
            },
            "final_mix": {
                "source_visual_weight": 0.55,
                "production_weight": 0.45,
            },
            "source_visual": {
                "method": "two-stage software silhouette camera search",
                "azimuth_step_degrees": 30,
                "elevations_degrees": [-15, 0, 15],
                "up_axis_hypotheses": ["y", "z"],
                "projection_stage_1": "global orthographic bank",
                "projection_stage_2": "local +/-15 degree refinement across orthographic and perspective camera distances [1.4, 2.4, 4.0]",
                "per_source_metric": "0.72 silhouette IoU + 0.28 boundary F1",
                "multi_source_aggregation": "<=2: 0.70 mean + 0.30 min; >=3: 0.65 mean + 0.25 lower-quartile mean + 0.10 min",
                "evaluate_every_geometry_source": True,
            },
            "appearance": {
                "mode": appearance_mode,
                "backend": "DINOv2 ViT-S/14 LVD-142M",
                "license": "Apache-2.0",
                "candidate_render": "Hayuya deterministic CPU RGB z-buffer from matched v2 camera, including recovered perspective",
                "texture_rendering": "per-pixel UV/base-color texture sampling with vertex-color fallback",
                "weight_when_active": 0.25,
                "whole_object_vs_detail_mix": "0.72 geometry appearance + 0.28 local-detail retrieval when detail refs exist",
                "detail_search": "8 canonical candidate views x whole-frame + 3x3 local patches",
                "fallback": "Judge v2 when DINOv2 is unavailable in auto mode"
            },
            "synthetic_normal_support": {
                "source": "Wonder3D ViewForge normals when available",
                "coordinate_system": "front-view OpenGL normal system from pinned Wonder3D",
                "weight": 0.06,
                "evidence_class": "synthetic support only; never equivalent to a real reference"
            },
            "future_extension": "normal/depth agreement + calibrated camera estimation + local-detail appearance Judge",
        },
        "model_root": str(model_root.resolve()),
        "output": "hayuya_final.glb",
    }


def choose_backends(
    lock: dict,
    profile: Profile,
    override: str | None,
    *,
    gpu_vram: int | None,
    allow_restricted: bool,
) -> list[str]:
    meta = backend_meta(lock)
    requested = list(profile.backends if not override else [x.strip() for x in override.split(",") if x.strip()])
    selected: list[str] = []
    for backend in requested:
        if backend not in meta:
            raise ValueError(f"unknown backend: {backend}")
        if backend == "pshuman":
            raise ValueError(
                "PSHuman is a gated character specialist; use "
                "--character-specialist auto|required with --allow-restricted"
            )
        entry = meta[backend]
        permissive = entry["license"] in {"MIT", "Apache-2.0"}
        if not permissive and not allow_restricted:
            print(f"SKIP {backend}: opt-in/restricted license", file=sys.stderr)
            continue
        if gpu_vram is not None and int(entry["min_vram_gb"]) > gpu_vram:
            print(
                f"SKIP {backend}: requires >= {entry['min_vram_gb']}GB VRAM, budget={gpu_vram}GB",
                file=sys.stderr,
            )
            continue
        if backend not in GENERATORS:
            print(f"SKIP {backend}: planner knows it but no executable adapter exists yet", file=sys.stderr)
            continue
        selected.append(backend)
    return selected


def run_single_backend(
    backend: str,
    image: Path,
    out_dir: Path,
    *,
    profile: Profile,
    seed: int,
    model_root: Path,
):
    if backend == "trellis2":
        return GENERATORS[backend](
            image,
            out_dir,
            seed=seed,
            resolution=profile.trellis2_resolution,
            faces=profile.hero_faces,
            texture_size=profile.texture_size,
            model_root=model_root,
        )
    if backend == "triposg":
        return GENERATORS[backend](
            image,
            out_dir,
            faces=profile.hero_faces,
            seed=seed,
            model_root=model_root,
        )
    if backend == "triposr":
        return GENERATORS[backend](
            image,
            out_dir,
            texture_size=profile.texture_size,
            model_root=model_root,
        )
    if backend == "instantmesh":
        return GENERATORS[backend](
            image,
            out_dir,
            seed=seed,
            model_root=model_root,
        )
    if backend == "pshuman":
        return GENERATORS[backend](
            image,
            out_dir,
            seed=seed,
            model_root=model_root,
        )
    if backend == "spar3d":
        return GENERATORS[backend](
            image,
            out_dir,
            texture_size=profile.texture_size,
            faces=profile.hero_faces,
            model_root=model_root,
        )
    raise ValueError(f"unsupported single-image backend: {backend}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HAYUYA MONSTER: open ensemble image-to-3D orchestrator for an arbitrary reference pool."
    )
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        default=[],
        help="source image; repeat as many times as useful",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        action="append",
        default=[],
        help="directory containing reference images; repeatable and recursively scanned",
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), default="monster")
    parser.add_argument(
        "--portable-target",
        choices=["auto", "compatibility", "balanced", "high", "flagship"],
        default="auto",
        help="runtime mobile portability tier; auto maps preview/mobile/game/monster/ultra to compatibility/compatibility/balanced/high/flagship",
    )
    parser.add_argument("--mode", choices=["auto", "prop", "character", "architecture"], default="auto")
    parser.add_argument("--asset-profile", choices=sorted(ASSET_PROFILE_IDS), default="auto")
    parser.add_argument("--animation", action="store_true", help="request the profile-compatible animation/postprocess path")
    parser.add_argument("--seed", type=int, default=1993)
    parser.add_argument("--backends", help="comma-separated override")
    parser.add_argument("--gpu-vram", type=int, help="VRAM budget in GB; skips larger backends")
    parser.add_argument(
        "--multiview-group-size",
        type=int,
        help="practical per-call multiview batch size; does not limit the total reference pool",
    )
    parser.add_argument(
        "--anchor-hypothesis-budget",
        type=int,
        default=0,
        help="single-image hypothesis budget; 0 means use every real source in multi-anchor profiles",
    )
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT / "out" / "hayuya3d")
    parser.add_argument("--execute", action="store_true", help="actually run installed backends")
    parser.add_argument("--require-all", action="store_true", help="fail if any selected backend candidate fails")
    parser.add_argument("--allow-restricted", action="store_true", help="allow explicitly opt-in non-permissive backends")
    parser.add_argument(
        "--source-autofix",
        choices=["off", "auto", "required"],
        default="auto",
        help=(
            "Tripo-style source preprocessing: recover face/head detail automatically "
            "from ordinary source photos; manual close-ups remain optional"
        ),
    )
    parser.add_argument(
        "--viewforge",
        choices=["off", "auto", "required"],
        default="auto",
        help="Wonder3D RGB+normal expansion policy; auto activates for one-source jobs when bootstrapped",
    )
    parser.add_argument(
        "--geometry-refine",
        choices=["off", "auto", "required"],
        default="auto",
        help="TripoSF SparseFlex geometry challenger policy for monster/ultra execution",
    )
    parser.add_argument(
        "--native-silhouette-conform",
        choices=["off", "auto", "required"],
        default="auto",
        help=(
            "source-driven silhouette repair on the native 3D champion. "
            "Creates a challenger only; never creates a front-projection proxy."
        ),
    )
    parser.add_argument(
        "--native-face-repair",
        choices=["off", "auto", "required"],
        default="auto",
        help=(
            "generate a native 3D head donor from the current source face/head "
            "evidence and add a seam-safe face-repair challenger."
        ),
    )
    parser.add_argument(
        "--mesh-doctor",
        choices=["off", "auto", "required"],
        default="auto",
        help="audit provisional champion and add a conservative structural-repair challenger when safe",
    )
    parser.add_argument(
        "--retopo",
        choices=["off", "auto", "required"],
        default="off",
        help="Downstream topology conversion. HAYUYA 3D keeps this off by default to preserve the approved AAA Hero Master.",
    )
    parser.add_argument(
        "--texture-superres",
        choices=["off", "auto", "required"],
        default="auto",
        help="Real-ESRGAN visible baseColor challenger; auto runs for Monster/Ultra only when the provisional champion is below the profile texture target",
    )
    parser.add_argument(
        "--character-specialist",
        choices=["off", "auto", "required"],
        default="off",
        help="PSHuman 40GB+ humanoid challenger. Mixed third-party licensing: requires explicit non-off selection plus --allow-restricted.",
    )
    parser.add_argument(
        "--gameprep",
        choices=["off", "auto", "required"],
        default="off",
        help="Downstream runtime preparation; disabled by default in HAYUYA 3D.",
    )
    parser.add_argument(
        "--portable-pack",
        choices=["off", "auto", "required"],
        default="off",
        help="Downstream runtime LOD packs; disabled by default in HAYUYA 3D.",
    )
    parser.add_argument(
        "--texture-delivery",
        choices=["off", "auto", "required"],
        default="off",
        help="Runtime texture delivery belongs to downstream products; disabled by default in HAYUYA 3D.",
    )
    parser.add_argument(
        "--appearance-judge",
        choices=["off", "auto", "required"],
        default="auto",
        help="Judge v3 DINOv2 appearance scoring policy; auto falls back to v2 if evaluator is not bootstrapped",
    )
    parser.add_argument(
        "--judge-v4",
        choices=["off", "auto", "required"],
        default="auto",
        help=(
            "fail-closed final visual acceptance using 24-view evidence, "
            "Q-ReAlign-Pro-9B, dense face geometry, DreamSim and InternVL3.5; "
            "auto is REQUIRED for Monster/Ultra characters"
        ),
    )
    parser.add_argument(
        "--judge-v5",
        choices=["off", "auto", "required"],
        default="auto",
        help=(
            "authoritative high-end visual acceptance ensemble. V5 consumes "
            "Judge V4 evidence plus VisualQuality-R1, SigLIP2 Giant, AdaFace "
            "identity and PyIQA face/general metrics. Missing/uncalibrated "
            "evidence can never become production-approved."
        ),
    )
    parser.add_argument(
        "--semantic-anatomy",
        choices=["off","auto","required"],
        default="auto",
        help=(
            "final GLB GroundingDINO+SAM2 anatomy validation; auto runs "
            "for Monster/Ultra characters when explicit critical anatomy "
            "references exist"
        ),
    )
    args = parser.parse_args()

    raw_inputs = list(args.input)
    for root in args.input_dir:
        root = root.resolve()
        if not root.is_dir():
            parser.error(f"--input-dir is not a directory: {root}")
        raw_inputs.extend(
            p for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
    if not raw_inputs:
        parser.error("provide at least one --input or --input-dir")

    inputs = validate_inputs(raw_inputs)
    roles = split_reference_roles(inputs)
    geometry_inputs = list(roles.geometry)
    real_detail_inputs = list(roles.detail)
    detail_inputs = list(real_detail_inputs)
    profile = PROFILES[args.profile]
    group_size = args.multiview_group_size or profile.multiview_group_size
    if group_size < 2:
        parser.error("--multiview-group-size must be >= 2")

    job_name = f"{geometry_inputs[0].stem}-{args.profile}-{args.seed}"
    job_dir = args.output_root / job_name
    candidates_dir = job_dir / "candidates"
    job_dir.mkdir(parents=True, exist_ok=True)

    # Tripo-style source preprocessing: a normal source photo is sufficient.
    # Derived face crops are auxiliary evidence tied to the real source and never
    # inflate the count of independent reference photos.
    source_autofix_result = None
    source_autofix_failure = None
    recovered_detail_inputs: list[Path] = []
    derived_detail_inputs: list[Path] = []
    semantic_head_detail_inputs: list[Path] = []
    content_reclassified_sources: list[Path] = []
    if args.source_autofix in {"auto", "required"} and args.execute and args.mode in {"auto", "character"}:
        try:
            from source_autofix import build_source_autofix
            source_autofix_result = build_source_autofix(
                geometry_inputs,
                job_dir / "source_autofix",
                policy=args.source_autofix,
            )
            recovered_detail_inputs = [
                Path(x).resolve()
                for x in source_autofix_result.derived_detail_sources
            ]
            print(
                "HAYUYA_SOURCE_AUTOFIX_READY "
                f"real_sources={len(geometry_inputs)} "
                f"recovered_head_details={len(recovered_detail_inputs)} "
                f"character_hint={str(bool(source_autofix_result.character_hint)).lower()} "
                f"manifest={source_autofix_result.manifest}"
            )
        except Exception as exc:
            source_autofix_failure = f"{type(exc).__name__}: {exc}"
            print(
                f"HAYUYA_SOURCE_AUTOFIX_FAILED {source_autofix_failure}",
                file=sys.stderr,
            )
            traceback.print_exc()
            if args.source_autofix == "required":
                raise

    if source_autofix_result is not None:
        (
            geometry_inputs,
            real_detail_inputs,
            content_reclassified_sources,
        )=reclassify_semantic_face_closeups(
            geometry_inputs,
            real_detail_inputs,
            source_autofix_result,
        )
        semantic_head_detail_inputs=list(content_reclassified_sources)

        if content_reclassified_sources:
            moved_set={
                Path(path).resolve()
                for path in content_reclassified_sources
            }
            redundant_derived=set()
            for item in list(
                getattr(source_autofix_result,"sources",[]) or []
            ):
                try:
                    source=Path(getattr(item,"source")).resolve()
                except Exception:
                    continue
                face_detail=getattr(item,"face_detail",None)
                if source in moved_set and face_detail:
                    redundant_derived.add(
                        Path(face_detail).resolve()
                    )
            recovered_detail_inputs=[
                path
                for path in recovered_detail_inputs
                if Path(path).resolve() not in redundant_derived
            ]
            print(
                "HAYUYA_REFERENCE_ROLE_RECLASSIFIED "
                f"semantic_head_details="
                f"{len(content_reclassified_sources)} "
                f"geometry_sources={len(geometry_inputs)} "
                f"redundant_derived_removed={len(redundant_derived)}"
            )

    mode = args.mode
    if mode == "auto":
        # Content beats filenames only when a face/head detector actually confirms it.
        if source_autofix_result is not None and source_autofix_result.character_hint:
            mode = "character"
        else:
            mode = infer_asset_mode(geometry_inputs[0])

    # Heuristic top-of-subject crops are safe auxiliary evidence for a character,
    # but they never turn an unknown prop into a character on their own.
    if mode == "character":
        derived_detail_inputs = list(recovered_detail_inputs)
    detail_inputs = [*real_detail_inputs, *derived_detail_inputs]

    lock = load_lock()
    selected = choose_backends(
        lock,
        profile,
        args.backends,
        gpu_vram=args.gpu_vram,
        allow_restricted=args.allow_restricted,
    )
    if not selected:
        raise SystemExit("No executable backends selected")

    if args.judge_v4 == "required" and mode != "character":
        parser.error("--judge-v4 required needs --mode character or a detected character source")
    if args.judge_v5 == "required" and mode != "character":
        parser.error("--judge-v5 required needs --mode character or a detected character source")
    if args.character_specialist != "off" and not args.allow_restricted:
        parser.error("--character-specialist requires --allow-restricted because PSHuman includes separately licensed third-party human-model components")
    if args.character_specialist == "required" and mode != "character":
        parser.error("--character-specialist required needs --mode character or a detected character source")

    reference_groups = (
        make_reference_groups(geometry_inputs, group_size)
        if len(geometry_inputs) > 1
        else [list(geometry_inputs)]
    )
    anchor_refs = (
        limit_anchor_refs(geometry_inputs, args.anchor_hypothesis_budget)
        if profile.multi_anchor
        else [geometry_inputs[0]]
    )
    face_seed_count=face_seed_hypothesis_count(
        args.profile,
        detail_inputs,
        semantic_head_inputs=semantic_head_detail_inputs,
    )

    plan = make_job_plan(
        inputs,
        profile_name=args.profile,
        mode=mode,
        seed=args.seed,
        selected_backends=selected,
        model_root=args.model_root,
        multiview_group_size=group_size,
        anchor_hypothesis_budget=args.anchor_hypothesis_budget,
        appearance_mode=args.appearance_judge,
        viewforge_mode=args.viewforge,
        geometry_refine_mode=args.geometry_refine,
        native_silhouette_conform_mode=args.native_silhouette_conform,
        native_face_repair_mode=args.native_face_repair,
        gameprep_mode=args.gameprep,
        character_specialist_mode=args.character_specialist,
        mesh_doctor_mode=args.mesh_doctor,
        retopo_mode=args.retopo,
        texture_superres_mode=args.texture_superres,
        portable_target=args.portable_target,
        portable_pack_mode=args.portable_pack,
        texture_delivery_mode=args.texture_delivery,
        asset_profile=(None if args.asset_profile == "auto" else args.asset_profile),
        animation_requested=args.animation,
        source_autofix_mode=args.source_autofix,
        derived_detail_inputs=derived_detail_inputs,
        geometry_inputs_override=geometry_inputs,
        real_detail_inputs_override=real_detail_inputs,
        semantic_head_detail_inputs=semantic_head_detail_inputs,
    )
    portable_runtime = plan["mobile_portability"]["runtime_target"]
    portable_lod0_ceiling = int(portable_runtime["lod0_triangles"][1])
    portable_texture_ceiling = int(portable_runtime["exceptional_texture_edge_px"])
    (job_dir / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, indent=2))

    if not args.execute:
        print(f"HAYUYA_PLAN_READY {job_dir / 'plan.json'}")
        return 0

    candidates: list[tuple[str, Path]] = []
    failures: dict[str, str] = {}

    viewforge_result = None
    viewforge_failure = None
    should_try_viewforge = args.viewforge in {"auto", "required"} and len(geometry_inputs) == 1
    if should_try_viewforge:
        wonder_ready = (args.model_root / "wonder3d").is_dir()
        if not wonder_ready and args.viewforge == "required":
            raise RuntimeError(
                "ViewForge required but Wonder3D is not bootstrapped. "
                "Run: python tools/hayuya3d/bootstrap.py --backend wonder3d"
            )
        if wonder_ready:
            try:
                from viewforge import generate_wonder3d_views
                viewforge_result = generate_wonder3d_views(
                    geometry_inputs[0],
                    job_dir / "viewforge",
                    seed=args.seed,
                    model_root=args.model_root,
                )
                print(
                    f"HAYUYA_VIEWFORGE_READY backend={viewforge_result.backend} "
                    f"synthetic_views={len(viewforge_result.synthetic_reconstruction_views)}"
                )
            except Exception as exc:
                viewforge_failure = f"{type(exc).__name__}: {exc}"
                print(f"HAYUYA_VIEWFORGE_FAILED {viewforge_failure}", file=sys.stderr)
                traceback.print_exc()
                if args.viewforge == "required":
                    raise

    character_specialist_failure = None
    character_specialist_status = "not_applicable"
    if mode == "character" and args.character_specialist in {"auto", "required"}:
        character_specialist_status = "checking"
        repo_ready = (args.model_root / "pshuman").is_dir()
        vram_ready = args.gpu_vram is None or args.gpu_vram >= 40
        assets_ready, missing_assets = pshuman_readiness(args.model_root) if repo_ready else (False, ["backend repo missing"])

        if not repo_ready or not vram_ready or not assets_ready:
            reasons = []
            if not repo_ready:
                reasons.append("PSHuman backend not bootstrapped")
            if not vram_ready:
                reasons.append(f"PSHuman requires >40GB VRAM; budget={args.gpu_vram}GB")
            if repo_ready and not assets_ready:
                reasons.append("missing auxiliary assets: " + ", ".join(missing_assets))
            character_specialist_failure = "; ".join(reasons)
            character_specialist_status = "skipped"
            print(
                f"HAYUYA_CHARACTER_SPECIALIST_SKIPPED {character_specialist_failure}",
                file=sys.stderr,
            )
            if args.character_specialist == "required":
                raise RuntimeError(character_specialist_failure)
        else:
            try:
                specialist = run_single_backend(
                    "pshuman",
                    geometry_inputs[0],
                    candidates_dir / "pshuman",
                    profile=profile,
                    seed=args.seed,
                    model_root=args.model_root,
                )
                candidates.append(("pshuman", specialist.model_path))
                character_specialist_status = "candidate_ready"
                print(
                    f"HAYUYA_CANDIDATE_READY pshuman {specialist.model_path} "
                    "specialist=humanoid"
                )
            except Exception as exc:
                character_specialist_failure = f"{type(exc).__name__}: {exc}"
                character_specialist_status = "failed"
                print(
                    f"HAYUYA_CHARACTER_SPECIALIST_FAILED {character_specialist_failure}",
                    file=sys.stderr,
                )
                traceback.print_exc()
                if args.character_specialist == "required":
                    raise

    for backend in selected:
        if backend == "pshuman":
            # Specialist is managed above so it cannot accidentally run twice.
            continue
        if backend == "trellis":
            # Native multi-image backend: every source participates in at least one group.
            for group_index, group in enumerate(reference_groups, start=1):
                label = f"trellis_group{group_index:02d}"
                try:
                    candidate = GENERATORS["trellis"](
                        group,
                        candidates_dir / label,
                        seed=args.seed + group_index - 1,
                        texture_size=profile.texture_size,
                        model_root=args.model_root,
                    )
                    candidates.append((label, candidate.model_path))
                    print(
                        f"HAYUYA_CANDIDATE_READY {label} {candidate.model_path} "
                        f"sources={len(group)}"
                    )
                except Exception as exc:
                    failures[label] = f"{type(exc).__name__}: {exc}"
                    print(f"HAYUYA_CANDIDATE_FAILED {label}: {failures[label]}", file=sys.stderr)
                    traceback.print_exc()
                    if args.require_all:
                        raise
            # One-photo jobs gain an additional native multi-image TRELLIS hypothesis
            # from the real anchor plus ViewForge's synthetic missing coverage.
            if viewforge_result is not None and len(geometry_inputs) == 1:
                synthetic = [
                    Path(p)
                    for p in viewforge_result.synthetic_reconstruction_views
                ][: max(0, group_size - 1)]
                vf_inputs = [geometry_inputs[0], *synthetic]
                if len(vf_inputs) > 1:
                    label = "trellis_viewforge"
                    try:
                        candidate = GENERATORS["trellis"](
                            vf_inputs,
                            candidates_dir / label,
                            seed=args.seed + 777,
                            texture_size=profile.texture_size,
                            model_root=args.model_root,
                        )
                        candidates.append((label, candidate.model_path))
                        print(
                            f"HAYUYA_CANDIDATE_READY {label} {candidate.model_path} "
                            f"real_sources=1 synthetic_sources={len(synthetic)}"
                        )
                    except Exception as exc:
                        failures[label] = f"{type(exc).__name__}: {exc}"
                        print(
                            f"HAYUYA_CANDIDATE_FAILED {label}: {failures[label]}",
                            file=sys.stderr,
                        )
                        traceback.print_exc()
                        if args.require_all:
                            raise
            continue

        # Expensive single-image backends normally run once from the primary
        # source. When explicit face evidence exists, Monster/Ultra allow a
        # bounded TRELLIS.2 seed tournament so the appearance Judge can choose
        # among genuinely different high-end face hypotheses instead of grading
        # one stochastic draw. No extra seeds run without face evidence.
        run_refs = anchor_refs if backend == "triposg" and profile.multi_anchor else [geometry_inputs[0]]
        seed_count = face_seed_count if backend == "trellis2" else 1
        for anchor_index, image in enumerate(run_refs, start=1):
            for seed_index in range(seed_count):
                seed_value=args.seed + anchor_index - 1 + seed_index*1009
                if len(run_refs)==1 and seed_count==1:
                    label=backend
                elif seed_count>1:
                    label=f"{backend}_seed{seed_index+1:02d}"
                else:
                    label=f"{backend}_anchor{anchor_index:03d}"
                try:
                    candidate = run_single_backend(
                        backend,
                        image,
                        candidates_dir / label,
                        profile=profile,
                        seed=seed_value,
                        model_root=args.model_root,
                    )
                    candidates.append((label, candidate.model_path))
                    print(
                        f"HAYUYA_CANDIDATE_READY {label} {candidate.model_path} "
                        f"source={image} seed={seed_value}"
                    )
                except Exception as exc:
                    failures[label] = f"{type(exc).__name__}: {exc}"
                    print(f"HAYUYA_CANDIDATE_FAILED {label}: {failures[label]}", file=sys.stderr)
                    traceback.print_exc()
                    if args.require_all:
                        raise

    # Never allow the diagnostic front-projection representation to
    # masquerade as a native image-to-3D result.  The projection/face tools are
    # downstream evidence and repair helpers only; geometry candidates must
    # originate from real 3D generators (TRELLIS.2/TripoSG/TRELLIS/etc.).
    native_candidates: list[tuple[str, Path]] = []
    native_geometry_guard = {}
    for label, candidate_path in candidates:
        try:
            provenance_report = assert_native_candidate(candidate_path, label=label)
            guard_report = {
                "provenance": provenance_report,
                "character_360": None,
            }
            if mode == "character":
                guard_report["character_360"] = assert_native_character_360(
                    candidate_path,
                    label=label,
                )
            native_candidates.append((label, candidate_path))
            native_geometry_guard[label] = guard_report
        except (ProjectionProxyRejected, Native360GeometryRejected) as exc:
            failure_key = f"{label}:native_geometry_guard"
            failures[failure_key] = str(exc)
            native_geometry_guard[label] = {
                "rejected": True,
                "reason": str(exc),
                "character_360_required": mode == "character",
            }
            print(
                f"HAYUYA_NATIVE_GEOMETRY_REJECTED {label} {candidate_path}: {exc}",
                file=sys.stderr,
            )
            if args.require_all:
                raise
    candidates = native_candidates
    plan["native_geometry_guard"] = native_geometry_guard

    if not candidates:
        manifest = {**plan, "status": "failed", "failures": failures}
        (job_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        raise SystemExit("All Hayuya candidates failed")

    normal_support_images = (
        {name: Path(path) for name, path in viewforge_result.normal_views.items()}
        if viewforge_result is not None
        else None
    )

    refinement_decision = None
    refinement_failure = None
    material_bridge_result = None
    material_bridge_failure = None
    should_try_refinement = (
        args.geometry_refine in {"auto", "required"}
        and args.profile in {"monster", "ultra"}
    )
    if should_try_refinement:
        triposf_ready = (args.model_root / "triposf").is_dir()
        enough_vram = args.gpu_vram is None or args.gpu_vram >= 12
        if args.geometry_refine == "required" and not triposf_ready:
            raise RuntimeError(
                "TripoSF refinement required but backend is not bootstrapped"
            )
        if args.geometry_refine == "required" and not enough_vram:
            raise RuntimeError(
                "TripoSF refinement required but VRAM budget is below 12GB"
            )

        if triposf_ready and enough_vram:
            try:
                preliminary = rank_candidates(
                    candidates,
                    mode=mode,
                    target_faces=profile.hero_faces,
                    target_texture_size=profile.texture_size,
                    source_images=geometry_inputs,
                    visual_weight=0.55,
                    appearance_mode="off",
                    normal_support_images=normal_support_images,
                    normal_support_weight=0.06,
                )
                eligible = [
                    item for item in preliminary
                    if item.valid and item.visual_score is not None
                ]
                if not eligible:
                    raise RuntimeError("no valid geometry seed candidate for TripoSF")
                seed_candidate = max(
                    eligible,
                    key=lambda item: (
                        item.visual_score or 0.0,
                        item.production_score or 0.0,
                    ),
                )

                refine_root = job_dir / "refinement" / "triposf"
                refined_raw = REFINERS["triposf"](
                    Path(seed_candidate.path),
                    refine_root / "raw",
                    model_root=args.model_root,
                )

                from geometry_refinement import (
                    compare_refinement,
                    restore_refined_bounds,
                    write_decision,
                )

                restored = restore_refined_bounds(
                    Path(seed_candidate.path),
                    refined_raw.model_path,
                    refine_root / "triposf_refined_bounds_restored.glb",
                )
                refinement_decision = compare_refinement(
                    seed_candidate.backend,
                    Path(seed_candidate.path),
                    restored,
                    sources=geometry_inputs,
                    mode=mode,
                    target_faces=profile.hero_faces,
                    normal_support_images=normal_support_images,
                )
                write_decision(
                    refine_root / "refinement_decision.json",
                    refinement_decision,
                )
                print(
                    "HAYUYA_REFINEMENT_READY "
                    f"source={seed_candidate.backend} "
                    f"preferred={refinement_decision.preferred} "
                    f"improvement={refinement_decision.improvement}"
                )

                if refinement_decision.promote_to_final_geometry:
                    try:
                        from material_bridge import transfer_best_material
                        bridged_path = (
                            refine_root / "triposf_material_bridge.glb"
                        )
                        material_bridge_result = transfer_best_material(
                            Path(seed_candidate.path),
                            restored,
                            bridged_path,
                            max_texture_size=profile.texture_size,
                        )
                        candidates.append(
                            ("triposf_material_bridge", bridged_path)
                        )
                        print(
                            "HAYUYA_MATERIAL_BRIDGE_READY "
                            f"{bridged_path}"
                        )
                    except Exception as bridge_exc:
                        material_bridge_failure = (
                            f"{type(bridge_exc).__name__}: {bridge_exc}"
                        )
                        print(
                            "HAYUYA_MATERIAL_BRIDGE_FAILED "
                            f"{material_bridge_failure}",
                            file=sys.stderr,
                        )
                        traceback.print_exc()
            except Exception as exc:
                refinement_failure = f"{type(exc).__name__}: {exc}"
                print(
                    f"HAYUYA_REFINEMENT_FAILED {refinement_failure}",
                    file=sys.stderr,
                )
                traceback.print_exc()
                if args.geometry_refine == "required":
                    raise

    ranking_pass = 0

    def run_full_ranking():
        nonlocal ranking_pass
        ranking_pass += 1
        result = rank_candidates(
            candidates,
            mode=mode,
            target_faces=profile.hero_faces,
            target_texture_size=profile.texture_size,
            source_images=geometry_inputs,
            detail_images=detail_inputs,
            visual_weight=0.55,
            appearance_mode=args.appearance_judge,
            appearance_model_root=args.model_root,
            appearance_render_root=job_dir / "judge_v3_renders",
            appearance_weight=0.25,
            normal_support_images=normal_support_images,
            normal_support_weight=0.06,
        )
        if mode=="character" and args.profile in {"monster","ultra"}:
            from qa import candidate_rank_key, character_quality_evidence_complete
            identity_required_for_ranking=any(
                infer_detail_region_hint(path)=="head"
                for path in detail_inputs
            )
            for item in result:
                hard_reasons=[]
                if not character_quality_evidence_complete(
                    item,
                    identity_required=identity_required_for_ranking,
                ):
                    hard_reasons.append("incomplete_character_quality_evidence")
                structure=getattr(item,"head_structure_score",None)
                try:
                    structure_ok=(
                        structure is not None
                        and math.isfinite(float(structure))
                        and float(structure)>=45.0
                    )
                except (TypeError,ValueError):
                    structure_ok=False
                if not structure_ok:
                    hard_reasons.append(
                        f"head_structure_below_gate:{structure}"
                    )
                if hard_reasons:
                    item.valid=False
                    item.notes.append(
                        "HARD CHARACTER PROMOTION VETO: "
                        + ";".join(hard_reasons)
                    )
            result=sorted(
                result,
                key=lambda item:candidate_rank_key(
                    item,
                    mode=mode,
                    identity_required=identity_required_for_ranking,
                ),
                reverse=True,
            )
        for position, item in enumerate(result, start=1):
            print(
                "HAYUYA_JUDGE_SCORE "
                f"backend={item.backend} score={item.score:.3f} "
                f"valid={str(bool(item.valid)).lower()} rank={position} pass={ranking_pass}"
            )
            live_metrics = {
                "backend": item.backend,
                "production_score": item.production_score,
                "visual_score": item.visual_score,
                "appearance_score": item.appearance_score,
                "appearance_detail_score": item.appearance_detail_score,
                "appearance_face_detail_score": item.appearance_face_detail_score,
                "appearance_face_detail_min_score": item.appearance_face_detail_min_score,
                "material_score": item.material_score,
                "texture_resolution_score": item.texture_resolution_score,
                "base_color_max_edge": item.base_color_max_edge,
                "base_color_min_edge": item.base_color_min_edge,
                "head_region_faces": item.head_region_faces,
                "head_region_vertices": item.head_region_vertices,
                "head_region_face_fraction": item.head_region_face_fraction,
                "global_median_edge_normalized": item.global_median_edge_normalized,
                "head_region_median_edge_normalized": item.head_region_median_edge_normalized,
                "head_region_density_ratio": item.head_region_density_ratio,
                "head_density_score": item.head_density_score,
                "head_texel_density_ratio": item.head_texel_density_ratio,
                "head_texel_density_score": item.head_texel_density_score,
                "head_texture_detail_ratio": item.head_texture_detail_ratio,
                "head_texture_detail_score": item.head_texture_detail_score,
                "head_texture_detail_mean": item.head_texture_detail_mean,
                "pbr_channels": item.pbr_channels,
            }
            print(
                "HAYUYA_JUDGE_METRICS "
                + json.dumps(live_metrics,separators=(",",":"))
            )
        return result

    ranked = run_full_ranking()
    valid = [x for x in ranked if x.valid]
    if not valid:
        raise SystemExit("Candidates were produced but none passed Hayuya Judge")

    native_conform_result = None
    native_conform_failure = None
    native_conform_status = (
        "off" if args.native_silhouette_conform == "off" else "checking"
    )
    native_conform_candidate_label = None

    if args.native_silhouette_conform in {"auto", "required"}:
        if len(geometry_inputs) > 1 and args.native_silhouette_conform == "auto":
            native_conform_status = "skipped_multi_reference"
            native_conform_failure = (
                "auto native conform is intentionally single-source; "
                "multi-reference jobs already provide real 3D coverage"
            )
            print(
                f"HAYUYA_NATIVE_CONFORM_SKIPPED {native_conform_failure}",
                file=sys.stderr,
            )
        else:
            provisional = valid[0]
            provisional_path = Path(provisional.path)
            native_conform_blockers: list[str] = []
            if provisional_path.suffix.lower() == ".glb":
                try:
                    from gltf_audit import audit_glb
                    native_conform_audit = audit_glb(provisional_path)
                    native_conform_blockers = native_conform_mutation_blockers(
                        native_conform_audit
                    )
                except Exception as exc:
                    native_conform_blockers = [
                        "audit_failed="
                        + type(exc).__name__
                    ]

            if native_conform_blockers:
                native_conform_status = "skipped_nonstatic_gltf"
                native_conform_failure = (
                    "native conform only mutates static pre-rig geometry; refusing "
                    "a trimesh round-trip that could damage skinning, animation, "
                    "morph targets, or an invalid GLB: "
                    + ",".join(native_conform_blockers)
                )
                print(
                    f"HAYUYA_NATIVE_CONFORM_SKIPPED {native_conform_failure}",
                    file=sys.stderr,
                )
                if args.native_silhouette_conform == "required":
                    raise RuntimeError(native_conform_failure)
            else:
                try:
                    from native_silhouette_conform import conform_native_silhouette

                    conform_dir = job_dir / "native_silhouette_conform"
                    native_conform_candidate_label = (
                        f"{provisional.backend}_native_conform"
                    )
                    conform_output = (
                        conform_dir / f"{native_conform_candidate_label}.glb"
                    )
                    native_conform_result = conform_native_silhouette(
                        provisional_path,
                        geometry_inputs[0],
                        conform_output,
                        report=conform_dir / "native_silhouette_conform.json",
                        size=256,
                        azimuth_step=30,
                        iterations=3,
                        boundary_band_px=5.0,
                        max_target_px=14.0,
                        per_vertex_cap_px=3.0,
                    )
                    if not native_conform_result.get("geometry_changed", False):
                        native_conform_status = "no_change_needed"
                        native_conform_candidate_label = None
                        print(
                            "HAYUYA_NATIVE_CONFORM_NOOP "
                            f"source={provisional.backend} "
                            f"score={native_conform_result['initial']['score']:.3f}->"
                            f"{native_conform_result['final']['score']:.3f} "
                            "original_glb_preserved=true"
                        )
                    else:
                        if mode == "character":
                            assert_native_character_360(
                                conform_output,
                                label=native_conform_candidate_label,
                            )
                        candidates.append(
                            (native_conform_candidate_label, conform_output)
                        )
                        native_conform_status = "candidate_ready"
                        print(
                            "HAYUYA_NATIVE_CONFORM_READY "
                            f"source={provisional.backend} "
                            f"candidate={native_conform_candidate_label} "
                            f"score={native_conform_result['initial']['score']:.3f}->"
                            f"{native_conform_result['final']['score']:.3f} "
                            f"max_body_span_delta="
                            f"{native_conform_result['max_displacement_body_span_ratio']:.6f}"
                        )

                        # It remains only a challenger. The complete production,
                        # silhouette, appearance and face-evidence arena decides if
                        # the native repair deserves promotion.
                        ranked = run_full_ranking()
                        valid = [x for x in ranked if x.valid]
                        if not valid:
                            raise RuntimeError(
                                "native silhouette conform re-ranking produced no valid candidates"
                            )
                except Exception as exc:
                    native_conform_status = "failed"
                    native_conform_failure = f"{type(exc).__name__}: {exc}"
                    print(
                        f"HAYUYA_NATIVE_CONFORM_FAILED {native_conform_failure}",
                        file=sys.stderr,
                    )
                    traceback.print_exc()
                    if args.native_silhouette_conform == "required":
                        raise

    source_face_repair_result = None
    source_face_repair_failure = None
    source_face_repair_status = (
        "off" if args.native_face_repair == "off" else "checking"
    )
    source_face_repair_candidate_label = None

    if args.native_face_repair in {"auto", "required"}:
        if mode != "character":
            source_face_repair_status = "skipped_not_character"
            source_face_repair_failure = (
                "native face repair only applies to detected/declared characters"
            )
            if args.native_face_repair == "required":
                raise RuntimeError(source_face_repair_failure)
        else:
            head_details = [
                Path(path)
                for path in detail_inputs
                if is_head_detail_evidence(
                    Path(path),
                    semantic_head_inputs=semantic_head_detail_inputs,
                )
            ]
            derive_head_from_full_source = not bool(head_details)
            face_source = (
                head_details[0]
                if head_details
                else Path(geometry_inputs[0])
            )
            if derive_head_from_full_source:
                print(
                    "HAYUYA_SOURCE_FACE_REPAIR_FALLBACK "
                    f"source={face_source} "
                    "method=foreground-silhouette-head-zoom"
                )

            provisional = valid[0]
            provisional_path = Path(provisional.path)
            try:
                from native_face_repair import (
                    prepare_source_face_repair_challenger,
                )

                face_dir = job_dir / "native_face_repair"
                source_face_repair_result = (
                    prepare_source_face_repair_challenger(
                        provisional_path,
                        face_source,
                        face_dir,
                        selected_backends=selected,
                        seed=args.seed + 9091,
                        hero_faces=max(
                            200_000,
                            min(int(profile.hero_faces), 750_000),
                        ),
                        trellis2_resolution=int(profile.trellis2_resolution),
                        texture_size=int(profile.texture_size),
                        model_root=args.model_root,
                        require_rebake=True,
                        derive_head_from_full_source=(
                            derive_head_from_full_source
                        ),
                    )
                )

                if not source_face_repair_result.ready:
                    source_face_repair_status = "rejected"
                    source_face_repair_failure = (
                        source_face_repair_result.error
                        or "source-derived face repair was not Judge-eligible"
                    )
                    print(
                        "HAYUYA_SOURCE_FACE_REPAIR_REJECTED "
                        + source_face_repair_failure,
                        file=sys.stderr,
                    )
                    if args.native_face_repair == "required":
                        raise RuntimeError(source_face_repair_failure)
                else:
                    source_face_repair_candidate_label = (
                        "source_face_repair_"
                        + str(source_face_repair_result.backend or "native")
                    )
                    repaired_path = Path(
                        str(source_face_repair_result.candidate_mesh)
                    )
                    assert_native_candidate(
                        repaired_path,
                        label=source_face_repair_candidate_label,
                    )
                    assert_native_character_360(
                        repaired_path,
                        label=source_face_repair_candidate_label,
                    )
                    candidates.append(
                        (source_face_repair_candidate_label, repaired_path)
                    )
                    source_face_repair_status = "candidate_ready"
                    print(
                        "HAYUYA_SOURCE_FACE_REPAIR_READY "
                        f"base={provisional.backend} "
                        f"donor_backend={source_face_repair_result.backend} "
                        f"detail={face_source} "
                        f"derived_from_full_source="
                        f"{str(derive_head_from_full_source).lower()} "
                        f"candidate={source_face_repair_candidate_label}"
                    )

                    ranked = run_full_ranking()
                    valid = [x for x in ranked if x.valid]
                    if not valid:
                        raise RuntimeError(
                            "source face repair re-ranking produced no valid candidates"
                        )
            except Exception as exc:
                source_face_repair_status = "failed"
                source_face_repair_failure = f"{type(exc).__name__}: {exc}"
                print(
                    f"HAYUYA_SOURCE_FACE_REPAIR_FAILED {source_face_repair_failure}",
                    file=sys.stderr,
                )
                traceback.print_exc()
                if args.native_face_repair == "required":
                    raise

    mesh_doctor_audit = None
    mesh_doctor_result = None
    mesh_doctor_failure = None
    mesh_doctor_status = "off" if args.mesh_doctor == "off" else "checking"

    if args.mesh_doctor in {"auto", "required"}:
        provisional = valid[0]
        provisional_path = Path(provisional.path)
        try:
            from mesh_doctor import audit_mesh, repair_candidate

            mesh_doctor_audit = audit_mesh(provisional_path)
            if not mesh_doctor_audit.valid:
                mesh_doctor_status = "audit_invalid"
                mesh_doctor_failure = "provisional champion failed Mesh Doctor audit"
                if args.mesh_doctor == "required":
                    raise RuntimeError(mesh_doctor_failure)
            else:
                boundary_repair_needed = bool(
                    mode in {"prop", "architecture"}
                    and mesh_doctor_audit.boundary_edges > 0
                    and not mesh_doctor_audit.watertight
                )
                repair_needed = bool(
                    mesh_doctor_audit.repair_recommended
                    or boundary_repair_needed
                )

                if not repair_needed:
                    mesh_doctor_status = "clean"
                    print(
                        "HAYUYA_MESH_DOCTOR_CLEAN "
                        f"defect_score={mesh_doctor_audit.defect_score:.3f}"
                    )
                    rigged = None
                else:
                    rigged = False

                if rigged is None:
                    pass
                else:
                    if provisional_path.suffix.lower() == ".glb":
                        try:
                            from gltf_audit import audit_glb
                            provisional_rig = audit_glb(provisional_path)
                            rigged = provisional_rig.skin_count > 0
                        except Exception:
                            rigged = False

                    if rigged:
                        mesh_doctor_status = "skipped_rigged"
                        mesh_doctor_failure = (
                            "structural repair needed but provisional champion is skinned; "
                            "topology-changing repair would invalidate JOINTS/WEIGHTS"
                        )
                        print(
                            f"HAYUYA_MESH_DOCTOR_SKIPPED {mesh_doctor_failure}",
                            file=sys.stderr,
                        )
                        if args.mesh_doctor == "required":
                            raise RuntimeError(mesh_doctor_failure)
                    else:
                        mesh_doctor_result = repair_candidate(
                            provisional_path,
                            job_dir / "mesh_doctor",
                            mode=mode,
                            texture_size=profile.texture_size,
                        )
                        if mesh_doctor_result.safe_for_arena:
                            candidates.append(
                                ("mesh_doctor_repair", Path(mesh_doctor_result.bridged_glb))
                            )
                            mesh_doctor_status = "candidate_ready"
                            print(
                                "HAYUYA_MESH_DOCTOR_READY "
                                f"defects={mesh_doctor_result.before.defect_score:.3f}->"
                                f"{mesh_doctor_result.after.defect_score:.3f} "
                                f"drift={mesh_doctor_result.vertex_surface_drift_normalized:.6f}"
                            )
                            ranked = run_full_ranking()
                            valid = [x for x in ranked if x.valid]
                            if not valid:
                                raise RuntimeError(
                                    "Mesh Doctor re-ranking produced no valid candidates"
                                )
                        else:
                            mesh_doctor_status = "rejected_unsafe"
                            mesh_doctor_failure = "; ".join(mesh_doctor_result.reasons)
                            print(
                                f"HAYUYA_MESH_DOCTOR_REJECTED {mesh_doctor_failure}",
                                file=sys.stderr,
                            )
                            if args.mesh_doctor == "required":
                                raise RuntimeError(mesh_doctor_failure)
        except Exception as exc:
            if mesh_doctor_status not in {"skipped_rigged", "rejected_unsafe", "audit_invalid"}:
                mesh_doctor_status = "failed"
                mesh_doctor_failure = f"{type(exc).__name__}: {exc}"
                print(
                    f"HAYUYA_MESH_DOCTOR_FAILED {mesh_doctor_failure}",
                    file=sys.stderr,
                )
                traceback.print_exc()
            if args.mesh_doctor == "required":
                raise

    retopo_result = None
    retopo_failure = None
    retopo_status = "off" if args.retopo == "off" else "checking"

    if args.retopo in {"auto", "required"}:
        provisional = valid[0]
        provisional_path = Path(provisional.path)
        rigged = False
        rig_reason = None

        if provisional_path.suffix.lower() == ".glb":
            try:
                from gltf_audit import audit_glb
                provisional_rig = audit_glb(provisional_path)
                rigged = provisional_rig.skin_count > 0
                if rigged:
                    rig_reason = (
                        f"provisional champion has {provisional_rig.skin_count} glTF skin(s); "
                        "retopology would destroy JOINTS/WEIGHTS"
                    )
            except Exception as exc:
                rig_reason = f"rig audit unavailable: {type(exc).__name__}: {exc}"

        if rigged:
            retopo_status = "skipped_rigged"
            retopo_failure = rig_reason
            print(f"HAYUYA_RETOPO_SKIPPED {rig_reason}", file=sys.stderr)
            if args.retopo == "required":
                raise RuntimeError(rig_reason)
        else:
            try:
                from retopo import retopo_readiness, run_retopology

                ready, missing = retopo_readiness(args.model_root)
                if not ready:
                    retopo_status = "skipped_unavailable"
                    retopo_failure = "; ".join(missing)
                    print(
                        f"HAYUYA_RETOPO_SKIPPED {retopo_failure}",
                        file=sys.stderr,
                    )
                    if args.retopo == "required":
                        raise RuntimeError(retopo_failure)
                else:
                    source_faces = int(provisional.faces or profile.faces)
                    target_runtime_faces = max(
                        200,
                        min(profile.faces, source_faces),
                    )
                    style = (
                        "quad_dominant"
                        if mode == "character"
                        else "pure_quad"
                    )
                    retopo_result = run_retopology(
                        provisional_path,
                        job_dir / "retopo",
                        target_triangle_faces=target_runtime_faces,
                        style=style,
                        texture_size=profile.texture_size,
                        model_root=args.model_root,
                    )
                    candidates.append(
                        ("instant_meshes_retopo", Path(retopo_result.bridged_glb))
                    )
                    retopo_status = "candidate_ready"
                    print(
                        "HAYUYA_RETOPO_READY "
                        f"style={retopo_result.style} "
                        f"quad_fraction={retopo_result.quad_fraction:.4f} "
                        f"obj={retopo_result.retopo_obj}"
                    )

                    # The retopologized/PBR-restored asset earns nothing for merely
                    # existing. Re-run exactly the same real-source Judge arena.
                    ranked = run_full_ranking()
                    valid = [x for x in ranked if x.valid]
                    if not valid:
                        raise RuntimeError("retopo re-ranking produced no valid candidates")
            except Exception as exc:
                if retopo_status != "skipped_unavailable":
                    retopo_status = "failed"
                    retopo_failure = f"{type(exc).__name__}: {exc}"
                    print(
                        f"HAYUYA_RETOPO_FAILED {retopo_failure}",
                        file=sys.stderr,
                    )
                    traceback.print_exc()
                if args.retopo == "required":
                    raise

    texture_superres_result = None
    texture_superres_failure = None
    texture_superres_status = (
        "off" if args.texture_superres == "off" else "checking"
    )

    if args.texture_superres in {"auto", "required"}:
        provisional = valid[0]
        provisional_edge = int(provisional.base_color_min_edge or 0)
        if args.profile not in {"monster", "ultra"}:
            texture_superres_status = "skipped_profile"
        elif provisional_edge <= 0:
            texture_superres_status = "skipped_no_basecolor"
            texture_superres_failure = (
                "provisional champion has no embedded visible baseColor texture"
            )
            print(
                f"HAYUYA_TEXTURE_SUPERRES_SKIPPED {texture_superres_failure}",
                file=sys.stderr,
            )
            if args.texture_superres == "required":
                raise RuntimeError(texture_superres_failure)
        elif not needs_texture_superres(
            args.profile,
            provisional_edge,
            profile.texture_size,
        ):
            texture_superres_status = "already_at_target"
            print(
                "HAYUYA_TEXTURE_SUPERRES_CLEAN "
                f"basecolor={provisional_edge} target={profile.texture_size}"
            )
        else:
            try:
                from texture_superres import superresolve_basecolor_glb

                sr_dir = job_dir / "texture_superres"
                sr_output = sr_dir / (
                    f"{provisional.backend}_basecolor_{profile.texture_size}.glb"
                )
                texture_superres_result = superresolve_basecolor_glb(
                    Path(provisional.path),
                    sr_output,
                    target_edge=profile.texture_size,
                    auto_install=True,
                )
                if texture_superres_result.ready:
                    sr_label = f"{provisional.backend}_texture_sr"
                    candidates.append(
                        (sr_label, Path(texture_superres_result.output_glb))
                    )
                    texture_superres_status = "candidate_ready"
                    print(
                        "HAYUYA_TEXTURE_SUPERRES_READY "
                        f"source={provisional.backend} candidate={sr_label} "
                        f"basecolor={provisional_edge}->{profile.texture_size} "
                        f"items={len(texture_superres_result.items)}"
                    )
                    print(
                        "HAYUYA_CANDIDATE_READY "
                        f"{sr_label} {texture_superres_result.output_glb} "
                        "source=texture_superres"
                    )
                    # Super-resolution earns nothing merely for reaching 4K.
                    # It must survive the same full real-source Judge arena.
                    ranked = run_full_ranking()
                    valid = [x for x in ranked if x.valid]
                    if not valid:
                        raise RuntimeError(
                            "texture super-resolution re-ranking produced no valid candidates"
                        )

                    source_item=next(
                        (x for x in ranked if x.backend==provisional.backend),
                        provisional,
                    )
                    sr_item=next(
                        (x for x in ranked if x.backend==sr_label),
                        None,
                    )
                    if sr_item is None:
                        raise RuntimeError(
                            "texture super-resolution challenger missing from re-ranking"
                        )
                    regressions=texture_refinement_regressions(
                        source_item,
                        sr_item,
                    )
                    if regressions:
                        sr_item.valid=False
                        sr_item.notes.append(
                            "texture refinement promotion guard rejected: "
                            + ";".join(regressions)
                        )
                        ranked=sorted(
                            ranked,
                            key=lambda x:(x.valid,x.score),
                            reverse=True,
                        )
                        valid=[x for x in ranked if x.valid]
                        texture_superres_status="rejected_regression"
                        texture_superres_failure=";".join(regressions)
                        print(
                            "HAYUYA_TEXTURE_SUPERRES_REJECTED "
                            + texture_superres_failure,
                            file=sys.stderr,
                        )
                        if args.texture_superres=="required":
                            raise RuntimeError(texture_superres_failure)
                    else:
                        texture_superres_status="guard_passed"
                        print(
                            "HAYUYA_TEXTURE_SUPERRES_GUARD_PASS "
                            f"source={source_item.backend} candidate={sr_label}"
                        )
                else:
                    texture_superres_failure = (
                        texture_superres_result.error
                        or texture_superres_result.method
                    )
                    texture_superres_status = (
                        "skipped_unavailable"
                        if texture_superres_result.method == "realesrgan_unavailable"
                        else "rejected"
                    )
                    print(
                        "HAYUYA_TEXTURE_SUPERRES_SKIPPED "
                        f"{texture_superres_failure}",
                        file=sys.stderr,
                    )
                    if args.texture_superres == "required":
                        raise RuntimeError(texture_superres_failure)
            except Exception as exc:
                if texture_superres_status != "skipped_unavailable":
                    texture_superres_status = "failed"
                    texture_superres_failure = f"{type(exc).__name__}: {exc}"
                    print(
                        f"HAYUYA_TEXTURE_SUPERRES_FAILED {texture_superres_failure}",
                        file=sys.stderr,
                    )
                    traceback.print_exc()
                if args.texture_superres == "required":
                    raise

    ranking_data = [asdict(x) for x in ranked]
    (job_dir / "ranking.json").write_text(
        json.dumps(ranking_data, indent=2) + "\n",
        encoding="utf-8",
    )

    composite_plan = None
    composite_plan_failure = None
    composite_execution = None
    composite_head_execution = None
    composite_local_executions = []

    from composite_champion import (
        build_composite_plan,
        execute_safe_accessory_challenger,
        execute_safe_head_wrap_challenger,
        execute_safe_local_detail_challenger,
        execute_safe_material_challenger,
        write_composite_plan,
    )
    from qa import candidate_rank_key

    identity_required = any(
        infer_detail_region_hint(path)=="head"
        for path in detail_inputs
    )

    def sort_current_ranking():
        nonlocal ranked, valid
        ranked=sorted(
            ranked,
            key=lambda item:candidate_rank_key(
                item,
                mode=mode,
                identity_required=identity_required,
            ),
            reverse=True,
        )
        valid=[item for item in ranked if item.valid]

    def remove_candidate(label: str | None):
        if not label:
            return
        candidates[:] = [pair for pair in candidates if pair[0] != label]

    def promote_composite_base(label: str):
        nonlocal ranked, valid
        chosen=next(
            (
                item for item in ranked
                if item.backend==label and item.valid
            ),
            None,
        )
        if chosen is None:
            raise RuntimeError(
                f"cannot promote missing Composite candidate: {label}"
            )
        ranked=[
            chosen,
            *[
                item for item in ranked
                if item is not chosen
            ],
        ]
        valid=[item for item in ranked if item.valid]

    def refresh_composite_plan():
        current=build_composite_plan(
            valid,
            mode=mode,
            max_finalists=5,
            inspect_parts=True,
        )
        composite_path=write_composite_plan(
            current,
            job_dir / "composite_champion_plan.json",
        )
        donor_summary=";".join(
            f"{item.region}:{item.donor_backend}"
            for item in current.donors
            if item.donor_backend != current.base_backend
        ) or "base_only"
        print(
            "HAYUYA_COMPOSITE_PLAN_READY "
            f"base={current.base_backend} "
            f"required={str(bool(current.composite_required)).lower()} "
            f"finalists={len(current.finalists)} "
            f"donors={donor_summary} "
            f"plan={composite_path}"
        )
        return current

    try:
        composite_plan=refresh_composite_plan()
    except Exception as exc:
        composite_plan_failure=f"{type(exc).__name__}: {exc}"
        print(
            f"HAYUYA_COMPOSITE_PLAN_FAILED {composite_plan_failure}",
            file=sys.stderr,
        )
        traceback.print_exc()

    if composite_plan is not None and "material_response" in composite_plan.executable_now:
        try:
            composite_execution=execute_safe_material_challenger(
                composite_plan,
                job_dir / "composite" / "material",
                texture_size=profile.texture_size,
            )
            if composite_execution.ready:
                label=str(composite_execution.candidate_label)
                candidates.append((
                    label,
                    Path(str(composite_execution.candidate_path)),
                ))
                print(
                    "HAYUYA_COMPOSITE_CANDIDATE_READY "
                    f"label={label} "
                    f"base={composite_execution.base_backend} "
                    f"donor={composite_execution.donor_backend} "
                    f"region={composite_execution.region} "
                    f"path={composite_execution.candidate_path}"
                )
                ranked=run_full_ranking()
                valid=[item for item in ranked if item.valid]
                base_item=next(
                    (item for item in ranked if item.backend==composite_execution.base_backend),
                    None,
                )
                composite_item=next(
                    (item for item in ranked if item.backend==label),
                    None,
                )
                if base_item is None or composite_item is None:
                    raise RuntimeError(
                        "composite material challenger missing after re-ranking"
                    )
                regressions=texture_refinement_regressions(
                    base_item,
                    composite_item,
                )
                regressions.extend(
                    _strict_metric_improvement(
                        base_item,
                        composite_item,
                        "material_score",
                    )
                )
                if regressions:
                    composite_item.valid=False
                    composite_item.notes.append(
                        "Composite Champion material guard rejected: "
                        + ";".join(regressions)
                    )
                    remove_candidate(label)
                    sort_current_ranking()
                    composite_execution.ready=False
                    composite_execution.error=(
                        "monotonic_guard:"+";".join(regressions)
                    )
                    print(
                        "HAYUYA_COMPOSITE_CANDIDATE_REJECTED "
                        + composite_execution.error,
                        file=sys.stderr,
                    )
                else:
                    promote_composite_base(label)
                    print(
                        "HAYUYA_COMPOSITE_CANDIDATE_GUARD_PASS "
                        f"label={label} canonical=true"
                    )
            elif composite_execution.attempted:
                print(
                    "HAYUYA_COMPOSITE_CANDIDATE_FAILED "
                    f"{composite_execution.error or 'unknown'}",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                "HAYUYA_COMPOSITE_EXECUTION_FAILED "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc()

        try:
            composite_plan=refresh_composite_plan()
        except Exception as exc:
            composite_plan_failure=f"{type(exc).__name__}: {exc}"

    if composite_plan is not None and "face_identity" in composite_plan.executable_now:
        try:
            composite_head_execution=execute_safe_head_wrap_challenger(
                composite_plan,
                job_dir / "composite" / "head",
                texture_size=profile.texture_size,
            )
            if composite_head_execution.ready:
                label=str(composite_head_execution.candidate_label)
                candidates.append((
                    label,
                    Path(str(composite_head_execution.candidate_path)),
                ))
                print(
                    "HAYUYA_COMPOSITE_HEAD_READY "
                    f"label={label} "
                    f"base={composite_head_execution.base_backend} "
                    f"donor={composite_head_execution.donor_backend} "
                    f"path={composite_head_execution.candidate_path}"
                )
                ranked=run_full_ranking()
                valid=[item for item in ranked if item.valid]
                base_item=next(
                    (item for item in ranked if item.backend==composite_head_execution.base_backend),
                    None,
                )
                head_item=next(
                    (item for item in ranked if item.backend==label),
                    None,
                )
                if base_item is None or head_item is None:
                    raise RuntimeError(
                        "composite head challenger missing after re-ranking"
                    )
                regressions=head_composite_regressions(
                    base_item,
                    head_item,
                )
                regressions.extend(
                    _strict_metric_improvement(
                        base_item,
                        head_item,
                        "appearance_face_detail_min_score",
                    )
                )
                if regressions:
                    head_item.valid=False
                    head_item.notes.append(
                        "Composite Champion head guard rejected: "
                        + ";".join(regressions)
                    )
                    remove_candidate(label)
                    sort_current_ranking()
                    composite_head_execution.ready=False
                    composite_head_execution.error=(
                        "head_guard:"+";".join(regressions)
                    )
                    print(
                        "HAYUYA_COMPOSITE_HEAD_REJECTED "
                        + composite_head_execution.error,
                        file=sys.stderr,
                    )
                else:
                    promote_composite_base(label)
                    print(
                        "HAYUYA_COMPOSITE_HEAD_GUARD_PASS "
                        f"label={label} canonical=true"
                    )
            elif composite_head_execution.attempted:
                print(
                    "HAYUYA_COMPOSITE_HEAD_FAILED "
                    f"{composite_head_execution.error or 'unknown'}",
                    file=sys.stderr,
                )
            elif composite_head_execution.error:
                print(
                    "HAYUYA_COMPOSITE_HEAD_SKIPPED "
                    f"{composite_head_execution.error}",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                "HAYUYA_COMPOSITE_HEAD_EXECUTION_FAILED "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc()

        try:
            composite_plan=refresh_composite_plan()
        except Exception as exc:
            composite_plan_failure=f"{type(exc).__name__}: {exc}"

    attempted_detail_tokens=set()
    while composite_plan is not None:
        detail_tokens=sorted(
            token
            for token in composite_plan.executable_now
            if token.startswith("detail:")
            and token not in attempted_detail_tokens
        )
        if not detail_tokens:
            break

        token=detail_tokens[0]
        attempted_detail_tokens.add(token)
        detail_source=token[len("detail:"):]
        detail_execution=None
        try:
            detail_plan_item=next(
                (
                    item for item in composite_plan.detail_donors
                    if item.source==detail_source
                ),
                None,
            )
            detail_strategy=(
                str(detail_plan_item.strategy)
                if detail_plan_item is not None else ""
            )
            is_rigged_accessory=(
                detail_strategy
                =="matched_rig_preserving_accessory_wrap_then_rebake"
            )
            is_inserted_accessory=(
                detail_strategy
                =="new_rigged_accessory_insert_weight_morph_transfer"
            )
            is_accessory=detail_strategy in {
                "matched_detached_accessory_swap_then_mesh_doctor",
                "matched_rig_preserving_accessory_wrap_then_rebake",
                "new_rigged_accessory_insert_weight_morph_transfer",
            }
            if is_accessory:
                detail_execution=execute_safe_accessory_challenger(
                    composite_plan,
                    job_dir / "composite" / "accessories",
                    detail_source=detail_source,
                    texture_size=profile.texture_size,
                )
            else:
                detail_execution=execute_safe_local_detail_challenger(
                    composite_plan,
                    job_dir / "composite" / "details",
                    detail_source=detail_source,
                )
            composite_local_executions.append(detail_execution)
            if detail_execution.ready:
                label=str(detail_execution.candidate_label)
                candidates.append((
                    label,
                    Path(str(detail_execution.candidate_path)),
                ))
                detail_fusion=detail_execution.fusion or {}
                print(
                    "HAYUYA_COMPOSITE_DETAIL_READY "
                    f"label={label} "
                    f"base={detail_execution.base_backend} "
                    f"donor={detail_execution.donor_backend} "
                    f"region={detail_execution.region_hint} "
                    f"source={Path(detail_source).name} "
                    f"strategy={('rigged_accessory_insert' if is_inserted_accessory else ('rigged_accessory_wrap' if is_rigged_accessory else ('accessory_swap' if is_accessory else 'texture_fusion')))} "
                    f"changed={detail_fusion.get('changed_fraction','none')} "
                    f"changed_vertices={detail_fusion.get('changed_vertices','none')} "
                    f"inserted_vertices={detail_fusion.get('inserted_vertices','none')} "
                    f"inserted_faces={detail_fusion.get('inserted_faces','none')} "
                    f"inserted_primitives={detail_fusion.get('inserted_primitives','none')} "
                    f"material_groups={detail_fusion.get('material_groups','none')} "
                    f"weight_transfer_vertices={detail_fusion.get('transferred_weight_vertices','none')} "
                    f"weight_source_max={detail_fusion.get('weight_source_max_distance_ratio','none')} "
                    f"surface_transfer={detail_fusion.get('surface_transfer_method','none')} "
                    f"surface_fallback_vertices={detail_fusion.get('surface_transfer_fallback_vertices','none')} "
                    f"surface_search_triangles={detail_fusion.get('surface_transfer_max_examined_triangles','none')} "
                    f"surface_bvh_nodes={detail_fusion.get('surface_transfer_max_visited_bvh_nodes','none')} "
                    f"surface_ambiguous_vertices={detail_fusion.get('surface_skin_ambiguous_vertices','none')} "
                    f"surface_skin_gap={detail_fusion.get('surface_skin_min_gap_ratio','none')} "
                    f"surface_skin_l1={detail_fusion.get('surface_skin_max_l1','none')} "
                    f"morph_targets_transferred={detail_fusion.get('morph_targets_transferred','none')} "
                    f"geometry_ready={detail_fusion.get('geometry_ready','none')} "
                    f"material_ready={detail_fusion.get('material_ready','none')} "
                    f"uv_ready={detail_fusion.get('uv_ready','none')} "
                    f"uv_tangent_ready={detail_fusion.get('uv_tangent_ready','none')} "
                    f"production_ready={detail_fusion.get('production_ready','none')} "
                    f"legacy_preserved={detail_fusion.get('legacy_payload_preserved','none')} "
                    f"material_channels={','.join(detail_fusion.get('material_channels') or []) or 'none'} "
                    f"seam_p95={detail_fusion.get('seam_added_delta_p95','none')} "
                    f"seam_max={detail_fusion.get('seam_added_delta_max','none')} "
                    f"accessory_confidence={detail_fusion.get('confidence','none')} "
                    f"runtime_preserved={detail_fusion.get('runtime_payload_preserved',detail_fusion.get('legacy_payload_preserved','none'))} "
                    f"rig_ready={detail_fusion.get('rig_ready','none')} "
                    f"skin_weights_ready={detail_fusion.get('skin_weights_ready','none')} "
                    f"morph_deformation_ready={detail_fusion.get('morph_deformation_ready','none')} "
                    f"animation_ready={detail_fusion.get('animation_ready','none')} "
                    f"deformation_ready={detail_fusion.get('deformation_ready','none')} "
                    f"attachment_ready={detail_fusion.get('attachment_ready','none')} "
                    f"rebake_ready={detail_fusion.get('rebake_ready','none')} "
                    f"path={detail_execution.candidate_path}"
                )
                ranked=run_full_ranking()
                valid=[item for item in ranked if item.valid]
                base_item=next(
                    (
                        item for item in ranked
                        if item.backend==detail_execution.base_backend
                    ),
                    None,
                )
                detail_item=next(
                    (
                        item for item in ranked
                        if item.backend==label
                    ),
                    None,
                )
                if base_item is None or detail_item is None:
                    raise RuntimeError(
                        "composite local-detail challenger missing after re-ranking"
                    )
                regressions=(
                    accessory_composite_regressions(
                        base_item,
                        detail_item,
                        detail_source,
                    )
                    if is_accessory
                    else local_detail_composite_regressions(
                        base_item,
                        detail_item,
                        detail_source,
                    )
                )
                if regressions:
                    detail_item.valid=False
                    detail_item.notes.append(
                        "Composite Champion local-detail guard rejected: "
                        +";".join(regressions)
                    )
                    remove_candidate(label)
                    sort_current_ranking()
                    detail_execution.ready=False
                    detail_execution.error=(
                        "detail_guard:"+ ";".join(regressions)
                    )
                    print(
                        "HAYUYA_COMPOSITE_DETAIL_REJECTED "
                        f"label={label} "
                        f"source={Path(detail_source).name} "
                        f"reason={detail_execution.error.replace(' ','_')}",
                        file=sys.stderr,
                    )
                else:
                    promote_composite_base(label)
                    print(
                        "HAYUYA_COMPOSITE_DETAIL_GUARD_PASS "
                        f"label={label} "
                        f"source={Path(detail_source).name} "
                        "canonical=true"
                    )
            elif detail_execution.attempted:
                print(
                    "HAYUYA_COMPOSITE_DETAIL_FAILED "
                    f"source={Path(detail_source).name} "
                    f"{detail_execution.error or 'unknown'}",
                    file=sys.stderr,
                )
        except Exception as exc:
            print(
                "HAYUYA_COMPOSITE_DETAIL_EXECUTION_FAILED "
                f"source={Path(detail_source).name} "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc()

        try:
            composite_plan=refresh_composite_plan()
        except Exception as exc:
            composite_plan_failure=f"{type(exc).__name__}: {exc}"
            break

    ranking_data=[asdict(item) for item in ranked]
    (job_dir / "ranking.json").write_text(
        json.dumps(ranking_data,indent=2)+"\n",
        encoding="utf-8",
    )

    champion = valid[0]
    source = Path(champion.path)
    final_glb = export_glb(source, job_dir / "hayuya_final.glb")

    semantic_anatomy_result = None
    semantic_anatomy_failure = None
    should_try_semantic_anatomy = bool(
        mode=="character"
        and args.semantic_anatomy!="off"
        and (
            args.semantic_anatomy=="required"
            or args.profile in {"monster","ultra"}
        )
    )
    if should_try_semantic_anatomy:
        try:
            from semantic_anatomy_runner import run_semantic_anatomy
            semantic_anatomy_result=run_semantic_anatomy(
                final_glb,
                detail_inputs,
                job_dir / "semantic_anatomy",
                policy=args.semantic_anatomy,
            )
            if semantic_anatomy_result.required:
                print(
                    "HAYUYA_SEMANTIC_ANATOMY_READY "
                    f"attempted={str(bool(semantic_anatomy_result.attempted)).lower()} "
                    f"ready={str(bool(semantic_anatomy_result.ready)).lower()} "
                    f"targets={','.join(semantic_anatomy_result.critical_targets) if semantic_anatomy_result.critical_targets else 'none'} "
                    f"views={len(semantic_anatomy_result.rendered_views)} "
                    f"report={str(job_dir / 'semantic_anatomy' / 'semantic_anatomy.json') if (job_dir / 'semantic_anatomy' / 'semantic_anatomy.json').is_file() else 'none'} "
                    f"error={(semantic_anatomy_result.error or 'none').replace(' ','_')}"
                )
                if (
                    args.semantic_anatomy=="required"
                    and not semantic_anatomy_result.ready
                ):
                    raise RuntimeError(
                        semantic_anatomy_result.error
                        or "required semantic anatomy validation failed"
                    )
        except Exception as exc:
            semantic_anatomy_failure=f"{type(exc).__name__}: {exc}"
            print(
                f"HAYUYA_SEMANTIC_ANATOMY_FAILED {semantic_anatomy_failure}",
                file=sys.stderr,
            )
            traceback.print_exc()
            if args.semantic_anatomy=="required":
                raise

    gameprep_result = None
    gameprep_failure = None
    should_try_gameprep = (
        args.gameprep in {"auto", "required"}
        and args.profile in {"mobile", "game", "monster", "ultra"}
    )
    if should_try_gameprep:
        try:
            from gameprep import build_gameprep
            from visual_judge import SourceViewScore

            anchor_view = None
            if champion.visual_views:
                anchor_view = SourceViewScore(**champion.visual_views[0])

            gameprep_result = build_gameprep(
                final_glb,
                job_dir / "gameprep",
                target_faces=min(profile.faces, portable_lod0_ceiling),
                anchor_view=anchor_view,
                material_samples=(
                    80000 if args.profile == "mobile"
                    else 120000 if args.profile == "game"
                    else 180000
                ),
                max_texture_size=portable_texture_ceiling,
            )
            print(
                "HAYUYA_GAMEPREP_READY "
                f"lods={len(gameprep_result.lods)} "
                f"collision={bool(gameprep_result.collision)} "
                f"turntable={len(gameprep_result.turntable_frames)}"
            )
        except Exception as exc:
            gameprep_failure = f"{type(exc).__name__}: {exc}"
            print(
                f"HAYUYA_GAMEPREP_FAILED {gameprep_failure}",
                file=sys.stderr,
            )
            traceback.print_exc()
            if args.gameprep == "required":
                raise

    judge_v4_result = None
    judge_v4_failure = None
    judge_v4_required = bool(
        mode=="character"
        and (
            args.judge_v4=="required"
            or (
                args.judge_v4=="auto"
                and args.profile in {"monster","ultra"}
            )
        )
    )
    should_run_judge_v4 = bool(
        mode=="character"
        and args.judge_v4!="off"
        and (
            judge_v4_required
            or args.profile in {"game","monster","ultra"}
        )
    )
    if should_run_judge_v4:
        try:
            if gameprep_result is None:
                raise RuntimeError(
                    "Judge v4 requires GamePrep turntable evidence"
                )
            from judge_v4 import run_judge_v4
            judge_v4_result=run_judge_v4(
                final_glb=final_glb,
                source_images=geometry_inputs,
                detail_images=detail_inputs,
                turntable_frames=[
                    Path(p) for p in gameprep_result.turntable_frames
                ],
                out_dir=job_dir / "judge_v4",
                policy=("required" if judge_v4_required else args.judge_v4),
            )
            print(
                "HAYUYA_JUDGE_V4_READY "
                f"passed={str(bool(judge_v4_result.passed)).lower()} "
                f"hard_failures={len(judge_v4_result.hard_fail_reasons)} "
                f"report={job_dir / 'judge_v4' / 'judge_v4.json'}"
            )
            if judge_v4_required and not judge_v4_result.passed:
                raise RuntimeError(
                    "Judge v4 rejected final character: "
                    + ";".join(judge_v4_result.hard_fail_reasons[:16])
                )
        except Exception as exc:
            judge_v4_failure=f"{type(exc).__name__}: {exc}"
            print(
                f"HAYUYA_JUDGE_V4_FAILED {judge_v4_failure}",
                file=sys.stderr,
            )
            traceback.print_exc()
            if judge_v4_required:
                raise

    judge_v5_result = None
    judge_v5_failure = None
    judge_v5_should_run = bool(
        mode=="character"
        and args.judge_v5!="off"
        and (
            args.judge_v5=="required"
            or args.profile in {"game","monster","ultra"}
        )
    )
    judge_v5_required = bool(args.judge_v5=="required")
    if judge_v5_should_run:
        try:
            if judge_v4_result is None:
                raise RuntimeError("Judge v5 requires Judge v4 evidence")
            from judge_v5 import run_judge_v5
            judge_v5_result=run_judge_v5(
                judge_v4=judge_v4_result,
                source_images=geometry_inputs,
                final_glb=final_glb,
                out_dir=job_dir / "judge_v5",
                python_executable=(
                    __import__("os").environ.get("HAYUYA_JUDGE_V4_PYTHON")
                    or None
                ),
            )
            print(
                "HAYUYA_JUDGE_V5_READY "
                f"status={judge_v5_result.status} "
                f"passed={str(bool(judge_v5_result.passed)).lower()} "
                f"hard_failures={len(judge_v5_result.hard_fail_reasons)} "
                f"report={job_dir / 'judge_v5' / 'judge_v5.json'}"
            )
            if judge_v5_required and not judge_v5_result.passed:
                raise RuntimeError(
                    "Judge v5 did not production-approve final character: "
                    f"status={judge_v5_result.status}; "
                    + ";".join(judge_v5_result.hard_fail_reasons[:16])
                )
        except Exception as exc:
            judge_v5_failure=f"{type(exc).__name__}: {exc}"
            print(
                f"HAYUYA_JUDGE_V5_FAILED {judge_v5_failure}",
                file=sys.stderr,
            )
            traceback.print_exc()
            if judge_v5_required:
                raise

    portable_pack_result = None
    portable_pack_failure = None
    should_try_portable_pack = (
        args.portable_pack in {"auto", "required"}
        and args.profile in {"mobile", "game", "monster", "ultra"}
    )
    if should_try_portable_pack:
        try:
            from portable_pack import build_portable_pack
            from visual_judge import SourceViewScore

            portable_anchor = None
            if champion.visual_views:
                portable_anchor = SourceViewScore(**champion.visual_views[0])

            portable_pack_result = build_portable_pack(
                final_glb,
                job_dir / "portable",
                mode=mode,
                profile_name=args.profile,
                anchor_view=portable_anchor,
                material_samples=(
                    80000 if args.profile == "mobile"
                    else 120000 if args.profile == "game"
                    else 180000
                ),
                texture_delivery_mode=args.texture_delivery,
            )
            print(
                "HAYUYA_PORTABLE_PACK_READY "
                f"tiers={len(portable_pack_result.tiers)} "
                f"complete_lods={portable_pack_result.complete_lod_chain} "
                f"lod_parity_ready={portable_pack_result.lod_parity_ready} "
                f"runtime_budget_ready={portable_pack_result.runtime_budget_ready} "
                f"manifest={portable_pack_result.manifest}"
            )
        except Exception as exc:
            portable_pack_failure = f"{type(exc).__name__}: {exc}"
            print(
                f"HAYUYA_PORTABLE_PACK_FAILED {portable_pack_failure}",
                file=sys.stderr,
            )
            traceback.print_exc()
            if args.portable_pack == "required":
                raise

    qa_package_result = None
    qa_package_failure = None
    try:
        from qa_package import build_qa_package

        qa_package_result = build_qa_package(
            final_glb,
            job_dir / "qa",
            champion=champion,
            mode=mode,
            profile=args.profile,
            source_images=geometry_inputs,
            detail_images=detail_inputs,
            gameprep=gameprep_result,
            target_faces=profile.hero_faces,
            target_texture_size=profile.texture_size,
        )
        print(
            "HAYUYA_QA_READY "
            f"production_ready={qa_package_result.production_ready} "
            f"material_ready={qa_package_result.material_ready} "
            f"texture_ready={qa_package_result.texture_resolution_ready} "
            f"texture_score={qa_package_result.texture_resolution_score if qa_package_result.texture_resolution_score is not None else 'none'} "
            f"basecolor_min={qa_package_result.base_color_min_edge} "
            f"basecolor_max={qa_package_result.base_color_max_edge} "
            f"texture_target={qa_package_result.target_texture_size if qa_package_result.target_texture_size is not None else 'none'} "
            f"rebake_ready={qa_package_result.material_rebake_ready} "
            f"rebaked={','.join(qa_package_result.material_rebaked_channels) if qa_package_result.material_rebaked_channels else 'none'} "
            f"rebake_pending={','.join(qa_package_result.material_rebake_pending_channels) if qa_package_result.material_rebake_pending_channels else 'none'} "
            f"rig_ready={qa_package_result.rig_ready} "
            f"morph_ready={qa_package_result.morph_ready} "
            f"morph_targets={qa_package_result.morph_target_count} "
            f"morph_deformation_ready={qa_package_result.morph_deformation_ready} "
            f"morph_deformation_poses={qa_package_result.morph_deformation_poses} "
            f"morph_deformation_max_disp={qa_package_result.morph_deformation_max_displacement_ratio if qa_package_result.morph_deformation_max_displacement_ratio is not None else 'none'} "
            f"crossing_ready={qa_package_result.component_crossing_ready} "
            f"crossing_pairs={qa_package_result.component_crossing_pairs} "
            f"self_intersection_ready={qa_package_result.self_intersection_ready} "
            f"self_intersection_pairs={qa_package_result.self_intersection_pairs} "
            f"composite_attachment_ready={qa_package_result.composite_attachment_ready} "
            f"composite_components={qa_package_result.composite_attachment_components} "
            f"composite_accessories={qa_package_result.composite_attachment_accessories} "
            f"composite_floating={qa_package_result.composite_attachment_floating} "
            f"composite_oversized_floating={qa_package_result.composite_attachment_oversized_floating} "
            f"uv_tangent_ready={qa_package_result.uv_tangent_ready} "
            f"uv_missing={qa_package_result.uv_missing_primitives} "
            f"uv_degenerate={qa_package_result.uv_degenerate_triangles} "
            f"shading_basis_ready={qa_package_result.shading_basis_ready} "
            f"shading_missing_normals={qa_package_result.shading_missing_normals} "
            f"shading_missing_tangents={qa_package_result.shading_missing_tangents} "
            f"shading_bad_handedness={qa_package_result.shading_invalid_handedness} "
            f"shading_nonorthogonal={qa_package_result.shading_nonorthogonal_tangents} "
            f"collision_ready={qa_package_result.collision_ready} "
            f"collision_faces={qa_package_result.collision_faces} "
            f"collision_convexity={qa_package_result.collision_convexity_ratio if qa_package_result.collision_convexity_ratio is not None else 'none'} "
            f"collision_bbox_ready={qa_package_result.collision_bbox_coverage_ready} "
            f"skin_weights_ready={qa_package_result.skin_weights_ready} "
            f"animation_ready={qa_package_result.animation_ready} "
            f"animation_integrity_ready={qa_package_result.animation_integrity_ready} "
            f"animation_channels={qa_package_result.animation_channels} "
            f"animation_keyframes={qa_package_result.animation_keyframes} "
            f"deformation_ready={qa_package_result.deformation_ready} "
            f"deformation_frames={qa_package_result.deformation_frames} "
            f"deformation_max_disp={qa_package_result.deformation_max_displacement_ratio if qa_package_result.deformation_max_displacement_ratio is not None else 'none'} "
            f"deformation_max_edge={qa_package_result.deformation_max_edge_stretch_ratio if qa_package_result.deformation_max_edge_stretch_ratio is not None else 'none'} "
            f"face_ready={qa_package_result.face_evidence_ready} "
            f"face_quality_ready={qa_package_result.face_quality_evidence_ready} "
            f"anatomy_ready={qa_package_result.anatomy_evidence_ready} "
            f"anatomy_expected={qa_package_result.anatomy_evidence_expected} "
            f"anatomy_evaluated={qa_package_result.anatomy_evidence_evaluated} "
            f"face_score={qa_package_result.face_evidence_score if qa_package_result.face_evidence_score is not None else 'none'} "
            f"face_min={qa_package_result.face_evidence_min_score if qa_package_result.face_evidence_min_score is not None else 'none'} "
            f"face_expected={qa_package_result.face_evidence_expected} "
            f"face_evaluated={qa_package_result.face_evidence_evaluated} "
            f"facemesh_score={qa_package_result.head_density_score if qa_package_result.head_density_score is not None else 'none'} "
            f"facetex_score={qa_package_result.head_texel_density_score if qa_package_result.head_texel_density_score is not None else 'none'} "
            f"facedetail_score={qa_package_result.head_texture_detail_score if qa_package_result.head_texture_detail_score is not None else 'none'} "
            f"report={qa_package_result.report}"
        )
    except Exception as exc:
        qa_package_failure = f"{type(exc).__name__}: {exc}"
        print(f"HAYUYA_QA_FAILED {qa_package_failure}", file=sys.stderr)
        traceback.print_exc()

    manifest = {
        **plan,
        "status": "success",
        "failures": failures,
        "source_autofix": (
            asdict(source_autofix_result)
            if source_autofix_result is not None
            else plan.get("source_autofix")
        ),
        "source_autofix_failure": source_autofix_failure,
        "viewforge": asdict(viewforge_result) if viewforge_result is not None else None,
        "viewforge_failure": viewforge_failure,
        "character_specialist": {
            "status": character_specialist_status,
            "failure": character_specialist_failure,
        },
        "native_face_repair": {
            "mode": args.native_face_repair,
            "status": source_face_repair_status,
            "result": (
                asdict(source_face_repair_result)
                if source_face_repair_result is not None else None
            ),
            "failure": source_face_repair_failure,
            "candidate_label": source_face_repair_candidate_label,
            "won_final_arena": bool(
                source_face_repair_candidate_label
                and champion.backend == source_face_repair_candidate_label
            ),
            "policy": (
                "current-source head evidence -> native 3D donor -> seam-safe "
                "full-body head wrap; never a PNG/front-projection replacement"
            ),
        },
        "mesh_doctor": {
            "status": mesh_doctor_status,
            "audit": asdict(mesh_doctor_audit) if mesh_doctor_audit is not None else None,
            "result": asdict(mesh_doctor_result) if mesh_doctor_result is not None else None,
            "failure": mesh_doctor_failure,
            "won_final_arena": champion.backend == "mesh_doctor_repair",
        },
        "retopology": {
            "status": retopo_status,
            "result": asdict(retopo_result) if retopo_result is not None else None,
            "failure": retopo_failure,
            "won_final_arena": champion.backend == "instant_meshes_retopo",
        },
        "texture_superres": {
            "mode": args.texture_superres,
            "status": texture_superres_status,
            "result": (
                asdict(texture_superres_result)
                if texture_superres_result is not None else None
            ),
            "failure": texture_superres_failure,
            "won_final_arena": champion.backend.endswith("_texture_sr"),
            "policy": "baseColor-only GLB payload rewrite; original candidate preserved; challenger must win complete Judge",
        },
        "semantic_anatomy": (
            asdict(semantic_anatomy_result)
            if semantic_anatomy_result is not None else None
        ),
        "semantic_anatomy_failure": semantic_anatomy_failure,
        "geometry_refinement": asdict(refinement_decision) if refinement_decision is not None else None,
        "geometry_refinement_failure": refinement_failure,
        "material_bridge": asdict(material_bridge_result) if material_bridge_result is not None else None,
        "material_bridge_failure": material_bridge_failure,
        "ranking": ranking_data,
        "composite_champion": (
            asdict(composite_plan)
            if composite_plan is not None else None
        ),
        "composite_champion_failure": composite_plan_failure,
        "composite_execution": (
            asdict(composite_execution)
            if composite_execution is not None else None
        ),
        "composite_head_execution": (
            asdict(composite_head_execution)
            if composite_head_execution is not None else None
        ),
        "composite_local_executions": [
            asdict(item)
            for item in composite_local_executions
        ],
        "composite_executions": [
            *[
                asdict(item)
                for item in (composite_execution, composite_head_execution)
                if item is not None
            ],
            *[
                asdict(item)
                for item in composite_local_executions
            ],
        ],
        "champion": asdict(champion),
        "final_glb": str(final_glb),
        "gameprep": asdict(gameprep_result) if gameprep_result is not None else None,
        "gameprep_failure": gameprep_failure,
        "portable_pack": asdict(portable_pack_result) if portable_pack_result is not None else None,
        "portable_pack_failure": portable_pack_failure,
        "qa_package": asdict(qa_package_result) if qa_package_result is not None else None,
        "qa_package_failure": qa_package_failure,
        "judge_v4": (
            asdict(judge_v4_result)
            if judge_v4_result is not None else None
        ),
        "judge_v4_failure": judge_v4_failure,
        "judge_v5": (
            asdict(judge_v5_result)
            if judge_v5_result is not None else None
        ),
        "judge_v5_failure": judge_v5_failure,
        "visual_approval": {
            "schema": 2,
            "production_approved": bool(
                judge_v5_result is not None
                and judge_v5_result.passed
                and judge_v5_result.status=="APPROVED"
            ),
            "state": (
                judge_v5_result.status
                if judge_v5_result is not None
                else (
                    "NOT_APPLICABLE"
                    if mode!="character"
                    else "NOT_EVALUATED"
                )
            ),
            "authoritative_judge": "HAYUYA_JUDGE_V5",
            "fail_closed": True,
        },
        "notes": [
            "Single-photo-first: one ordinary source photo is sufficient; HAYUYA automatically derives face/head zoom evidence when possible and never requires a manual close-up.",
            "Derived source-autofix crops are auxiliary evidence tied to the original photo and never count as independent real references.",
            "The reference pool has no Hayuya-level photo-count cap.",
            "All unique full-object/geometry source photos participate in Judge v2.",
            "Detail/close-up sources stay out of whole-object silhouette scoring but enter Judge v3 through multi-view local patch retrieval when DINOv2 is active.",
            "Multi-image backends receive grouped real geometry references when one call should be bounded for VRAM/practicality.",
            "Monster/Ultra multi-anchor mode can generate TripoSG hypotheses from every source unless the user explicitly sets a budget.",
            "A one-photo job can add a TRELLIS fusion candidate from the real anchor plus Wonder3D RGB/normal ViewForge coverage; synthetic RGB views never enter the real-source Judge.",
            "Wonder3D normal maps may contribute a deliberately small 6% synthetic-support score using the pinned front-view normal coordinate convention.",
            "TripoSF can challenge the best geometry seed at 1024^3 in Monster/Ultra; it must pass real-source geometry evidence.",
            "If TripoSF wins geometry, Material Bridge v2 reprojects packed PBR UV/material evidence when available (base-color fallback otherwise) and the bridged GLB re-enters the final Judge rather than being auto-promoted.",
            "Mesh Doctor audits the provisional champion before retopology; conservative structural repairs are material-restored and must win the same Judge, while tiny disconnected components are audit-only to protect intentional accessories.",
            "Instant Meshes retopology is an optional deterministic challenger: editable quad/quad-dominant OBJ is preserved, Material Bridge v2 restores runtime material evidence, and the bridged GLB must win the same Judge.",
            "Monster/Ultra may add one Real-ESRGAN baseColor-only super-resolution challenger when the provisional champion is below the native texture target; geometry/skin/animation buffers are preserved and the refined GLB must win the complete Judge.",
            "GamePrep audits glTF rig/skin state first; skinned assets skip destructive retopology/LOD simplification and preserve exact master/LOD0 until skin-weight transfer exists.",
            "QA Package v1 records geometry/material/reference/rig/GamePrep readiness and creates a source-vs-turntable contact sheet.",
            "Mobile portability is resolved from the versioned HAYUYA knowledge base; the source-faithful Hero Master is preserved while GamePrep derives tier-budget LODs and texture ceilings.",
            "Portable Pack derives Flagship, High, Balanced and Compatibility independently from the same Hero Master; lower tiers never become the source for higher tiers.",
            "Judge v2 combines production mesh health with source-image silhouette agreement.",
            "Judge v3 remains a candidate-ranking signal; Monster/Ultra character promotion is now vetoed when face-quality evidence or gross head structure is incomplete.",
            "Judge v4 is the fail-closed final visual acceptance layer for Monster/Ultra characters: 24 fixed turntable views, Q-ReAlign-Pro-9B quality scoring, MediaPipe dense face geometry, DreamSim reference similarity and two order-swapped InternVL3.5 visual critiques. No weighted average can rescue a critical V4 failure.",
            "Composite Champion Planner keeps the strongest global finalist as the canonical base, records regional winners across face identity/geometry/texel/detail/material/appearance, and never overwrites originals.",
            "Regional transfers are promotion-gated challengers: unsafe face/body geometry stays deferred until wrap/seam/skin-weight proof exists, while safer texture/material transfers can be attempted and must re-enter the complete Judge.",
            "Next judge stage adds normal/depth agreement, calibrated camera estimation and local-detail matching.",
        ],
    }
    aaa_acceptance_result = None
    aaa_acceptance_failure = None
    try:
        if qa_package_result is None:
            raise RuntimeError("QA Package missing; AAA acceptance cannot run")
        from aaa_acceptance import evaluate_aaa_acceptance, write_aaa_report
        qa_report_data=json.loads(
            Path(qa_package_result.report).read_text(encoding="utf-8")
        )
        aaa_acceptance_result=evaluate_aaa_acceptance(
            manifest,
            qa_report_data,
        )
        aaa_report_path=write_aaa_report(
            aaa_acceptance_result,
            job_dir / "aaa_acceptance.json",
        )
        manifest["aaa_acceptance"]=asdict(aaa_acceptance_result)
        manifest["aaa_acceptance_report"]=str(aaa_report_path)
        blocker_ids=[
            gate.id
            for gate in aaa_acceptance_result.gates
            if gate.required and not gate.ready
        ]
        print(
            "HAYUYA_AAA_READY "
            f"ready={str(bool(aaa_acceptance_result.ready)).lower()} "
            f"passed={aaa_acceptance_result.passed_required} "
            f"total={aaa_acceptance_result.total_required} "
            f"blockers={','.join(blocker_ids) if blocker_ids else 'none'} "
            f"report={aaa_report_path}"
        )
    except Exception as exc:
        aaa_acceptance_failure=f"{type(exc).__name__}: {exc}"
        manifest["aaa_acceptance"]=None
        manifest["aaa_acceptance_failure"]=aaa_acceptance_failure
        print(
            f"HAYUYA_AAA_FAILED {aaa_acceptance_failure}",
            file=sys.stderr,
        )
        traceback.print_exc()

    (job_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"HAYUYA_MONSTER_READY {final_glb}")
    print(
        f"HAYUYA_CHAMPION backend={champion.backend} score={champion.score} "
        f"references={len(inputs)} geometry_refs={len(geometry_inputs)} "
        f"detail_refs={len(detail_inputs)} candidates={len(candidates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
