#!/usr/bin/env python3
"""Zipalign, sign and verify a CTW mod APK or split-APK output set."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import apk_identity


def find_build_tool(name: str, explicit: Path | None = None) -> str:
    if explicit is not None:
        if explicit.is_file():
            return str(explicit)
        raise FileNotFoundError(explicit)

    found = shutil.which(name)
    if found:
        return found

    roots = []
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(key)
        if value:
            roots.append(Path(value))

    exe = name + (".exe" if os.name == "nt" else "")
    for root in roots:
        build_tools = root / "build-tools"
        if not build_tools.is_dir():
            continue
        for version in sorted(
            (p for p in build_tools.iterdir() if p.is_dir()),
            reverse=True,
        ):
            candidate = version / exe
            if candidate.is_file():
                return str(candidate)

    raise FileNotFoundError(
        f"{name} not found; install Android SDK build-tools or pass --{name}"
    )


def collect_apks(source: Path) -> tuple[str, list[Path]]:
    if source.is_file():
        if source.suffix.lower() != ".apk":
            raise ValueError("single input must be an .apk file")
        return "apk", [source]

    if source.is_dir():
        apks = sorted(
            p for p in source.iterdir()
            if p.is_file() and p.suffix.lower() == ".apk"
        )
        if not apks:
            raise ValueError("input directory contains no APK files")
        return "apkset", apks

    raise FileNotFoundError(source)


def _run(command: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"command failed ({proc.returncode}): {command[0]}: {detail}"
        )
    return proc


def _sign_one(
    source: Path,
    destination: Path,
    *,
    zipalign: str,
    apksigner: str,
    keystore: Path,
    alias: str,
    ks_pass_env: str,
    key_pass_env: str,
    temp_root: Path,
) -> dict:
    aligned = temp_root / f"{source.stem}.aligned.apk"

    _run([
        zipalign,
        "-P", "16",
        "-f",
        "4",
        str(source),
        str(aligned),
    ])

    _run([
        apksigner,
        "sign",
        "--ks", str(keystore),
        "--ks-key-alias", alias,
        "--ks-pass", f"env:{ks_pass_env}",
        "--key-pass", f"env:{key_pass_env}",
        "--out", str(destination),
        str(aligned),
    ])

    verify = _run([
        apksigner,
        "verify",
        "--verbose",
        "--print-certs",
        str(destination),
    ])
    cert = apk_identity.parse_apksigner_certs(verify.stdout)

    return {
        "input_apk": str(source),
        "signed_apk": str(destination),
        "certificate": cert,
    }


def sign_modpack(
    source: Path,
    output: Path,
    *,
    keystore: Path,
    alias: str,
    ks_pass_env: str = "CTW_KEYSTORE_PASS",
    key_pass_env: str = "CTW_KEY_PASS",
    zipalign_path: Path | None = None,
    apksigner_path: Path | None = None,
) -> dict:
    if not keystore.is_file():
        raise FileNotFoundError(keystore)
    if not alias.strip():
        raise ValueError("keystore alias is required")
    if not os.environ.get(ks_pass_env):
        raise ValueError(f"environment variable {ks_pass_env} is not set")
    if not os.environ.get(key_pass_env):
        raise ValueError(f"environment variable {key_pass_env} is not set")

    mode, apks = collect_apks(source)
    zipalign = find_build_tool("zipalign", zipalign_path)
    apksigner = find_build_tool("apksigner", apksigner_path)

    if mode == "apk":
        output.parent.mkdir(parents=True, exist_ok=True)
    else:
        output.mkdir(parents=True, exist_ok=True)

    signed = []
    with tempfile.TemporaryDirectory(prefix="ctw-sign-") as td:
        temp_root = Path(td)
        for apk in apks:
            destination = (
                output
                if mode == "apk"
                else output / apk.name
            )
            signed.append(
                _sign_one(
                    apk,
                    destination,
                    zipalign=zipalign,
                    apksigner=apksigner,
                    keystore=keystore,
                    alias=alias,
                    ks_pass_env=ks_pass_env,
                    key_pass_env=key_pass_env,
                    temp_root=temp_root,
                )
            )

    cert_pairs = {
        (
            item["certificate"]["sha1"],
            item["certificate"]["sha256"],
        )
        for item in signed
    }
    if len(cert_pairs) != 1:
        raise RuntimeError(
            "signed APK set does not share one certificate identity"
        )

    cert = signed[0]["certificate"]
    return {
        "ok": True,
        "mode": mode,
        "source": str(source),
        "output": str(output),
        "apk_count": len(signed),
        "certificate": cert,
        "signed_apks": signed,
        "tools": {
            "zipalign": zipalign,
            "apksigner": apksigner,
        },
        "next_step": (
            "Install the signed APK"
            if mode == "apk"
            else "Install all signed APKs together with adb install-multiple"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--keystore", type=Path, required=True)
    ap.add_argument("--alias", required=True)
    ap.add_argument("--ks-pass-env", default="CTW_KEYSTORE_PASS")
    ap.add_argument("--key-pass-env", default="CTW_KEY_PASS")
    ap.add_argument("--zipalign", type=Path)
    ap.add_argument("--apksigner", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    try:
        report = sign_modpack(
            args.source,
            args.out,
            keystore=args.keystore,
            alias=args.alias,
            ks_pass_env=args.ks_pass_env,
            key_pass_env=args.key_pass_env,
            zipalign_path=args.zipalign,
            apksigner_path=args.apksigner,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
