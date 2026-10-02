#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import struct
from dataclasses import asdict, dataclass
from pathlib import Path

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942

_COMPONENT = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
_WIDTH = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}

@dataclass
class MeshGateReport:
    path: str
    valid: bool
    passed: bool
    vertices: int
    faces: int
    triangle_primitives: int
    normal_primitives: int
    missing_normal_primitives: int
    components: int
    largest_component_fraction: float
    degenerate_ratio: float
    bbox_extents: list[float]
    bbox_aspect_ratio: float
    axis_alignment_weighted: float
    axis_aligned_area_98: float
    dominant_normal_axis_area: list[float]
    reasons: list[str]
    warnings: list[str]

def _read_glb(path: Path):
    blob = path.read_bytes()
    if len(blob) < 20 or blob[:4] != b"glTF":
        raise ValueError("not a GLB")
    version, total = struct.unpack_from("<II", blob, 4)
    if version != 2 or total > len(blob):
        raise ValueError("invalid GLB header")
    offset = 12
    doc = None
    binary = None
    while offset + 8 <= total:
        length, chunk_type = struct.unpack_from("<II", blob, offset)
        offset += 8
        end = offset + length
        if end > total:
            raise ValueError("chunk exceeds GLB length")
        data = blob[offset:end]
        offset = end
        if chunk_type == JSON_CHUNK:
            doc = json.loads(data.rstrip(b"\x00 \t\r\n").decode("utf-8"))
        elif chunk_type == BIN_CHUNK:
            binary = data
    if doc is None or binary is None:
        raise ValueError("GLB missing JSON or BIN chunk")
    return doc, binary

def _accessor(doc, binary: bytes, index: int):
    accessor = doc["accessors"][index]
    if "bufferView" not in accessor:
        raise ValueError(f"sparse/implicit accessor unsupported: {index}")
    view = doc["bufferViews"][accessor["bufferView"]]
    fmt, scalar_bytes = _COMPONENT[accessor["componentType"]]
    width = _WIDTH[accessor["type"]]
    count = int(accessor["count"])
    base = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    stride = int(view.get("byteStride", scalar_bytes * width))
    item = struct.Struct("<" + fmt * width)
    out = []
    mv = memoryview(binary)
    for i in range(count):
        off = base + i * stride
        out.append(item.unpack_from(mv, off))
    return out

def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )

def _geometric_connectivity(vertices, faces, scale: float) -> tuple[int, float]:
    """Count connected geometry after welding coincident POSITION vertices.

    glTF requires one attribute tuple per vertex. UV seams therefore duplicate
    POSITION values even when the underlying surface is continuous. Connectivity
    QA must operate on welded geometric positions, otherwise a valid textured
    atlas can look catastrophically fragmented purely because of UV chart seams.
    """
    weld_epsilon=max(abs(float(scale))*1e-7,1e-9)
    key_to_id={}
    remap=[]
    for vertex in vertices:
        key=tuple(
            int(round(float(component)/weld_epsilon))
            for component in vertex[:3]
        )
        welded=key_to_id.get(key)
        if welded is None:
            welded=len(key_to_id)
            key_to_id[key]=welded
        remap.append(welded)

    parent=list(range(len(key_to_id)))
    size=[1]*len(key_to_id)

    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x

    def union(a,b):
        ra,rb=find(a),find(b)
        if ra==rb:
            return
        if size[ra]<size[rb]:
            ra,rb=rb,ra
        parent[rb]=ra
        size[ra]+=size[rb]

    used=set()
    for a,b,c in faces:
        wa,wb,wc=remap[a],remap[b],remap[c]
        union(wa,wb)
        union(wa,wc)
        used.update((wa,wb,wc))

    roots={}
    for vertex in used:
        root=find(vertex)
        roots[root]=roots.get(root,0)+1
    component_sizes=sorted(roots.values(),reverse=True)
    components=len(component_sizes)
    largest_fraction=(
        component_sizes[0]/max(1,len(used))
        if component_sizes else 0.0
    )
    return components,largest_fraction


