#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# These generators are reconstruction aids, not authoritative native 3D.
# They may produce useful diagnostics or repair evidence, but HAYUYA 3D must
# never present them as an approved Monster/Ultra Hero Master.
DIAGNOSTIC_ONLY_GENERATORS = {
    "microsoft/TRELLIS.2-preview-recovery",
    "microsoft/TRELLIS.2-preview-normal-hero",
}


@dataclass(frozen=True)
class AAAEligibility:
    eligible: bool
    generator: str
    reasons: tuple[str, ...]
    diagnostic_only: bool


def assess_aaa_candidate(
    *,
    generator: str | None,
    hero_master: dict[str, Any] | None,
    texture_quality: str,
) -> AAAEligibility:
    name = str(generator or "").strip()
    quality = str(texture_quality or "").strip().lower()
    report = hero_master or {}
    reasons: list[str] = []

    diagnostic_only = name in DIAGNOSTIC_ONLY_GENERATORS
    if diagnostic_only:
        reasons.append("preview_reconstruction_is_diagnostic_only")

    # High/Ultra are the user-facing quality tiers where a provider-capped or
    # explicitly provisional mesh must not masquerade as an AAA final.
    if quality in {"high", "ultra"}:
        if report.get("provider_capped") is True:
            reasons.append("provider_capped_geometry_requires_native_replacement")
        if report.get("refinement_required") is True:
            reasons.append("required_geometry_refinement_not_resolved")
        if report.get("dense_master_ready") is False:
            reasons.append("dense_master_not_ready")

    # Ultra keeps the 2M-class target but does not approve on polygon count.
    # A native/refined candidate may be under the nominal target and still reach
    # Judge; a preview-derived candidate never can.
    if quality == "ultra" and report.get("native_latent_extraction") is False:
        reasons.append("native_or_model_generated_geometry_required")

    # Stable unique ordering makes CI output deterministic.
    unique = tuple(dict.fromkeys(reasons))
    return AAAEligibility(
        eligible=not unique,
        generator=name,
        reasons=unique,
        diagnostic_only=diagnostic_only,
    )
