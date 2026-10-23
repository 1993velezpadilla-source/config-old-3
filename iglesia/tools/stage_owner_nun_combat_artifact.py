#!/usr/bin/env python3
"""Stage only 20 offline-rendered source-authentic Nun PNGs into Iglesia.

The owner-authored five-clip 24-bone skeleton is used only in an isolated
Godot CI bake (run 39899606644). Its meshes, textures and GLTF never ship
in the phone APK. RGBA pixels and frame identity are validated before import.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops

EXPECTED={"idle":2,"walk":4,"attack":6,"death":8}
SOURCE_RUN_ID=39899606644
SOURCE_ARTIFACT="Iglesia-Original-Nun-2D-20CombatFrames"

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--artifact",type=Path,required=True)
    ap.add_argument("--assets",type=Path,default=Path("iglesia/assets"))
    args=ap.parse_args()
    root=args.artifact
    dest=args.assets/"enemies"/"gothic_nun_2d"
    dest.mkdir(parents=True,exist_ok=True)
    paths=sorted(root.rglob("*.png"))
    expected={f"{role}_{i:02d}.png" for role,count in EXPECTED.items() for i in range(count)}
    matching={p.name:p for p in paths if p.name in expected}
    if set(matching)!=expected or len(paths)!=20:
        raise ValueError("IGLESIA_COMBAT_AUTHORED_PNG_COUNT_RED "+str(sorted(expected-set(matching))))
    hashes={}
    for role,count in EXPECTED.items():
        imgs=[]
        for i in range(count):
            name=f"{role}_{i:02d}.png"
            path=matching[name]
            payload=path.read_bytes()
            with Image.open(path) as obj:
                frame=obj.convert("RGBA")
                if frame.size!=(384,640):
                    raise ValueError("NUN_SPRITE_DIMENSIONS_RED "+name)
                alpha=frame.getchannel("A")
                if alpha.getextrema()[0]>=255 or alpha.getbbox() is None:
                    raise ValueError("NUN_SPRITE_ALPHA_RED "+name)
                imgs.append(frame.copy())
            hashes[name]=hashlib.sha256(payload).hexdigest()
            (dest/name).write_bytes(payload)
        if role in ("attack","death"):
            changed=sum(ImageChops.difference(imgs[0],x).getbbox() is not None for x in imgs[1:])
            if changed < 2:
                raise ValueError("NUN_SOURCE_STATIC_COMBAT_CLIP_RED "+role)
        print("IGLESIA_NUN_REAL_SOURCE_ROLE_GREEN",role,count)
    (dest/"AUTHORED_SOURCE_MANIFEST.json").write_text(json.dumps({
        "schema":2,"origin":"original user-owned animated 24-bone Gothic Nun",
        "source_run":SOURCE_RUN_ID,"artifact":SOURCE_ARTIFACT,
        "frame_counts":EXPECTED,"total_frames":20,
        "offline_bake_only":True,"model3d_shipped_in_android":False,
        "visual_style_still_pending_owner_approval":True,
        "sha256":hashes,
    },indent=2)+"\n")
    print("IGLESIA_REAL_NUN_ATTACK_DEATH_2D_STAGED_GREEN total=20")

if __name__=="__main__":
    main()
