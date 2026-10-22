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


# Authentic, authored MP40 and animated first-person hands recovered from
# this user's existing GitHub project. No image generation, no fake sprites.
NUN_MP40_FILES = {
    "gun.glb": ("xogot/assets/weapons/aether_waw_real/mp40/viewmodel.glb", "d6344a545d5e46125fb26add71436df0725c5437"),
    "viewhands.glb": ("xogot/assets/weapons/aether_waw_hands/t4_marine/mp40/viewhands.glb", "fe1b0735cd4b768ae3a6bfeb731fc61050cdb1f2"),
    "gun_color.png": ("xogot/assets/weapons/aether_waw_textures/weapon_mp40_c.png", "1e0b3090a85a01b729c7708ac7adfbf0aa535215"),
    "hands_atlas.png": ("xogot/assets/weapons/aether_waw_hands/t4_marine/common/textures/viewmodel_usa_marine_c.png", "91d95e6b711258c048768234dae9e6e71c86952d"),
}

def stage_nun_mp40_source() -> None:
    import struct
    source_dir = ASSETS / "weapons" / "mp40_nun"
    source_dir.mkdir(parents=True, exist_ok=True)
    evidence = {"protagonist":"selected dark Nun", "model_files":{}, "source_geometry_unmodified": True,
                "look":"black habit, pale skin, ink-shaded gothic gun", "final_bare_hands_qa":False}
    for target,(path,expected) in NUN_MP40_FILES.items():
        original = ROOT / path
        if not original.is_file():
            raise RuntimeError("NUN_GUN_GITHUB_ORIGINAL_MISSING "+path)
        payload = original.read_bytes()
        if git_sha(payload) != expected:
            raise RuntimeError("NUN_GUN_GITHUB_ORIGINAL_HASH_RED "+path)
        out = source_dir / target
        out.write_bytes(payload)
        metadata = {"source":path,"git_sha":expected,"bytes":len(payload)}
        if target.endswith(".glb"):
            if payload[:4] != b"glTF":
                raise RuntimeError("NUN_MP40_BAD_GLB "+target)
            size,kind=struct.unpack_from("<II",payload,12)
            if kind!=0x4E4F534A:
                raise RuntimeError("NUN_MP40_BAD_GLB_JSON "+target)
            doc=json.loads(payload[20:20+size])
            names=[str(a.get("name","")).lower() for a in doc.get("animations",[])]
            if not doc.get("meshes") or not doc.get("skins") or not names:
                raise RuntimeError("NUN_MP40_MODEL_UNRIGGED "+target)
            for role in ["idle","fire","reload"]:
                if not any(role in name for name in names):
                    raise RuntimeError("NUN_MP40_REQUIRED_SOURCE_ANIM_MISSING "+target+" "+role)
            metadata.update({"meshes":len(doc["meshes"]),"skins":len(doc["skins"]),"animations":names})
        evidence["model_files"][target]=metadata
        print("IGLESIA_NUN_AUTHORED_SOURCE_GREEN",target,len(payload))
    (source_dir/"manifest.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")

def main() -> None:
    if not (ROOT / "xogot/assets/environment/church/altar.glb").exists():
        print("Run from full config-old-3 checkout on the church-art source branch.", file=sys.stderr)
        raise SystemExit(2)
    stage_local_art()
    from stage_tripo_fixtures import stage_fixtures
    stage_fixtures(ROOT, ASSETS, git_sha)
    stage_hud()
    stage_nun_mp40_source()
    # Rejected PNG atlas is kept ONLY as an emergency fallback for import
    # testing; the gameplay HUD switches it off when the real 3D rig loads.
    stage_mp40()
    from optimize_mobile_assets import apply_mobile_texture_budget
    apply_mobile_texture_budget(ASSETS)
    print("IGLESIA_OWNER_ART_STAGED: true; VISUAL_RENDER_AND_APK_NOT_YET_VALIDATED")

if __name__ == "__main__":
    main()
