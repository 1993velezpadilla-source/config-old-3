#!/usr/bin/env python3
"""Use only the user's already-baked original Nun 2.5D PNG artifact.

The 16-source-frame artifact was produced by real Godot render from the owner's
24-bone original model on a dedicated CI branch. Never include 3D source in
the Android runtime or replace missing images with procedural rectangles.
Only four front-facing walk PNGs are staged until visual owner approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from PIL import Image

SOURCE_RUN = 39886161142
SOURCE_ARTIFACT = "Iglesia-Real-Nun-2D-16Frames-SourceBake"
EXPECTED_DIMENSIONS = (384, 640)


def stage(artifact: Path, assets: Path) -> dict:
    frames = list(artifact.rglob("nun_*_walk_*.png"))
    expected = {f"nun_{direction}_walk_{frame:02d}.png"
                for direction in range(4) for frame in range(4)}
    available = {p.name for p in frames}
    if len(frames) != 16 or available != expected:
        raise RuntimeError(f"OWNER_NUN_ARTIFACT_INCOMPLETE {len(frames)}/16 {sorted(expected-available)}")
    target = assets / "enemies" / "gothic_nun_2d"
    target.mkdir(parents=True, exist_ok=True)
    old = list(target.glob("walk_*.png"))
    for p in old:
        p.unlink()
    hashes = {}
    for path in sorted(frames):
        payload = path.read_bytes()
        if payload[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"NUN_SPRITE_INVALID_PNG: {path.name}")
        with Image.open(path) as im:
            rgba = im.convert("RGBA")
            if rgba.size != EXPECTED_DIMENSIONS:
                raise RuntimeError(f"NUN_SPRITE_SIZE_RED: {path.name} {rgba.size}")
            extrema = rgba.getchannel("A").getextrema()
            if extrema[0] >= 255 or extrema[1] <= 0:
                raise RuntimeError(f"NUN_SPRITE_ALPHA_RED: {path.name} {extrema}")
            bounds = rgba.getchannel("A").getbbox()
            if bounds is None or (bounds[2]-bounds[0]) < 70 or (bounds[3]-bounds[1]) < 150:
                raise RuntimeError(f"NUN_SPRITE_SILHOUETTE_RED: {path.name} {bounds}")
        hashes[path.name] = hashlib.sha256(payload).hexdigest()
        # Front direction rendered against source camera; runtime uses only
        # this direction to avoid importing unnecessary alternate PNGs.
        if path.name.startswith("nun_0_"):
            name = path.name.removeprefix("nun_0_")
            shutil.copyfile(path, target / name)
            print("IGLESIA_AUTHENTIC_NUN_PNG_STAGED",name,len(payload),"bytes")
    if len(list(target.glob("walk_*.png"))) != 4:
        raise RuntimeError("NUN_PREVIEW_FOUR_WALK_FRAMES_NOT_STAGED")
    info = {
        "schema": 1, "source_workflow_run_id": SOURCE_RUN,
        "source_artifact": SOURCE_ARTIFACT,
        "artifact_frames_verified": 16, "runtime_frames_staged": 4,
        "source_is_offline_animated_owner_nun_render": True,
        "runtime_has_no_nun_mesh_or_skeleton": True,
        "preview_only": True,
        "missing_authored_roles": ["idle", "attack", "death"],
        "art_not_owner_visually_approved": True, "sha256_by_source_frame": hashes,
    }
    (target / "SOURCE_BAKE_MANIFEST.json").write_text(
        json.dumps(info,indent=2)+"\n",encoding="utf-8")
    print("IGLESIA_NUN_2D_REAL_SOURCE_PREVIEW_STAGED_NOT_FINAL",len(frames))
    return info


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--artifact",type=Path,required=True)
    cli.add_argument("--assets",type=Path,default=Path("iglesia/assets"))
    args=cli.parse_args()
    stage(args.artifact,args.assets)


if __name__=="__main__":
    main()
