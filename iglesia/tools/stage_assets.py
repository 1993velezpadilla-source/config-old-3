#!/usr/bin/env python3
"""Stage ONLY approved art into standalone Iglesia. No old engine/code is copied."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]  # parent repository checkout
PROJECT = ROOT / "iglesia"
SOURCES = json.loads((PROJECT / "assets/SOURCES.json").read_text(encoding="utf-8"))
ASSETS = PROJECT / "assets"

def git_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()

def check(data: bytes, expected: str, path: str) -> None:
    actual = git_sha(data)
    if actual != expected:
        raise RuntimeError(f"SOURCE_HASH_RED {path}: {actual} != {expected}")

def fetch(owner_repo: str, revision: str, path: str) -> bytes:
    # Raw GitHub is used only for owner-approved original art from pinned refs.
    escaped = "/".join(urllib.parse.quote(s, safe="") for s in path.split("/"))
    url = f"https://raw.githubusercontent.com/{owner_repo}/{revision}/{escaped}"
    request = urllib.request.Request(url, headers={"User-Agent": "Iglesia-source-audit/1.0"})
    with urllib.request.urlopen(request, timeout=100) as response:
        return response.read()

def stage_local_art() -> None:
    for destination, source in SOURCES["church_art"]["items"].items():
        src = ROOT / source["source"]
        if not src.is_file():
            raise FileNotFoundError(f"CHURCH_ASSET_MISSING: {src}")
        data = src.read_bytes()
        check(data, source["git_blob_sha"], str(src))
        dst = ASSETS / destination
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        print(f"ART_GREEN {destination} {len(data)} bytes")

def stage_hud() -> None:
    cfg = SOURCES["hud"]
    folder = ASSETS / "hud"
    folder.mkdir(parents=True, exist_ok=True)
    for name in cfg["names"]:
        blob = fetch(cfg["repo"], cfg["commit"], f'{cfg["path"]}/{name}')
        if blob[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"HUD_PNG_RED: {name}")
        (folder / name).write_bytes(blob)
        print(f"HUD_APPROVED_GREEN {name}")

def stage_mp40() -> None:
    from PIL import Image
    cfg = SOURCES["mp40"]
    folder = ASSETS / "weapons" / "mp40"
    folder.mkdir(parents=True, exist_ok=True)
    blob = fetch(cfg["repo"], cfg["commit"], cfg["path"])
    check(blob, "ec99d9508409ff9e16afc481c919ef1fd3ca36be", cfg["path"])
    sheet_path = folder / "owner_original_sheet.png"
    sheet_path.write_bytes(blob)
    sheet = Image.open(sheet_path).convert("RGBA")
    if list(sheet.size) != cfg["size"]:
        raise RuntimeError(f"MP40_DIMENSIONS_RED {sheet.size}")
    width, height = sheet.size
    for index, label in enumerate(cfg["frames"]):
        col, row = index % 3, index // 3
        x0 = round(col * width / 3)
        x1 = round((col + 1) * width / 3)
        # Labels are in the bottom 36 pixels of each 362-pixel cell.
        frame = sheet.crop((x0, row * 362, x1, row * 362 + 326))
        alpha = frame.getchannel("A")
        if not alpha.getbbox() or alpha.getextrema()[0] >= 250:
            raise RuntimeError(f"MP40_ALPHA_RED: {label} (no valid transparency)")
        frame.save(folder / f"{label}.png")
        print(f"MP40_SOURCE_FRAME_GREEN {label} {frame.size}")

def main() -> None:
    if not (ROOT / "xogot/assets/environment/church/altar.glb").exists():
        print("Run from full config-old-3 checkout on the church-art source branch.", file=sys.stderr)
        raise SystemExit(2)
    stage_local_art()
    stage_hud()
    stage_mp40()
    print("IGLESIA_OWNER_ART_STAGED: true; VISUAL_RENDER_AND_APK_NOT_YET_VALIDATED")

if __name__ == "__main__":
    main()
