#!/usr/bin/env python3
"""Read and validate Android APK identity for the CTW mod target.

Uses Android SDK build-tools (aapt/aapt2) for binary AndroidManifest.xml.
No proprietary data is extracted.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


PACKAGE_RE = re.compile(
    r"^package:\s+name='([^']+)'\s+versionCode='([^']+)'\s+versionName='([^']+)'",
    re.MULTILINE,
)
SDK_RE = re.compile(r"^sdkVersion:'([^']+)'", re.MULTILINE)
TARGET_SDK_RE = re.compile(r"^targetSdkVersion:'([^']+)'", re.MULTILINE)
NATIVE_RE = re.compile(r"^native-code:\s+(.+)$", re.MULTILINE)
QUOTED_RE = re.compile(r"'([^']+)'")


def parse_badging(text: str) -> dict:
    pkg = PACKAGE_RE.search(text)
    if not pkg:
        raise ValueError("aapt output is missing package/version identity")

    sdk = SDK_RE.search(text)
    target = TARGET_SDK_RE.search(text)
    native = NATIVE_RE.search(text)
    abis = QUOTED_RE.findall(native.group(1)) if native else []

    version_code_raw = pkg.group(2)
    try:
        version_code = int(version_code_raw, 10)
    except ValueError:
        raise ValueError(f"invalid versionCode: {version_code_raw!r}")

    return {
        "package": pkg.group(1),
        "version_code": version_code,
        "version_name": pkg.group(3),
        "min_sdk": sdk.group(1) if sdk else None,
        "target_sdk": target.group(1) if target else None,
        "native_code": abis,
    }


def _sdk_candidates() -> list[Path]:
    roots = []
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(key)
        if value:
            roots.append(Path(value))

    candidates = []
    for root in roots:
        build_tools = root / "build-tools"
        if build_tools.is_dir():
            versions = sorted(
                (p for p in build_tools.iterdir() if p.is_dir()),
                reverse=True,
            )
            for version in versions:
                candidates += [version / "aapt2", version / "aapt"]
    return candidates


def find_aapt(explicit: Path | None = None) -> str:
    if explicit is not None:
        if explicit.is_file():
            return str(explicit)
        raise FileNotFoundError(explicit)

    for name in ("aapt2", "aapt"):
        found = shutil.which(name)
        if found:
            return found

    for candidate in _sdk_candidates():
        if candidate.is_file():
            return str(candidate)

    raise FileNotFoundError(
        "Android aapt/aapt2 not found; install Android SDK build-tools"
    )


def inspect_apk_identity(apk: Path, aapt: Path | None = None) -> dict:
    if not apk.is_file():
        raise FileNotFoundError(apk)

    tool = find_aapt(aapt)
    proc = subprocess.run(
        [tool, "dump", "badging", str(apk)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"aapt dump badging failed: {detail}")

    out = parse_badging(proc.stdout)
    out["aapt"] = tool
    return out


def validate_reference(identity: dict, reference: dict) -> dict:
    ref = reference["reference_build"]
    target = reference["android_mod_target"]
    expected_package = reference["package"]

    checks = {
        "package": identity.get("package") == expected_package,
        "version_name": identity.get("version_name") == ref["version_name"],
        "version_code": identity.get("version_code") == ref["version_code"],
        "arm64": target["preferred_abi"] in identity.get("native_code", []),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "expected": {
            "package": expected_package,
            "version_name": ref["version_name"],
            "version_code": ref["version_code"],
            "preferred_abi": target["preferred_abi"],
        },
        "actual": identity,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", type=Path)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--aapt", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--allow-mismatch", action="store_true")
    args = ap.parse_args()

    try:
        identity = inspect_apk_identity(args.apk, args.aapt)
        reference = json.loads(args.reference.read_text(encoding="utf-8"))
        report = validate_reference(identity, reference)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)

    return 0 if report["ok"] or args.allow_mismatch else 1


if __name__ == "__main__":
    raise SystemExit(main())
