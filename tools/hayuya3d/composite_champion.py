#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class RegionalMetric:
    region: str
    metric: str
    strategy: str
    seam_risk: str
    rig_risk: str
    destructive: bool


@dataclass
class RegionalDonor:
    region: str
    metric: str
    base_backend: str
    donor_backend: str
    base_score: float | None
    donor_score: float | None
    improvement: float | None
    strategy: str
    seam_risk: str
    rig_risk: str
    destructive: bool
    requires_rejudge: bool = True


@dataclass
class DetailDonor:
    source: str
    region_hint: str | None
    base_backend: str
    donor_backend: str
    base_score: float | None
    donor_score: float
    improvement: float | None
    strategy: str
    seam_risk: str
    rig_risk: str
    accessory_match: dict | None = None
    requires_rejudge: bool = True


@dataclass
class FinalistSummary:
    backend: str
    path: str
    global_score: float
    valid: bool
    production_score: float | None
    visual_score: float | None
    appearance_score: float | None
    face_score: float | None
    face_min_score: float | None
    head_density_score: float | None
    head_texel_density_score: float | None
    head_texture_detail_score: float | None
    material_score: float | None
    texture_resolution_score: float | None
    appearance_details: list[dict] | None = None
    up_axis: str | None = None
    accessory_components: int | None = None


@dataclass
class CompositeExecutionResult:
    attempted: bool
    ready: bool
    base_backend: str
    donor_backend: str | None
    candidate_label: str | None
    candidate_path: str | None
    region: str | None
    strategy: str | None
    geometry_preserved: bool
    rebake_required: list[str]
    runtime_payload_preserved: bool | None = None
    error: str | None = None
    method: str = "hayuya-composite-material-challenger-v1"


@dataclass
class HeadWrapExecutionResult:
    attempted: bool
    ready: bool
    base_backend: str
    donor_backend: str | None
    candidate_label: str | None
    candidate_path: str | None
    fusion: dict | None
    error: str | None = None
    method: str = "hayuya-composite-head-wrap-challenger-v1"


@dataclass
class LocalDetailExecutionResult:
    attempted: bool
    ready: bool
    base_backend: str
    donor_backend: str | None
    source: str | None
    region_hint: str | None
    candidate_label: str | None
    candidate_path: str | None
    fusion: dict | None
    error: str | None = None
    method: str = "hayuya-composite-local-detail-challenger-v1"


@dataclass
class CompositeChampionPlan:
    version: int
    mode: str
    base_backend: str
    base_path: str
    finalist_backends: list[str]
    finalists: list[FinalistSummary]
    donors: list[RegionalDonor]
    detail_donors: list[DetailDonor]
    composite_required: bool
    executable_now: list[str]
    deferred_transfers: list[str]
    promotion_contract: list[str]
    notes: list[str]
    method: str = "hayuya-composite-champion-planner-v1"


REGIONAL_METRICS: tuple[RegionalMetric, ...] = (
    RegionalMetric(
        "face_identity",
        "appearance_face_detail_min_score",
        "surface_wrap_plus_identity_texture_projection",
        "high",
        "high",
        True,
    ),
    RegionalMetric(
        "face_geometry",
        "head_density_score",
        "local_surface_wrap",
        "high",
        "high",
        True,
    ),
    RegionalMetric(
        "face_texel_budget",
        "head_texel_density_score",
        "uv_local_reallocation_or_texture_projection",
        "medium",
        "medium",
        True,
    ),
    RegionalMetric(
        "face_surface_detail",
        "head_texture_detail_score",
        "local_texture_detail_projection",
        "medium",
        "low",
        False,
    ),
    RegionalMetric(
        "global_shape",
        "visual_score",
        "retain_base_geometry",
        "low",
        "low",
        False,
    ),
    RegionalMetric(
        "global_appearance",
        "appearance_score",
        "material_and_texture_reference",
        "medium",
        "low",
        False,
    ),
    RegionalMetric(
        "material_response",
        "material_score",
        "material_projection_then_rebake",
        "medium",
        "low",
        False,
    ),
    RegionalMetric(
        "texture_resolution",
        "texture_resolution_score",
        "texture_challenger_reference",
        "low",
        "low",
        False,
    ),
)


def _finite(value: Any) -> float | None:
    try:
        value=float(value)
    except (TypeError,ValueError):
        return None
    return value if math.isfinite(value) else None


def _get(item: Any, name: str, default: Any=None) -> Any:
    if isinstance(item,dict):
        return item.get(name,default)
    return getattr(item,name,default)


