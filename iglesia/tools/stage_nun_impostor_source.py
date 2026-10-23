#!/usr/bin/env python3
"""Prepare exact original (not AI-generated) animated Nun for 2.5D bake.

Input exists in this user's own church GitHub repository and includes FIVE
genuine authored zombie clips on a 24-bone skeleton. This tool copies only
temporary original source assets for an OFFLINE screenshot-to-sprite bake.
A published Android APK must include the baked sprites, NEVER the original
2-million-triangle source GLTF/92MB BIN.
"""
from __future__ import annotations
from pathlib import Path
from shutil import copyfile
import hashlib, json

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "xogot/assets/zombies/monja_clean/clean_runtime"
TARGET = REPO / "iglesia/assets/zombies/_bake_source"
GIT_SHAS = {
    "monja_basica_clean_rig.gltf":"2502f97e95fc5f7a4e7a5b1ea938117172669d46",
    "monja_basica_clean_rig.bin":"890b4e90a3cdac822226b83d8861005e019b23e9",
    "baseColor_1.jpg":"1aa4680222e8210be327f0df801f32d06fda797a",
    "normal_1.png":"ab967fb91608177b17069332ef72891d508eac80",
    "metallicRoughness_1.jpg":"93979713def871dd62df3c7848732557e2a49fec",
}
def main() -> None:
    TARGET.mkdir(parents=True,exist_ok=True)
    results={}
    for name,expected in GIT_SHAS.items():
        old=SOURCE/name
        if not old.is_file():
            raise FileNotFoundError("IGLESIA_NUN_BAKE_SOURCE_MISSING: "+name)
        blob=old.read_bytes()
        sha=hashlib.sha1(f"blob {len(blob)}\0".encode()+blob).hexdigest()
        if sha!=expected:
            raise RuntimeError(f"IGLESIA_NUN_BAKE_ORIGINAL_SHA_RED {name} {sha}")
        copyfile(old,TARGET/name)
        results[name]={"bytes":len(blob),"git_sha":sha}
    source=json.loads((TARGET/"monja_basica_clean_rig.gltf").read_text())
    clips=[str(a.get("name","")) for a in source.get("animations",[])]
    if len(source.get("skins",[]))<1 or len(clips)<5 or not any("Walk" in x for x in clips):
        raise RuntimeError("IGLESIA_NUN_SOURCE_3D_RIG_AND_WALK_REQUIRED")
    print("IGLESIA_USER_ORIGINAL_ANIMATED_NUN_SOURCE_READY",
          "bone_joints",len(source["skins"][0]["joints"]), "clips",clips)
    (TARGET/"authority.json").write_text(json.dumps(
      {"schema":1,"owner_original":True,"source_files":results,
       "clips":clips, "source_copy_only":True,
       "android_runtime_must_never_use_this_directory":True},indent=2)+"\n")
if __name__=="__main__":
    main()
