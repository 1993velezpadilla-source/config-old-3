#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

import coacd
import numpy as np
import trimesh


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def load_mesh(path: Path) -> trimesh.Trimesh:
    loaded=trimesh.load(path, force="mesh", process=False)
    if not isinstance(loaded, trimesh.Trimesh):
        raise RuntimeError(f"expected triangle mesh, got {type(loaded)!r}")
    if len(loaded.vertices) < 4 or len(loaded.faces) < 4:
        raise RuntimeError("input collision mesh is too small")
    if loaded.faces.shape[1] != 3:
        raise RuntimeError("input collision mesh must be triangulated")
    loaded.remove_unreferenced_vertices()
    return loaded


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--threshold", type=float, default=0.08)
    ap.add_argument("--max-hulls", type=int, default=128)
    ap.add_argument("--max-hull-vertices", type=int, default=64)
    ap.add_argument("--real-metric", action="store_true")
    args=ap.parse_args()

    src=Path(args.input).resolve()
    dst=Path(args.output).resolve()
    report_path=Path(args.report).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    mesh=load_mesh(src)
    vertices=np.asarray(mesh.vertices,dtype=np.float64)
    faces=np.asarray(mesh.faces,dtype=np.int32)

    source=coacd.Mesh(vertices,faces)
    parts=coacd.run_coacd(
        source,
        threshold=float(args.threshold),
        max_convex_hull=int(args.max_hulls),
        preprocess_mode="auto",
        preprocess_resolution=50,
        resolution=2000,
        mcts_nodes=20,
        mcts_iterations=150,
        mcts_max_depth=3,
        merge=True,
        decimate=True,
        max_ch_vertex=int(args.max_hull_vertices),
        seed=0,
        real_metric=bool(args.real_metric),
    )

    if not parts:
        raise SystemExit("XZIEL_COACD_FAIL: no convex hulls generated")

    scene=trimesh.Scene()
    hull_rows=[]
    total_vertices=0
    total_faces=0

    for i,(pv,pf) in enumerate(parts):
        hull=trimesh.Trimesh(
            vertices=np.asarray(pv,dtype=np.float64),
            faces=np.asarray(pf,dtype=np.int64),
            process=False,
        )
        hull.remove_unreferenced_vertices()
        if len(hull.vertices) < 4 or len(hull.faces) < 4:
            continue
        name=f"XZIEL_COLLISION_HULL_{i:03d}"
        scene.add_geometry(hull,node_name=name,geom_name=name)
        total_vertices += len(hull.vertices)
        total_faces += len(hull.faces)
        hull_rows.append({
            "name":name,
            "vertices":int(len(hull.vertices)),
            "triangles":int(len(hull.faces)),
            "volume":float(abs(hull.volume)),
            "bounds":np.asarray(hull.bounds,dtype=float).tolist(),
        })

    if not hull_rows:
        raise SystemExit("XZIEL_COACD_FAIL: all generated hulls were empty")

    scene.export(file_obj=str(dst),file_type="glb")
    if not dst.is_file() or dst.stat().st_size < 256:
        raise SystemExit("XZIEL_COACD_FAIL: output GLB missing or empty")

    report={
        "status":"PASS",
        "tool":"CoACD + trimesh",
        "trimesh_version":trimesh.__version__,
        "input":str(src),
        "input_bytes":src.stat().st_size,
        "input_sha256":sha256(src),
        "input_vertices":int(len(mesh.vertices)),
        "input_triangles":int(len(mesh.faces)),
        "threshold":float(args.threshold),
        "real_metric":bool(args.real_metric),
        "max_hulls":int(args.max_hulls),
        "max_hull_vertices":int(args.max_hull_vertices),
        "hull_count":len(hull_rows),
        "hull_vertices":int(total_vertices),
        "hull_triangles":int(total_faces),
        "output":str(dst),
        "output_bytes":dst.stat().st_size,
        "output_sha256":sha256(dst),
        "hulls":hull_rows,
        "runtime_note":(
            "Convex decomposition is a candidate collision sidecar. Existing fitted "
            "collision remains fallback authority until the XZIEL runtime loader is wired."
        ),
    }
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("XZIEL_COACD_COLLISION_PASS")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