def _summary(item: Any) -> FinalistSummary:
    views=_get(item,"visual_views") or []
    up_axis=None
    if views:
        first=views[0]
        if isinstance(first,dict):
            raw=first.get("best_up_axis")
        else:
            raw=getattr(first,"best_up_axis",None)
        if raw in {"x","y","z"}:
            up_axis=str(raw)
    return FinalistSummary(
        backend=str(_get(item,"backend","unknown")),
        path=str(_get(item,"path","")),
        global_score=float(_get(item,"score",0.0) or 0.0),
        valid=bool(_get(item,"valid",False)),
        production_score=_finite(_get(item,"production_score")),
        visual_score=_finite(_get(item,"visual_score")),
        appearance_score=_finite(_get(item,"appearance_score")),
        face_score=_finite(_get(item,"appearance_face_detail_score")),
        face_min_score=_finite(_get(item,"appearance_face_detail_min_score")),
        head_density_score=_finite(_get(item,"head_density_score")),
        head_texel_density_score=_finite(_get(item,"head_texel_density_score")),
        head_texture_detail_score=_finite(_get(item,"head_texture_detail_score")),
        material_score=_finite(_get(item,"material_score")),
        texture_resolution_score=_finite(_get(item,"texture_resolution_score")),
        appearance_details=[
            dict(detail)
            for detail in (_get(item,"appearance_details") or [])
            if isinstance(detail,dict)
        ] or None,
        up_axis=up_axis,
    )


def _metric_value(summary: FinalistSummary, metric: str) -> float | None:
    aliases={
        "appearance_face_detail_min_score":"face_min_score",
    }
    return _finite(getattr(summary,aliases.get(metric,metric),None))


def _best_donor(
    finalists: list[FinalistSummary],
    spec: RegionalMetric,
) -> FinalistSummary | None:
    eligible=[
        (value,item)
        for item in finalists
        if (value:=_metric_value(item,spec.metric)) is not None
    ]
    if not eligible:
        return None
    return max(eligible,key=lambda pair:(pair[0],pair[1].global_score))[1]


def _improvement(base: float | None, donor: float | None) -> float | None:
    if donor is None:
        return None
    if base is None:
        return donor
    return donor-base


def _detail_map(summary: FinalistSummary) -> dict[str,dict]:
    out={}
    for detail in summary.appearance_details or []:
        source=str(detail.get("source") or "")
        score=_finite(detail.get("score"))
        if not source or score is None:
            continue
        out[source]={
            "score":score,
            "region_hint":(
                str(detail.get("region_hint"))
                if detail.get("region_hint") is not None else None
            ),
        }
    return out


def _detail_strategy(region_hint: str | None) -> tuple[str,str,str]:
    region=str(region_hint or "local").lower()
    if region=="head":
        return ("local_face_texture_projection","medium","low")
    if region in {"middle","lower"}:
        return ("local_body_texture_projection","medium","low")
    return ("local_detail_surface_projection","medium","low")


def _part_map_accessory_count(
    path: str,
    mode: str,
    up_axis: str | None=None,
) -> int | None:
    if not path or mode not in {"character","prop","architecture"}:
        return None
    try:
        from part_map import build_part_map
        result=build_part_map(
            Path(path),
            mode=mode,
            up_axis=(up_axis if up_axis in {"x","y","z"} else "y"),
        )
        return len(result.accessory_component_ids)
    except Exception:
        return None


