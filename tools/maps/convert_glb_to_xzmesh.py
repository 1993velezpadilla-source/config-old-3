#!/usr/bin/env python3
"""Convert one static glTF 2.0 GLB into XZIEL's compact XZMS v2 mesh format.

XZMS v2 preserves glTF tangent-space data so authored normal maps can use the
same basis on Android without shipping a full glTF parser. Geometry is flattened
from the GLB scene graph, converted from glTF Y-up to XZIEL Z-up, and stored as:

  header: <4sIIIIIII6f
    magic='XZMS', version=2, vertexCount, indexCount, submeshCount,
    flags, vertexStrideBytes, submeshStrideBytes, boundsMinXYZ, boundsMaxXYZ
  vertices: vertexCount * <12f> =
    position.xyz, normal.xyz, uv.xy, tangent.xyzw
  indices:  indexCount * <I>
  submeshes: submeshCount * <IIII>
    firstIndex, indexCount, materialIndex (0xffffffff if none), attributeFlags

attributeFlags: bit0 POSITION, bit1 NORMAL, bit2 TEXCOORD_0, bit3 TANGENT.
Missing NORMAL/UV/TANGENT are explicit in the submesh flags; fixed vertex fields
are zero-filled only so the binary stride stays constant.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct

MAGIC = b"XZMS"
VERSION = 2
HEADER = struct.Struct("<4sIIIIIII6f")
VERTEX = struct.Struct("<12f")
SUBMESH = struct.Struct("<IIII")
FLAG_GLTF_TO_XZIEL = 1 << 0
FLAG_INDEX_U32 = 1 << 1
ATTR_POSITION = 1 << 0
ATTR_NORMAL = 1 << 1
ATTR_UV0 = 1 << 2
ATTR_TANGENT = 1 << 3
NO_MATERIAL = 0xFFFFFFFF
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942

COMPONENTS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
}
COMPONENT_INFO = {
    5121: ("B", 1),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}


def parse_glb(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError(f"GLB too small: {path}")
    magic, version, declared = struct.unpack_from("<III", raw, 0)
    if magic != 0x46546C67 or version != 2 or declared != len(raw):
        raise ValueError(f"invalid GLB header: {path}")

    offset = 12
    doc = None
    binary = None
    while offset + 8 <= len(raw):
        length, kind = struct.unpack_from("<II", raw, offset)
        offset += 8
        end = offset + length
        if end > len(raw):
            raise ValueError(f"GLB chunk overflow: {path}")
        chunk = raw[offset:end]
        offset = end
        if kind == JSON_CHUNK:
            doc = json.loads(chunk.rstrip(b" \t\r\n\x00").decode("utf-8"))
        elif kind == BIN_CHUNK:
            binary = bytes(chunk)

    if not isinstance(doc, dict):
        raise ValueError(f"GLB JSON chunk missing: {path}")
    if str(doc.get("asset", {}).get("version")) != "2.0":
        raise ValueError(f"GLB asset.version drift: {path}")
    if binary is None:
        binary = b""
    buffers = doc.get("buffers", [])
    if len(buffers) > 1:
        raise ValueError(f"XZMS v1 supports one GLB buffer, got {len(buffers)}: {path}")
    if buffers:
        declared_bytes = int(buffers[0].get("byteLength", 0))
        if declared_bytes > len(binary):
            raise ValueError(f"GLB BIN shorter than declared buffer: {path}")
    return doc, binary


def matmul(a: list[float], b: list[float]) -> list[float]:
    out = [0.0] * 16
    for c in range(4):
        for r in range(4):
            out[c * 4 + r] = sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4))
    return out


IDENTITY = [
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
]


def node_matrix(node: dict) -> list[float]:
    if "matrix" in node:
        m = [float(v) for v in node["matrix"]]
        if len(m) != 16:
            raise ValueError("glTF node matrix must contain 16 values")
        return m

    tx, ty, tz = [float(v) for v in node.get("translation", [0, 0, 0])]
    sx, sy, sz = [float(v) for v in node.get("scale", [1, 1, 1])]
    qx, qy, qz, qw = [float(v) for v in node.get("rotation", [0, 0, 0, 1])]

    length = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if length <= 1e-20:
        qx = qy = qz = 0.0
        qw = 1.0
    else:
        qx, qy, qz, qw = qx/length, qy/length, qz/length, qw/length

    xx, yy, zz = qx*qx, qy*qy, qz*qz
    xy, xz, yz = qx*qy, qx*qz, qy*qz
    wx, wy, wz = qw*qx, qw*qy, qw*qz

    r00 = 1 - 2 * (yy + zz)
    r01 = 2 * (xy - wz)
    r02 = 2 * (xz + wy)
    r10 = 2 * (xy + wz)
    r11 = 1 - 2 * (xx + zz)
    r12 = 2 * (yz - wx)
    r20 = 2 * (xz - wy)
    r21 = 2 * (yz + wx)
    r22 = 1 - 2 * (xx + yy)

    return [
        r00*sx, r10*sx, r20*sx, 0.0,
        r01*sy, r11*sy, r21*sy, 0.0,
        r02*sz, r12*sz, r22*sz, 0.0,
        tx, ty, tz, 1.0,
    ]


def transform_point(m: list[float], p: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = p
    return (
        m[0]*x + m[4]*y + m[8]*z + m[12],
        m[1]*x + m[5]*y + m[9]*z + m[13],
        m[2]*x + m[6]*y + m[10]*z + m[14],
    )


def upper_rows(m: list[float]) -> list[list[float]]:
    return [
        [m[0], m[4], m[8]],
        [m[1], m[5], m[9]],
        [m[2], m[6], m[10]],
    ]


def inverse3(a: list[list[float]]) -> list[list[float]]:
    a00,a01,a02 = a[0]
    a10,a11,a12 = a[1]
    a20,a21,a22 = a[2]
    c00 = a11*a22 - a12*a21
    c01 = -(a10*a22 - a12*a20)
    c02 = a10*a21 - a11*a20
    c10 = -(a01*a22 - a02*a21)
    c11 = a00*a22 - a02*a20
    c12 = -(a00*a21 - a01*a20)
    c20 = a01*a12 - a02*a11
    c21 = -(a00*a12 - a02*a10)
    c22 = a00*a11 - a01*a10
    det = a00*c00 + a01*c01 + a02*c02
    if abs(det) <= 1e-20:
        raise ValueError("singular node transform cannot transform normals")
    inv_det = 1.0 / det
    # adjugate / determinant
    return [
        [c00*inv_det, c10*inv_det, c20*inv_det],
        [c01*inv_det, c11*inv_det, c21*inv_det],
        [c02*inv_det, c12*inv_det, c22*inv_det],
    ]


def normal_matrix(m: list[float]) -> list[list[float]]:
    inv = inverse3(upper_rows(m))
    return [[inv[c][r] for c in range(3)] for r in range(3)]


def determinant3(a: list[list[float]]) -> float:
    return (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )


def transform_direction(
    rows: list[list[float]],
    v: tuple[float, float, float],
) -> tuple[float, float, float]:
    x, y, z = v
    return (
        rows[0][0] * x + rows[0][1] * y + rows[0][2] * z,
        rows[1][0] * x + rows[1][1] * y + rows[1][2] * z,
        rows[2][0] * x + rows[2][1] * y + rows[2][2] * z,
    )


def normalize3(v: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length <= 1e-20:
        raise ValueError("zero-length tangent basis vector")
    return (v[0] / length, v[1] / length, v[2] / length)


def transform_normal(nm: list[list[float]], n: tuple[float,float,float]) -> tuple[float,float,float]:
    x,y,z=n
    out=(
        nm[0][0]*x + nm[0][1]*y + nm[0][2]*z,
        nm[1][0]*x + nm[1][1]*y + nm[1][2]*z,
        nm[2][0]*x + nm[2][1]*y + nm[2][2]*z,
    )
    length=math.sqrt(out[0]*out[0]+out[1]*out[1]+out[2]*out[2])
    if length <= 1e-20:
        return (0.0,0.0,0.0)
    return (out[0]/length,out[1]/length,out[2]/length)


def gltf_to_xziel(v: tuple[float,float,float]) -> tuple[float,float,float]:
    # glTF Y-up -> XZIEL/Blender Z-up.
    return (v[0], -v[2], v[1])


def accessor_values(doc: dict, binary: bytes, index: int) -> list[tuple]:
    accessors = doc.get("accessors", [])
    views = doc.get("bufferViews", [])
    if not isinstance(index, int) or not (0 <= index < len(accessors)):
        raise ValueError(f"invalid accessor index {index}")
    acc = accessors[index]
    if "sparse" in acc:
        raise ValueError("XZMS v1 does not accept sparse accessors")
    view_index = acc.get("bufferView")
    if not isinstance(view_index, int) or not (0 <= view_index < len(views)):
        raise ValueError(f"accessor {index} has no valid bufferView")
    view = views[view_index]

    component_type = int(acc.get("componentType", 0))
    if component_type not in COMPONENT_INFO:
        raise ValueError(f"unsupported glTF componentType {component_type}")
    fmt, size = COMPONENT_INFO[component_type]
    kind = acc.get("type")
    if kind not in COMPONENTS:
        raise ValueError(f"unsupported glTF accessor type {kind!r}")
    width = COMPONENTS[kind]
    count = int(acc.get("count", 0))
    if count < 0:
        raise ValueError("negative accessor count")

    packed = size * width
    stride = int(view.get("byteStride", packed) or packed)
    if stride < packed:
        raise ValueError("bufferView byteStride smaller than packed accessor")
    offset = int(view.get("byteOffset", 0) or 0) + int(acc.get("byteOffset", 0) or 0)
    view_len = int(view.get("byteLength", 0) or 0)
    view_start = int(view.get("byteOffset", 0) or 0)
    view_end = view_start + view_len

    st = struct.Struct("<" + fmt * width)
    out = []
    for i in range(count):
        at = offset + i * stride
        end = at + packed
        if at < view_start or end > view_end or end > len(binary):
            raise ValueError(f"accessor {index} exceeds BIN bounds")
        out.append(st.unpack_from(binary, at))
    return out


def primitive_vertices(doc: dict, binary: bytes, primitive: dict, world: list[float]) -> tuple[list[tuple], list[int], int]:
    attrs = primitive.get("attributes", {})
    pos_index = attrs.get("POSITION")
    if not isinstance(pos_index, int):
        raise ValueError("primitive missing POSITION")
    positions = accessor_values(doc, binary, pos_index)
    if not positions or len(positions[0]) != 3:
        raise ValueError("POSITION accessor must be non-empty VEC3 float")
    if doc["accessors"][pos_index].get("componentType") != 5126:
        raise ValueError("POSITION must use FLOAT componentType")

    attr_flags = ATTR_POSITION

    normals = None
    normal_index = attrs.get("NORMAL")
    if isinstance(normal_index, int):
        normals = accessor_values(doc, binary, normal_index)
        if doc["accessors"][normal_index].get("componentType") != 5126:
            raise ValueError("NORMAL must use FLOAT componentType")
        if len(normals) != len(positions):
            raise ValueError("NORMAL count mismatch")
        attr_flags |= ATTR_NORMAL

    tangents = None
    tangent_index = attrs.get("TANGENT")
    if isinstance(tangent_index, int):
        tangents = accessor_values(doc, binary, tangent_index)
        tangent_accessor = doc["accessors"][tangent_index]
        if tangent_accessor.get("componentType") != 5126:
            raise ValueError("TANGENT must use FLOAT componentType")
        if tangent_accessor.get("type") != "VEC4":
            raise ValueError("TANGENT must be VEC4")
        if len(tangents) != len(positions):
            raise ValueError("TANGENT count mismatch")
        attr_flags |= ATTR_TANGENT

    uvs = None
    uv_index = attrs.get("TEXCOORD_0")
    if isinstance(uv_index, int):
        uvs = accessor_values(doc, binary, uv_index)
        if doc["accessors"][uv_index].get("componentType") != 5126:
            raise ValueError("TEXCOORD_0 must use FLOAT componentType")
        if len(uvs) != len(positions):
            raise ValueError("TEXCOORD_0 count mismatch")
        attr_flags |= ATTR_UV0

    mode = int(primitive.get("mode", 4))
    if mode != 4:
        raise ValueError(f"XZMS v1 only accepts TRIANGLES (mode 4), got {mode}")

    if isinstance(primitive.get("indices"), int):
        idx_accessor = primitive["indices"]
        component = int(doc["accessors"][idx_accessor].get("componentType", 0))
        if component not in (5121,5123,5125):
            raise ValueError(f"unsupported index componentType {component}")
        raw_indices = accessor_values(doc, binary, idx_accessor)
        indices = [int(row[0]) for row in raw_indices]
    else:
        indices = list(range(len(positions)))

    if len(indices) % 3 != 0:
        raise ValueError("triangle index count is not divisible by 3")
    if indices and max(indices) >= len(positions):
        raise ValueError("index references vertex outside POSITION accessor")

    nm = normal_matrix(world) if normals is not None else None
    linear = upper_rows(world)
    world_handedness = -1.0 if determinant3(linear) < 0.0 else 1.0

    vertices = []
    for i, pos in enumerate(positions):
        p = gltf_to_xziel(transform_point(world, tuple(float(v) for v in pos)))
        n_world = None
        if normals is not None and nm is not None:
            n_world = transform_normal(
                nm,
                tuple(float(v) for v in normals[i]),
            )
            n = normalize3(gltf_to_xziel(n_world))
        else:
            n = (0.0, 0.0, 0.0)

        tangent = (0.0, 0.0, 0.0, 0.0)
        if tangents is not None:
            raw = tuple(float(v) for v in tangents[i])
            if not all(math.isfinite(v) for v in raw):
                raise ValueError("non-finite TANGENT")
            if abs(abs(raw[3]) - 1.0) > 1.0e-4:
                raise ValueError(
                    f"TANGENT handedness must be +/-1, got {raw[3]}"
                )

            t_world = transform_direction(
                linear,
                (raw[0], raw[1], raw[2]),
            )
            if n_world is not None:
                dot_nt = (
                    n_world[0] * t_world[0]
                    + n_world[1] * t_world[1]
                    + n_world[2] * t_world[2]
                )
                t_world = (
                    t_world[0] - n_world[0] * dot_nt,
                    t_world[1] - n_world[1] * dot_nt,
                    t_world[2] - n_world[2] * dot_nt,
                )
            t_world = normalize3(t_world)
            t = normalize3(gltf_to_xziel(t_world))
            handedness = (
                (1.0 if raw[3] >= 0.0 else -1.0)
                * world_handedness
            )
            tangent = (t[0], t[1], t[2], handedness)

        uv = tuple(float(v) for v in uvs[i]) if uvs is not None else (0.0,0.0)
        vertices.append((
            p[0], p[1], p[2],
            n[0], n[1], n[2],
            uv[0], uv[1],
            tangent[0], tangent[1], tangent[2], tangent[3],
        ))
    return vertices, indices, attr_flags


def flatten_scene(doc: dict, binary: bytes) -> tuple[list[tuple], list[int], list[dict]]:
    nodes=doc.get("nodes",[])
    meshes=doc.get("meshes",[])
    scenes=doc.get("scenes",[])
    scene_index=int(doc.get("scene",0) or 0)
    if scenes and 0 <= scene_index < len(scenes):
        roots=scenes[scene_index].get("nodes",[])
    elif nodes:
        roots=list(range(len(nodes)))
    else:
        raise ValueError("GLB contains no scene nodes")

    vertices=[]
    indices=[]
    submeshes=[]

    def visit(node_index:int,parent:list[float]):
        if not isinstance(node_index,int) or not (0 <= node_index < len(nodes)):
            raise ValueError(f"invalid node index {node_index}")
        node=nodes[node_index]
        world=matmul(parent,node_matrix(node))
        mesh_index=node.get("mesh")
        if isinstance(mesh_index,int):
            if not (0 <= mesh_index < len(meshes)):
                raise ValueError(f"node {node_index} references invalid mesh {mesh_index}")
            for primitive in meshes[mesh_index].get("primitives",[]):
                local_vertices, local_indices, attr_flags = primitive_vertices(doc,binary,primitive,world)
                base_vertex=len(vertices)
                first_index=len(indices)
                vertices.extend(local_vertices)
                indices.extend(base_vertex + idx for idx in local_indices)
                material=primitive.get("material")
                material_index=int(material) if isinstance(material,int) else NO_MATERIAL
                submeshes.append({
                    "firstIndex":first_index,
                    "indexCount":len(local_indices),
                    "materialIndex":material_index,
                    "attributeFlags":attr_flags,
                })
        for child in node.get("children",[]):
            visit(child,world)

    for root in roots:
        visit(root,IDENTITY)

    if not vertices or not indices or not submeshes:
        raise ValueError("GLB produced no renderable triangle geometry")
    return vertices,indices,submeshes


def convert(path: Path, output: Path) -> dict:
    doc,binary=parse_glb(path)
    vertices,indices,submeshes=flatten_scene(doc,binary)

    mins=[min(v[i] for v in vertices) for i in range(3)]
    maxs=[max(v[i] for v in vertices) for i in range(3)]

    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("wb") as f:
        f.write(HEADER.pack(
            MAGIC,
            VERSION,
            len(vertices),
            len(indices),
            len(submeshes),
            FLAG_GLTF_TO_XZIEL | FLAG_INDEX_U32,
            VERTEX.size,
            SUBMESH.size,
            mins[0],mins[1],mins[2],maxs[0],maxs[1],maxs[2],
        ))
        for vertex in vertices:
            f.write(VERTEX.pack(*vertex))
        for index in indices:
            f.write(struct.pack("<I",index))
        for row in submeshes:
            f.write(SUBMESH.pack(
                row["firstIndex"],
                row["indexCount"],
                row["materialIndex"],
                row["attributeFlags"],
            ))

    return {
        "vertexCount":len(vertices),
        "indexCount":len(indices),
        "triangleCount":len(indices)//3,
        "submeshCount":len(submeshes),
        "submeshesWithoutNormals":sum((r["attributeFlags"] & ATTR_NORMAL)==0 for r in submeshes),
        "submeshesWithoutUv0":sum((r["attributeFlags"] & ATTR_UV0)==0 for r in submeshes),
        "submeshesWithoutTangents":sum((r["attributeFlags"] & ATTR_TANGENT)==0 for r in submeshes),
        "bounds":{"min":mins,"max":maxs},
        "bytes":output.stat().st_size,
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("input",type=Path)
    ap.add_argument("output",type=Path)
    ap.add_argument("--report",type=Path)
    args=ap.parse_args()
    result=convert(args.input,args.output)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("XZIEL_XZMS_CONVERT_OK",json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
