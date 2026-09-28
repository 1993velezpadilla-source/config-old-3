#!/usr/bin/env python3
"""Choose the CTW proxy loader variant from verified hook evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import profile_template


SIMPLE = "simple_copy_trampoline_candidate"
ADVANCED = "advanced_relocator_required"


def select_loader_variant(profile: dict) -> dict:
    targets = profile.get("patch_targets_rva", {})
    target_ledger = profile.get("target_verification", {})
    abi_ledger = profile.get("abi_verification", {})

    per_target = {}
    missing = []
    advanced = []
    simple = []

    for key in profile_template.TARGET_KEYS:
        rva = targets.get(key)
        verified = target_ledger.get(key, {})
        if (
            not isinstance(rva, int)
            or rva <= 0
            or not isinstance(verified, dict)
            or verified.get("status") != "verified"
            or verified.get("rva") != rva
        ):
            per_target[key] = {
                "rva": rva,
                "strategy": None,
                "reason": "target_rva_not_verified",
            }
            missing.append(key)
            continue

        abi = abi_ledger.get(key, {})
        candidates = abi.get("candidates") if isinstance(abi, dict) else None
        matches = [
            candidate
            for candidate in (candidates or [])
            if isinstance(candidate, dict)
            and candidate.get("rva") == rva
            and candidate.get("trampoline_strategy_hint") in (SIMPLE, ADVANCED)
        ]

        if len(matches) != 1:
            per_target[key] = {
                "rva": rva,
                "strategy": None,
                "reason": (
                    "missing_strategy_for_verified_rva"
                    if not matches
                    else "ambiguous_strategy_for_verified_rva"
                ),
            }
            missing.append(key)
            continue

        strategy = matches[0]["trampoline_strategy_hint"]
        per_target[key] = {
            "rva": rva,
            "strategy": strategy,
            "function": matches[0].get("function"),
            "source": matches[0].get("source"),
        }

        if strategy == ADVANCED:
            advanced.append(key)
        else:
            simple.append(key)

    if missing:
        variant = "undetermined"
        ready = False
    elif advanced:
        variant = "shadowhook"
        ready = True
    else:
        variant = "minimal"
        ready = True

    return {
        "ready": ready,
        "loader_variant": variant,
        "simple_copy_targets": simple,
        "advanced_relocator_targets": advanced,
        "undetermined_targets": missing,
        "targets": per_target,
        "note": (
            "Variant selection is based only on the verified target RVAs and "
            "their matching prologue strategy evidence. It does not mark the "
            "hook ABI or playable mod as verified."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        report = select_loader_variant(profile)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
