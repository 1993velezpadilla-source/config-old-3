#!/usr/bin/env python3
"""Install a signed CTW mod APK or split APK set over ADB, fail-closed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

import adb_collect
import sign_modpack

PACKAGE = "com.rockstargames.gtactw"


class InstallError(RuntimeError):
    def __init__(self, message: str, *, signature_conflict: bool = False):
        super().__init__(message)
        self.signature_conflict = signature_conflict


def find_adb(explicit: Path | None = None) -> str:
    if explicit is not None:
        if explicit.is_file():
            return str(explicit)
        raise FileNotFoundError(explicit)
    found = shutil.which("adb")
    if found:
        return found
    raise FileNotFoundError("adb not found; install Android platform-tools")


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _failure_text(proc: subprocess.CompletedProcess) -> str:
    return (proc.stderr.strip() or proc.stdout.strip() or "unknown adb failure")


def install_signed_modpack(
    source: Path,
    *,
    adb_path: Path | None = None,
    serial: str | None = None,
    grant_permissions: bool = False,
) -> dict:
    adb = find_adb(adb_path)
    selected = adb_collect.choose_serial(adb, serial)
    mode, apks = sign_modpack.collect_apks(source)

    command = [adb, "-s", selected]
    if mode == "apk":
        command += ["install", "-r"]
    else:
        command += ["install-multiple", "-r"]

    if grant_permissions:
        command.append("-g")
    command += [str(p) for p in apks]

    proc = _run(command)
    if proc.returncode != 0:
        detail = _failure_text(proc)
        conflict = (
            "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in detail
            or "signatures do not match" in detail.lower()
            or "signature mismatch" in detail.lower()
        )
        if conflict:
            raise InstallError(
                "Android rejected the mod because the installed CTW package "
                "uses a different signing certificate. The installer did not "
                "uninstall or modify the existing app/data.",
                signature_conflict=True,
            )
        raise InstallError(f"adb install failed: {detail}")

    verify = _run([
        adb,
        "-s",
        selected,
        "shell",
        "pm",
        "path",
        PACKAGE,
    ])
    if verify.returncode != 0:
        raise InstallError(
            "install command succeeded but package verification failed: "
            + _failure_text(verify)
        )

    package_paths = []
    for line in verify.stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            package_paths.append(line[len("package:"):].strip())

    if not package_paths:
        raise InstallError(
            "install command succeeded but pm path returned no CTW package paths"
        )

    return {
        "ok": True,
        "serial": selected,
        "mode": mode,
        "apk_count": len(apks),
        "package": PACKAGE,
        "installed_package_paths": package_paths,
        "grant_permissions": grant_permissions,
        "command_mode": "install" if mode == "apk" else "install-multiple",
        "note": (
            "No uninstall operation is performed automatically. A signature "
            "conflict with the official app must be resolved explicitly."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--adb", type=Path)
    ap.add_argument("--serial")
    ap.add_argument("--grant-permissions", action="store_true")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    try:
        report = install_signed_modpack(
            args.source,
            adb_path=args.adb,
            serial=args.serial,
            grant_permissions=args.grant_permissions,
        )
    except InstallError as exc:
        payload = {
            "ok": False,
            "error": str(exc),
            "signature_conflict": exc.signature_conflict,
        }
        print(json.dumps(payload, indent=2))
        return 3 if exc.signature_conflict else 2
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
