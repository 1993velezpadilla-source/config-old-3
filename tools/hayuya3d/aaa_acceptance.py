#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Any


@dataclass
class AAAGate:
    id: str
    category: str
    ready: bool
    required: bool
    evidence: str
    blocker: str | None=None


@dataclass
class AAAReadinessReport:
    version: int
    ready: bool
    passed_required: int
    total_required: int
    blockers: list[str]
    advisories: list[str]
    gates: list[AAAGate]
    method: str="hayuya-internal-aaa-acceptance-contract-v1"


def _finite(value:Any)->bool:
    try:
        return math.isfinite(float(value))
    except (TypeError,ValueError):
        return False


def _gate(
    gates:list[AAAGate],
    gate_id:str,
    category:str,
    ready:bool,
    evidence:str,
    *,
    required:bool=True,
    blocker:str|None=None,
)->None:
    gates.append(AAAGate(
        id=gate_id,
        category=category,
        ready=bool(ready),
        required=required,
        evidence=evidence,
        blocker=(blocker if required and not ready else None),
    ))


def evaluate_aaa_acceptance(
    manifest:dict,
    qa_report:dict,
)->AAAReadinessReport:
    """Evaluate HAYUYA's strict internal high-end acceptance contract.

    "AAA" here is an internal engineering bar, not an external certification.
    The contract is evidence-completeness-first: missing proof fails closed.
    Numeric aesthetic floors are intentionally not invented until calibrated on
    a larger real-asset corpus.
    """
    gates:list[AAAGate]=[]
    advisories:list[str]=[]

    mode=str(qa_report.get("mode") or manifest.get("mode") or "prop")
    profile=str(qa_report.get("profile") or manifest.get("profile") or "")
    high_end=profile in {"monster","ultra"}

    _gate(
        gates,"pipeline.success","pipeline",
        manifest.get("status")=="success",
        f"status={manifest.get('status')}",
        blocker="pipeline did not complete successfully",
    )

    geometry=qa_report.get("geometry") or {}
    structure=qa_report.get("structure") or {}
    geometry_integrity=bool(
        geometry.get("ready")
        and structure.get("valid")
        and structure.get("finite_vertices")
        and int(structure.get("duplicate_faces") or 0)==0
        and int(structure.get("degenerate_faces") or 0)==0
        and int(structure.get("nonmanifold_edges") or 0)==0
        and structure.get("winding_consistent")
    )
    _gate(
        gates,"geometry.integrity","geometry",geometry_integrity,
        "QA geometry + Mesh Doctor structural audit",
        blocker="geometry has unresolved structural defects",
    )
    crossing=qa_report.get("component_crossing") or {}
    _gate(
        gates,"geometry.surface_crossings","geometry",
        bool(crossing.get("ready")),
        (
            f"applicable={crossing.get('applicable')} "
            f"large_components={crossing.get('large_component_count')} "
            f"crossing_pairs={crossing.get('crossing_triangle_pairs')}"
        ),
        blocker=(
            "major disconnected surfaces interpenetrate or "
            "surface-crossing evidence is unavailable"
        ),
    )

    self_intersection=qa_report.get("self_intersection") or {}
    _gate(
        gates,"geometry.self_intersection","geometry",
        bool(self_intersection.get("ready")),
        (
            f"applicable={self_intersection.get('applicable')} "
            f"audited_components={self_intersection.get('audited_component_count')} "
            f"crossing_pairs={self_intersection.get('crossing_triangle_pairs')}"
        ),
        blocker=(
            "connected mesh surfaces self-intersect or "
            "self-intersection evidence is unavailable"
        ),
    )

    attachment=qa_report.get("composite_attachment") or {}
    _gate(
        gates,"geometry.composite_attachment","geometry",
        bool(
            attachment.get("applicable")
            and attachment.get("ready")
        ),
        (
            f"components={attachment.get('component_count')} "
            f"accessories={attachment.get('accessory_candidates')} "
            f"anchored={attachment.get('anchored_accessories')} "
            f"floating={attachment.get('floating_components')} "
            f"oversized_floating={attachment.get('oversized_floating_components')}"
        ),
        blocker=(
            "detached accessory or donor islands lack a coherent "
            "attachment path to the main asset"
        ),
    )

    source=qa_report.get("source_coverage") or {}
    source_ready=bool(
        int(source.get("judged") or 0)>=int(source.get("expected") or 0)
    )
    _gate(
        gates,"source.coverage","fidelity",source_ready,
        f"judged={source.get('judged')} expected={source.get('expected')}",
        blocker="not every real geometry source has Judge evidence",
    )

    turn=qa_report.get("turntable_qa")
    turn_ready=bool(
        int(source.get("expected") or 0)==0
        or (isinstance(turn,dict) and turn.get("ready"))
    )
    _gate(
        gates,"source.turntable","fidelity",turn_ready,
        "source-vs-turntable validation",
        blocker="final asset lacks passing multi-view source-vs-turntable proof",
    )

    material=qa_report.get("material") or {}
    channels=set(material.get("channels") or [])
    material_ready=bool(
        material.get("ready")
        and material.get("texture_resolution_ready")
        and material.get("rebake_ready")
    )
    _gate(
        gates,"material.readiness","materials",material_ready,
        f"channels={sorted(channels)} texture={material.get('base_color_min_edge')} target={material.get('target_texture_size')}",
        blocker="material/texture/rebake contract is incomplete",
    )

    uv_tangent=qa_report.get("uv_tangent") or {}
    _gate(
        gates,"material.uv_tangent","materials",
        bool(uv_tangent.get("ready")),
        (
            f"applicable={uv_tangent.get('applicable')} "
            f"missing_uv_primitives={uv_tangent.get('missing_uv_primitives')} "
            f"degenerate_uv_triangles={uv_tangent.get('degenerate_uv_triangles')} "
            f"invalid_tangent_primitives={uv_tangent.get('invalid_tangent_primitives')}"
        ),
        blocker=(
            "textured UV/tangent structural QA failed "
            "(missing/collapsed UVs or unusable tangent derivation)"
        ),
        required=high_end,
    )

    shading_basis=qa_report.get("shading_basis") or {}
    _gate(
        gates,"material.shading_basis","materials",
        bool(shading_basis.get("ready")),
        (
            f"applicable={shading_basis.get('applicable')} "
            f"missing_normals={shading_basis.get('missing_normals')} "
            f"missing_tangents={shading_basis.get('missing_required_tangents')} "
            f"bad_handedness={shading_basis.get('invalid_handedness')} "
            f"nonorthogonal={shading_basis.get('nonorthogonal_tangents')}"
        ),
        blocker=(
            "high-end normal-mapped asset lacks a valid explicit "
            "normal/tangent shading basis"
        ),
        required=bool(high_end and "normal" in channels),
    )

    if mode=="character" and high_end:
        visual_v4=manifest.get("judge_v4") or {}
        _gate(
            gates,"character.visual_judge_v4","character",
            bool(visual_v4.get("passed")),
            (
                f"passed={visual_v4.get('passed')} "
                f"hard_failures={len(visual_v4.get('hard_fail_reasons') or [])} "
                f"method={visual_v4.get('method')}"
            ),
            blocker=(
                "final high-end character failed or lacks fail-closed Judge v4 "
                "visual evidence"
            ),
        )
        visual_v5=manifest.get("judge_v5") or {}
        visual_approval=manifest.get("visual_approval") or {}
        v5_ready=bool(
            visual_v5.get("passed") is True
            and visual_v5.get("status")=="APPROVED"
            and visual_approval.get("production_approved") is True
        )
        _gate(
            gates,"character.visual_judge_v5","character",
            v5_ready,
            (
                f"status={visual_v5.get('status')} "
                f"passed={visual_v5.get('passed')} "
                f"production_approved={visual_approval.get('production_approved')} "
                f"hard_failures={len(visual_v5.get('hard_fail_reasons') or [])}"
            ),
            blocker=(
                "high-end character lacks authoritative Judge v5 production "
                "approval; V4 alone can never ship a Monster/Ultra character"
            ),
        )

    if high_end:
        pbr_core={"baseColor","roughness","normal"}
        pbr_ready=pbr_core.issubset(channels)
        _gate(
            gates,"material.pbr_core","materials",pbr_ready,
            f"required={sorted(pbr_core)} actual={sorted(channels)}",
            blocker="high-end asset is missing core PBR evidence",
        )
        target=int(material.get("target_texture_size") or 0)
        min_edge=int(material.get("base_color_min_edge") or 0)
        _gate(
            gates,"texture.hero_resolution","materials",
            bool(target>0 and min_edge>=target),
            f"weakest_baseColor={min_edge}px target={target}px",
            blocker="Hero Master visible texture target is not met",
        )

    face=qa_report.get("face_evidence") or {}
    if mode=="character":
        face_chain=bool(face.get("quality_evidence_ready"))
        _gate(
            gates,"character.face_chain","character",face_chain,
            "identity/FaceMesh/FaceTex/FaceDetail evidence chain",
            blocker="character face-quality evidence chain is incomplete",
        )
        if face.get("required"):
            _gate(
                gates,"character.face_refs","character",
                bool(face.get("ready")),
                f"evaluated={face.get('evaluated')} expected={face.get('expected')} worst={face.get('min_score')}",
                blocker="explicit face references are not completely evaluated",
            )
        anatomy=qa_report.get("critical_anatomy") or {}
        if anatomy.get("required"):
            _gate(
                gates,"character.critical_anatomy","character",
                bool(anatomy.get("ready")),
                (
                    f"evaluated={anatomy.get('evaluated')} "
                    f"expected={anatomy.get('expected')} "
                    f"targets={[x.get('target') for x in (anatomy.get('targets') or [])]}"
                ),
                blocker=(
                    "one or more explicit critical anatomy references "
                    "(eyes/mouth/teeth/hands/hair/ears/wounds) were not evaluated"
                ),
            )

            semantic=manifest.get("semantic_anatomy") or {}
            aggregate=semantic.get("aggregate") or {}
            _gate(
                gates,"character.semantic_anatomy","character",
                bool(
                    semantic.get("attempted")
                    and semantic.get("ready")
                    and aggregate.get("ready")
                ),
                (
                    f"attempted={semantic.get('attempted')} "
                    f"targets={semantic.get('critical_targets')} "
                    f"views={len(semantic.get('rendered_views') or [])} "
                    f"missing={aggregate.get('missing_parts')} "
                    f"error={semantic.get('error')}"
                ),
                required=high_end,
                blocker=(
                    "final high-end character lacks passing multi-view "
                    "semantic anatomy GroundingDINO/SAM2 proof for explicitly "
                    "referenced critical anatomy"
                ),
            )

        for key in (
            "head_density_score",
            "head_texel_density_score",
            "head_texture_detail_score",
        ):
            _gate(
                gates,f"character.{key}","character",
                _finite(geometry.get(key)),
                f"{key}={geometry.get(key)}",
                blocker=f"missing {key} evidence",
            )

        rig=qa_report.get("rig") or {}
        _gate(
            gates,"character.rig","character",bool(rig.get("rig_ready")),
            f"skins={rig.get('skins')} joints={rig.get('joint_count')}",
            blocker="character has no validated skin/rig",
        )
        morph_targets=int(rig.get("morph_target_count") or 0)
        if morph_targets>0:
            _gate(
                gates,"character.morphs","character",
                bool(rig.get("morph_ready")),
                (
                    f"targets={morph_targets} "
                    f"meshes={rig.get('morph_mesh_count')} "
                    f"primitives={rig.get('morph_primitive_count')}"
                ),
                blocker=(
                    "character morph/blendshape payload or weight-channel "
                    "wiring is malformed"
                ),
            )
            morph_deformation=qa_report.get("morph_deformation") or {}
            _gate(
                gates,"character.morph_deformation","character",
                bool(
                    morph_deformation.get("applicable")
                    and morph_deformation.get("ready")
                ),
                (
                    f"poses={morph_deformation.get('sampled_poses')} "
                    f"max_disp={morph_deformation.get('max_displacement_ratio')} "
                    f"catastrophic={morph_deformation.get('catastrophic_poses')} "
                    f"nonfinite={morph_deformation.get('nonfinite_vertices')}"
                ),
                blocker=(
                    "character blendshapes are wired but fail sampled morph "
                    "deformation QA (explosion/collapse/non-finite/cubic overshoot)"
                ),
            )
        skin_weights=qa_report.get("skin_weights") or {}
        _gate(
            gates,"character.skin_weights","character",
            bool(skin_weights.get("applicable") and skin_weights.get("ready")),
            (
                f"applicable={skin_weights.get('applicable')} "
                f"weighted={skin_weights.get('weighted_vertices')} "
                f"zero={skin_weights.get('zero_weight_vertices')} "
                f"non_normalized={skin_weights.get('non_normalized_vertices')} "
                f"invalid_joints={skin_weights.get('invalid_joint_references')}"
            ),
            blocker="character skin weights are missing, malformed, non-normalized, or reference invalid joints",
        )
        _gate(
            gates,"character.animation","character",
            bool(rig.get("animation_ready")),
            f"animations={rig.get('animations')}",
            blocker="character has no embedded animation clips",
        )
        animation_qa=qa_report.get("animation_qa") or {}
        _gate(
            gates,"character.animation_integrity","character",
            bool(
                animation_qa.get("applicable")
                and animation_qa.get("ready")
            ),
            (
                f"applicable={animation_qa.get('applicable')} "
                f"channels={animation_qa.get('channel_count')} "
                f"keyframes={animation_qa.get('total_keyframes')}"
            ),
            blocker=(
                "character animation clips fail integrity QA "
                "(timestamps/samples/quaternions/channels)"
            ),
        )
        deformation_qa=qa_report.get("deformation_qa") or {}
        _gate(
            gates,"character.deformation","character",
            bool(
                deformation_qa.get("applicable")
                and deformation_qa.get("ready")
            ),
            (
                f"frames={deformation_qa.get('sampled_frames')} "
                f"max_disp={deformation_qa.get('max_displacement_ratio')} "
                f"max_edge={deformation_qa.get('max_edge_stretch_ratio')} "
                f"catastrophic={deformation_qa.get('catastrophic_frames')}"
            ),
            blocker=(
                "character fails sampled skin-deformation QA "
                "(explosion/collapse/non-finite/edge stretch)"
            ),
        )

    gameprep=manifest.get("gameprep") or qa_report.get("gameprep")
    lods=(gameprep or {}).get("lods") or []
    _gate(
        gates,"runtime.gameprep","runtime",
        bool(gameprep and lods),
        f"lod_count={len(lods)}",
        blocker="GamePrep runtime package is missing",
    )

    collision=qa_report.get("collision_qa") or {}
    _gate(
        gates,"runtime.collision","runtime",
        bool(
            collision.get("applicable")
            and collision.get("ready")
        ),
        (
            f"faces={collision.get('faces')} "
            f"watertight={collision.get('watertight')} "
            f"volume={collision.get('volume')} "
            f"convexity={collision.get('convexity_ratio')} "
            f"bbox={collision.get('bbox_coverage_ready')}"
        ),
        blocker=(
            "runtime collision proxy is missing, non-watertight, "
            "non-convex, volumeless, or does not cover the Hero Master"
        ),
        required=profile in {"mobile","game","monster","ultra"},
    )

    pack=manifest.get("portable_pack") or {}
    tiers=pack.get("tiers") or []
    complete_lods=pack.get("complete_lod_chain")
    _gate(
        gates,"runtime.portable_pack","runtime",
        bool(pack and tiers and complete_lods),
        f"tiers={len(tiers)} complete_lod_chain={complete_lods}",
        blocker="portable runtime tiers are incomplete",
        required=profile in {"mobile","game","monster","ultra"},
    )
    lod_parity_ready=bool(pack.get("lod_parity_ready"))
    _gate(
        gates,"runtime.lod_parity","runtime",
        bool(pack and tiers and lod_parity_ready),
        (
            f"tiers={len(tiers)} "
            f"lod_parity_ready={lod_parity_ready}"
        ),
        blocker=(
            "one or more runtime LOD tiers fail Hero Master parity "
            "(shape/material/rig/morph/animation/deformation)"
        ),
        required=profile in {"mobile","game","monster","ultra"},
    )
    runtime_budget_ready=bool(pack.get("runtime_budget_ready"))
    _gate(
        gates,"runtime.asset_budget","runtime",
        bool(pack and tiers and runtime_budget_ready),
        (
            f"tiers={len(tiers)} "
            f"runtime_budget_ready={runtime_budget_ready}"
        ),
        blocker=(
            "one or more runtime tiers exceed HAYUYA house asset budgets "
            "(triangles/material slots/texture edge)"
        ),
        required=profile in {"mobile","game","monster","ultra"},
    )

    composite=manifest.get("composite_champion") or {}
    composite_required=bool(composite.get("composite_required"))
    deferred=list(composite.get("deferred_transfers") or [])
    executable=list(composite.get("executable_now") or [])
    if composite_required:
        _gate(
            gates,"composite.optimized","composite",False,
            (
                f"final_plan_required=true deferred={deferred} "
                f"executable={executable} "
                f"champion={manifest.get('champion',{}).get('backend')}"
            ),
            blocker="better regional donor evidence still exists after all implemented Composite Champion passes",
        )
    else:
        _gate(
            gates,"composite.optimized","composite",True,
            "final Composite plan reports no stronger unresolved regional donor",
        )

    qa_ready=bool(qa_report.get("production_ready"))
    _gate(
        gates,"qa.production_ready","qa",qa_ready,
        f"production_ready={qa_ready}",
        blocker="QA Package does not consider the asset production-ready",
    )

    warnings=[str(x) for x in (qa_report.get("warnings") or []) if str(x).strip()]
    if warnings:
        advisories.extend(warnings[:20])

    required=[g for g in gates if g.required]
    blockers=[g.blocker for g in required if not g.ready and g.blocker]
    passed=sum(1 for g in required if g.ready)
    return AAAReadinessReport(
        version=1,
        ready=not blockers,
        passed_required=passed,
        total_required=len(required),
        blockers=blockers,
        advisories=advisories,
        gates=gates,
    )


def write_aaa_report(report:AAAReadinessReport,path:Path)->Path:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(asdict(report),indent=2)+"\n",encoding="utf-8")
    return path


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(description="HAYUYA internal AAA acceptance contract.")
    parser.add_argument("manifest",type=Path)
    parser.add_argument("qa_report",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=evaluate_aaa_acceptance(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        json.loads(args.qa_report.read_text(encoding="utf-8")),
    )
    write_aaa_report(report,args.output)
    print(json.dumps(asdict(report),indent=2))
    return 0 if report.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
