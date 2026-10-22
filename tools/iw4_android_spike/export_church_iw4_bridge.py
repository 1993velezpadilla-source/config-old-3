#!/usr/bin/env python3
"""Export Xziel XZSM v4 church geometry into an IW4 bridge staging directory.

This does not generate proprietary IW4 fastfiles. It converts our own runtime
geometry into neutral OBJ chunks and a machine-readable manifest that can be
fed into a locally installed IW3/IW4 custom-map toolchain.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path


FILE_HEADER = struct.Struct("<4sIIII")
BATCH_HEADER = struct.Struct("<II96sI6f")
VERTEX = struct.Struct("<8f4B")
INDEX = struct.Struct("<H")
XZSM_VERSION = 4
MAX_UINT16_VERTICES = 65535


@dataclass
class Batch:
    index: int
    vertex_count: int
    index_count: int
    texture: str
    flags: int
    mins: tuple[float, float, float]
    maxs: tuple[float, float, float]
    vertices: list[tuple]
    indices: list[int]

    @property
    def triangle_count(self) -> int:
        return self.index_count // 3

    @property
    def double_sided(self) -> bool:
        return bool(self.flags & 1)


def _decode_c_string(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("utf-8", errors="strict")


def parse_xzsm(path: Path) -> tuple[dict, list[Batch]]:
    data = path.read_bytes()
    if len(data) < FILE_HEADER.size:
        raise ValueError("XZSM is truncated")

    magic, version, batch_count, total_vertices, total_indices = FILE_HEADER.unpack_from(
        data, 0
    )
    if magic != b"XZSM":
        raise ValueError("not an XZSM file")
    if version != XZSM_VERSION:
        raise ValueError(f"unsupported XZSM version {version}; expected 4")

    cursor = FILE_HEADER.size
    batches: list[Batch] = []
    seen_vertices = 0
    seen_indices = 0

    for batch_index in range(batch_count):
        if cursor + BATCH_HEADER.size > len(data):
            raise ValueError(f"batch {batch_index}: truncated header")
        (
            vertex_count,
            index_count,
            texture_raw,
            flags,
            min_x,
            min_y,
            min_z,
            max_x,
            max_y,
            max_z,
        ) = BATCH_HEADER.unpack_from(data, cursor)
        cursor += BATCH_HEADER.size

        if vertex_count > MAX_UINT16_VERTICES:
            raise ValueError(
                f"batch {batch_index}: {vertex_count} vertices exceed uint16 limit"
            )
        if index_count % 3:
            raise ValueError(
                f"batch {batch_index}: index count {index_count} is not triangles"
            )

        vertex_bytes = vertex_count * VERTEX.size
        index_bytes = index_count * INDEX.size
        if cursor + vertex_bytes + index_bytes > len(data):
            raise ValueError(f"batch {batch_index}: truncated payload")

        vertices = [
            VERTEX.unpack_from(data, cursor + i * VERTEX.size)
            for i in range(vertex_count)
        ]
        cursor += vertex_bytes

        if index_count:
            indices = list(
                struct.unpack_from("<" + "H" * index_count, data, cursor)
            )
        else:
            indices = []
        cursor += index_bytes

        if indices and max(indices) >= vertex_count:
            raise ValueError(f"batch {batch_index}: index references missing vertex")

        batch = Batch(
            index=batch_index,
            vertex_count=vertex_count,
            index_count=index_count,
            texture=_decode_c_string(texture_raw),
            flags=flags,
            mins=(min_x, min_y, min_z),
            maxs=(max_x, max_y, max_z),
            vertices=vertices,
            indices=indices,
        )
        batches.append(batch)
        seen_vertices += vertex_count
        seen_indices += index_count

    if cursor != len(data):
        raise ValueError(
            f"XZSM has {len(data) - cursor} unexpected trailing bytes"
        )
    if seen_vertices != total_vertices or seen_indices != total_indices:
        raise ValueError(
            "XZSM aggregate counts do not match its batch payloads"
        )

    return (
        {
            "version": version,
            "batchCount": batch_count,
            "totalVertices": total_vertices,
            "totalIndices": total_indices,
            "totalTriangles": total_indices // 3,
        },
        batches,
    )


def write_obj(batch: Batch, out_dir: Path) -> dict:
    stem = f"sanctum_batch_{batch.index:04d}"
    obj_path = out_dir / f"{stem}.obj"
    mtl_path = out_dir / f"{stem}.mtl"

    material_name = f"{stem}_material"
    texture_leaf = Path(batch.texture).name
    if not texture_leaf.lower().endswith((".png", ".tga", ".jpg", ".jpeg", ".dds")):
        texture_leaf += ".png"

    with obj_path.open("w", encoding="utf-8", newline="\n") as out:
        out.write("# Xziel -> IW4 bridge staging geometry\n")
        out.write(f"mtllib {mtl_path.name}\n")
        out.write(f"o {stem}\n")
        out.write(f"usemtl {material_name}\n")

        for vertex in batch.vertices:
            x, y, z, nx, ny, nz, u, v, *_rgba = vertex
            # Keep Xziel native coordinates unchanged in staging. Axis/scale
            # conversion belongs to the local CoD asset compiler preset so it
            # can be calibrated once against a known unit cube.
            out.write(f"v {x:.9g} {y:.9g} {z:.9g}\n")
        for vertex in batch.vertices:
            _x, _y, _z, _nx, _ny, _nz, u, v, *_rgba = vertex
            out.write(f"vt {u:.9g} {v:.9g}\n")
        for vertex in batch.vertices:
            _x, _y, _z, nx, ny, nz, _u, _v, *_rgba = vertex
            out.write(f"vn {nx:.9g} {ny:.9g} {nz:.9g}\n")

        for tri in range(0, len(batch.indices), 3):
            a, b, c = (batch.indices[tri + i] + 1 for i in range(3))
            out.write(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n")

    with mtl_path.open("w", encoding="utf-8", newline="\n") as out:
        out.write(f"newmtl {material_name}\n")
        out.write("Kd 1 1 1\n")
        out.write("Ka 0 0 0\n")
        out.write("Ks 0 0 0\n")
        out.write(f"map_Kd {texture_leaf}\n")

    return {
        "id": stem,
        "obj": obj_path.name,
        "mtl": mtl_path.name,
        "sourceTexture": batch.texture,
        "expectedTextureLeaf": texture_leaf,
        "vertexCount": batch.vertex_count,
        "indexCount": batch.index_count,
        "triangleCount": batch.triangle_count,
        "doubleSided": batch.double_sided,
        "boundsMin": list(batch.mins),
        "boundsMax": list(batch.maxs),
        "iw4Role": "static_model_visual",
        "collisionAuthority": False,
    }


def export_bridge(xzsm: Path, out_dir: Path, map_name: str) -> dict:
    header, batches = parse_xzsm(xzsm)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = [write_obj(batch, out_dir) for batch in batches]

    manifest = {
        "schema": 1,
        "bridge": "xziel_xzsm_v4_to_iw4_usermap_staging",
        "mapName": map_name,
        "source": {
            "path": str(xzsm),
            **header,
        },
        "visualChunks": records,
        "collision": {
            "required": True,
            "strategy": "authored_coarse_world_shell",
            "reason": (
                "Photogrammetry/static visual chunks are not accepted as IW4 "
                "player collision authority."
            ),
        },
        "nextStages": [
            "compile each OBJ chunk as a local custom XModel/static model",
            "bind/copy matching original church textures in the local toolchain",
            "author coarse worldspawn/player collision and spawn volume",
            "place visual chunks at a calibrated common origin",
            "build an IW3/IW4 custom map locally",
            "port/build the map into MW2 usermaps/xziel_sanctum",
            "launch the Android compatibility profile with +map xziel_sanctum",
        ],
        "containsProprietaryGamePayload": False,
    }

    (out_dir / "iw4_bridge_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xzsm", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--map-name", default="xziel_sanctum")
    args = parser.parse_args()

    manifest = export_bridge(args.xzsm, args.out_dir, args.map_name)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