def build_composite_plan(
    ranked: Iterable[Any],
    *,
    mode: str,
    max_finalists: int=5,
    minimum_regional_gain: float=0.5,
    inspect_parts: bool=True,
) -> CompositeChampionPlan:
    valid=[item for item in ranked if bool(_get(item,"valid",False))]
    if not valid:
        raise ValueError("composite planning requires at least one valid finalist")

    finalists=[_summary(item) for item in valid[:max(1,int(max_finalists))]]
    base=finalists[0]

    if inspect_parts:
        for item in finalists:
            item.accessory_components=_part_map_accessory_count(
                item.path,
                mode,
                item.up_axis,
            )

    donors: list[RegionalDonor]=[]
    for spec in REGIONAL_METRICS:
        donor=_best_donor(finalists,spec)
        if donor is None:
            continue
        base_value=_metric_value(base,spec.metric)
        donor_value=_metric_value(donor,spec.metric)
        gain=_improvement(base_value,donor_value)

        # Always record the region winner. A donor only requests a composite when
        # it differs from the base and provides meaningful or previously missing evidence.
        donors.append(RegionalDonor(
            region=spec.region,
            metric=spec.metric,
            base_backend=base.backend,
            donor_backend=donor.backend,
            base_score=base_value,
            donor_score=donor_value,
            improvement=round(gain,3) if gain is not None else None,
            strategy=spec.strategy,
            seam_risk=spec.seam_risk,
            rig_risk=spec.rig_risk,
            destructive=spec.destructive,
        ))

    detail_donors: list[DetailDonor]=[]
    detail_sources=sorted({
        source
        for finalist in finalists
        for source in _detail_map(finalist)
    })
    base_details=_detail_map(base)
    for source in detail_sources:
        candidates=[]
        for finalist in finalists:
            item=_detail_map(finalist).get(source)
            if item is None:
                continue
            candidates.append((
                float(item["score"]),
                finalist.global_score,
                finalist,
                item,
            ))
        if not candidates:
            continue
        _,_,winner,winner_item=max(
            candidates,
            key=lambda row:(row[0],row[1]),
        )
        base_item=base_details.get(source)
        base_score=(
            float(base_item["score"])
            if base_item is not None else None
        )
        donor_score=float(winner_item["score"])
        gain=_improvement(base_score,donor_score)
        strategy,seam_risk,rig_risk=_detail_strategy(
            winner_item.get("region_hint")
        )
        accessory_match_data=None
        if (
            inspect_parts
            and winner.backend!=base.backend
            and str(winner_item.get("region_hint") or "").lower()=="local"
        ):
            try:
                from accessory_match import match_accessories
                match_report=match_accessories(
                    Path(base.path),
                    Path(winner.path),
                    mode=mode,
                    base_up_axis=(
                        base.up_axis
                        if base.up_axis in {"x","y","z"}
                        else "y"
                    ),
                    donor_up_axis=(
                        winner.up_axis
                        if winner.up_axis in {"x","y","z"}
                        else None
                    ),
                )
                accessory_match_data=asdict(match_report)
                if match_report.ready:
                    strategy="matched_detached_accessory_swap_then_mesh_doctor"
                    seam_risk="low"
                    rig_risk=("high" if mode=="character" else "low")
                    if mode=="character":
                        try:
                            from gltf_audit import audit_glb
                            base_runtime=audit_glb(Path(base.path))
                            if (
                                base_runtime.skin_count>0
                                or base_runtime.skinned_mesh_nodes>0
                            ):
                                from rigged_accessory_wrap import (
                                    rigged_accessory_wrap_supported,
                                )
                                supported,blocker=(
                                    rigged_accessory_wrap_supported(
                                        Path(base.path)
                                    )
                                )
                                accessory_match_data[
                                    "rigged_wrap_supported"
                                ]=bool(supported)
                                accessory_match_data[
                                    "rigged_wrap_blocker"
                                ]=blocker
                                if supported:
                                    strategy=(
                                        "matched_rig_preserving_"
                                        "accessory_wrap_then_rebake"
                                    )
                                    rig_risk="low"
                        except Exception as exc:
                            accessory_match_data[
                                "rigged_wrap_supported"
                            ]=False
                            accessory_match_data[
                                "rigged_wrap_blocker"
                            ]=(
                                f"{type(exc).__name__}:{exc}"
                            )
                elif (
                    mode=="character"
                    and int(match_report.base_accessories)==0
                    and int(match_report.donor_accessories)>=1
                ):
                    try:
                        from rigged_accessory_insert import (
                            rigged_accessory_insert_supported,
                        )
                        supported,blocker=rigged_accessory_insert_supported(
                            Path(base.path),
                            Path(winner.path),
                            base_up_axis=(
                                base.up_axis
                                if base.up_axis in {"x","y","z"}
                                else "y"
                            ),
                            donor_up_axis=(
                                winner.up_axis
                                if winner.up_axis in {"x","y","z"}
                                else None
                            ),
                        )
                        accessory_match_data[
                            "rigged_insert_supported"
                        ]=bool(supported)
                        accessory_match_data[
                            "rigged_insert_blocker"
                        ]=blocker
                        if supported:
                            strategy=(
                                "new_rigged_accessory_insert_"
                                "weight_morph_transfer"
                            )
                            seam_risk="low"
                            rig_risk="medium"
                            material_ready=False
                            material_blocker=(
                                "donor UV/material transfer is not proven"
                            )
                            try:
                                from accessory_material_transfer import (
                                    accessory_material_transfer_supported,
                                )
                                (
                                    material_ready,
                                    material_blocker,
                                )=accessory_material_transfer_supported(
                                    Path(winner.path),
                                    up_axis=(
                                        winner.up_axis
                                        if winner.up_axis in {"x","y","z"}
                                        else "y"
                                    ),
                                )
                            except Exception as material_exc:
                                material_ready=False
                                material_blocker=(
                                    f"{type(material_exc).__name__}:"
                                    f"{material_exc}"
                                )
                            accessory_match_data[
                                "rigged_insert_material_ready"
                            ]=bool(material_ready)
                            accessory_match_data[
                                "rigged_insert_production_blocker"
                            ]=material_blocker
                    except Exception as exc:
                        accessory_match_data[
                            "rigged_insert_supported"
                        ]=False
                        accessory_match_data[
                            "rigged_insert_blocker"
                        ]=f"{type(exc).__name__}:{exc}"
            except Exception as exc:
                accessory_match_data={
                    "ready":False,
                    "error":f"{type(exc).__name__}:{exc}",
                }

        detail_donors.append(DetailDonor(
            source=source,
            region_hint=winner_item.get("region_hint"),
            base_backend=base.backend,
            donor_backend=winner.backend,
            base_score=base_score,
            donor_score=donor_score,
            improvement=round(gain,3) if gain is not None else None,
            strategy=strategy,
            seam_risk=seam_risk,
            rig_risk=rig_risk,
            accessory_match=accessory_match_data,
        ))

    meaningful_detail=[
        item for item in detail_donors
        if item.donor_backend!=base.backend
        and (
            item.base_score is None
            or item.improvement is None
            or item.improvement>=minimum_regional_gain
        )
    ]

    meaningful=[
        d for d in donors
        if d.donor_backend!=base.backend
        and (
            d.base_score is None
            or d.improvement is None
            or d.improvement>=minimum_regional_gain
        )
    ]
    # Implemented Composite challengers:
    # - material_response: topology-preserving Material Bridge projection.
    # - face_identity: seam-aware head wrap with rig/skin preservation gates.
    # - detail:<source>: baseColor-only semantic fusion for localized
    #   head/middle/lower references, one donor/reference per challenger pass.
    executable_detail={
        "detail:"+item.source
        for item in meaningful_detail
        if (
            str(item.region_hint or "").lower() in {"head","middle","lower"}
            or (
                (
                    mode!="character"
                    and item.strategy=="matched_detached_accessory_swap_then_mesh_doctor"
                )
                or (
                    mode=="character"
                    and item.strategy=="matched_rig_preserving_accessory_wrap_then_rebake"
                )
            )
            and bool((item.accessory_match or {}).get("ready"))
            or (
                mode=="character"
                and item.strategy=="new_rigged_accessory_insert_weight_morph_transfer"
                and bool(
                    (item.accessory_match or {}).get(
                        "rigged_insert_supported"
                    )
                )
                and bool(
                    (item.accessory_match or {}).get(
                        "rigged_insert_material_ready"
                    )
                )
            )
        )
    }
    executable_now=sorted({
        d.region for d in meaningful
        if (
            d.strategy=="material_projection_then_rebake"
            or d.region=="face_identity"
        )
    } | executable_detail)
    deferred=sorted({
        d.region for d in meaningful
        if d.region not in executable_now
    } | {
        "detail:"+item.source
        for item in meaningful_detail
        if "detail:"+item.source not in executable_detail
    })

    return CompositeChampionPlan(
        version=1,
        mode=mode,
        base_backend=base.backend,
        base_path=base.path,
        finalist_backends=[x.backend for x in finalists],
        finalists=finalists,
        donors=donors,
        detail_donors=detail_donors,
        composite_required=bool(meaningful or meaningful_detail),
        executable_now=executable_now,
        deferred_transfers=deferred,
        promotion_contract=[
            "composite must re-enter the complete real-source Judge arena",
            "global score must not regress against the base champion",
            "weakest face-reference score must not regress when face evidence exists",
            "FaceMesh, FaceTex and FaceDetail evidence must remain complete for characters",
            "geometry/topology must pass Mesh Doctor after any geometry transfer",
            "detached accessory/donor components must pass Composite Attachment QA and remain reachable from the canonical base",
            "normal and occlusion must be rebaked after geometry, topology or UV changes",
            "rig/skin/animation must remain valid for skinned characters",
            "source-vs-turntable QA must pass after fusion",
            "no original finalist is overwritten; composite is always a challenger",
        ],
        notes=[
            "The base finalist supplies the canonical coordinate system and continuity.",
            "Regional donors are evidence sources, not unconditional copy/paste instructions.",
            "Every explicit local/detail reference gets its own donor winner so scars, hands, jewelry, wounds and clothing details cannot disappear inside an aggregate score.",
            "Detached accessory candidates are never chosen by component count alone; local accessory donors need explicit reference superiority plus non-ambiguous spatial/attachment correspondence.",
            "Multi-piece chains, rosaries, medals and loose detail may remain disconnected meshes, but their proximity graph must stay anchored to the canonical base instead of becoming floating donor islands.",
            "Existing skinned accessory topology may be reshaped through the rig-preserving wrap path; missing accessories may be inserted as one primitive/atlas or as a proven anchored multi-piece source-group cluster, but Composite promotion requires exact barycentric skin+morph transfer plus complete donor UV/PBR/tangent and runtime QA for every inserted primitive.",
            "High-risk body/face geometry transfers stay deferred until wrap/seam/skin-weight proof exists.",
            "Texture/material transfers can be attempted earlier because they preserve base topology.",
            "Every fusion is atomic: rejection restores the untouched base champion.",
        ],
    )


