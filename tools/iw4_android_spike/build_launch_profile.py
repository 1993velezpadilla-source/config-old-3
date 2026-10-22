#!/usr/bin/env python3
"""Build a non-proprietary Android compatibility launch profile for IW4.

Consumes the manifest emitted by prepare_owned_install.py. The output contains
only paths/settings/arguments and can be stored safely when paths are redacted.
It never copies or bundles game files.
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path


SUPPORTED_BACKENDS = ("winlator", "hangover")


def build_profile(manifest: dict, backend: str, direct_map: bool) -> dict:
    if backend not in SUPPORTED_BACKENDS:
        raise ValueError(f"unsupported backend: {backend}")

    exe = manifest.get("executable", {})
    if exe.get("machineName") != "x86" or exe.get("peKind") != "PE32":
        raise ValueError(
            "IW4 Android spike expects the Windows runtime to be PE32/x86"
        )

    root = Path(manifest["gameRoot"])
    executable = root / exe.get("name", "iw4mp.exe")
    map_name = manifest.get("churchMapName", "xziel_sanctum")

    # Keep the first boot minimal. Map launch is enabled only when the validator
    # already confirmed that the usermap directory exists.
    game_args = ["-nointro"]
    if direct_map:
        if not manifest.get("churchMapPresent", False):
            raise ValueError(
                f"direct map launch requested but usermap {map_name!r} is absent"
            )
        game_args.extend(["+map", map_name])

    common = {
        "schema": 1,
        "runtime": "IW4",
        "backend": backend,
        "architecture": {
            "guest": "x86",
            "host": "arm64",
        },
        "game": {
            "workingDirectory": str(root),
            "executable": str(executable),
            "arguments": game_args,
            "map": map_name if direct_map else None,
        },
        "graphics": {
            "guestApi": "Direct3D9",
            "translation": "DXVK",
            "hostApi": "Vulkan",
        },
        "acceptance": {
            "requireRenderer": True,
            "requireMapLoad": direct_map,
            "minimumAliveSeconds": 60,
            "captureLog": True,
            "captureScreenshot": True,
        },
        "redistributeGamePayload": False,
    }

    if backend == "winlator":
        common["compatibility"] = {
            "wine": True,
            "x86Translation": "Box86/Box64-compatible",
            "containerMode": "per-game",
        }
    else:
        common["compatibility"] = {
            "wine": True,
            "x86Translation": "Hangover i386-on-aarch64",
            "containerMode": "WoW64",
        }

    # Useful for humans/tools without prescribing a particular Android app UI.
    common["previewCommand"] = " ".join(
        [shlex.quote(str(executable))]
        + [shlex.quote(arg) for arg in game_args]
    )
    return common


def redact_profile(profile: dict) -> dict:
    result = json.loads(json.dumps(profile))
    result["game"]["workingDirectory"] = "<OWNED_MW2_ROOT>"
    exe_name = Path(result["game"]["executable"]).name
    result["game"]["executable"] = f"<OWNED_MW2_ROOT>/{exe_name}"
    args = result["game"]["arguments"]
    result["previewCommand"] = " ".join(
        [result["game"]["executable"]]
        + [shlex.quote(arg) for arg in args]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--backend", choices=SUPPORTED_BACKENDS, default="winlator"
    )
    parser.add_argument("--direct-map", action="store_true")
    parser.add_argument("--redact-paths", action="store_true")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    profile = build_profile(manifest, args.backend, args.direct_map)
    if args.redact_paths:
        profile = redact_profile(profile)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(profile, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(profile, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
