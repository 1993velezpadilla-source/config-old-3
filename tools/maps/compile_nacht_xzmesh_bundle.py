#!/usr/bin/env python3
"""Compile all 492 BO3 Nacht reference GLBs into XZMS v2 and emit a bundle manifest.

Runtime filenames are deliberately compact ordinals (m0000.xzm ... m0491.xzm).
Vril inherits Quake's 64-byte MAX_QPATH and 128-byte MAX_OSPATH constraints;
source asset names remain in the manifest for identity/provenance and are never
used as runtime VFS filenames.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_ASSETS=ROOT/"assets/nacht_reference/pavlov_scene_reference/assets.json"
CONVERTER=ROOT/"tools/maps/convert_glb_to_xzmesh.py"
EXPECTED=492


def load_module():
    spec=importlib.util.spec_from_file_location("xzmesh_converter",CONVERTER)
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load {CONVERTER}")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


converter=load_module()


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def runtime_name(index:int)->str:
    if not 0 <= index < 10000:
        raise ValueError(f"runtime mesh ordinal out of range: {index}")
    return f"m{index:04d}.xzm"


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--assets",type=Path,default=DEFAULT_ASSETS)
    ap.add_argument("--glb-root",type=Path,required=True)
    ap.add_argument("--output-root",type=Path,required=True)
    ap.add_argument("--manifest",type=Path,required=True)
    args=ap.parse_args()

    assets=json.loads(args.assets.read_text(encoding="utf-8"))
    rows=assets.get("meshes",[])
    if assets.get("uniqueMeshCount")!=EXPECTED or len(rows)!=EXPECTED:
        raise SystemExit(f"expected {EXPECTED} mesh references")

    glbs={}
    for p in args.glb_root.rglob("*.glb"):
        key=p.stem.lower()
        if key in glbs:
            raise SystemExit(f"duplicate GLB stem: {p.stem}")
        glbs[key]=p

    output_rows=[]
    totals={
        "meshes":0,"vertices":0,"indices":0,"triangles":0,"submeshes":0,
        "submeshesWithoutNormals":0,
        "submeshesWithoutUv0":0,
        "submeshesWithoutUv1":0,
        "submeshesWithoutUv2":0,
        "submeshesWithoutUv3":0,
        "bytes":0,
    }
    args.output_root.mkdir(parents=True,exist_ok=True)

    for index,row in enumerate(rows):
        source=row["sourcePath"].replace("\\","/").rstrip("/")
        name=source.rsplit("/",1)[-1]
        src=glbs.get(name.lower())
        if src is None:
            raise SystemExit(f"missing GLB for {name}")
        runtime=runtime_name(index)
        dst=args.output_root/runtime
        stats=converter.convert(src,dst)
        output_rows.append({
            "index":index,
            "id":row["id"],
            "sourcePath":row["sourcePath"],
            "sourceGlb":f"meshes/{name}.glb",
            "runtimeMesh":f"meshes/{runtime}",
            "runtimeFile":runtime,
            "sha256":sha256(dst),
            "stats":stats,
        })
        totals["meshes"]+=1
        totals["vertices"]+=stats["vertexCount"]
        totals["indices"]+=stats["indexCount"]
        totals["triangles"]+=stats["triangleCount"]
        totals["submeshes"]+=stats["submeshCount"]
        totals["submeshesWithoutNormals"]+=stats["submeshesWithoutNormals"]
        totals["submeshesWithoutUv0"]+=stats["submeshesWithoutUv0"]
        totals["submeshesWithoutUv1"]+=stats["submeshesWithoutUv1"]
        totals["submeshesWithoutUv2"]+=stats["submeshesWithoutUv2"]
        totals["submeshesWithoutUv3"]+=stats["submeshesWithoutUv3"]
        totals["bytes"]+=stats["bytes"]

    if totals["meshes"]!=EXPECTED:
        raise SystemExit(f"converted only {totals['meshes']} meshes")

    runtime_files=[row["runtimeFile"] for row in output_rows]
    if len(set(runtime_files)) != EXPECTED:
        raise SystemExit("runtime mesh filenames are not unique")

    manifest={
        "schemaVersion":2,
        "format":"xziel_xzmesh_bundle_v2",
        "mapId":"bo3_nacht_reference",
        "meshFormat":{
            "magic":"XZMS",
            "version":2,
            "vertexLayout":"position3f_normal3f_uv0_2f_uv1_2f_uv2_2f_uv3_2f",
            "indexType":"uint32",
            "coordinateBasis":"XZIEL_Z_UP",
            "sourceBasisConversion":"glTF_Y_UP -> XZIEL_Z_UP: (x,-z,y)",
        },
        "runtimeNaming":{
            "scheme":"compact_ordinal_v1",
            "pattern":"m%04d.xzm",
            "quakeMaxQpathBytes":63,
            "sourceIdentityPreservedInManifest":True,
        },
        "policy":{
            "requiredMeshCount":EXPECTED,
            "zeroOmission":True,
            "noSilentFallbacks":True,
            "missingNormalOrUvIsExplicitPerSubmesh":True,
            "thirdPartyMeshBytesCommittedToRepository":False,
        },
        "summary":{
            "meshCount":totals["meshes"],
            "vertexCount":totals["vertices"],
            "indexCount":totals["indices"],
            "triangleCount":totals["triangles"],
            "submeshCount":totals["submeshes"],
            "submeshesWithoutNormals":totals["submeshesWithoutNormals"],
            "submeshesWithoutUv0":totals["submeshesWithoutUv0"],
            "submeshesWithoutUv1":totals["submeshesWithoutUv1"],
            "submeshesWithoutUv2":totals["submeshesWithoutUv2"],
            "submeshesWithoutUv3":totals["submeshesWithoutUv3"],
            "runtimeMeshBytes":totals["bytes"],
            "geometryRuntimeFormatReady":True,
            "materialBindingReady":False,
        },
        "meshes":output_rows,
    }
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    args.manifest.write_text(json.dumps(manifest,separators=(",",":"))+"\n",encoding="utf-8")
    print("XZIEL_NACHT_XZMS_BUNDLE_OK",json.dumps(manifest["summary"],sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
