#!/usr/bin/env python3
import argparse, json, subprocess, sys
from pathlib import Path

def run(cmd):
    p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return {"cmd":cmd, "returncode":p.returncode, "output":p.stdout[-4000:]}

ap=argparse.ArgumentParser()
ap.add_argument("--root", default=".xziel-tools")
ap.add_argument("--deep", action="store_true")
ap.add_argument("--deep-only", action="store_true")
ap.add_argument("--out", default="xziel-toolchain-report.json")
args=ap.parse_args()
root=Path(args.root).resolve()
checks={}

gltfpack=root/"bin"/"gltfpack"
ktx=root/"bin"/"ktx"
checks["gltfpack"]={"exists":gltfpack.is_file(), **(run([str(gltfpack),"-h"]) if gltfpack.is_file() else {})}
checks["ktx"]={"exists":ktx.is_file(), **(run([str(ktx),"--version"]) if ktx.is_file() else {})}
checks["xatlas"]={"exists":(root/"lib"/"libxatlas.a").is_file(), "header":(root/"include"/"xatlas"/"xatlas.h").is_file()}
recast_libs=list((root/"recast").rglob("libRecast*")) if (root/"recast").exists() else []
detour_libs=list((root/"recast").rglob("libDetour*")) if (root/"recast").exists() else []
checks["recast"]={"libs":[str(p.relative_to(root)) for p in recast_libs]}
checks["detour"]={"libs":[str(p.relative_to(root)) for p in detour_libs]}

if args.deep or args.deep_only:
    py=root/"deep-venv"/"bin"/"python"
    checks["deep_python"]={"exists":py.is_file()}
    if py.is_file():
        checks["open3d"]=run([str(py),"-c","import open3d as o; print(o.__version__)"])
        checks["pycolmap"]=run([str(py),"-c","import pycolmap as p; print(p.__version__)"])
        checks["manifold3d"]=run([str(py),"-c","import manifold3d as m; print(m.Manifold.cube((1,1,1)).volume())"])
        checks["coacd"]=run([str(py),"-c","import coacd; print('COACD_IMPORT_OK')"])

fast_ok = (
    checks["gltfpack"].get("exists") and
    checks["ktx"].get("exists") and
    checks["xatlas"].get("exists") and
    bool(checks["recast"]["libs"]) and
    bool(checks["detour"]["libs"]) and
    checks["gltfpack"].get("returncode",1) in (0,1) and
    checks["ktx"].get("returncode",1) in (0,1)
)
deep_ok = (
    checks.get("open3d",{}).get("returncode")==0 and
    checks.get("pycolmap",{}).get("returncode")==0 and
    checks.get("manifold3d",{}).get("returncode")==0 and
    checks.get("coacd",{}).get("returncode")==0
)
if args.deep_only:
    ok = deep_ok
elif args.deep:
    ok = fast_ok and deep_ok
else:
    ok = fast_ok

report={"status":"PASS" if ok else "FAIL","root":str(root),"deep":args.deep,"deep_only":args.deep_only,"checks":checks}
Path(args.out).write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
if not ok:
    sys.exit(2)
