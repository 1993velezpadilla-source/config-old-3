#!/usr/bin/env python3
"""Verify a filled CTW runtime patch profile against the exact libGame.so."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import aarch64_xref
import elf_probe
import profile_template


def _target_prefix(blob: bytes, sections: list[dict], rva: int, size: int = 16) -> bytes:
    for sec in sections:
        if not (int(sec.get("flags") or 0) & 0x4):  # SHF_EXECINSTR
            continue
        start = int(sec["addr"])
        end = start + int(sec["size"])
        if rva < start or rva + size > end:
            continue
        file_off = int(sec["offset"]) + (rva - start)
        raw = blob[file_off:file_off + size]
        if len(raw) != size:
            raise ValueError(f"target RVA 0x{rva:X} is truncated")
        return raw
    raise ValueError(f"target RVA 0x{rva:X} is not inside an executable section")


def verify_profile(libgame: Path, profile_path: Path) -> dict:
    blob = libgame.read_bytes()
    report = elf_probe.inspect_elf(libgame)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    fp = profile.get("fingerprint", {})
    jni = fp.get("jni_rvas", {})
    details = report.get("symbols", {}).get("known_jni_details", {})

    def actual_jni(short_name: str):
        full = profile_template.PREFIX + short_name
        item = details.get(full)
        if not item or not item.get("present"):
            return None
        return int(item["value"])

    checks = {
        "sha256": fp.get("sha256") == report.get("sha256"),
        "text_sha256": fp.get("text_sha256") == report.get("text", {}).get("sha256"),
        "gnu_build_id": fp.get("gnu_build_id") == report.get("elf", {}).get("build_id"),
        "jni_implOnDrawFrame": (
            jni.get("implOnDrawFrame") == actual_jni("implOnDrawFrame")
        ),
        "jni_implOnInitialSetup": (
            jni.get("implOnInitialSetup") == actual_jni("implOnInitialSetup")
        ),
        "jni_implOnGamepadAxesChanged": (
            jni.get("implOnGamepadAxesChanged")
            == actual_jni("implOnGamepadAxesChanged")
        ),
    }

    sections = aarch64_xref._read_sections(blob)
    target_checks = {}
    targets = profile.get("patch_targets_rva", {})
    verification = profile.get("target_verification", {})

    for key in profile_template.TARGET_KEYS:
        item = verification.get(key)
        target_rva = targets.get(key)
        result = {
            "ok": False,
            "rva": target_rva,
            "status": item.get("status") if isinstance(item, dict) else None,
        }

        try:
            if not isinstance(item, dict) or item.get("status") != "verified":
                raise ValueError("target status is not verified")
            if not isinstance(target_rva, int) or target_rva <= 0:
                raise ValueError("target RVA is missing")
            if item.get("rva") != target_rva:
                raise ValueError("verification RVA differs from patch target")

            expected_hex = item.get("code_prefix_hex")
            if not isinstance(expected_hex, str):
                raise ValueError("code_prefix_hex is missing")
            clean = expected_hex.removeprefix("0x").strip().lower()
            if len(clean) < 32:
                raise ValueError("code_prefix_hex contains fewer than 16 bytes")
            expected = bytes.fromhex(clean[:32])

            actual = _target_prefix(blob, sections, target_rva, 16)
            result.update({
                "expected_prefix_hex": expected.hex(),
                "actual_prefix_hex": actual.hex(),
                "prefix_match": actual == expected,
                "executable_rva": True,
                "ok": actual == expected,
            })
            if actual != expected:
                result["error"] = "target byte signature mismatch"
        except Exception as exc:
            result["error"] = str(exc)

        target_checks[key] = result
        checks[f"target_{key}"] = result["ok"]

    return {
        "ok": all(checks.values()),
        "libgame": str(libgame),
        "profile": str(profile_path),
        "checks": checks,
        "targets": target_checks,
        "actual_fingerprint": {
            "sha256": report.get("sha256"),
            "text_sha256": report.get("text", {}).get("sha256"),
            "gnu_build_id": report.get("elf", {}).get("build_id"),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        result = verify_profile(args.libgame, args.profile)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
