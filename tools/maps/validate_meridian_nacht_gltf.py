#!/usr/bin/env python3
"""Verify Mermaid's [sic: Meridian] REAL generated GLB source actor TRS.
Godot's glTF Y-up coordinates must match XZIEL->Godot basis exactly.
No vertex or spatial position invented in this test.
"""
import argparse
import json
import math
from pathlib import Path
import struct
import sys


def mul(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def local(node):
    if "matrix" in node:
        raw = node["matrix"]
        if len(raw) != 16:
            raise ValueError("GLB matrix invalid")
        return [[raw[j*4 + i] for j in range(4)] for i in range(4)]
    x,y,z,w = node.get("rotation", [0,0,0,1])
    norm = math.sqrt(x*x+y*y+z*z+w*w)
    if norm < 1e-9:
        raise ValueError("quaternion has zero length")
    x,y,z,w = (v/norm for v in (x,y,z,w))
    a,b,c = node.get("translation", [0,0,0])
    sx,sy,sz = node.get("scale", [1,1,1])
    return [
        [(1-2*(y*y+z*z))*sx,2*(x*y-z*w)*sy,2*(x*z+y*w)*sz,a],
        [2*(x*y+z*w)*sx,(1-2*(x*x+z*z))*sy,2*(y*z-x*w)*sz,b],
        [2*(x*z-y*w)*sx,2*(y*z+x*w)*sy,(1-2*(x*x+y*y))*sz,c],
        [0,0,0,1]
    ]


def nodes_with_world(doc):
    nodes = doc["nodes"]
    seen = set()
    ident = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
    def walk(i, parent):
        if i in seen:
            raise ValueError("glTF node visited twice; unexpected instance graph")
        seen.add(i)
        node = nodes[i]
        m = mul(parent, local(node))
        yield node, m
        for child in node.get("children", []):
            yield from walk(child, m)
    for root in doc["scenes"][doc.get("scene", 0)]["nodes"]:
        yield from walk(root, ident)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.report.read_text())
    b = args.glb.read_bytes()
    if b[:4] != b"glTF":
        raise ValueError("Meridian generated a non-GLB file")
    length, chunk_type = struct.unpack_from("<II", b, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError("Meridian generated GLB without JSON")
    doc = json.loads(b[20:20+length])
    expected = source["source_world_positions"]
    actual = {}
    mesh_instances = 0
    for node, mat in nodes_with_world(doc):
        name = node.get("name","")
        if name in expected:
            actual[name] = mat
        if "mesh" in node:
            mesh_instances += 1
    errors = []
    for name, row in expected.items():
        if name not in actual:
            errors.append(name + ":actor_absent_after_Meridian")
            continue
        world = actual[name]
        position = [world[i][3] for i in range(3)]
        target = row["expected_godot_position_m"]
        pos_err = math.dist(position,target)
        if pos_err > 1e-3:
            errors.append(name + ":source_to_Godot_position_err_m=%.6f" % pos_err)
        expected_source = row["xz_position_m"]
        print("XZOGOT_MERIDIAN_ACTOR_PARITY", name,
              "xziel=",expected_source,"expected_godot=",target,
              "actual_exported=",position,"err_m=",pos_err)
    if mesh_instances < len(expected):
        errors.append("Meridian_mesh_node_loss=%d_expected_%d" % (mesh_instances,len(expected)))
    if source["made_up_source_objects"] is not True:
        print("XZOGOT_REAL_UE_GEOMETRY_NEEDS_INDEPENDENT_VERTEX_BOUNDS_PARITY",
              "native mesh positions alone are not complete map approval")
    result={"source_count":len(expected),"Meridian_GLTF_mesh_nodes":mesh_instances,
            "source_actor_world_transforms_pass":len(errors)==0,
            "errors":errors,"original_BO3_T7_claim":False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    if errors:
        print("XZOGOT_NACHT_MERIDIAN_SOURCE_XFORM_RED",json.dumps(errors))
        return 5
    print("XZOGOT_NACHT_MERIDIAN_SOURCE_XFORM_GREEN actors=",len(expected),
          "mesh_nodes=",mesh_instances,"is_synthetic_test_fixture=",
          source["made_up_source_objects"])
    return 0


if __name__=="__main__":
    sys.exit(main())