def _catastrophic_fragmentation_reason(components: int, largest_fraction: float) -> str | None:
    # Extremely fragmented geometry is not a detailed multi-part asset; it is a
    # failed surface extraction. Keep normal clothing/hair/accessory islands as
    # telemetry, but reject outputs where no coherent body surface dominates.
    if components > 1024 and largest_fraction < 0.05:
        return (
            "catastrophic_fragmentation:"
            f"components={components},largest={largest_fraction:.3f}"
        )
    if components > 512 and largest_fraction < 0.01:
        return (
            "catastrophic_fragmentation:"
            f"components={components},largest={largest_fraction:.3f}"
        )
    return None


def inspect(path: Path, *, require_normals: bool = False) -> MeshGateReport:
    reasons = []
    warnings = []
    triangle_primitives = 0
    normal_primitives = 0
    missing_normal_primitives = 0
    try:
        doc, binary = _read_glb(path)
        vertices = []
        faces = []

        for mesh in doc.get("meshes", []):
            for primitive in mesh.get("primitives", []):
                if int(primitive.get("mode", 4)) != 4:
                    continue
                attributes = primitive.get("attributes", {})
                pos_idx = attributes.get("POSITION")
                if pos_idx is None:
                    continue
                triangle_primitives += 1
                if attributes.get("NORMAL") is None:
                    missing_normal_primitives += 1
                else:
                    normal_primitives += 1
                local = [tuple(float(x) for x in row[:3]) for row in _accessor(doc, binary, pos_idx)]
                base = len(vertices)
                vertices.extend(local)

                idx_acc = primitive.get("indices")
                if idx_acc is None:
                    idx = list(range(len(local)))
                else:
                    idx = [int(row[0]) for row in _accessor(doc, binary, idx_acc)]
                tri_count = len(idx) // 3
                for i in range(tri_count):
                    a, b, c = idx[i * 3 : i * 3 + 3]
                    if 0 <= a < len(local) and 0 <= b < len(local) and 0 <= c < len(local):
                        faces.append((base + a, base + b, base + c))

        if not vertices or not faces:
            raise ValueError("no triangle geometry")

        mins = [min(v[i] for v in vertices) for i in range(3)]
        maxs = [max(v[i] for v in vertices) for i in range(3)]
        ext = [maxs[i] - mins[i] for i in range(3)]
        positive = [x for x in ext if x > 1e-12]
        aspect = max(positive) / min(positive) if len(positive) == 3 else float("inf")
        scale = max(ext)
        epsilon_area2 = max(scale * scale * 1e-12, 1e-18)

        total_area2 = 0.0
        degenerate = 0
        aligned98_area2 = 0.0
        alignment_sum = 0.0
        axis_area2 = [0.0, 0.0, 0.0]

        for a, b, c in faces:
            va, vb, vc = vertices[a], vertices[b], vertices[c]
            e1 = (vb[0]-va[0], vb[1]-va[1], vb[2]-va[2])
            e2 = (vc[0]-va[0], vc[1]-va[1], vc[2]-va[2])
            cr = _cross(e1, e2)
            area2 = math.sqrt(cr[0]*cr[0] + cr[1]*cr[1] + cr[2]*cr[2])
            if not math.isfinite(area2) or area2 <= epsilon_area2:
                degenerate += 1
                continue
            nx, ny, nz = cr[0]/area2, cr[1]/area2, cr[2]/area2
            absn = (abs(nx), abs(ny), abs(nz))
            peak = max(absn)
            axis = 0 if absn[0] >= absn[1] and absn[0] >= absn[2] else (1 if absn[1] >= absn[2] else 2)
            total_area2 += area2
            alignment_sum += area2 * peak
            axis_area2[axis] += area2
            if peak >= 0.98:
                aligned98_area2 += area2

        components,largest_fraction=_geometric_connectivity(
            vertices,faces,scale
        )

        degenerate_ratio = degenerate / max(1, len(faces))
        if total_area2 <= 0:
            alignment = 1.0
            aligned98 = 1.0
            axis_fraction = [0.0, 0.0, 0.0]
        else:
            alignment = alignment_sum / total_area2
            aligned98 = aligned98_area2 / total_area2
            axis_fraction = [x / total_area2 for x in axis_area2]

        if len(faces) < 500:
            reasons.append(f"too_few_faces:{len(faces)}")
        if degenerate_ratio > 0.20:
            reasons.append(f"degenerate_surface:{degenerate_ratio:.3f}")
        if not math.isfinite(aspect) or aspect > 120.0:
            reasons.append(f"collapsed_or_extreme_bounds:{aspect:.2f}")

        ordered_axes = sorted(axis_fraction, reverse=True)
        if (
            aligned98 > 0.94
            and alignment > 0.985
            and ordered_axes[0] + ordered_axes[1] > 0.96
            and ordered_axes[2] < 0.05
        ):
            reasons.append(
                "billboard_cross_detected:"
                f"aligned98={aligned98:.3f},axis={','.join(f'{x:.3f}' for x in axis_fraction)}"
            )

        if require_normals and missing_normal_primitives:
            reasons.append(
                "missing_vertex_normals:"
                f"{missing_normal_primitives}/{triangle_primitives}_triangle_primitives"
            )

        fragmentation_reason = _catastrophic_fragmentation_reason(
            components, largest_fraction
        )
        if fragmentation_reason:
            reasons.append(fragmentation_reason)

        # TRELLIS can legitimately emit disconnected clothing/hair/accessory
        # islands. Moderate fragmentation remains telemetry; only the extreme
        # failed-extraction regime above is a hard reject.
        if components > 128 and largest_fraction < 0.45:
            warnings.append(
                f"fragmented_surface:components={components},largest={largest_fraction:.3f}"
            )
        if components > 512:
            warnings.append(f"high_component_count:{components}")

        return MeshGateReport(
            path=str(path),
            valid=True,
            passed=not reasons,
            vertices=len(vertices),
            faces=len(faces),
            triangle_primitives=triangle_primitives,
            normal_primitives=normal_primitives,
            missing_normal_primitives=missing_normal_primitives,
            components=components,
            largest_component_fraction=round(largest_fraction, 6),
            degenerate_ratio=round(degenerate_ratio, 6),
            bbox_extents=[round(x, 8) for x in ext],
            bbox_aspect_ratio=round(aspect, 6) if math.isfinite(aspect) else float("inf"),
            axis_alignment_weighted=round(alignment, 6),
            axis_aligned_area_98=round(aligned98, 6),
            dominant_normal_axis_area=[round(x, 6) for x in axis_fraction],
            reasons=reasons,
            warnings=warnings,
        )
    except Exception as exc:
        return MeshGateReport(
            path=str(path),
            valid=False,
            passed=False,
            vertices=0,
            faces=0,
            triangle_primitives=triangle_primitives,
            normal_primitives=normal_primitives,
            missing_normal_primitives=missing_normal_primitives,
            components=0,
            largest_component_fraction=0.0,
            degenerate_ratio=1.0,
            bbox_extents=[],
            bbox_aspect_ratio=float("inf"),
            axis_alignment_weighted=1.0,
            axis_aligned_area_98=1.0,
            dominant_normal_axis_area=[],
            reasons=[f"{type(exc).__name__}:{exc}"],
            warnings=[],
        )

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="HAYUYA lightweight catastrophic-mesh gate.")
    parser.add_argument("glb", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--require-normals", action="store_true")
    args = parser.parse_args()
    report = inspect(args.glb, require_normals=args.require_normals)
    payload = json.dumps(asdict(report), indent=2)
    print(payload)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + "\n", encoding="utf-8")
    return 0 if report.passed else 3

if __name__ == "__main__":
    raise SystemExit(main())
