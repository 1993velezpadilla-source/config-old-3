#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--exclude-prefix",
        action="append",
        default=["SANCTUM_OUTER_BAKED", "SANCTUM_COSMETIC_"],
        help="Scene-node prefix to exclude from runtime collision/navigation geometry.",
    )
    args = ap.parse_args()

    src = Path(args.input).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    loaded = trimesh.load(src, force="scene", process=False)
    scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)

    collision_pieces = []
    nav_pieces = []
    included = []
    excluded = []
    nav_nodes = []

    def is_authored_nav_node(name: str) -> bool:
        return (
            name == "SANCTUM_GAMEPLAY_FLOOR"
            or name.startswith("SANCTUM_MAIN_FLOOR_")
            or name == "SANCTUM_UNDERCROFT_FLOOR"
            or name.startswith("SANCTUM_UNDERCROFT_RAMP_")
            or name.startswith("SANCTUM_UPPER_RAMP_")
            or name == "SANCTUM_UPPER_REAR_BRIDGE"
            or (name.startswith("SANCTUM_UPPER_") and name.endswith("_WALKWAY"))
        )

    for node in sorted(scene.graph.nodes_geometry):
        node_name = str(node)
        transform, geometry_name = scene.graph.get(node)

        if any(node_name.startswith(prefix) for prefix in args.exclude_prefix):
            excluded.append(node_name)
            continue

        geom = scene.geometry[geometry_name].copy()
        geom.apply_transform(transform)
        if len(geom.vertices) < 3 or len(geom.faces) < 1:
            continue

        # Runtime navigation/collision sidecars do not need authored textures.
        # Stripping visuals keeps the OBJ/GLB deterministic and lightweight.
        geom.visual = trimesh.visual.ColorVisuals(mesh=geom)
        collision_pieces.append(geom)
        if is_authored_nav_node(node_name):
            nav_pieces.append(geom.copy())
            nav_nodes.append(node_name)
        included.append({
            "node": node_name,
            "geometry": str(geometry_name),
            "vertices": int(len(geom.vertices)),
            "triangles": int(len(geom.faces)),
        })

    if not collision_pieces:
        raise SystemExit("XZIEL_RUNTIME_GEOMETRY_FAIL: no included mesh geometry")

    # Older Sanctum builds used one node named SANCTUM_GAMEPLAY_FLOOR.
    # The vertical map intentionally segments that floor so real stair openings
    # can exist. Accept either representation, but still require an authored
    # main gameplay floor family so a shell-only export cannot pass.
    floor_nodes = [
        row["node"] for row in included
        if row["node"] == "SANCTUM_GAMEPLAY_FLOOR"
        or row["node"].startswith("SANCTUM_MAIN_FLOOR_")
    ]
    if not floor_nodes:
        raise SystemExit("XZIEL_RUNTIME_GEOMETRY_FAIL: gameplay floor missing")

    if not nav_pieces:
        raise SystemExit("XZIEL_RUNTIME_GEOMETRY_FAIL: no authored navigation geometry")

    collision_merged = trimesh.util.concatenate(collision_pieces)
    collision_merged.remove_unreferenced_vertices()
    nav_merged = trimesh.util.concatenate(nav_pieces)
    nav_merged.remove_unreferenced_vertices()

    if len(collision_merged.vertices) < 4 or len(collision_merged.faces) < 2:
        raise SystemExit("XZIEL_RUNTIME_GEOMETRY_FAIL: merged collision mesh too small")
    if len(nav_merged.vertices) < 4 or len(nav_merged.faces) < 2:
        raise SystemExit("XZIEL_RUNTIME_GEOMETRY_FAIL: merged nav mesh too small")

    nav_obj = out / "sanctum-nav-source.obj"
    collision_glb = out / "sanctum-collision-source.glb"
    report_path = out / "runtime-geometry-report.json"

    # Navigation intentionally uses only authored gameplay surfaces. Feeding
    # the full art mesh to Recast let arches, ledges and decorative masonry
    # occlude otherwise valid upper-floor spans. Collision still uses the full
    # runtime geometry, so visual/detail meshes remain physically represented.
    #
    # glTF is Y-up and trimesh preserves that world-space convention. The OBJ
    # therefore feeds Recast with Y as the vertical axis without a second
    # coordinate conversion.
    nav_merged.export(nav_obj, include_texture=False)
    collision_merged.export(collision_glb)

    report = {
        "status": "PASS",
        "tool": "trimesh runtime geometry extractor",
        "trimesh_version": trimesh.__version__,
        "input": str(src),
        "input_bytes": src.stat().st_size,
        "input_sha256": sha256(src),
        "excluded_prefixes": list(args.exclude_prefix),
        "included_nodes": included,
        "excluded_nodes": excluded,
        "floor_nodes": floor_nodes,
        "nav_nodes": nav_nodes,
        "included_node_count": len(included),
        "excluded_node_count": len(excluded),
        "vertices": int(len(collision_merged.vertices)),
        "triangles": int(len(collision_merged.faces)),
        "bounds": np.asarray(collision_merged.bounds, dtype=float).tolist(),
        "nav_vertices": int(len(nav_merged.vertices)),
        "nav_triangles": int(len(nav_merged.faces)),
        "nav_bounds": np.asarray(nav_merged.bounds, dtype=float).tolist(),
        "nav_obj": nav_obj.name,
        "nav_obj_bytes": nav_obj.stat().st_size,
        "nav_obj_sha256": sha256(nav_obj),
        "collision_glb": collision_glb.name,
        "collision_glb_bytes": collision_glb.stat().st_size,
        "collision_glb_sha256": sha256(collision_glb),
        "axis_policy": "Y-up inherited from exported glTF world coordinates",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("XZIEL_RUNTIME_GEOMETRY_PASS")
    print(json.dumps({
        "included_nodes": report["included_node_count"],
        "excluded_nodes": report["excluded_node_count"],
        "floor_nodes": report["floor_nodes"],
        "nav_nodes": report["nav_nodes"],
        "vertices": report["vertices"],
        "triangles": report["triangles"],
        "nav_vertices": report["nav_vertices"],
        "nav_triangles": report["nav_triangles"],
        "nav_obj_bytes": report["nav_obj_bytes"],
        "collision_glb_bytes": report["collision_glb_bytes"],
    }, indent=2))


if __name__ == "__main__":
    main()
