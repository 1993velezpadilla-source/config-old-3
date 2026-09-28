#!/usr/bin/env python3
"""Verify and ingest a CTW Capture folder exported by the Android helper."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import aarch64_xref
import elf_probe
import plt_calls
import profile_template

TARGET_PACKAGE = "com.rockstargames.gtactw"
TARGET_VERSION_NAME = "4.4.243"
TARGET_VERSION_CODE = 4277603
TARGET_CERT_SHA256 = (
    "e8c76284d4d652f1881525853ce0aa9fe82b89e276f6204f1a7a53aef67fce19"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_file(root: Path, name: str) -> Path:
    if not name or Path(name).name != name:
        raise ValueError(f"unsafe capture file name: {name!r}")
    path = root / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def verify_capture(root: Path, allow_non_target: bool = False) -> dict:
    root = root.resolve()
    manifest_path = root / "capture_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1:
        raise ValueError("unsupported CTW Capture manifest schema")

    identity = {
        "package": manifest.get("package"),
        "version_name": manifest.get("version_name"),
        "version_code": manifest.get("version_code"),
        "exact_target_match": bool(manifest.get("exact_target_match")),
        "expected_signer_sha256": manifest.get("expected_signer_sha256"),
        "signer_sha256": list(manifest.get("signer_sha256") or []),
    }

    identity_checks = {
        "package": identity["package"] == TARGET_PACKAGE,
        "version_name": identity["version_name"] == TARGET_VERSION_NAME,
        "version_code": identity["version_code"] == TARGET_VERSION_CODE,
        "expected_signer": (
            identity["expected_signer_sha256"] == TARGET_CERT_SHA256
        ),
        "actual_signer": TARGET_CERT_SHA256 in identity["signer_sha256"],
        "capture_exact_target": identity["exact_target_match"],
    }
    exact = all(identity_checks.values())
    if not exact and not allow_non_target:
        failed = ", ".join(
            key for key, value in identity_checks.items() if not value
        )
        raise ValueError(
            "CTW Capture identity is not the verified 4.4.243 target: "
            + failed
        )

    apks = []
    for item in manifest.get("apks") or []:
        name = item.get("name")
        path = _safe_file(root, name)
        expected_size = item.get("size_bytes")
        expected_sha = str(item.get("sha256") or "").lower()
        actual_size = path.stat().st_size
        actual_sha = sha256_file(path)
        if expected_size != actual_size:
            raise ValueError(
                f"{name}: size mismatch {actual_size} != {expected_size}"
            )
        if expected_sha != actual_sha:
            raise ValueError(f"{name}: SHA-256 mismatch")
        apks.append({
            "name": name,
            "path": str(path),
            "size_bytes": actual_size,
            "sha256": actual_sha,
        })

    artifacts = {}
    for item in manifest.get("artifacts") or []:
        name = item.get("name")
        path = _safe_file(root, name)
        expected_size = item.get("size_bytes")
        expected_sha = str(item.get("sha256") or "").lower()
        actual_size = path.stat().st_size
        actual_sha = sha256_file(path)
        if expected_size != actual_size:
            raise ValueError(
                f"{name}: size mismatch {actual_size} != {expected_size}"
            )
        if expected_sha != actual_sha:
            raise ValueError(f"{name}: SHA-256 mismatch")
        artifacts[name] = {
            "path": str(path),
            "size_bytes": actual_size,
            "sha256": actual_sha,
            "source_apk": item.get("source_apk"),
            "zip_entry": item.get("zip_entry"),
        }

    if "libGame.so" not in artifacts:
        raise ValueError(
            "capture does not contain the ARM64 libGame.so analysis artifact"
        )

    return {
        "ok": True,
        "root": str(root),
        "identity": identity,
        "identity_checks": identity_checks,
        "exact_target_match": exact,
        "apks": apks,
        "artifacts": artifacts,
        "manifest_sha256": sha256_file(manifest_path),
    }


def analyze_verified_capture(verified: dict) -> dict:
    libgame = Path(verified["artifacts"]["libGame.so"]["path"])

    elf = elf_probe.inspect_elf(libgame)
    xrefs = aarch64_xref.scan_libgame(libgame)
    plt = plt_calls.scan_plt_calls(libgame)
    profile = profile_template.make_profile(elf, xrefs, plt)

    return {
        "libgame": elf,
        "arm64_xrefs": xrefs,
        "plt_calls": plt,
        "profile_template": profile,
        "six_hook_rankings": profile.get("target_evidence_rankings", {}),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_dir", type=Path)
    ap.add_argument("--allow-non-target", action="store_true")
    ap.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify manifest/files without running ARM64 analysis",
    )
    ap.add_argument("--out", type=Path)
    ap.add_argument("--profile-out", type=Path)
    args = ap.parse_args()

    try:
        verified = verify_capture(
            args.capture_dir,
            allow_non_target=args.allow_non_target,
        )
        report = {
            "ok": True,
            "capture": verified,
            "analysis": None,
        }
        if not args.verify_only:
            report["analysis"] = analyze_verified_capture(verified)
    except Exception as exc:
        report = {"ok": False, "error": str(exc)}

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    if (
        args.profile_out
        and report.get("ok")
        and report.get("analysis")
        and report["analysis"].get("profile_template")
    ):
        args.profile_out.parent.mkdir(parents=True, exist_ok=True)
        args.profile_out.write_text(
            json.dumps(report["analysis"]["profile_template"], indent=2)
            + "\n",
            encoding="utf-8",
        )

    print(payload)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
