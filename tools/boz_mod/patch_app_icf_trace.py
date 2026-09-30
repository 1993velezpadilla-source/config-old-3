#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

CHANNELS = {
    "DEFAULT": 4,
    "LOADER": 4,
    "FILE": 4,
    "RESMANAGER": 4,
    "RESMANAGER_MOUNT": 4,
    "STARTGAME": 4,
    "GAME": 4,
    "CORE": 4,
    "DEVICE": 4,
    "SURFACE": 4,
    "FLASH": 4,
    "NETWORK": 4,
    "NETWORK_ERROR": 4,
    "ONLINE": 4,
    "HTTP": 4,
    "RESDOWNLOADER": 4,
    "EXT": 4,
}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    lines = args.input.read_text(encoding="latin1").splitlines()
    out = []
    in_trace = False
    seen = set()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_trace:
                for key, value in CHANNELS.items():
                    if key not in seen:
                        out.append(f"{key}={value}")
            in_trace = stripped.upper() == "[TRACE]"
            if in_trace:
                seen = set()
            out.append(line)
            continue

        if in_trace and "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip().upper()
            if key in CHANNELS:
                out.append(f"{key}={CHANNELS[key]}")
                seen.add(key)
                continue

        if stripped.lower().startswith("splashscreenmintime="):
            out.append("SplashScreenMinTime=0")
            continue

        out.append(line)

    if in_trace:
        for key, value in CHANNELS.items():
            if key not in seen:
                out.append(f"{key}={value}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out) + "\n", encoding="latin1")
    print("XZIEL_BOZ_TRACE_CONFIG_PATCH_OK")
    for key, value in CHANNELS.items():
        print("TRACE", key, value)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
