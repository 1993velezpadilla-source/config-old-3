#!/usr/bin/env python3
"""Create a concise evidence dossier for the six CTW runtime hook targets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import profile_template


def _candidate_abi_by_rva(profile: dict, target: str) -> dict[int, dict]:
    abi = profile.get("abi_verification", {}).get(target, {})
    candidates = abi.get("candidates") if isinstance(abi, dict) else None
    out = {}
    for item in candidates or []:
        if not isinstance(item, dict):
            continue
        rva = item.get("rva")
        if isinstance(rva, int) and rva > 0:
            out[rva] = item
    return out



def _abi_review_card(abi_evidence: dict, caller_evidence: dict) -> dict:
    arg = (
        abi_evidence.get("argument_register_hints", {})
        if isinstance(abi_evidence, dict)
        else {}
    )
    callee_gpr = {
        f"x{n}" for n in arg.get("likely_gpr_inputs_x0_x7", [])
        if isinstance(n, int)
    }
    callee_fp = {
        f"v{n}" for n in arg.get("likely_fp_inputs_v0_v7", [])
        if isinstance(n, int)
    }

    locally_prepared = set()
    passthrough = set()
    caller_reg_stats = {}
    return_counts = {
        "x0": {
            "consumed": 0,
            "overwritten_without_read": 0,
            "not_observed_in_window": 0,
        },
        "v0": {
            "consumed": 0,
            "overwritten_without_read": 0,
            "not_observed_in_window": 0,
        },
    }

    callers = (
        caller_evidence.get("callers", [])
        if isinstance(caller_evidence, dict)
        else []
    )
    for caller in callers:
        if not isinstance(caller, dict):
            continue
        context = caller.get("context", {})
        if not isinstance(context, dict):
            continue
        local_regs = {
            x
            for x in context.get(
                "locally_prepared_argument_registers",
                [],
            )
            if isinstance(x, str)
        }
        pass_regs = {
            x
            for x in context.get(
                "possible_passthrough_argument_registers",
                [],
            )
            if isinstance(x, str)
        }
        locally_prepared.update(local_regs)
        passthrough.update(pass_regs)

        for reg in sorted(local_regs | pass_regs):
            stats = caller_reg_stats.setdefault(reg, {
                "locally_prepared_count": 0,
                "passthrough_count": 0,
                "kind_counts": {},
            })
            if reg in local_regs:
                stats["locally_prepared_count"] += 1
            if reg in pass_regs:
                stats["passthrough_count"] += 1
        return_use = context.get("return_use", {})
        if isinstance(return_use, dict):
            for reg in ("x0", "v0"):
                item = return_use.get(reg, {})
                status = item.get("status") if isinstance(item, dict) else None
                if status in return_counts[reg]:
                    return_counts[reg][status] += 1

    return_hints = (
        abi_evidence.get("return_value_hints", {})
        if isinstance(abi_evidence, dict)
        else {}
    )
    callee_shapes = (
        abi_evidence.get("argument_shape_hints", {})
        if isinstance(abi_evidence, dict)
        else {}
    )

    caller_kinds = {}
    for caller in callers:
        if not isinstance(caller, dict):
            continue
        context = caller.get("context", {})
        prepared_map = (
            context.get("prepared_registers", {})
            if isinstance(context, dict)
            else {}
        )
        if not isinstance(prepared_map, dict):
            continue
        for reg, item in prepared_map.items():
            if not isinstance(item, dict):
                continue
            kind = item.get("kind_hint")
            if not isinstance(kind, str) or not kind:
                continue
            caller_kinds.setdefault(reg, set()).add(kind)
            stats = caller_reg_stats.setdefault(reg, {
                "locally_prepared_count": 0,
                "passthrough_count": 0,
                "kind_counts": {},
            })
            stats["kind_counts"][kind] = (
                stats["kind_counts"].get(kind, 0) + 1
            )

    def shape_compatible(callee_kind: str, caller_kind: str) -> bool:
        pointer_like = {
            "pointer_like",
            "address_like",
            "stack_address_like",
            "scalar_or_pointer_64",
        }
        scalar32 = {
            "scalar_32_like",
            "boolean_like",
            "integer_or_pointer",
        }
        if callee_kind == "pointer_like":
            return caller_kind in pointer_like
        if callee_kind == "scalar_32_like":
            return caller_kind in scalar32
        if callee_kind == "scalar_or_pointer_64":
            return caller_kind in pointer_like | {"loaded_64_value"}
        if callee_kind == "float32_like":
            return caller_kind == "float32_like"
        if callee_kind == "float64_like":
            return caller_kind == "float64_like"
        if callee_kind == "vector_or_aggregate":
            return caller_kind == "vector_or_aggregate"
        return True

    shape_review = {}
    callee_gpr_shapes = (
        callee_shapes.get("gpr", {})
        if isinstance(callee_shapes, dict)
        else {}
    )
    callee_fp_shapes = (
        callee_shapes.get("fp", {})
        if isinstance(callee_shapes, dict)
        else {}
    )
    for reg, item in {
        **(callee_gpr_shapes if isinstance(callee_gpr_shapes, dict) else {}),
        **(callee_fp_shapes if isinstance(callee_fp_shapes, dict) else {}),
    }.items():
        if not isinstance(item, dict):
            continue
        callee_kind = item.get("kind_hint")
        caller_values = sorted(caller_kinds.get(reg, set()))
        compatible = [
            value
            for value in caller_values
            if isinstance(callee_kind, str)
            and shape_compatible(callee_kind, value)
        ]
        incompatible = [
            value
            for value in caller_values
            if isinstance(callee_kind, str)
            and not shape_compatible(callee_kind, value)
        ]
        shape_review[reg] = {
            "callee_kind_hint": callee_kind,
            "caller_kind_hints": caller_values,
            "compatible_caller_hints": compatible,
            "incompatible_caller_hints": incompatible,
            "status": (
                "conflict"
                if incompatible
                else "supported"
                if compatible
                else "no_direct_caller_shape"
            ),
        }

    caller_count = len(callers)
    caller_argument_consensus = {}
    for reg, stats in sorted(caller_reg_stats.items()):
        local_count = stats["locally_prepared_count"]
        pass_count = stats["passthrough_count"]
        seen_count = min(caller_count, local_count + pass_count)
        absent_count = max(0, caller_count - seen_count)

        if caller_count == 0:
            status = "no_callers"
        elif local_count == caller_count:
            status = "locally_prepared_by_all_callers"
        elif pass_count == caller_count:
            status = "passthrough_in_all_callers"
        elif seen_count == caller_count:
            status = "mixed_but_present_in_all_callers"
        else:
            status = "present_in_subset_of_callers"

        caller_argument_consensus[reg] = {
            **stats,
            "caller_count": caller_count,
            "seen_count": seen_count,
            "absent_count": absent_count,
            "status": status,
        }

    return {
        "callee_gpr_inputs": sorted(callee_gpr),
        "callee_fp_inputs": sorted(callee_fp),
        "caller_locally_prepared": sorted(locally_prepared),
        "caller_possible_passthrough": sorted(passthrough),
        "caller_argument_consensus": caller_argument_consensus,
        "gpr_supported_by_callee_and_callers": sorted(
            callee_gpr & (locally_prepared | passthrough)
        ),
        "fp_supported_by_callee_and_callers": sorted(
            callee_fp & (locally_prepared | passthrough)
        ),
        "callee_only_argument_hints": sorted(
            (callee_gpr | callee_fp)
            - (locally_prepared | passthrough)
        ),
        "caller_only_argument_hints": sorted(
            (locally_prepared | passthrough)
            - (callee_gpr | callee_fp)
        ),
        "caller_return_use_counts": return_counts,
        "argument_shape_review": shape_review,
        "callee_return_register_classes": return_hints.get(
            "register_classes_seen",
            [],
        ),
        "direct_call_site_count": (
            caller_evidence.get("direct_call_site_count")
            if isinstance(caller_evidence, dict)
            else None
        ),
        "callers_analyzed": len(callers),
        "note": (
            "This card summarizes agreement between callee dataflow and "
            "direct-call-site evidence. It is review evidence only and never "
            "declares a prototype verified."
        ),
    }


def _manual_review_readiness(
    abi_evidence: dict,
    caller_evidence: dict,
    review_card: dict,
    trampoline_strategy_hint: str | None,
) -> dict:
    """Summarize whether a candidate has enough evidence for human ABI review."""
    blockers = []
    cautions = []
    supports = []

    if not isinstance(abi_evidence, dict) or not abi_evidence:
        blockers.append("missing_callee_abi_evidence")

    direct_calls = review_card.get("direct_call_site_count")
    callers_analyzed = review_card.get("callers_analyzed", 0)
    if isinstance(direct_calls, int):
        if direct_calls == 0:
            blockers.append("no_direct_call_sites")
            cautions.append(
                "candidate may be reached indirectly; inspect register/function-pointer call paths"
            )
        elif callers_analyzed == 0:
            blockers.append("direct_callers_not_analyzed")
        else:
            supports.append("caller_side_abi_evidence")
            if callers_analyzed < direct_calls:
                cautions.append("caller_analysis_is_partial")

    shape_review = review_card.get("argument_shape_review", {})
    conflicts = sorted(
        reg
        for reg, item in shape_review.items()
        if isinstance(item, dict) and item.get("status") == "conflict"
    )
    if conflicts:
        blockers.append("argument_shape_conflict")
        cautions.append(
            "callee/caller kind hints conflict for " + ",".join(conflicts)
        )
    elif shape_review:
        supported = sorted(
            reg
            for reg, item in shape_review.items()
            if isinstance(item, dict) and item.get("status") == "supported"
        )
        if supported:
            supports.append("callee_caller_argument_shape_agreement")

    consensus = review_card.get("caller_argument_consensus", {})
    consensus_all = sorted(
        reg
        for reg, item in consensus.items()
        if isinstance(item, dict)
        and item.get("status") in {
            "locally_prepared_by_all_callers",
            "passthrough_in_all_callers",
            "mixed_but_present_in_all_callers",
        }
    )
    if consensus_all:
        supports.append("multi_caller_argument_consensus")

    if trampoline_strategy_hint:
        supports.append("trampoline_strategy_available")
    else:
        blockers.append("missing_trampoline_strategy")

    return_counts = review_card.get("caller_return_use_counts", {})
    consumed_return_classes = sorted(
        reg
        for reg, counts in return_counts.items()
        if isinstance(counts, dict) and counts.get("consumed", 0) > 0
    )
    if consumed_return_classes:
        supports.append("caller_return_use_observed")

    if "argument_shape_conflict" in blockers:
        status = "shape_conflict"
    elif "missing_callee_abi_evidence" in blockers:
        status = "needs_callee_abi_evidence"
    elif (
        "no_direct_call_sites" in blockers
        or "direct_callers_not_analyzed" in blockers
    ):
        status = "needs_caller_path_review"
    elif "missing_trampoline_strategy" in blockers:
        status = "needs_trampoline_review"
    else:
        status = "manual_review_ready"

    return {
        "status": status,
        "blockers": blockers,
        "cautions": cautions,
        "supports": sorted(set(supports)),
        "consensus_registers": consensus_all,
        "consumed_return_classes": consumed_return_classes,
        "note": (
            "Readiness means enough static evidence is present for focused "
            "human review. It never verifies an RVA, prototype, adapter, or "
            "hook automatically."
        ),
    }


def build_dossier(profile: dict, top: int = 5) -> dict:
    if top < 1 or top > 16:
        raise ValueError("top must be between 1 and 16")

    rankings = profile.get("target_evidence_rankings", {})
    targets = profile.get("patch_targets_rva", {})
    verification = profile.get("target_verification", {})
    result = {}

    for target in profile_template.TARGET_KEYS:
        abi_by_rva = _candidate_abi_by_rva(profile, target)
        entries = []

        for rank, candidate in enumerate(rankings.get(target, [])[:top], start=1):
            rva = candidate.get("rva")
            if not isinstance(rva, int) or rva <= 0:
                continue

            abi_candidate = abi_by_rva.get(rva, {})
            abi_evidence = abi_candidate.get("abi_evidence", {})
            caller_evidence = abi_candidate.get(
                "caller_abi_evidence",
                {},
            )
            arg_hints = (
                abi_evidence.get("argument_register_hints", {})
                if isinstance(abi_evidence, dict)
                else {}
            )
            prologue = (
                abi_evidence.get("prologue_relocation", {})
                if isinstance(abi_evidence, dict)
                else {}
            )

            review_card = _abi_review_card(
                abi_evidence,
                caller_evidence,
            )
            manual_review = _manual_review_readiness(
                abi_evidence,
                caller_evidence,
                review_card,
                abi_candidate.get("trampoline_strategy_hint"),
            )

            entries.append({
                "rank": rank,
                "rva": rva,
                "rva_hex": f"0x{rva:X}",
                "function": candidate.get("function"),
                "score": candidate.get("score"),
                "reasons": candidate.get("reasons", []),
                "strings": candidate.get("strings", []),
                "plt_imports": candidate.get("plt_imports", []),
                "draw_frame_hops": candidate.get("draw_frame_hops"),
                "draw_frame_path_functions": candidate.get(
                    "draw_frame_path_functions",
                    [],
                ),
                "call_neighborhood": candidate.get("call_neighborhood"),
                "function_fingerprint": candidate.get(
                    "function_fingerprint"
                ),
                "trampoline_strategy_hint": abi_candidate.get(
                    "trampoline_strategy_hint"
                ),
                "stack_frame_bytes_hint": (
                    abi_evidence.get("stack_frame_bytes_hint")
                    if isinstance(abi_evidence, dict)
                    else None
                ),
                "likely_gpr_inputs_x0_x7": arg_hints.get(
                    "likely_gpr_inputs_x0_x7",
                    [],
                ),
                "likely_fp_inputs_v0_v7": arg_hints.get(
                    "likely_fp_inputs_v0_v7",
                    [],
                ),
                "argument_analysis": arg_hints.get("analysis"),
                "argument_first_access": arg_hints.get(
                    "first_access",
                    {},
                ),
                "overwritten_gpr_before_read_x0_x7": arg_hints.get(
                    "overwritten_gpr_early_x0_x7",
                    [],
                ),
                "overwritten_fp_before_read_v0_v7": arg_hints.get(
                    "overwritten_fp_before_read_v0_v7",
                    [],
                ),
                "argument_shape_hints": (
                    abi_evidence.get("argument_shape_hints", {})
                    if isinstance(abi_evidence, dict)
                    else {}
                ),
                "return_value_hints": (
                    abi_evidence.get("return_value_hints", {})
                    if isinstance(abi_evidence, dict)
                    else {}
                ),
                "caller_abi_evidence": (
                    caller_evidence
                    if isinstance(caller_evidence, dict)
                    else {}
                ),
                "abi_review_card": review_card,
                "manual_review": manual_review,
                "direct_call_site_count": (
                    caller_evidence.get("direct_call_site_count")
                    if isinstance(caller_evidence, dict)
                    else None
                ),
                "callers_analyzed": (
                    caller_evidence.get("callers_analyzed")
                    if isinstance(caller_evidence, dict)
                    else None
                ),
                "calls": (
                    abi_evidence.get("calls", [])
                    if isinstance(abi_evidence, dict)
                    else []
                ),
                "prologue_simple_copy_safe": (
                    prologue.get("simple_copy_trampoline_safe")
                    if isinstance(prologue, dict)
                    else None
                ),
                "prologue_instructions": (
                    prologue.get("instructions", [])
                    if isinstance(prologue, dict)
                    else []
                ),
            })

        verified = verification.get(target, {})
        verified_rva = targets.get(target)
        review_ready = [
            entry
            for entry in entries
            if entry.get("manual_review", {}).get("status")
            == "manual_review_ready"
        ]
        result[target] = {
            "verified": bool(
                isinstance(verified, dict)
                and verified.get("status") == "verified"
                and verified.get("rva") == verified_rva
                and isinstance(verified_rva, int)
                and verified_rva > 0
            ),
            "verified_rva": verified_rva,
            "candidate_count_shown": len(entries),
            "manual_review_ready_count": len(review_ready),
            "first_manual_review_ready_candidate": (
                {
                    "rank": review_ready[0]["rank"],
                    "rva": review_ready[0]["rva"],
                    "rva_hex": review_ready[0]["rva_hex"],
                    "function": review_ready[0].get("function"),
                }
                if review_ready
                else None
            ),
            "candidates": entries,
        }

    anchors = profile.get("public_4243_engine_anchors", {})
    return {
        "fingerprint": profile.get("fingerprint", {}),
        "public_4243_engine_anchors": anchors,
        "targets": result,
        "summary": {
            "targets_verified": sum(
                1 for item in result.values() if item["verified"]
            ),
            "targets_total": len(profile_template.TARGET_KEYS),
            "targets_with_candidates": sum(
                1 for item in result.values() if item["candidates"]
            ),
            "targets_with_manual_review_ready_candidate": sum(
                1
                for item in result.values()
                if item["manual_review_ready_count"] > 0
            ),
            "manual_review_ready_candidates": sum(
                item["manual_review_ready_count"]
                for item in result.values()
            ),
            "top_candidates_per_target": top,
        },
        "note": (
            "This dossier is evidence for manual reverse-engineering review. "
            "Candidate rank, ABI hints and trampoline strategy never promote "
            "a target to verified automatically."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", type=Path)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        report = build_dossier(profile, args.top)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