def execute_safe_accessory_challenger(
    plan: CompositeChampionPlan,
    out_dir: Path,
    *,
    detail_source: str | None=None,
    texture_size: int=4096,
) -> LocalDetailExecutionResult:
    donor=None
    for item in plan.detail_donors:
        token="detail:"+item.source
        if token not in plan.executable_now:
            continue
        if detail_source is not None and item.source!=detail_source:
            continue
        if item.donor_backend==plan.base_backend:
            continue
        if item.strategy not in {
            "matched_detached_accessory_swap_then_mesh_doctor",
            "matched_rig_preserving_accessory_wrap_then_rebake",
            "new_rigged_accessory_insert_weight_morph_transfer",
        }:
            continue
        proof=item.accessory_match or {}
        if (
            item.strategy=="new_rigged_accessory_insert_weight_morph_transfer"
            and not bool(proof.get("rigged_insert_supported"))
        ):
            continue
        if (
            item.strategy!="new_rigged_accessory_insert_weight_morph_transfer"
            and not bool(proof.get("ready"))
        ):
            continue
        donor=item
        break

    if donor is None:
        deferred_error=None
        if plan.mode=="character":
            for item in plan.detail_donors:
                if detail_source is not None and item.source!=detail_source:
                    continue
                if (
                    item.strategy=="new_rigged_accessory_insert_weight_morph_transfer"
                    and bool(
                        (item.accessory_match or {}).get(
                            "rigged_insert_supported"
                        )
                    )
                ):
                    deferred_error=(
                        "new-vertex character accessory has geometry/runtime "
                        "skin+morph proof but remains deferred until donor "
                        "UV/material transfer is proven"
                    )
                    break
                if (
                    item.strategy=="matched_detached_accessory_swap_then_mesh_doctor"
                    and bool((item.accessory_match or {}).get("ready"))
                ):
                    deferred_error=(
                        "character accessory geometry remains deferred unless "
                        "the base has a proven topology-preserving rigged wrap; "
                        "brand-new/replaced topology requires explicit skin-weight "
                        "and morph transfer"
                    )
                    break
        return LocalDetailExecutionResult(
            attempted=False,
            ready=False,
            base_backend=plan.base_backend,
            donor_backend=None,
            source=detail_source,
            region_hint="local",
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error=deferred_error,
        )

    by_backend={item.backend:item for item in plan.finalists}
    base=by_backend.get(plan.base_backend)
    source=by_backend.get(donor.donor_backend)
    if base is None or source is None:
        return LocalDetailExecutionResult(
            attempted=True,
            ready=False,
            base_backend=plan.base_backend,
            donor_backend=donor.donor_backend,
            source=donor.source,
            region_hint="local",
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error="base or accessory donor finalist metadata missing",
        )

    try:
        safe_backend="".join(
            ch if ch.isalnum() or ch in {"-","_"} else "_"
            for ch in source.backend
        )
        safe_source="".join(
            ch if ch.isalnum() or ch in {"-","_"} else "_"
            for ch in Path(donor.source).stem
        )[:48] or "accessory"
        out_dir.mkdir(parents=True,exist_ok=True)
        output=out_dir/f"composite_accessory_{safe_backend}_{safe_source}.glb"
        if donor.strategy=="matched_rig_preserving_accessory_wrap_then_rebake":
            from rigged_accessory_wrap import (
                prepare_rigged_accessory_challenger,
            )
            swap=prepare_rigged_accessory_challenger(
                Path(base.path),
                Path(source.path),
                out_dir/f"rigged_{safe_backend}_{safe_source}",
                texture_size=int(texture_size),
                base_up_axis=(
                    base.up_axis
                    if base.up_axis in {"x","y","z"} else "y"
                ),
                donor_up_axis=(
                    source.up_axis
                    if source.up_axis in {"x","y","z"} else None
                ),
            )
            output=Path(swap.output_glb)
        elif donor.strategy=="new_rigged_accessory_insert_weight_morph_transfer":
            from rigged_accessory_insert import (
                prepare_production_rigged_accessory_insert,
            )
            swap=prepare_production_rigged_accessory_insert(
                Path(base.path),
                Path(source.path),
                out_dir/f"insert_{safe_backend}_{safe_source}",
                base_up_axis=(
                    base.up_axis
                    if base.up_axis in {"x","y","z"} else "y"
                ),
                donor_up_axis=(
                    source.up_axis
                    if source.up_axis in {"x","y","z"} else None
                ),
            )
            output=Path(swap.output_glb)
        else:
            from accessory_swap import swap_detached_accessory
            swap=swap_detached_accessory(
                Path(base.path),
                Path(source.path),
                output,
                mode=plan.mode,
                base_up_axis=(
                    base.up_axis
                    if base.up_axis in {"x","y","z"} else "y"
                ),
                donor_up_axis=(
                    source.up_axis
                    if source.up_axis in {"x","y","z"} else None
                ),
            )
        swap_data=asdict(swap)
        if (
            donor.strategy=="new_rigged_accessory_insert_weight_morph_transfer"
            and not bool(getattr(swap,"production_ready",False))
        ):
            return LocalDetailExecutionResult(
                attempted=True,
                ready=False,
                base_backend=base.backend,
                donor_backend=source.backend,
                source=donor.source,
                region_hint="local",
                candidate_label=None,
                candidate_path=str(output) if output.exists() else None,
                fusion=swap_data,
                error=(
                    "new-vertex accessory geometry/runtime proof is not "
                    "production-ready: donor UV/material transfer unproven"
                ),
            )
        if not swap.ready:
            return LocalDetailExecutionResult(
                attempted=True,
                ready=False,
                base_backend=base.backend,
                donor_backend=source.backend,
                source=donor.source,
                region_hint="local",
                candidate_label=None,
                candidate_path=str(output) if output.exists() else None,
                fusion=swap_data,
                error=(
                    ";".join(swap.errors)
                    if swap.errors else
                    "accessory swap is not Judge-eligible"
                ),
            )
        label=f"composite_accessory_{safe_backend}_{safe_source}"
        return LocalDetailExecutionResult(
            attempted=True,
            ready=True,
            base_backend=base.backend,
            donor_backend=source.backend,
            source=donor.source,
            region_hint="local",
            candidate_label=label,
            candidate_path=str(output),
            fusion=swap_data,
            error=None,
        )
    except Exception as exc:
        return LocalDetailExecutionResult(
            attempted=True,
            ready=False,
            base_backend=base.backend,
            donor_backend=source.backend,
            source=donor.source,
            region_hint="local",
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error=f"{type(exc).__name__}:{exc}",
        )


