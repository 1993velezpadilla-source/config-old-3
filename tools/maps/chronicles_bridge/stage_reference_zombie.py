#!/usr/bin/env python3
"""Bridge already-decoded Nacht UE4.21 workshop zombie rig into a Godot test scene.

Runs only in a temporary CI workspace. Never commits third-party model bytes.
Original first-party BO3/T7 provenance is NOT claimed.
"""
import argparse
import json
from pathlib import Path
from xz_skeletal_library_to_gltf import build_one

def report(root, name):
    hits=list(root.rglob(f"{name}/report.json"))
    if len(hits)!=1:raise RuntimeError(f"{name}: expected 1 source report, got {len(hits)}")
    return hits[0],json.loads(hits[0].read_text())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("source",type=Path)
    ap.add_argument("church",type=Path)
    args=ap.parse_args()
    root=args.source
    rpath,r=report(root,"skeletons")
    mpath,m=report(root,"skeletal-meshes")
    apath,a=report(root,"animations")
    if (len(r["skeletons"]),len(m["meshes"]),len(a["animations"]))!=(45,60,106):
        raise RuntimeError("Recovered five-day rig census mismatch: expected 45/60/106")
    rig=next(x for x in r["skeletons"] if x["file"]=="r0040.xrg")
    mesh=next(x for x in m["meshes"] if x["file"]=="s0048.xsk")
    anims=[x for x in a["animations"] if x["skeletonHash"]==rig["skeletonHash"]]
    if rig["skeletonHash"]!="bcd0ac6b5cae8d26" or mesh["skeletonHash"]!=rig["skeletonHash"] or len(anims)<20:
        raise RuntimeError("102-bone zombie source rig/animation hash mismatch")
    dest=args.church/"assets/zombies/chronicles"
    dest.mkdir(parents=True,exist_ok=True)
    built=build_one(48,mesh,rig,anims,rpath.parent,mpath.parent,apath.parent,dest)
    src=dest/built["output"]
    destfile=dest/"reference_nazi_zombie.gltf"
    src.rename(destfile)
    if built["bones"]!=102:
        raise RuntimeError("Wrong source skeleton bone count")
    clips={row["name"] for row in built["animations"]}
    roles={"idle":"Idle_Body_Head_V1","walk":"ai_zombie_walk_v1",
           "attack":"Attack_Body_Head_V1","hit":"Body_Head_Tesla1_V1",
           "death":"Idle_Body_Death1_V1","getup":"Body_Head_rising_V1"}
    for role,clip in roles.items():
        if clip not in clips:raise RuntimeError(f"missing authored {role} animation {clip}")
    manifestpath=args.church/"data/church_chronicles_template.json"
    manifest=json.loads(manifestpath.read_text())
    spec=manifest["workshopZombie"]
    spec.update({"status":"VERIFIED_REFERENCE_IMPORT",
                 "sourcePath":"res://assets/zombies/chronicles/reference_nazi_zombie.gltf",
                 "animationRoles":roles})
    manifestpath.write_text(json.dumps(manifest,indent=2)+"\n")
    print(f"XZOGOT_NACHT_102BONE_REFERENCE_IMPORTED clips={len(anims)} meshes=1 bones=102")
    print("XZOGOT_NACHT_SOURCE_PAVLOV_WORKSHOP_UE421_NOT_FIRST_PARTY_BO3")
    return 0

if __name__=="__main__":raise SystemExit(main())
