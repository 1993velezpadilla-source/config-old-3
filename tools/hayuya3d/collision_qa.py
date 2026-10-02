#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class CollisionQAAudit:
    master:str
    collision:str|None
    applicable:bool
    ready:bool
    vertices:int
    faces:int
    watertight:bool
    finite:bool
    positive_volume:bool
    volume:float|None
    convexity_ratio:float|None
    bbox_coverage_ready:bool
    bbox_min_delta_ratio:float|None
    bbox_max_delta_ratio:float|None
    warnings:list[str]
    errors:list[str]
    method:str="hayuya-collision-qa-v1"


def _deps():
    import numpy as np
    import trimesh
    return np,trimesh


def _combined(path:Path):
    np,trimesh=_deps()
    loaded=trimesh.load(path,force="scene",process=False)
    meshes=[]
    for node_name in loaded.graph.nodes_geometry:
        transform,geom_name=loaded.graph[node_name]
        geom=loaded.geometry[geom_name]
        if not hasattr(geom,"faces") or not len(geom.faces):
            continue
        copy=geom.copy()
        copy.apply_transform(transform)
        meshes.append(copy)
    if not meshes:
        raise ValueError("no triangle geometry")
    return trimesh.util.concatenate(meshes)


def audit_collision(
    master:Path,
    collision:Path|None,
    *,
    bbox_tolerance_ratio:float=0.02,
    min_convexity_ratio:float=0.98,
    max_convexity_ratio:float=1.02,
)->CollisionQAAudit:
    np,trimesh=_deps()
    warnings=[]
    errors=[]
    if collision is None:
        return CollisionQAAudit(
            master=str(master),
            collision=None,
            applicable=False,
            ready=False,
            vertices=0,
            faces=0,
            watertight=False,
            finite=False,
            positive_volume=False,
            volume=None,
            convexity_ratio=None,
            bbox_coverage_ready=False,
            bbox_min_delta_ratio=None,
            bbox_max_delta_ratio=None,
            warnings=[],
            errors=["collision proxy missing"],
        )

    collision=Path(collision)
    if not collision.is_file():
        return CollisionQAAudit(
            master=str(master),
            collision=str(collision),
            applicable=False,
            ready=False,
            vertices=0,
            faces=0,
            watertight=False,
            finite=False,
            positive_volume=False,
            volume=None,
            convexity_ratio=None,
            bbox_coverage_ready=False,
            bbox_min_delta_ratio=None,
            bbox_max_delta_ratio=None,
            warnings=[],
            errors=["collision proxy path does not exist"],
        )

    try:
        master_mesh=_combined(master)
        proxy=_combined(collision)
        vertices=np.asarray(proxy.vertices,dtype=np.float64)
        faces=np.asarray(proxy.faces,dtype=np.int64)
        finite=bool(
            len(vertices)
            and len(faces)
            and np.isfinite(vertices).all()
        )
        watertight=bool(proxy.is_watertight)
        volume=None
        positive_volume=False
        if finite and watertight:
            try:
                volume=abs(float(proxy.volume))
                positive_volume=bool(
                    math.isfinite(volume)
                    and volume>1e-12
                )
            except Exception:
                volume=None
                positive_volume=False

        convexity_ratio=None
        if positive_volume:
            try:
                hull=proxy.convex_hull
                hull_volume=abs(float(hull.volume))
                if (
                    math.isfinite(hull_volume)
                    and hull_volume>1e-12
                ):
                    convexity_ratio=volume/hull_volume
                    if not (
                        min_convexity_ratio
                        <=convexity_ratio
                        <=max_convexity_ratio
                    ):
                        errors.append(
                            "collision proxy is not sufficiently convex: "
                            f"ratio={convexity_ratio:.6f}"
                        )
            except Exception as exc:
                errors.append(
                    "collision convexity audit failed: "
                    f"{type(exc).__name__}:{exc}"
                )

        master_vertices=np.asarray(
            master_mesh.vertices,
            dtype=np.float64,
        )
        master_lo=np.min(master_vertices,axis=0)
        master_hi=np.max(master_vertices,axis=0)
        proxy_lo=np.min(vertices,axis=0)
        proxy_hi=np.max(vertices,axis=0)
        master_extent=master_hi-master_lo
        diagonal=max(
            float(np.linalg.norm(master_extent)),
            1e-9,
        )
        min_delta=np.maximum(
            0.0,
            proxy_lo-master_lo,
        )
        max_delta=np.maximum(
            0.0,
            master_hi-proxy_hi,
        )
        min_ratio=float(
            np.max(min_delta)/diagonal
        )
        max_ratio=float(
            np.max(max_delta)/diagonal
        )
        bbox_ready=bool(
            min_ratio<=bbox_tolerance_ratio
            and max_ratio<=bbox_tolerance_ratio
        )

        if not finite:
            errors.append(
                "collision proxy has empty or non-finite geometry"
            )
        if len(faces)<4:
            errors.append(
                f"collision proxy has too few faces: {len(faces)}"
            )
        if not watertight:
            errors.append(
                "collision proxy is not watertight"
            )
        if not positive_volume:
            errors.append(
                "collision proxy has no positive enclosed volume"
            )
        if not bbox_ready:
            errors.append(
                "collision proxy does not cover Hero Master bounds: "
                f"min_delta={min_ratio:.6f} "
                f"max_delta={max_ratio:.6f} "
                f"tol={bbox_tolerance_ratio:.6f}"
            )

        return CollisionQAAudit(
            master=str(master),
            collision=str(collision),
            applicable=True,
            ready=not errors,
            vertices=int(len(vertices)),
            faces=int(len(faces)),
            watertight=watertight,
            finite=finite,
            positive_volume=positive_volume,
            volume=(
                None if volume is None
                else round(float(volume),8)
            ),
            convexity_ratio=(
                None if convexity_ratio is None
                else round(float(convexity_ratio),8)
            ),
            bbox_coverage_ready=bbox_ready,
            bbox_min_delta_ratio=round(min_ratio,8),
            bbox_max_delta_ratio=round(max_ratio,8),
            warnings=warnings,
            errors=errors,
        )
    except Exception as exc:
        return CollisionQAAudit(
            master=str(master),
            collision=str(collision),
            applicable=True,
            ready=False,
            vertices=0,
            faces=0,
            watertight=False,
            finite=False,
            positive_volume=False,
            volume=None,
            convexity_ratio=None,
            bbox_coverage_ready=False,
            bbox_min_delta_ratio=None,
            bbox_max_delta_ratio=None,
            warnings=warnings,
            errors=[
                f"{type(exc).__name__}:{exc}"
            ],
        )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="HAYUYA runtime collision proxy QA."
    )
    parser.add_argument(
        "--master",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--collision",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--json",
        type=Path,
    )
    args=parser.parse_args()
    result=audit_collision(
        args.master,
        args.collision,
    )
    payload=json.dumps(
        asdict(result),
        indent=2,
    )
    print(payload)
    if args.json:
        args.json.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.json.write_text(
            payload+"\n",
            encoding="utf-8",
        )
    return 0 if result.ready else 2


if __name__=="__main__":
    raise SystemExit(main())
