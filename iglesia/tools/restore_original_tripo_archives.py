#!/usr/bin/env python3
"""Reconstitute original user-owned Tripo church archives from SHA-locked git blobs.
This is the exact same private GitHub binary-art strategy used for altar/benches,
with original ZIP bytes split into <2 MiB Git blobs for connector safety.
No synthetic models or fallback art. Full restoration required before Android export.
"""
from __future__ import annotations
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARTS = ROOT / "iglesia/source_tripo_packs/.parts"
OUT = ROOT / "iglesia/source_tripo_packs"
CONFIG = ROOT / "iglesia/tools/ORIGINAL_TRIPO_BINARY_PARTS.json"

def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()

def main() -> None:
    catalog = json.loads(CONFIG.read_text(encoding="utf-8"))
    if catalog.get("schema") != 1 or len(catalog.get("archives", {})) != 8:
        raise RuntimeError("IGLESIA_REAL_TRIPO_8_ARCHIVE_MANIFEST_INVALID")
    OUT.mkdir(parents=True, exist_ok=True)
    preview = os.environ.get("IGLESIA_TRIPO_FIRSTROOM_PREVIEW", "0") == "1"
    wanted = ("chandeliers.zip", "candleholders.zip") if preview else tuple(catalog["archives"])
    rebuilt = 0
    for filename in wanted:
        item = catalog["archives"][filename]
        if filename != Path(filename).name or not filename.endswith(".zip"):
            raise RuntimeError("TRIPO_ARCHIVE_NAME_REJECTED " + filename)
        target = OUT / filename
        tmp = OUT / (filename + ".verified.tmp")
        total = 0
        digest = hashlib.sha256()
        with tmp.open("wb") as destination:
            for part in item["parts"]:
                chunk = PARTS / part["name"]
                if not chunk.is_file():
                    raise RuntimeError("ORIGINAL_TRIPO_BINARY_PART_MISSING " + str(chunk))
                payload = chunk.read_bytes()
                if len(payload) != part["bytes"]:
                    raise RuntimeError("ORIGINAL_TRIPO_PART_LENGTH_RED " + chunk.name)
                if git_blob_sha(payload) != part["git_blob_sha"]:
                    raise RuntimeError("ORIGINAL_TRIPO_PART_GITSHA_RED " + chunk.name)
                destination.write(payload)
                digest.update(payload)
                total += len(payload)
        if total != item["bytes"] or digest.hexdigest() != item["sha256"]:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("ORIGINAL_TRIPO_REBUILT_SHA256_RED " + filename)
        tmp.replace(target)
        rebuilt += 1
        print("ORIGINAL_TRIPO_ARCHIVE_REBUILT_GREEN", filename, total, digest.hexdigest())
    if rebuilt != len(wanted):
        raise RuntimeError("ORIGINAL_TRIPO_ARCHIVES_REBUILT_INCOMPLETE")
    if preview:
        print("IGLESIA_TRIPO_2_REAL_FIRSTROOM_ZIPS_RESTORED_FROM_GITHUB_GREEN")
    else:
        print("IGLESIA_TRIPO_8_GENUINE_ZIPS_RESTORED_FROM_GITHUB_GREEN")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("IGLESIA_RESTORE_RED:", error, file=sys.stderr)
        raise