def execute_safe_local_detail_challenger(
    plan: CompositeChampionPlan,
    out_dir: Path,
    *,
    detail_source: str | None=None,
    donor_samples: int=60_000,
) -> LocalDetailExecutionResult:
    executable={
        item
        for item in plan.executable_now
        if item.startswith("detail:")
    }
    donor=None
    for item in plan.detail_donors:
        token="detail:"+item.source
        if token not in executable:
            continue
        if detail_source is not None and item.source!=detail_source:
            continue
        if item.donor_backend==plan.base_backend:
            continue
        donor=item
        break

    if donor is None:
        return LocalDetailExecutionResult(
            attempted=False,
            ready=False,
            base_backend=plan.base_backend,
            donor_backend=None,
            source=detail_source,
            region_hint=None,
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error=None,
        )

    by_backend={item.backend:item for item in plan.finalists}
    base=by_backend.get(plan.base_backend)
    source=by_backend.get(donor.donor_backend)
    if base is None or source is None:
        return LocalDetailExecutionResult(
            attempted=True,
            ready=False,
            base_backend=plan.base_backend,
            donor_backend=donor.donor_backend,
            source=donor.source,
            region_hint=donor.region_hint,
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error="base or local-detail donor finalist metadata missing",
        )

    region=str(donor.region_hint or "").lower()
    if region not in {"head","middle","lower"}:
        return LocalDetailExecutionResult(
            attempted=False,
            ready=False,
            base_backend=base.backend,
            donor_backend=source.backend,
            source=donor.source,
            region_hint=donor.region_hint,
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error=f"detail region {donor.region_hint!r} is not executable",
        )

    try:
        from local_detail_fusion import fuse_local_basecolor
        safe_backend="".join(
            ch if ch.isalnum() or ch in {"-","_"} else "_"
            for ch in source.backend
        )
        safe_source="".join(
            ch if ch.isalnum() or ch in {"-","_"} else "_"
            for ch in Path(donor.source).stem
        )[:48] or "detail"
        out_dir.mkdir(parents=True,exist_ok=True)
        output=out_dir/f"composite_detail_{region}_{safe_backend}_{safe_source}.glb"
        fusion=fuse_local_basecolor(
            Path(base.path),
            Path(source.path),
            output,
            region=region,
            up_axis=base.up_axis or source.up_axis or "y",
            donor_samples=int(donor_samples),
        )
        fusion_data=asdict(fusion)
        if not fusion.ready:
            return LocalDetailExecutionResult(
                attempted=True,
                ready=False,
                base_backend=base.backend,
                donor_backend=source.backend,
                source=donor.source,
                region_hint=region,
                candidate_label=None,
                candidate_path=str(output) if output.exists() else None,
                fusion=fusion_data,
                error=fusion.error or "local detail fusion is not Judge-eligible",
            )
        label=f"composite_detail_{region}_{safe_backend}_{safe_source}"
        return LocalDetailExecutionResult(
            attempted=True,
            ready=True,
            base_backend=base.backend,
            donor_backend=source.backend,
            source=donor.source,
            region_hint=region,
            candidate_label=label,
            candidate_path=str(output),
            fusion=fusion_data,
            error=None,
        )
    except Exception as exc:
        return LocalDetailExecutionResult(
            attempted=True,
            ready=False,
            base_backend=base.backend,
            donor_backend=source.backend,
            source=donor.source,
            region_hint=region,
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error=f"{type(exc).__name__}:{exc}",
        )


