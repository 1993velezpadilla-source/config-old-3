#!/usr/bin/env python3
"""Explicitly mark one CTW hook ABI/adapter as verified after manual review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import loader_variant
import profile_template


VALID_STRATEGIES = {
    loader_variant.SIMPLE,
    loader_variant.ADVANCED,
}


def mark_abi_verified(
    profile: dict,
    *,
    target: str,
    prototype: str,
    adapter: str,
    method: str,
    detail: str,
    allow_unprobed: bool = False,
    strategy: str | None = None,
) -> dict:
    if target not in profile_template.TARGET_KEYS:
        raise ValueError(f"unknown target: {target}")
    if not prototype.strip():
        raise ValueError("prototype is required")
    if not adapter.strip():
        raise ValueError("adapter is required")
    if not method.strip() or not detail.strip():
        raise ValueError("method and detail are required")

    rva = profile.get("patch_targets_rva", {}).get(target)
    target_record = profile.get("target_verification", {}).get(target, {})
    target_verified = bool(
        isinstance(rva, int)
        and rva > 0
        and isinstance(target_record, dict)
        and target_record.get("status") == "verified"
        and target_record.get("rva") == rva
    )
    if not target_verified:
        raise ValueError(
            f"{target} target RVA must be verified before ABI approval"
        )

    out = json.loads(json.dumps(profile))
    ledger = out.setdefault("abi_verification", {})
    item = ledger.setdefault(target, {
        "status": "pending",
        "prototype": None,
        "calling_convention": "aarch64_aapcs64",
        "adapter": None,
        "evidence": [],
        "candidates": [],
    })
    candidates = item.get("candidates")
    matches = [
        candidate
        for candidate in (candidates or [])
        if isinstance(candidate, dict)
        and candidate.get("rva") == rva
        and candidate.get("trampoline_strategy_hint") in VALID_STRATEGIES
        and isinstance(candidate.get("abi_evidence"), dict)
    ]

    selected_strategy = None
    if len(matches) == 1:
        selected_strategy = matches[0]["trampoline_strategy_hint"]
    elif not allow_unprobed:
        reason = "missing" if not matches else "ambiguous"
        raise ValueError(
            f"{target} has {reason} ABI/prologue evidence for verified "
            f"RVA 0x{rva:X}"
        )

    if strategy is not None:
        if strategy not in VALID_STRATEGIES:
            raise ValueError(f"invalid strategy: {strategy}")
        if selected_strategy is not None and strategy != selected_strategy:
            raise ValueError(
                "explicit strategy conflicts with probed strategy for "
                f"{target} RVA 0x{rva:X}"
            )
        selected_strategy = strategy

    if selected_strategy is None:
        raise ValueError(
            "explicit strategy is required when allow_unprobed is used"
        )

    evidence = item.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    record = {
        "method": method.strip(),
        "detail": detail.strip(),
        "rva": rva,
        "trampoline_strategy": selected_strategy,
    }
    if record not in evidence:
        evidence.append(record)

    item["status"] = "verified"
    item["prototype"] = prototype.strip()
    item["calling_convention"] = "aarch64_aapcs64"
    item["adapter"] = adapter.strip()
    item["evidence"] = evidence
    item["verified_rva"] = rva
    item["trampoline_strategy"] = selected_strategy

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", type=Path)
    ap.add_argument("--target", required=True, choices=profile_template.TARGET_KEYS)
    ap.add_argument("--prototype", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--method", required=True)
    ap.add_argument("--detail", required=True)
    ap.add_argument("--allow-unprobed", action="store_true")
    ap.add_argument(
        "--strategy",
        choices=sorted(VALID_STRATEGIES),
    )
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        updated = mark_abi_verified(
            profile,
            target=args.target,
            prototype=args.prototype,
            adapter=args.adapter,
            method=args.method,
            detail=args.detail,
            allow_unprobed=args.allow_unprobed,
            strategy=args.strategy,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    item = updated["abi_verification"][args.target]
    print(json.dumps({
        "ok": True,
        "target": args.target,
        "rva": item["verified_rva"],
        "prototype": item["prototype"],
        "adapter": item["adapter"],
        "trampoline_strategy": item["trampoline_strategy"],
        "out": str(args.out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
