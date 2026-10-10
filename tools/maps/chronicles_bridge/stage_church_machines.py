#!/usr/bin/env python3
"""Stage existing Nacht machine 3D references for a PRIVATE CI-only Godot test.

These are geometry references from an archived community workshop map, not
native BO3/T7 first-party files. Do not upload this derived GLB folder.
"""
import argparse
import json
from pathlib import Path
from xzms_to_glb import build_glb

MACHINES = {
    "mystery_main": "m0539.xzm",
    "pap_shell": "m0535.xzm",
    "pap_inside": "m0536.xzm",
    "power_hand": "m0542.xzm",
    "power_base": "m0543.xzm",
    "revive_body": "m0552.xzm",
    "revive_sign": "m0553.xzm",
    "revive_sign_holder": "m0554.xzm",
    "revive_bottle_body": "m0555.xzm",
    "revive_bottle_cap": "m0556.xzm",
    "revive_bottle_mouth": "m0557.xzm",
    "jugg_bottle_one": "m0564.xzm",
    "jugg_bottle_two": "m0565.xzm",
}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("source",type=Path)
    ap.add_argument("church",type=Path)
    args=ap.parse_args()
    source_reports=list(args.source.rglob("static-meshes/report.json"))
    if len(source_reports)!=1:
        raise RuntimeError("Original archived static mesh report missing/ambiguous")
    report=json.loads(source_reports[0].read_text())
    rows={r["file"]:r for r in report["meshes"]}
    target=args.church/"assets/reference/church/machines"
    target.mkdir(parents=True,exist_ok=True)
    result=[]
    for name,filename in MACHINES.items():
        entry=rows.get(filename)
        if entry is None:
            raise RuntimeError("Exact previously decoded machine index absent: "+filename)
        raw=source_reports[0].parent/filename
        if not raw.is_file():
            raise RuntimeError("Exact native source XZMS payload absent: "+filename)
        glb=target/(name+".glb")
        converted=build_glb(raw,glb)
        if converted["vertices"]<3 or converted["indices"]<3:
            raise RuntimeError("Native source machine has zero triangles: "+filename)
        result.append({"machine":name,"file":filename,"sourcePackage":entry["packagePath"],
                       "vertices":converted["vertices"],"triangles":converted["indices"]//3,
                       "surfaces":converted["submeshes"],"glbBytes":converted["bytes"]})
        print("XZOGOT_MACHINE_SOURCE_3D_READY",name,filename,converted["vertices"],converted["indices"]//3)
    (target/"audit.json").write_text(json.dumps({
        "provenance":"community Pavlov VR UE4.21 reference, not official BO3",
        "publicRedistributionApproved":False,
        "machineCount":len(result),"meshes":result},indent=2)+"\n")
    print("XZOGOT_NACHT_13_MACHINE_PIECES_CONVERTED_GREEN")
if __name__=="__main__":
    main()
