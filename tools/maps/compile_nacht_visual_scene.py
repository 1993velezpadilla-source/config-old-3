#!/usr/bin/env python3
"""Compile exported Nacht StaticMesh GLBs + persisted placements into XZIEL visual scene metadata.

This compiler is deliberately geometry-only. It proves that every one of the
492 referenced StaticMesh packages has a valid GLB export and that every one of
the 10,791 persisted scene instances resolves to one of those meshes. It emits
runtime-friendly XZIEL-basis transform matrices and per-asset hashes.

No third-party mesh bytes are committed by this tool. The GLBs remain external
user-owned/licensed payload mounted at build/install time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_ROOT = ROOT / "assets/nacht_reference/pavlov_scene_reference"
EXPECTED_MESHES = 492
EXPECTED_INSTANCES = 10791
GLB_MAGIC = 0x46546C67
GLB_JSON = 0x4E4F534A


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def mesh_basename(source_path: str) -> str:
    value = source_path.replace("\\", "/").rstrip("/")
    name = value.rsplit("/", 1)[-1]
    if not name:
        raise ValueError(f"invalid mesh source path: {source_path!r}")
    return name


def inspect_glb(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError(f"GLB too small: {path}")
    magic, version, declared = struct.unpack_from("<III", raw, 0)
    if magic != GLB_MAGIC:
        raise ValueError(f"not a GLB file: {path}")
    if version != 2:
        raise ValueError(f"GLB version must be 2: {path}")
    if declared != len(raw):
        raise ValueError(f"GLB length mismatch: {path}")
    chunk_len, chunk_type = struct.unpack_from("<II", raw, 12)
    if chunk_type != GLB_JSON:
        raise ValueError(f"first GLB chunk must be JSON: {path}")
    end = 20 + chunk_len
    if end > len(raw):
        raise ValueError(f"GLB JSON chunk overflow: {path}")
    payload = raw[20:end].rstrip(b" \t\r\n\x00")
    try:
        doc = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid GLB JSON: {path}: {exc}") from exc
    if str(doc.get("asset", {}).get("version")) != "2.0":
        raise ValueError(f"GLB asset.version must be 2.0: {path}")
    meshes = doc.get("meshes", [])
    primitive_count = sum(
        len(mesh.get("primitives", []))
        for mesh in meshes
        if isinstance(mesh, dict)
    )
    if not meshes or primitive_count <= 0:
        raise ValueError(f"GLB contains no renderable mesh primitives: {path}")
    return {
        "meshObjects": len(meshes),
        "primitives": primitive_count,
        "materials": len(doc.get("materials", [])),
        "images": len(doc.get("images", [])),
        "textures": len(doc.get("textures", [])),
    }


def matmul3(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)]
        for r in range(3)
    ]


def ue_rotation_xziel(rot: dict | None) -> list[list[float]]:
    if not isinstance(rot, dict):
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    p = math.radians(float(rot.get("Pitch", 0.0) or 0.0))
    y = math.radians(float(rot.get("Yaw", 0.0) or 0.0))
    r = math.radians(float(rot.get("Roll", 0.0) or 0.0))
    sp, sy, sr = math.sin(p), math.sin(y), math.sin(r)
    cp, cy, cr = math.cos(p), math.cos(y), math.cos(r)

    # Unreal FRotationTranslationMatrix rows.
    ue_rows = [
        [cp * cy, cp * sy, sp],
        [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp],
        [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp],
    ]

    # Old validation workflow used Matrix(rows).transposed() for column-vector
    # math, then B @ R @ B for UE (X,Y,Z) -> XZIEL (X,-Y,Z).
    ue_col = [[ue_rows[c][r] for c in range(3)] for r in range(3)]
    basis = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
    return matmul3(matmul3(basis, ue_col), basis)


def transform_matrix(transform: dict | None) -> tuple[list[float], dict[str, bool]]:
    transform = transform if isinstance(transform, dict) else {}
    pos = transform.get("position")
    rotation = transform.get("sourceRotationUE")
    scale = transform.get("sourceScale")

    defaults = {
        "position": not isinstance(pos, dict),
        "rotation": not isinstance(rotation, dict),
        "scale": not isinstance(scale, dict),
    }

    if not isinstance(pos, dict):
        pos = {"x": 0.0, "y": 0.0, "z": 0.0}
    if not isinstance(scale, dict):
        scale = {"X": 1.0, "Y": 1.0, "Z": 1.0}

    tx = float(pos.get("x", 0.0) or 0.0)
    ty = float(pos.get("y", 0.0) or 0.0)
    tz = float(pos.get("z", 0.0) or 0.0)
    sx = float(scale.get("X", 1.0) or 1.0)
    sy = float(scale.get("Y", 1.0) or 1.0)
    sz = float(scale.get("Z", 1.0) or 1.0)

    rot = ue_rotation_xziel(rotation)
    # Row-major 4x4, column-vector convention: T * R * S.
    matrix = [
        rot[0][0] * sx, rot[0][1] * sy, rot[0][2] * sz, tx,
        rot[1][0] * sx, rot[1][1] * sy, rot[1][2] * sz, ty,
        rot[2][0] * sx, rot[2][1] * sy, rot[2][2] * sz, tz,
        0.0, 0.0, 0.0, 1.0,
    ]
    return matrix, defaults


def index_glbs(root: Path) -> dict[str, Path]:
    by_stem: dict[str, list[Path]] = {}
    for path in root.rglob("*.glb"):
        by_stem.setdefault(path.stem.lower(), []).append(path)
    duplicates = {k: v for k, v in by_stem.items() if len(v) > 1}
    if duplicates:
        names = ", ".join(sorted(duplicates)[:8])
        raise SystemExit(f"XZIEL visual scene rejected: duplicate GLB basenames: {names}")
    return {k: v[0] for k, v in by_stem.items()}


def compile_scene(reference_root: Path, mesh_root: Path) -> dict:
    assets = json.loads((reference_root / "assets.json").read_text(encoding="utf-8"))
    scene = json.loads((reference_root / "scene_instances.json").read_text(encoding="utf-8"))
    environment = json.loads((reference_root / "environment.json").read_text(encoding="utf-8"))

    asset_rows = assets.get("meshes", [])
    instances = scene.get("instances", [])
    env_rows = environment.get("actors", [])

    if assets.get("uniqueMeshCount") != EXPECTED_MESHES or len(asset_rows) != EXPECTED_MESHES:
        raise SystemExit(
            f"XZIEL visual scene rejected: expected {EXPECTED_MESHES} mesh references"
        )
    if len(instances) != EXPECTED_INSTANCES:
        raise SystemExit(
            f"XZIEL visual scene rejected: expected {EXPECTED_INSTANCES} scene instances, got {len(instances)}"
        )

    source_paths = [row.get("sourcePath") for row in asset_rows]
    if any(not isinstance(p, str) or not p for p in source_paths):
        raise SystemExit("XZIEL visual scene rejected: invalid sourcePath")
    if len(set(source_paths)) != EXPECTED_MESHES:
        raise SystemExit("XZIEL visual scene rejected: mesh source paths are not unique")

    basenames = [mesh_basename(p) for p in source_paths]
    if len({x.lower() for x in basenames}) != EXPECTED_MESHES:
        raise SystemExit("XZIEL visual scene rejected: mesh basenames collide")

    glbs = index_glbs(mesh_root)
    missing = [
        name for name in basenames
        if name.lower() not in glbs
    ]
    if missing:
        raise SystemExit(
            "XZIEL visual scene rejected: missing exported GLBs: "
            + ", ".join(missing[:20])
            + (f" (+{len(missing)-20} more)" if len(missing) > 20 else "")
        )

    mesh_index: dict[str, int] = {}
    compiled_meshes = []
    total_bytes = 0
    primitive_count = 0
    for index, row in enumerate(asset_rows):
        source = row["sourcePath"]
        name = mesh_basename(source)
        path = glbs[name.lower()]
        info = inspect_glb(path)
        size = path.stat().st_size
        total_bytes += size
        primitive_count += info["primitives"]
        mesh_index[source] = index
        compiled_meshes.append({
            "index": index,
            "id": row["id"],
            "sourcePath": source,
            "sourceBasename": name,
            "runtimeFile": f"meshes/{name}.glb",
            "bytes": size,
            "sha256": sha256(path),
            "gltf": info,
        })

    compiled_instances = []
    referenced = set()
    default_counts = {"position": 0, "rotation": 0, "scale": 0}
    for index, row in enumerate(instances):
        source = row.get("mesh")
        if source not in mesh_index:
            raise SystemExit(
                f"XZIEL visual scene rejected: instance {index} references unknown mesh {source!r}"
            )
        matrix, defaults = transform_matrix(row.get("transform"))
        for key, used in defaults.items():
            if used:
                default_counts[key] += 1
        referenced.add(source)
        compiled_instances.append({
            "instanceId": row.get("instanceId") or f"instance_{index:05d}",
            "meshIndex": mesh_index[source],
            "matrixRowMajor": [round(float(v), 9) for v in matrix],
        })

    if len(referenced) != EXPECTED_MESHES:
        raise SystemExit(
            f"XZIEL visual scene rejected: only {len(referenced)} of {EXPECTED_MESHES} meshes are referenced by the scene"
        )

    return {
        "schemaVersion": 1,
        "format": "xziel_visual_scene_v1",
        "mapId": "bo3_nacht_reference",
        "scope": "static_mesh_geometry",
        "coordinateSystem": {
            "units": "meters",
            "basis": "X,-Y,Z",
            "matrixConvention": "row_major_column_vector_T_R_S",
        },
        "policy": {
            "zeroOmission": True,
            "noSilentFallbacks": True,
            "meshPayloadExternal": True,
            "materialsPresentationReady": False,
            "lightingPresentationReady": False,
            "runtimePromotionRequiresPresentationLanes": True,
        },
        "summary": {
            "requiredMeshCount": EXPECTED_MESHES,
            "resolvedMeshCount": len(compiled_meshes),
            "sceneInstanceCount": len(compiled_instances),
            "referencedMeshCount": len(referenced),
            "totalMeshBytes": total_bytes,
            "totalPrimitives": primitive_count,
            "environmentActorReferenceCount": len(env_rows),
            "defaultTransformFields": default_counts,
            "geometryReady": True,
            "visualParityReady": False,
        },
        "meshes": compiled_meshes,
        "instances": compiled_instances,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference-root", type=Path, default=DEFAULT_REFERENCE_ROOT)
    ap.add_argument("--mesh-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    if not args.mesh_root.is_dir():
        raise SystemExit(f"mesh root is not a directory: {args.mesh_root}")

    result = compile_scene(args.reference_root, args.mesh_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
    print("XZIEL_NACHT_VISUAL_SCENE_OK", json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
