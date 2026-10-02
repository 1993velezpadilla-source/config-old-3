#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description="Render a factual HAYUYA preview pack from a generated 3D model.")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--size", type=int, default=1024)
    return p.parse_args(argv)


def load_asset(path: Path):
    ext = path.suffix.lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path.resolve()), automatic_bone_orientation=False)
    elif ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    elif ext == ".obj":
        try:
            bpy.ops.wm.obj_import(filepath=str(path.resolve()))
        except Exception:
            bpy.ops.import_scene.obj(filepath=str(path.resolve()))
    else:
        raise RuntimeError(f"unsupported:{ext}")


def world_bounds(meshes):
    pts = []
    for obj in meshes:
        for c in obj.bound_box:
            pts.append(obj.matrix_world @ Vector(c))
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def clear_cameras_and_lights():
    for obj in list(bpy.context.scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)


def add_light(location, target, energy, size):
    bpy.ops.object.light_add(type="AREA", location=location)
    light = bpy.context.object
    light.data.energy = energy
    light.data.size = size
    look_at(light, target)


def render_view(scene, cam, output, target, offset, ortho_scale):
    cam.location = target + offset
    look_at(cam, target)
    cam.data.ortho_scale = ortho_scale
    scene.render.filepath = str(output.resolve())
    bpy.ops.render.render(write_still=True)


def main():
    a = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    load_asset(a.input)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]
    if not meshes:
        raise RuntimeError("no_meshes")

    mn, mx = world_bounds(meshes)
    center = (mn + mx) * 0.5
    ext = mx - mn
    height = max(float(ext.z), 1e-6)
    radius = max(float(ext.x), float(ext.y), float(ext.z)) * 0.72
    radius = max(radius, 0.5)

    clear_cameras_and_lights()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = a.size
    scene.render.resolution_y = a.size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    if scene.world is None:
        scene.world = bpy.data.worlds.new("HAYUYA_Preview_World")
    scene.world.color = (0.025, 0.025, 0.03)

    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        try:
            scene.view_settings.look = "Medium High Contrast"
        except Exception:
            pass

    bpy.ops.object.camera_add()
    cam = bpy.context.object
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.lens = 50
    cam.data.clip_start = 0.01
    cam.data.clip_end = max(100.0, radius * 20.0)

    add_light(center + Vector((-2.0 * radius, 2.2 * radius, 2.2 * radius)), center, 520, 4.0 * radius)
    add_light(center + Vector((2.2 * radius, 1.2 * radius, 0.7 * radius)), center, 260, 3.0 * radius)
    add_light(center + Vector((0.0, -1.8 * radius, 2.8 * radius)), center, 360, 3.0 * radius)

    a.output_dir.mkdir(parents=True, exist_ok=True)

    # Blender's orthographic scale behaves like a half-span for this imported
    # glTF scene. The previous 1.30 factor left the subject at ~39% of frame.
    # Keep factual geometry, but frame it like a production turntable.
    full_scale = max(float(ext.x), float(ext.y), float(ext.z)) * 0.66
    full_scale = max(full_scale, 0.28)

    views = {
        # AniGen's glTF export faces +Y after Blender imports Y-up glTF into
        # Blender's Z-up scene. The old preview labeled the back as "front".
        "front": {
            "target": center,
            "offset": Vector((0.0, 3.2 * radius, 0.0)),
            "scale": full_scale,
        },
        "three_quarter": {
            "target": center,
            "offset": Vector((2.30 * radius, 2.30 * radius, 0.0)),
            "scale": full_scale,
        },
        "side": {
            "target": center,
            "offset": Vector((3.2 * radius, 0.0, 0.0)),
            "scale": full_scale,
        },
        "opposite": {
            "target": center,
            "offset": Vector((0.0, -3.2 * radius, 0.0)),
            "scale": full_scale,
        },
        "three_quarter_opposite": {
            "target": center,
            "offset": Vector((-2.30 * radius, -2.30 * radius, 0.0)),
            "scale": full_scale,
        },
        "side_opposite": {
            "target": center,
            "offset": Vector((-3.2 * radius, 0.0, 0.0)),
            "scale": full_scale,
        },
    }

    head_target = center.copy()
    head_target.z = mn.z + ext.z * 0.78
    head_scale = max(height * 0.22, float(ext.x) * 0.36, float(ext.y) * 0.36, 0.14)
    views["face"] = {
        "target": head_target,
        "offset": Vector((0.0, 3.0 * radius, 0.05 * radius)),
        "scale": head_scale,
    }
    views["face_opposite"] = {
        "target": head_target,
        "offset": Vector((0.0, -3.0 * radius, 0.05 * radius)),
        "scale": head_scale,
    }

    rendered = {}
    for name, spec in views.items():
        output = a.output_dir / f"{name}.png"
        render_view(scene, cam, output, spec["target"], spec["offset"], spec["scale"])
        rendered[name] = str(output)

    manifest = {
        "schema": 1,
        "source": str(a.input),
        "size": a.size,
        "bounds": {
            "min": [round(float(v), 7) for v in mn],
            "max": [round(float(v), 7) for v in mx],
            "extents": [round(float(v), 7) for v in ext],
        },
        "renders": rendered,
        "renderer": "blender_eevee_generated_model_preview_v2_eye_framed",
    }
    (a.output_dir / "preview_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("HAYUYA_MODEL_PREVIEW_PACK", json.dumps(manifest))


if __name__ == "__main__":
    main()
