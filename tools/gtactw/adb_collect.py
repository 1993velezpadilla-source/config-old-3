#!/usr/bin/env python3
"""Collect a user-installed GTA CTW APK set over ADB and analyze it locally.

No root is assumed. The tool asks Android Package Manager for the installed APK
paths, pulls those package files, and optionally feeds the resulting directory
into analyze_apkset.py.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import analyze_apkset


DEFAULT_PACKAGE = "com.rockstargames.gtactw"


def find_adb(explicit: Path | None = None) -> str:
    if explicit is not None:
        if explicit.is_file():
            return str(explicit)
        raise FileNotFoundError(explicit)

    found = shutil.which("adb")
    if found:
        return found

    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(key)
        if not root:
            continue
        candidate = Path(root) / "platform-tools" / (
            "adb.exe" if os.name == "nt" else "adb"
        )
        if candidate.is_file():
            return str(candidate)

    raise FileNotFoundError(
        "adb not found; install Android SDK platform-tools or pass --adb"
    )


def parse_pm_path(text: str) -> list[str]:
    paths = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("package:"):
            line = line[len("package:"):]
        if not line.startswith("/"):
            continue
        if not line.endswith(".apk"):
            continue
        if line not in paths:
            paths.append(line)
    return paths


def _run(
    adb: str,
    serial: str | None,
    args: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess:
    cmd = [adb]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def connected_devices(adb: str) -> list[dict]:
    proc = subprocess.run(
        [adb, "devices", "-l"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    devices = []
    for line in proc.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        metadata = {}
        for token in parts[2:]:
            if ":" in token:
                k, v = token.split(":", 1)
                metadata[k] = v
        devices.append({
            "serial": serial,
            "state": state,
            "metadata": metadata,
        })
    return devices


def choose_serial(adb: str, requested: str | None) -> str:
    devices = connected_devices(adb)
    usable = [d for d in devices if d["state"] == "device"]

    if requested:
        for device in usable:
            if device["serial"] == requested:
                return requested
        raise RuntimeError(
            f"requested ADB serial {requested!r} is not connected/authorized"
        )

    if len(usable) == 1:
        return usable[0]["serial"]
    if not usable:
        raise RuntimeError(
            "no authorized Android device found; enable USB debugging and "
            "accept the ADB authorization prompt"
        )
    raise RuntimeError(
        "multiple authorized devices found; pass --serial explicitly"
    )


def safe_local_name(remote: str, index: int) -> str:
    name = Path(remote).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    if not name.endswith(".apk"):
        name += ".apk"
    return f"{index:02d}_{name}"


def collect_package_apks(
    adb: str,
    serial: str,
    package: str,
    out_dir: Path,
) -> dict:
    proc = _run(
        adb,
        serial,
        ["shell", "pm", "path", package],
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"pm path failed: {detail}")

    remote_paths = parse_pm_path(proc.stdout)
    if not remote_paths:
        raise RuntimeError(
            f"package {package!r} is not installed or exposes no APK paths"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    pulled = []

    for index, remote in enumerate(remote_paths):
        local = out_dir / safe_local_name(remote, index)
        pull = _run(
            adb,
            serial,
            ["pull", remote, str(local)],
            check=False,
        )
        if pull.returncode != 0 or not local.is_file():
            detail = pull.stderr.strip() or pull.stdout.strip()
            raise RuntimeError(
                f"failed to pull installed APK {remote}: {detail}"
            )
        pulled.append({
            "remote": remote,
            "local": str(local),
            "size": local.stat().st_size,
        })

    return {
        "package": package,
        "serial": serial,
        "apk_count": len(pulled),
        "apks": pulled,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", default=DEFAULT_PACKAGE)
    ap.add_argument("--serial")
    ap.add_argument("--adb", type=Path)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("./local_ctw/adb_apks"),
    )
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--reference", type=Path)
    ap.add_argument("--analysis-out", type=Path)
    ap.add_argument("--profile-out", type=Path)
    ap.add_argument("--aapt", type=Path)
    ap.add_argument("--apksigner", type=Path)
    args = ap.parse_args()

    try:
        adb = find_adb(args.adb)
        serial = choose_serial(adb, args.serial)
        manifest = collect_package_apks(
            adb,
            serial,
            args.package,
            args.out_dir,
        )

        result = {
            "ok": True,
            "collection": manifest,
            "analysis": None,
        }

        if args.analyze:
            analysis = analyze_apkset.analyze_apkset(
                args.out_dir,
                args.reference,
                args.aapt,
                args.apksigner,
            )
            result["analysis"] = analysis
            result["ok"] = bool(analysis.get("ok"))

            if args.analysis_out:
                args.analysis_out.parent.mkdir(parents=True, exist_ok=True)
                args.analysis_out.write_text(
                    json.dumps(analysis, indent=2) + "\n",
                    encoding="utf-8",
                )

            if args.profile_out and analysis.get("profile_template") is not None:
                args.profile_out.parent.mkdir(parents=True, exist_ok=True)
                args.profile_out.write_text(
                    json.dumps(
                        analysis["profile_template"],
                        indent=2,
                    ) + "\n",
                    encoding="utf-8",
                )

        if args.manifest:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )

        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
