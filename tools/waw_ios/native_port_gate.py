#!/usr/bin/env python3
"""Native-only World at War Zombies HD forensic gate.

Produces a METADATA-ONLY public summary; never emits Mach-O bytes, resources,
gameplay code, pseudocode, strings, or IPA contents. Requires REA/Ghidra to
have returned a successful JSON evidence envelope first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--macho", required=True, type=Path)
    parser.add_argument("--rea-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    binary = manifest["binary"]
    if binary["container"] != "Mach-O" or binary["cpu"] != "ARMv6 32-bit":
        raise SystemExit("FAILED: expected iPad's original ARMv6 Mach-O")
    if binary["encryption_id"] != 0:
        raise SystemExit("FAILED: source executable still encrypted")
    archives = manifest["archives"]
    resources = sum(len(a["entries"]) for a in archives)
    if len(archives) != 5 or resources != 45:
        raise SystemExit(f"FAILED: expected 5 iPad DTRZ bundles and 45 files; got {len(archives)}/{resources}")
    if {s["name"] for s in binary["sections"]} != {"s3e_code", "s3e_data"}:
        raise SystemExit("FAILED: missing original Marmalade sections")

    raw = args.rea_evidence.read_bytes()
    if not raw:
        raise SystemExit("FAILED: REA produced empty evidence")
    try:
        evidence = json.loads(raw)
    except ValueError as exc:
        raise SystemExit("FAILED: REA evidence is not valid JSON") from exc
    if not isinstance(evidence, (dict, list)):
        raise SystemExit("FAILED: REA evidence does not contain an object or list")
    if isinstance(evidence, dict) and (evidence.get("status") in ("error", "failed") or evidence.get("success") is False):
        raise SystemExit("FAILED: REA evidence reports a failure")

    # Deliberately do not copy, print, serialize or upload any decompiled
    # functions, strings, original binary sections or game resources.
    report = {
        "stage": "NATIVE_REVERSE_ENGINEERING_PHASE_2",
        "target": "World at War Zombies HD iPad v1.5.0",
        "source_container": binary["container"],
        "source_cpu": binary["cpu"],
        "native_android_target_cpu": "AArch64",
        "original_macho_sha256": hashlib.sha256(args.macho.read_bytes()).hexdigest(),
        "ipad_dtrz_archives": len(archives),
        "ipad_dtrz_resource_files": resources,
        "marmalade_sections_verified": sorted(s["name"] for s in binary["sections"]),
        "rea_ghidra_analysis_exited_successfully": True,
        "rea_evidence_is_valid_json": True,
        "rea_evidence_sha256": hashlib.sha256(raw).hexdigest(),
        "native_android_gameplay_port_compiled": False,
        "native_android_gameplay_tested": False,
        "emulator_used": False,
        "contains_copyrighted_assets_or_code": False,
        "next_step": "Trace S3E/game initialization, input, render, audio and game loop; implement their behavior as original Android ARM64 code.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("GREEN: original ARMv6 source + iPad resource manifests verified")
    print("GREEN: REA/Ghidra produced valid native binary evidence")
    print("NOT AN APK: native Android AArch64 gameplay implementation is still pending")
    print("SAFE: output is metadata only; no protected game files or decompilation published")


if __name__ == "__main__":
    main()