def execute_safe_head_wrap_challenger(
    plan: CompositeChampionPlan,
    out_dir: Path,
    *,
    texture_size: int,
    blender: str | Path | None=None,
) -> HeadWrapExecutionResult:
    donor=next(
        (
            item for item in plan.donors
            if item.region=="face_identity"
            and item.donor_backend!=plan.base_backend
            and item.region in plan.executable_now
        ),
        None,
    )
    if donor is None:
        return HeadWrapExecutionResult(
            attempted=False,
            ready=False,
            base_backend=plan.base_backend,
            donor_backend=None,
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error=None,
        )

    by_backend={item.backend:item for item in plan.finalists}
    base=by_backend.get(plan.base_backend)
    source=by_backend.get(donor.donor_backend)
    if base is None or source is None:
        return HeadWrapExecutionResult(
            attempted=True,
            ready=False,
            base_backend=plan.base_backend,
            donor_backend=donor.donor_backend,
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error="base or face donor finalist metadata missing",
        )

    try:
        from regional_fusion import prepare_head_wrap_challenger
        fusion=prepare_head_wrap_challenger(
            Path(base.path),
            Path(source.path),
            out_dir,
            texture_size=int(texture_size),
            blender=blender,
            require_rebake=True,
            up_axis=base.up_axis or source.up_axis,
        )
        fusion_data=asdict(fusion)
        if not fusion.ready_for_judge:
            return HeadWrapExecutionResult(
                attempted=bool(fusion.attempted),
                ready=False,
                base_backend=base.backend,
                donor_backend=source.backend,
                candidate_label=None,
                candidate_path=fusion.output_glb,
                fusion=fusion_data,
                error=fusion.error or "head wrap is not Judge-eligible",
            )
        safe_name="".join(
            ch if ch.isalnum() or ch in {"-","_"} else "_"
            for ch in source.backend
        )
        label=f"composite_head_{safe_name}"
        return HeadWrapExecutionResult(
            attempted=True,
            ready=True,
            base_backend=base.backend,
            donor_backend=source.backend,
            candidate_label=label,
            candidate_path=fusion.output_glb,
            fusion=fusion_data,
            error=None,
        )
    except Exception as exc:
        return HeadWrapExecutionResult(
            attempted=True,
            ready=False,
            base_backend=base.backend,
            donor_backend=source.backend,
            candidate_label=None,
            candidate_path=None,
            fusion=None,
            error=f"{type(exc).__name__}:{exc}",
        )


