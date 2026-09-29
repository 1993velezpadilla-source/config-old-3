#!/usr/bin/env python3
"""Inspect a Windows-distributed World at War custom-map installer.

The tool never executes the installer. It identifies the PE header, hashes the
file, asks 7-Zip for embedded members when possible, and classifies payload
types that are useful to the XZIEL map-import pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import subprocess
from collections import Counter


MACHINE_NAMES = {
    0x014C: "x86",
    0x8664: "x86_64",
    0xAA64: "arm64",
}

INTERESTING_SUFFIXES = {
    ".ff": "fastfile",
    ".iwd": "iwd_archive",
    ".bsp": "bsp",
    ".dll": "dll",
    ".exe": "exe",
    ".cfg": "config",
    ".gsc": "script",
    ".csc": "client_script",
    ".csv": "csv",
    ".wav": "audio",
    ".mp3": "audio",
}


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_pe(path: pathlib.Path) -> dict:
    with path.open("rb") as handle:
        mz = handle.read(64)
        if len(mz) < 64 or mz[:2] != b"MZ":
            return {"isPE": False}
        pe_offset = struct.unpack_from("<I", mz, 0x3C)[0]
        handle.seek(pe_offset)
        signature = handle.read(4)
        if signature != b"PE\0\0":
            return {"isPE": False, "mz": True}
        coff = handle.read(20)
        if len(coff) != 20:
            return {"isPE": False, "mz": True, "peSignature": True}
        machine, sections, timestamp, _, _, optional_size, characteristics = (
            struct.unpack("<HHIIIHH", coff)
        )
        return {
            "isPE": True,
            "machine": MACHINE_NAMES.get(machine, hex(machine)),
            "machineRaw": machine,
            "sections": sections,
            "timestamp": timestamp,
            "optionalHeaderBytes": optional_size,
            "characteristics": characteristics,
        }


def seven_zip_members(path: pathlib.Path) -> tuple[list[str], str | None]:
    try:
        proc = subprocess.run(
            ["7z", "l", "-slt", str(path)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        return [], "7z not installed"

    if proc.returncode != 0:
        tail = "\n".join(proc.stdout.splitlines()[-12:])
        return [], f"7z exit={proc.returncode}: {tail}"

    members = []
    in_listing = False
    for line in proc.stdout.splitlines():
        if line.startswith("----------"):
            in_listing = True
            continue
        if in_listing and line.startswith("Path = "):
            value = line[7:].strip().replace("\\", "/")
            if value:
                members.append(value)
    return members, None


def classify(members: list[str]) -> dict:
    counts: Counter[str] = Counter()
    interesting = []
    for member in members:
        suffix = pathlib.PurePosixPath(member).suffix.lower()
        kind = INTERESTING_SUFFIXES.get(suffix)
        if kind:
            counts[kind] += 1
            interesting.append({"path": member, "kind": kind})
    return {
        "counts": dict(sorted(counts.items())),
        "interesting": interesting[:1000],
        "interestingTruncated": len(interesting) > 1000,
        "hasWaWPayload": bool(counts["fastfile"] or counts["iwd_archive"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args()

    path = args.installer.resolve()
    if not path.is_file():
        raise SystemExit(f"installer not found: {path}")

    members, archive_error = seven_zip_members(path)
    report = {
        "format": "xziel_waw_exe_probe_v1",
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "pe": inspect_pe(path),
        "archive": {
            "memberCount": len(members),
            "error": archive_error,
        },
        "payload": classify(members),
    }

    encoded = json.dumps(report, indent=2, sort_keys=True)
    print(encoded)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
