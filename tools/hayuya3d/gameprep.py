#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from material_bridge import (
    _scene_meshes,
    prepare_material_transfer,
    transfer_material_from_context,
)
from visual_judge import SourceViewScore


@dataclass
class LODArtifact:
    name: str
    path: str
    target_faces: int
    actual_faces: int
    material_policy: str
    material_channels: list[str] | None = None
    dropped_channels: list[str] | None = None
    rebake_required: list[str] | None = None
    rebaked_channels: list[str] | None = None
    rebake_method: str | None = None
    rebake_error: str | None = None


@dataclass
class GamePrepResult:
    master: str
    lods: list[LODArtifact]
    collision: str | None
    turntable_frames: list[str]
    manifest: str
    source_faces: int
    target_lod0_faces: int
    rig_audit: dict
    rig_audit_path: str
    lod_policy: str


def _deps():
    import trimesh
    return trimesh


def load_combined_mesh(path: Path):
    trimesh = _deps()
    meshes = _scene_meshes(path)
    return trimesh.util.concatenate(meshes)


def export_glb(mesh, path: Path) -> Path:
    trimesh = _deps()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(trimesh.exchange.gltf.export_glb(trimesh.Scene(mesh)))
    if path.read_bytes()[:4] != b"glTF":
        raise RuntimeError(f"invalid GLB export: {path}")
    return path


def simplify_to_faces(mesh, target_faces: int):
    target_faces = max(4, int(target_faces))
    if len(mesh.faces) <= target_faces:
        return mesh.copy()
    simplified = mesh.simplify_quadric_decimation(
        face_count=target_faces,
        aggression=7,
    )
    if simplified is None or not len(simplified.faces):
        raise RuntimeError("quadric simplification returned empty mesh")
    return simplified


def build_turntable(
    master_glb: Path,
    out_dir: Path,
    *,
    anchor_view: SourceViewScore | None,
) -> list[str]:
    from appearance_judge import _mesh_rgb_arrays, render_candidate_rgb_arrays

    vertices, faces, colors, uvs, face_texture_ids, textures = _mesh_rgb_arrays(
        master_glb,
        max_faces=16000,
    )
    if anchor_view is None:
        anchor_view = SourceViewScore(
            source="gameprep",
            best_score=0.0,
            best_azimuth=0.0,
            best_elevation=0.0,
            best_up_axis="y",
            silhouette_iou=0.0,
            boundary_f1=0.0,
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[str] = []
    for index, offset in enumerate(range(0, 360, 15)):
        view = SourceViewScore(
            source="gameprep",
            best_score=0.0,
            best_azimuth=(anchor_view.best_azimuth + offset) % 360.0,
            best_elevation=anchor_view.best_elevation,
            best_up_axis=anchor_view.best_up_axis,
            silhouette_iou=0.0,
            boundary_f1=0.0,
            projection=anchor_view.projection,
            camera_distance=anchor_view.camera_distance,
        )
        image = render_candidate_rgb_arrays(
            vertices,
            faces,
            colors,
            view,
            uvs=uvs,
            face_texture_ids=face_texture_ids,
            textures=textures,
            size=384,
        )
        frame = out_dir / f"{index:02d}_{offset:03d}.png"
        image.save(frame)
        frames.append(str(frame))
    return frames


def _audit_master(master_glb: Path, out_dir: Path):
    from gltf_audit import audit_glb

    audit = audit_glb(master_glb)
    audit_path = out_dir / "rig_audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(asdict(audit), indent=2) + "\n",
        encoding="utf-8",
    )
    return audit, audit_path


