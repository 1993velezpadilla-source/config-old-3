#!/usr/bin/env python3
"""Summarize readiness of a CTW runtime patch profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import profile_template


def profile_status(profile: dict) -> dict:
    fp = profile.get("fingerprint", {})
    jni = fp.get("jni_rvas", {})

    fingerprint_checks = {
        "sha256": isinstance(fp.get("sha256"), str) and len(fp["sha256"]) == 64,
        "text_sha256": (
            isinstance(fp.get("text_sha256"), str)
            and len(fp["text_sha256"]) == 64
        ),
        "gnu_build_id": bool(fp.get("gnu_build_id")),
        "implOnDrawFrame": isinstance(jni.get("implOnDrawFrame"), int)
            and jni["implOnDrawFrame"] > 0,
        "implOnInitialSetup": isinstance(jni.get("implOnInitialSetup"), int)
            and jni["implOnInitialSetup"] > 0,
        "implOnGamepadAxesChanged": (
            isinstance(jni.get("implOnGamepadAxesChanged"), int)
            and jni["implOnGamepadAxesChanged"] > 0
        ),
    }
    fingerprint_ready = all(fingerprint_checks.values())

    targets = profile.get("patch_targets_rva", {})
    target_ledger = profile.get("target_verification", {})
    abi_ledger = profile.get("abi_verification", {})

    target_status = {}
    abi_status = {}
    target_verified = 0
    abi_verified = 0

    for key in profile_template.TARGET_KEYS:
        rva = targets.get(key)
        item = target_ledger.get(key)
        evidence = item.get("evidence") if isinstance(item, dict) else None
        prefix = item.get("code_prefix_hex") if isinstance(item, dict) else None
        target_ok = bool(
            isinstance(rva, int)
            and rva > 0
            and isinstance(item, dict)
            and item.get("status") == "verified"
            and item.get("rva") == rva
            and isinstance(evidence, list)
            and len(evidence) > 0
            and isinstance(prefix, str)
            and len(prefix.removeprefix("0x")) >= 32
        )
        if target_ok:
            target_verified += 1

        target_status[key] = {
            "verified": target_ok,
            "rva": rva,
            "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
            "code_signature_present": (
                isinstance(prefix, str)
                and len(prefix.removeprefix("0x")) >= 32
            ),
        }

        abi = abi_ledger.get(key)
        abi_evidence = abi.get("evidence") if isinstance(abi, dict) else None
        abi_ok = bool(
            target_ok
            and isinstance(abi, dict)
            and abi.get("status") == "verified"
            and isinstance(abi.get("prototype"), str)
            and abi["prototype"].strip()
            and abi.get("calling_convention") == "aarch64_aapcs64"
            and isinstance(abi.get("adapter"), str)
            and abi["adapter"].strip()
            and isinstance(abi_evidence, list)
            and len(abi_evidence) > 0
        )
        if abi_ok:
            abi_verified += 1

        candidates = abi.get("candidates") if isinstance(abi, dict) else None
        abi_status[key] = {
            "verified": abi_ok,
            "status": abi.get("status") if isinstance(abi, dict) else None,
            "prototype": abi.get("prototype") if isinstance(abi, dict) else None,
            "adapter": abi.get("adapter") if isinstance(abi, dict) else None,
            "evidence_count": (
                len(abi_evidence) if isinstance(abi_evidence, list) else 0
            ),
            "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
        }

    all_targets = target_verified == len(profile_template.TARGET_KEYS)
    all_abis = abi_verified == len(profile_template.TARGET_KEYS)

    if not fingerprint_ready:
        phase = "needs_exact_build_fingerprint"
    elif not all_targets:
        phase = "needs_verified_target_rvas"
    elif not all_abis:
        phase = "needs_verified_hook_abis"
    else:
        phase = "abi_verified_ready_for_hook_adapter_gate"

    return {
        "phase": phase,
        "fingerprint_ready": fingerprint_ready,
        "fingerprint_checks": fingerprint_checks,
        "targets_verified": target_verified,
        "targets_total": len(profile_template.TARGET_KEYS),
        "abis_verified": abi_verified,
        "abis_total": len(profile_template.TARGET_KEYS),
        "runtime_hooks_installed": False,
        "playable_3d_mod_ready": False,
        "target_status": target_status,
        "abi_status": abi_status,
        "note": (
            "Even a fully ABI-verified profile is not marked playable until "
            "runtime hook installation and Android capture gates pass."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        report = profile_status(profile)
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
