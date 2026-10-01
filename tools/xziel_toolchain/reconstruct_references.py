#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import open3d as o3d
import pycolmap

SUPPORTED = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def matrix34(rigid):
    r = np.asarray(rigid.rotation.matrix(), dtype=float)
    t = np.asarray(rigid.translation, dtype=float).reshape(3, 1)
    return np.concatenate([r, t], axis=1).tolist()


def enum_name(value):
    return getattr(value, "name", str(value))


def image_manifest(image_dir: Path):
    result = []
    for p in sorted(image_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            result.append(
                {
                    "name": p.relative_to(image_dir).as_posix(),
                    "bytes": p.stat().st_size,
                    "sha256": sha256(p),
                }
            )
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-image-size", type=int, default=2400)
    args = ap.parse_args()

    image_dir = Path(args.images).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    images = image_manifest(image_dir)
    if len(images) < 3:
        raise SystemExit(
            f"XZIEL_REFERENCE_RECON_FAIL: need at least 3 overlapping photos, found {len(images)}"
        )

    database_path = out / "database.db"
    sparse_dir = out / "sparse"
    if database_path.exists():
        database_path.unlink()
    if sparse_dir.exists():
        shutil.rmtree(sparse_dir)
    sparse_dir.mkdir(parents=True)

    pycolmap.set_random_seed(0)

    extraction = pycolmap.FeatureExtractionOptions()
    extraction.max_image_size = int(args.max_image_size)
    extraction.num_threads = -1
    extraction.use_gpu = False

    matching = pycolmap.FeatureMatchingOptions()
    matching.num_threads = -1
    matching.use_gpu = False

    pycolmap.extract_features(
        database_path=database_path,
        image_path=image_dir,
        camera_mode=pycolmap.CameraMode.AUTO,
        extraction_options=extraction,
        device=pycolmap.Device.cpu,
    )

    pycolmap.match_exhaustive(
        database_path=database_path,
        matching_options=matching,
        device=pycolmap.Device.cpu,
    )

    options = pycolmap.IncrementalPipelineOptions()
    options.min_model_size = 3
    options.multiple_models = True
    options.random_seed = 0
    options.num_threads = -1

    reconstructions = pycolmap.incremental_mapping(
        database_path=database_path,
        image_path=image_dir,
        output_path=sparse_dir,
        options=options,
    )

    if not reconstructions:
        raise SystemExit("XZIEL_REFERENCE_RECON_FAIL: COLMAP recovered no model")

    models = []
    if hasattr(reconstructions, "items"):
        iterator = reconstructions.items()
    else:
        iterator = enumerate(reconstructions)

    for model_id, rec in iterator:
        models.append(
            {
                "id": int(model_id),
                "reconstruction": rec,
                "registered_images": int(rec.num_reg_images()),
                "points3D": int(rec.num_points3D()),
            }
        )

    models.sort(
        key=lambda x: (x["registered_images"], x["points3D"]),
        reverse=True,
    )
    best_meta = models[0]
    best = best_meta["reconstruction"]

    if best_meta["registered_images"] < 3:
        raise SystemExit(
            "XZIEL_REFERENCE_RECON_FAIL: fewer than 3 registered images"
        )
    if best_meta["points3D"] < 20:
        raise SystemExit(
            f"XZIEL_REFERENCE_RECON_FAIL: sparse model too weak ({best_meta['points3D']} points)"
        )

    raw_ply = out / "sparse-points.ply"
    clean_ply = out / "sparse-points-clean.ply"
    best.export_PLY(str(raw_ply))

    cloud = o3d.io.read_point_cloud(str(raw_ply))
    raw_points = len(cloud.points)
    if raw_points < 20:
        raise SystemExit("XZIEL_REFERENCE_RECON_FAIL: exported PLY has too few points")

    if raw_points >= 40:
        nb = min(20, max(5, raw_points - 1))
        clean, indices = cloud.remove_statistical_outlier(
            nb_neighbors=nb,
            std_ratio=2.0,
        )
        if len(clean.points) >= 20:
            cloud = clean

    o3d.io.write_point_cloud(str(clean_ply), cloud, write_ascii=False)
    pts = np.asarray(cloud.points)
    bbox_min = pts.min(axis=0).tolist()
    bbox_max = pts.max(axis=0).tolist()

    cameras = []
    for image in best.images.values():
        camera = best.cameras[image.camera_id]
        cam_from_world = image.cam_from_world()
        world_from_cam = cam_from_world.inverse()
        cameras.append(
            {
                "image_id": int(image.image_id),
                "image_name": str(image.name),
                "camera_id": int(image.camera_id),
                "camera_model": enum_name(camera.model),
                "width": int(camera.width),
                "height": int(camera.height),
                "params": np.asarray(camera.params, dtype=float).tolist(),
                "cam_from_world_3x4": matrix34(cam_from_world),
                "world_from_cam_3x4": matrix34(world_from_cam),
            }
        )

    cameras.sort(key=lambda x: x["image_name"])
    (out / "cameras.json").write_text(
        json.dumps(cameras, indent=2),
        encoding="utf-8",
    )

    report = {
        "status": "PASS",
        "tool": "pyCOLMAP + Open3D",
        "pycolmap_version": pycolmap.__version__,
        "open3d_version": o3d.__version__,
        "input_dir": str(image_dir),
        "input_images": images,
        "input_image_count": len(images),
        "models": [
            {
                "id": m["id"],
                "registered_images": m["registered_images"],
                "points3D": m["points3D"],
            }
            for m in models
        ],
        "selected_model": {
            "id": best_meta["id"],
            "registered_images": best_meta["registered_images"],
            "points3D": best_meta["points3D"],
        },
        "clean_point_count": int(len(cloud.points)),
        "bbox": {
            "min": bbox_min,
            "max": bbox_max,
            "size": (np.asarray(bbox_max) - np.asarray(bbox_min)).tolist(),
        },
        "camera_count": len(cameras),
        "database": database_path.name,
        "raw_ply": raw_ply.name,
        "clean_ply": clean_ply.name,
        "cameras_json": "cameras.json",
        "metric_scale_known": False,
        "metric_note": (
            "SfM scale is arbitrary until at least one trusted real-world measurement "
            "is applied. Do not call this a metric 1:1 reconstruction yet."
        ),
    }

    (out / "reference-reconstruction.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print("XZIEL_REFERENCE_RECON_PASS")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
