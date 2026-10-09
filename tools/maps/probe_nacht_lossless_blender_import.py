#!/usr/bin/env python3
"""Experimental lossless triangle import A/B: original glTF indices -> Blender mesh.

Hypothesis: bpy glTF importer removes 1,051 genuine original source triangles;
building Blender mesh faces from exact native GLB POSITION+index buffers may
preserve source topology. Diagnostics ONLY, not ready for shipping/materials.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import bpy


def native(path):
    raw = path.read_bytes()
    if raw[:4] != b"glTF":
        raise ValueError("source GLB missing")
    json_size, kind = struct.unpack_from("<II",raw,12)
    if kind != 0x4E4F534A:
        raise ValueError("glb JSON missing")
    doc = json.loads(raw[20:20+json_size])
    bstart = 20 + json_size
    bin_size, bin_kind = struct.unpack_from("<II",raw,bstart)
    if bin_kind != 0x004E4942:
        raise ValueError("glb BIN missing")
    return doc, memoryview(raw)[bstart+8:bstart+8+bin_size]


def accessor(doc, binary, idx):
    a = doc["accessors"][idx]
    if a.get("sparse"):
        raise ValueError("sparse glb accessor not supported")
    component = a["componentType"]
    count = a["count"]
    typ = a["type"]
    width = {"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4}[typ]
    fmt = {5121:"B",5123:"H",5125:"I",5126:"f"}[component]
    byte_width = struct.calcsize("<"+fmt)*width
    bv = doc["bufferViews"][a["bufferView"]]
    stride = bv.get("byteStride",byte_width)
    off = bv.get("byteOffset",0)+a.get("byteOffset",0)
    unpack = struct.Struct("<"+fmt*width)
    return [unpack.unpack_from(binary,off+i*stride) for i in range(count)]


def make_mesh_from_raw(doc, binary, idx):
    verts = []
    faces = []
    for primitive in doc["meshes"][idx]["primitives"]:
        if primitive.get("mode",4)!=4:
            raise ValueError("source geometry not triangles")
        p=accessor(doc,binary,primitive["attributes"]["POSITION"])
        ids=([row[0] for row in accessor(doc,binary,primitive["indices"])]
             if "indices" in primitive else list(range(len(p))))
        if len(ids)%3:
            raise ValueError("bad triangle array")
        needed=sorted(set(ids))
        remap={src:i+len(verts) for i,src in enumerate(needed)}
        verts.extend(p[k] for k in needed)
        faces.extend(tuple(remap[v] for v in ids[k:k+3])
                     for k in range(0,len(ids),3))
    mesh=bpy.data.meshes.new("native_exact_faces")
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    return mesh,len(faces)


def count_triangles_glb(path):
    doc,_=native(path)
    count=0
    for mesh in doc["meshes"]:
        for p in mesh["primitives"]:
            a=p.get("indices",p["attributes"]["POSITION"])
            count+=doc["accessors"][a]["count"]//3
    return count


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scene",type=Path,required=True)
    p.add_argument("--native-glb-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--mesh-index",type=int,nargs="+",required=True)
    opts=p.parse_args(sys.argv[sys.argv.index("--")+1:])
    scene=json.loads(opts.scene.read_text())
    meshes={int(m["index"]):m for m in scene["meshes"]}
    result=[]
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    for idx in opts.mesh_index:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        file=opts.native_glb_dir/(Path(meshes[idx]["runtimeFile"]).stem+".glb")
        doc,binary=native(file)
        source=count_triangles_glb(file)
        imported=[]
        for j in range(len(doc["meshes"])):
            mesh,faces=make_mesh_from_raw(doc,binary,j)
            obj=bpy.data.objects.new(f"Source_{idx}_mesh_{j}",mesh)
            bpy.context.scene.collection.objects.link(obj)
            imported.append((obj,faces))
        blender=sum(len(obj.data.polygons) for obj,_ in imported)
        if blender!=source:
            raise ValueError(f"raw builder removed faces source={source} blender={blender}")
        name=opts.output.parent / f"raw_triangle_source_mesh_{idx}.glb"
        bpy.ops.export_scene.gltf(filepath=str(name),export_format="GLB",
                                  export_yup=True)
        exported=count_triangles_glb(name)
        row={"mesh_index":idx,"source_native_triangles":source,
             "manual_blender_polygons":blender,
             "after_real_Blender_GLTF_export":exported,
             "triangles_lost_after_export":source-exported}
        print("XZOGOT_NACHT_DIRECT_TRIANGLES_STAGE",json.dumps(row))
        result.append(row)
        opts.output.write_text(json.dumps(result,indent=2)+"\n")
    print("XZOGOT_NACHT_DIRECT_RAW_TRIANGLE_EXPERIMENT_DONE",
          "count",len(result),
          "lost_total",sum(x["triangles_lost_after_export"] for x in result))


if __name__=="__main__":
    main()
