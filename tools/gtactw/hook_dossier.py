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