def execute_safe_material_challenger(
    plan: CompositeChampionPlan,
    out_dir: Path,
    *,
    texture_size: int,
    total_samples: int=200_000,
) -> CompositeExecutionResult:
    """Project a stronger finalist material onto the untouched base topology.

    This is the first executable Composite Champion transfer because Material
    Bridge already has a topology-preserving path. The produced GLB is only a
    challenger; callers must re-run the complete Judge before promotion.
    """
    base_backend=plan.base_backend
    donor=next(
        (
            item for item in plan.donors
            if item.region=="material_response"
            and item.donor_backend!=base_backend
            and item.region in plan.executable_now
        ),
        None,
    )
    if donor is None:
        return CompositeExecutionResult(
            attempted=False,
            ready=False,
            base_backend=base_backend,
            donor_backend=None,
            candidate_label=None,
            candidate_path=None,
            region=None,
            strategy=None,
            geometry_preserved=True,
            rebake_required=[],
            error=None,
        )

    by_backend={item.backend:item for item in plan.finalists}
    base=by_backend.get(base_backend)
    source=by_backend.get(donor.donor_backend)
    if base is None or source is None:
        return CompositeExecutionResult(
            attempted=True,
            ready=False,
            base_backend=base_backend,
            donor_backend=donor.donor_backend,
            candidate_label=None,
            candidate_path=None,
            region=donor.region,
            strategy=donor.strategy,
            geometry_preserved=False,
            rebake_required=[],
            error="base or donor finalist metadata missing",
        )

    runtime_payload_preserved=None
    try:
        from material_bridge import transfer_best_material
        from qa import inspect_mesh

        safe_name="".join(
            ch if ch.isalnum() or ch in {"-","_"} else "_"
            for ch in donor.donor_backend
        )
        out_dir.mkdir(parents=True,exist_ok=True)
        output=out_dir/f"composite_material_{safe_name}.glb"
        bridge=transfer_best_material(
            Path(source.path),
            Path(base.path),
            output,
            total_samples=total_samples,
            max_texture_size=int(texture_size),
        )
        if not output.is_file() or output.read_bytes()[:4]!=b"glTF":
            raise RuntimeError("Material Bridge did not produce a valid GLB")

        runtime_payload_preserved=None
        from gltf_audit import audit_glb
        base_runtime=audit_glb(Path(base.path))
        runtime_required=bool(
            base_runtime.skin_count>0
            or base_runtime.animation_count>0
            or base_runtime.morph_target_count>0
        )
        if runtime_required:
            from gltf_position_patch import runtime_payload_signature
            output_runtime=audit_glb(output)
            runtime_payload_preserved=bool(
                output_runtime.skin_count==base_runtime.skin_count
                and output_runtime.joint_count==base_runtime.joint_count
                and output_runtime.animation_count==base_runtime.animation_count
                and output_runtime.morph_mesh_count==base_runtime.morph_mesh_count
                and output_runtime.morph_primitive_count==base_runtime.morph_primitive_count
                and output_runtime.morph_target_count==base_runtime.morph_target_count
                and output_runtime.morph_ready==base_runtime.morph_ready
                and runtime_payload_signature(output)
                    ==runtime_payload_signature(Path(base.path))
            )
            if not runtime_payload_preserved:
                raise RuntimeError(
                    "material-only composite changed protected runtime payload "
                    "(skin/animation/morph)"
                )

        base_mesh=inspect_mesh(
            Path(base.path),
            backend=base.backend,
            mode=plan.mode,
            target_faces=max(1,1),
        )
        composite_mesh=inspect_mesh(
            output,
            backend="composite_material",
            mode=plan.mode,
            target_faces=max(1,1),
        )
        geometry_preserved=bool(
            base_mesh.valid
            and composite_mesh.valid
            and base_mesh.vertices==composite_mesh.vertices
            and base_mesh.faces==composite_mesh.faces
            and base_mesh.components==composite_mesh.components
            and list(base_mesh.bbox or [])==list(composite_mesh.bbox or [])
        )
        if not geometry_preserved:
            raise RuntimeError(
                "material-only composite changed base geometry/topology"
            )

        label=f"composite_material_{safe_name}"
        return CompositeExecutionResult(
            attempted=True,
            ready=True,
            base_backend=base_backend,
            donor_backend=donor.donor_backend,
            candidate_label=label,
            candidate_path=str(output),
            region=donor.region,
            strategy=donor.strategy,
            geometry_preserved=True,
            rebake_required=list(bridge.rebake_required or []),
            runtime_payload_preserved=runtime_payload_preserved,
            error=None,
        )
    except Exception as exc:
        return CompositeExecutionResult(
            attempted=True,
            ready=False,
            base_backend=base_backend,
            donor_backend=donor.donor_backend,
            candidate_label=None,
            candidate_path=None,
            region=donor.region,
            strategy=donor.strategy,
            geometry_preserved=False,
            rebake_required=[],
            runtime_payload_preserved=runtime_payload_preserved,
            error=f"{type(exc).__name__}:{exc}",
        )


def write_composite_plan(plan: CompositeChampionPlan, path: Path) -> Path:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(asdict(plan),indent=2)+"\n",encoding="utf-8")
    return path


def main() -> int:
    import argparse

    parser=argparse.ArgumentParser(
        description="HAYUYA Composite Champion regional donor planner."
    )
    parser.add_argument("ranking_json",type=Path)
    parser.add_argument("--mode",choices=["prop","character","architecture"],required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--max-finalists",type=int,default=5)
    parser.add_argument("--no-part-inspection",action="store_true")
    args=parser.parse_args()

    ranking=json.loads(args.ranking_json.read_text(encoding="utf-8"))
    plan=build_composite_plan(
        ranking,
        mode=args.mode,
        max_finalists=args.max_finalists,
        inspect_parts=not args.no_part_inspection,
    )
    write_composite_plan(plan,args.output)
    print(json.dumps(asdict(plan),indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
