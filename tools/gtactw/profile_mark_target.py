#!/usr/bin/env python3
"""Explicitly mark one CTW hook target RVA as verified after manual review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import aarch64_xref
import profile_template
import profile_verify_binary


def mark_target_verified(
    libgame: Path,
    profile: dict,
    *,
    target: str,
    rva: int,
    method: str,
    detail: str,
    allow_unranked: bool = False,
) -> dict:
    if target not in profile_template.TARGET_KEYS:
        raise ValueError(f"unknown target: {target}")
    if not isinstance(rva, int) or rva <= 0:
        raise ValueError("rva must be a positive integer")
    if not method.strip() or not detail.strip():
        raise ValueError("method and detail are required")

    rankings = profile.get("target_evidence_rankings", {}).get(target, [])
    ranked_rvas = {
        item.get("rva")
        for item in rankings
        if isinstance(item, dict) and isinstance(item.get("rva"), int)
    }
    if not allow_unranked and rva not in ranked_rvas:
        raise ValueError(
            f"RVA 0x{rva:X} is not in {target} evidence rankings; "
            "use allow_unranked only after independent manual verification"
        )

    blob = libgame.read_bytes()
    sections = aarch64_xref._read_sections(blob)
    prefix = profile_verify_binary._target_prefix(blob, sections, rva, 16)

    out = json.loads(json.dumps(profile))
    targets = out.setdefault("patch_targets_rva", {})
    ledger = out.setdefault("target_verification", {})
    previous = ledger.get(target, {})
    previous_evidence = (
        previous.get("evidence")
        if isinstance(previous, dict)
        and isinstance(previous.get("evidence"), list)
        else []
    )

    evidence = list(previous_evidence)
    record = {
        "method": method.strip(),
        "detail": detail.strip(),
    }
    if record not in evidence:
        evidence.append(record)

    targets[target] = rva
    ledger[target] = {
        "status": "verified",
        "rva": rva,
        "evidence": evidence,
        "code_prefix_hex": prefix.hex(),
    }

    # Target verification never verifies ABI automatically.
    abi = out.setdefault("abi_verification", {}).setdefault(target, {
        "status": "pending",
        "prototype": None,
        "calling_convention": "aarch64_aapcs64",
        "adapter": None,
        "evidence": [],
    })
    if abi.get("status") != "verified":
        abi["status"] = "pending"

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument("--target", required=True, choices=profile_template.TARGET_KEYS)
    ap.add_argument("--rva", required=True, type=lambda x: int(x, 0))
    ap.add_argument("--method", required=True)
    ap.add_argument("--detail", required=True)
    ap.add_argument("--allow-unranked", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        updated = mark_target_verified(
            args.libgame,
            profile,
            target=args.target,
            rva=args.rva,
            method=args.method,
            detail=args.detail,
            allow_unranked=args.allow_unranked,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "target": args.target,
        "rva": args.rva,
        "rva_hex": f"0x{args.rva:X}",
        "out": str(args.out),
        "abi_status": updated["abi_verification"][args.target]["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
