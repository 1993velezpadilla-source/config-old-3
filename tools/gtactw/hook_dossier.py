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
        locally_prepared.update(
            x
            for x in context.get(
                "locally_prepared_argument_registers",
                [],
            )
            if isinstance(x, str)
        )
        passthrough.update(
            x
            for x in context.get(
                "possible_passthrough_argument_registers",
                [],
            )
            if isinstance(x, str)
        )
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

    return {
        "callee_gpr_inputs": sorted(callee_gpr),
        "callee_fp_inputs": sorted(callee_fp),
        "caller_locally_prepared": sorted(locally_prepared),
        "caller_possible_passthrough": sorted(passthrough),
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
                "abi_review_card": _abi_review_card(
                    abi_evidence,
                    caller_evidence,
                ),
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