def build_gameprep(
    master_glb: Path,
    out_dir: Path,
    *,
    target_faces: int,
    anchor_view: SourceViewScore | None = None,
    material_samples: int = 180_000,
    max_texture_size: int = 2048,
) -> GamePrepResult:
    trimesh = _deps()
    out_dir.mkdir(parents=True, exist_ok=True)

    master_out = out_dir / "master.glb"
    shutil.copy2(master_glb, master_out)

    master_mesh = load_combined_mesh(master_glb)
    source_faces = int(len(master_mesh.faces))
    lod0_target = min(source_faces, max(4, int(target_faces)))

    rig_audit, rig_audit_path = _audit_master(master_glb, out_dir)
    has_skin = rig_audit.skin_count > 0
    if has_skin:
        # Trimesh simplification does not preserve glTF JOINTS/WEIGHTS/skin
        # structures. Never silently turn a rigged character into an unrigged LOD.
        ratios = [1.0]
        lod_policy = (
            "rigged source preserved: LOD0 is exact master; LOD1-LOD3 deferred "
            "until skin-weight-preserving simplification is implemented"
        )
        transfer_context = None
    else:
        ratios = [1.0, 0.55, 0.28, 0.12]
        lod_policy = (
            "unrigged source: every runtime LOD, including LOD0, is derived through "
            "the tier texture ceiling with shared Material Bridge v2 PBR/base-color "
            "transfer; Hero Master remains exact and untouched"
        )
        # One source/material transfer context is shared across all simplified LODs.
        transfer_context = prepare_material_transfer(
            master_glb,
            total_samples=material_samples,
            max_texture_size=max_texture_size,
        )

    lods: list[LODArtifact] = []
    for index, ratio in enumerate(ratios):
        name = f"LOD{index}"
        target = max(4, min(source_faces, int(round(lod0_target * ratio))))
        final_path = out_dir / f"{name}.glb"

        transfer_result = None
        rebake_result = None
        effective_channels = None
        remaining_rebakes: list[str] = []
        if has_skin:
            shutil.copy2(master_glb, final_path)
            actual = source_faces
            material_policy = "exact rig/skin/material preservation"
        else:
            simplified = simplify_to_faces(master_mesh, target)
            raw_path = out_dir / "_raw" / f"{name}_geometry.glb"
            export_glb(simplified, raw_path)
            transfer_result = transfer_material_from_context(
                master_glb,
                transfer_context,
                raw_path,
                final_path,
            )
            effective_channels = list(transfer_result.channels or [])
            remaining_rebakes = list(transfer_result.rebake_required or [])
            material_policy = (
                "Material Bridge v2 PBR UV projection"
                if transfer_result.method.startswith("surface-sample nearest-UV")
                else "Material Bridge v1 base-color vertex projection fallback"
            )

            if remaining_rebakes:
                try:
                    from material_rebake import rebake_material_channels
                    rebake_path = out_dir / "_rebake" / f"{name}_material.glb"
                    rebake_result = rebake_material_channels(
                        master_glb,
                        final_path,
                        rebake_path,
                        required=remaining_rebakes,
                        max_texture_size=max_texture_size,
                    )
                    if rebake_result.resolved_channels:
                        shutil.copy2(rebake_result.output_glb, final_path)
                        effective_channels = sorted(
                            set(effective_channels or [])
                            | set(rebake_result.resolved_channels or [])
                        )
                        material_policy += (
                            " + verified Blender topology material rebake "
                            f"({','.join(rebake_result.resolved_channels)})"
                        )
                    remaining_rebakes = list(rebake_result.remaining_channels or [])
                except Exception as exc:
                    # Rebake is a quality upgrade, never a reason to hide a valid
                    # inspectable LOD. Leave all requested channels unresolved so
                    # final QA keeps production_ready false.
                    remaining_rebakes = list(transfer_result.rebake_required or [])
                    rebake_result = None

            reloaded = load_combined_mesh(final_path)
            actual = int(len(reloaded.faces))

        lods.append(
            LODArtifact(
                name=name,
                path=str(final_path),
                target_faces=target,
                actual_faces=actual,
                material_policy=material_policy,
                material_channels=effective_channels,
                dropped_channels=(
                    list(transfer_result.dropped_channels or [])
                    if transfer_result is not None
                    else []
                ),
                rebake_required=remaining_rebakes,
                rebaked_channels=(
                    list(rebake_result.resolved_channels or [])
                    if rebake_result is not None
                    else []
                ),
                rebake_method=(
                    rebake_result.method
                    if rebake_result is not None
                    else None
                ),
                rebake_error=(
                    rebake_result.error
                    if rebake_result is not None
                    else None
                ),
            )
        )

    collision_path = None
    try:
        hull = master_mesh.convex_hull
        collision_file = out_dir / "collision_convex.glb"
        export_glb(hull, collision_file)
        collision_path = str(collision_file)
    except Exception:
        collision_path = None

    turntable_frames = build_turntable(
        master_glb,
        out_dir / "turntable",
        anchor_view=anchor_view,
    )

    manifest_path = out_dir / "gameprep_manifest.json"
    result = GamePrepResult(
        master=str(master_out),
        lods=lods,
        collision=collision_path,
        turntable_frames=turntable_frames,
        manifest=str(manifest_path),
        source_faces=source_faces,
        target_lod0_faces=lod0_target,
        rig_audit=asdict(rig_audit),
        rig_audit_path=str(rig_audit_path),
        lod_policy=lod_policy,
    )
    manifest_path.write_text(
        json.dumps(asdict(result), indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="HAYUYA GamePrep v2 with PBR-aware LOD transfer.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-faces", type=int, required=True)
    parser.add_argument("--max-texture-size", type=int, default=2048)
    args = parser.parse_args()

    result = build_gameprep(
        args.input,
        args.output,
        target_faces=args.target_faces,
        max_texture_size=args.max_texture_size,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
