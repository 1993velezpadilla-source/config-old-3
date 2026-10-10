#!/usr/bin/env python3
"""Identify WHICH stage loses original nondegenerate source triangles.

Read original glTF triangle primitive counts, then import exactly those
native GLBs through the pinned Blender 5.0 importer without Meridian.
No synthesized geometry or per-asset fixes; research-only provenance.
"""
import argparse
import json
from pathlib import Path
import sys
import struct

import bpy


def source_counts(path):
    blob = path.read_bytes()
    if blob[:4] != b"glTF":
        raise ValueError("original file not a GLB: " + path.name)
    jsonlen, kind = struct.unpack_from("<II", blob, 12)
    if kind != 0x4E4F534A:
        raise ValueError("GLB JSON missing")
    doc = json.loads(blob[20:20+jsonlen])
    triangles = 0
    for mesh in doc["meshes"]:
        for prim in mesh["primitives"]:
            if prim.get("mode", 4) != 4:
                raise ValueError("native GLB triangle mode unsupported")
            idx = prim.get("indices")
            count = doc["accessors"][idx]["count"] if idx is not None else (
                doc["accessors"][prim["attributes"]["POSITION"]]["count"]
            )
            if count % 3:
                raise ValueError("source triangle index count wrong")
            triangles += count//3
    return triangles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=Path, required=True)
    ap.add_argument("--native-glb-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--mesh-index", type=int, nargs="+", required=True)
    args = ap.parse_args(sys.argv[sys.argv.index("--")+1:])
    data = json.loads(args.scene.read_text())
    meshes = {int(m["index"]):m for m in data["meshes"]}
    out = []
    for idx in args.mesh_index:
        m = meshes[idx]
        path = args.native_glb_dir / (Path(m["runtimeFile"]).stem + ".glb")
        native = source_counts(path)
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path))
        added = set(bpy.data.objects) - before
        imported_meshes = [o for o in added if o.type=="MESH"]
        if not imported_meshes:
            raise ValueError("Blender native GLB importer dropped entire mesh "+path.name)
        faces = sum(len(o.data.polygons) for o in imported_meshes)
        tris = sum(len(o.data.loop_triangles) for o in imported_meshes)
        row = {"mesh_index":idx,"path":path.name,
               "source_raw_glb_triangles":native,
               "blender_import_polygons":faces,
               "blender_import_triangles":tris,
               "blender_import_loss":native-tris}
        out.append(row)
        print("XZOGOT_NACHT_TRIANGLE_IMPORT_STAGE",json.dumps(row))
        if not args.out.parent.exists():
            args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(out,indent=2)+"\n")
    print("XZOGOT_NACHT_TRIANGLE_IMPORT_STAGE_DIAGNOSTIC_DONE",
          "models",len(out),
          "missing_at_blender_import",sum(x["blender_import_loss"] for x in out))
    return 0


if __name__=="__main__":
    sys.exit(main())
