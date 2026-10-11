#!/usr/bin/env python3
"""Experimental Aether/WaW MP40 -> Quake MDL v6 for NZ:P Vril Android.

Runs inside Blender (bpy). Bakes ORIGINAL authored weapon AND T4 hands actions
to 46 Vril-compatible vertex poses. No automatic left/right mirroring and no
fabricated reload motion. Experimental visuals MUST be reviewed on a phone.

Usage:
 blender -b -noaudio --python tools/vril_mp40/bake_mp40_mdl.py -- \
   <gun.glb> <hands.glb> <output-dir>
"""
import json
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector

FRAME_COUNT = 46
SKIN_W, SKIN_H = 256, 128
MAX_VERTS = 1950
MAX_TRIS = 3900
ORIGINAL_MIN = (10.0, -16.58, -30.0)
ORIGINAL_MAX = (78.09, 7.76, -5.15)


def fail(message):
    raise RuntimeError("VRIL_MP40_BAKE_RED: " + message)


def imported(path):
    old = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    objects = list(set(bpy.data.objects) - old)
    armatures = [o for o in objects if o.type == "ARMATURE"]
    meshes = [o for o in objects if o.type == "MESH"]
    if not armatures or not meshes:
        fail(f"{path.name}: no armature or no render mesh")
    return objects, armatures, meshes


def armature_with(armatures, bone):
    candidates = [a for a in armatures if bone in a.pose.bones]
    if not candidates:
        fail(f"source skeleton does not contain {bone}")
    return max(candidates, key=lambda a: len(a.pose.bones))


def locate_action(armature, role):
    actions = list(bpy.data.actions)
    names = {
        "hand_idle": ("HandIdleMP40",),
        "gun_idle": ("HandIdleMP40",),
        "hand_reload": ("viewmodel_mp40_reload_empty",),
        "gun_reload": ("viewmodel_mp40_reload",),
        "gun_empty": ("viewmodel_mp40_reload_empty",),
        "gun_fire": ("viewmodel_mp40_fire",),
        "hand_fire": ("viewmodel_mp40_fire",),
        "hand_equip": ("MP40Equip",),
        "gun_equip": ("MP40Equip",),
        "hand_unequip": ("MP40Unequip",),
        "gun_unequip": ("MP40Unequip",),
    }
    candidates = [a for a in actions if any(
        a.name == "PSA_" + n or a.name == n for n in names[role]
    )]
    if not candidates:
        # This is better than inventing a reload; peripheral animations
        # may fall back to idle and are explicitly recorded in the report.
        if "reload" in role:
            fail(f"authored source {role} animation missing")
        return None
    # Each imported GLB may contain duplicate action names. Select those
    # referenced by NLA on the CORRECT armature, not the other model.
    nla = armature.animation_data
    owned = set()
    if nla:
        for track in nla.nla_tracks:
            for strip in track.strips:
                if strip.action:
                    owned.add(strip.action.name)
    for action in candidates:
        if action.name in owned:
            return action
    fail(f"{role}: no action attached to expected skeleton {armature.name}")


def use_action(arm, action, fraction):
    data = arm.animation_data_create()
    for track in data.nla_tracks:
        track.mute = True
    data.action = action
    if action:
        start, end = action.frame_range
        frame = start + (end - start) * fraction
    else:
        frame = 1
    base = math.floor(frame)
    bpy.context.scene.frame_set(base, subframe=frame - base)
    bpy.context.view_layer.update()


def decimate(meshes, desired_total):
    sizes = [(o, len(o.data.vertices)) for o in meshes]
    total = sum(s for _, s in sizes)
    if total == 0:
        fail("no mesh vertices")
    if total <= desired_total:
        return
    for obj, size in sizes:
        goal = max(70, round(size * desired_total / total))
        if size <= goal:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new("VRIL_TEST_LOD", "DECIMATE")
        mod.ratio = max(0.02, min(0.999, goal / size))
        # Decimate the REST mesh BEFORE armature deformation. Deforming
        # after topology reduction keeps constant vertex IDs per frame.
        while obj.modifiers.find(mod.name) > 0:
            bpy.ops.object.modifier_move_up(modifier=mod.name)
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception as exc:
            fail(f"cannot decimate skinned mesh {obj.name}: {exc}")


def topology(meshes):
    """Expand UV seams, and remember original evaluated vertex indices."""
    vertex_refs = []
    st = []
    tris = []
    for group, objs in enumerate(meshes):
        for obj in objs:
            mesh = obj.data
            mesh.calc_loop_triangles()
            uv_layer = mesh.uv_layers.active
            if uv_layer is None:
                fail(f"{obj.name}: no texture UV0")
            cache = {}
            for triangle in mesh.loop_triangles:
                face = []
                for vid, loop in zip(triangle.vertices, triangle.loops):
                    uv = uv_layer.data[loop].uv
                    # Atlas has gun on left half; hands on right half.
                    u = float(uv.x) * 0.5 + (0.5 if group == 1 else 0.0)
                    v = float(uv.y)
                    su = max(0, min(SKIN_W - 1, round(u * (SKIN_W - 1))))
                    sv = max(0, min(SKIN_H - 1, round((1.0 - v) * (SKIN_H - 1))))
                    key = (int(vid), su, sv)
                    if key not in cache:
                        cache[key] = len(vertex_refs)
                        vertex_refs.append((obj, int(vid)))
                        st.append((0, su, sv))
                    face.append(cache[key])
                tris.append(tuple(face))
    if len(vertex_refs) > MAX_VERTS or len(tris) > MAX_TRIS:
        fail(f"MDL vertex/triangle budget exceeded: {len(vertex_refs)}/{MAX_VERTS} "
             f"verts and {len(tris)}/{MAX_TRIS} triangles")
    return vertex_refs, st, tris


def get_positions(meshes, arm, action, fraction):
    use_action(arm, action, fraction)
    deps = bpy.context.evaluated_depsgraph_get()
    result = {}
    for obj in meshes:
        evaluated = obj.evaluated_get(deps)
        baked = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=deps)
        try:
            if len(baked.vertices) != len(obj.data.vertices):
                fail(f"animated topology changed in {obj.name}")
            result[obj] = [obj.matrix_world @ v.co for v in baked.vertices]
        finally:
            evaluated.to_mesh_clear()
    return result


def bone_world(arm, name):
    return arm.matrix_world @ arm.pose.bones[name].matrix


def pose_recipe(frame):
    if frame in (1, 2):
        return "fire", (frame - 1) / 1
    if 4 <= frame <= 31:
        return "reload", (frame - 4) / 27
    if 32 <= frame <= 34:
        return "unequip", (frame - 32) / 2
    if 35 <= frame <= 37:
        return "equip", (frame - 35) / 2
    # No source sprint clip has been verified for this MP40.
    return "idle", 0.0


def bake_frames(gun, hand, gun_arm, hand_arm, refs):
    actions = {}
    for role in ("idle", "fire", "reload", "equip", "unequip"):
        actions[(0, role)] = locate_action(gun_arm, "gun_" + role)
        actions[(1, role)] = locate_action(hand_arm, "hand_" + role)
    if actions[(1, "reload")] is None or actions[(0, "reload")] is None:
        fail("reload animation missing")
    poses = []
    clip_movements = []
    role_log = []
    for frame in range(FRAME_COUNT):
        role, fraction = pose_recipe(frame)
        # Capture hands first. Gun and hands may have DIFFERENT source
        # action lengths and must be sampled at the same normalized phase.
        hands_data = get_positions(hand, hand_arm, actions[(1, role)], fraction)
        socket = bone_world(hand_arm, "tag_weapon").copy()
        gun_data = get_positions(gun, gun_arm, actions[(0, role)], fraction)
        root = bone_world(gun_arm, "j_gun").copy()
        mount = socket @ root.inverted()
        # Use the actual animated socket; do not guess a fixed rotation.
        positions = []
        for obj, index in refs:
            p = gun_data[obj][index] if obj in gun_data else hands_data[obj][index]
            if obj in gun_data:
                p = mount @ p
            # Blender/glTF coordinate system -> Quake model coordinates.
            positions.append((p.x, p.z, p.y))
        if role == "reload":
            clip = mount @ bone_world(gun_arm, "j_clip").translation
            clip_movements.append([clip.x, clip.z, clip.y])
        poses.append(positions)
        role_log.append({"frame": frame, "source": role, "fraction": fraction})
    # Fit the ORIGINAL NZ:P MP40 camera-space bounding box at frame0.
    # Uniform scaling preserves original geometry proportions.
    idle = poses[0]
    mins = [min(v[i] for v in idle) for i in range(3)]
    maxs = [max(v[i] for v in idle) for i in range(3)]
    spans = [maxs[i] - mins[i] for i in range(3)]
    if min(spans) < 0.0001:
        fail("collapsed or invisible viewmodel")
    ratios = [(ORIGINAL_MAX[i] - ORIGINAL_MIN[i]) / spans[i] for i in range(3)]
    scale = min(ratios)
    offsets = [((ORIGINAL_MAX[i] + ORIGINAL_MIN[i]) / 2.0)
               - (maxs[i] + mins[i]) * scale / 2.0 for i in range(3)]
    poses = [[tuple(v[i] * scale + offsets[i] for i in range(3))
              for v in f] for f in poses]
    return poses, role_log, {
        "source_idle_bbox": [mins, maxs],
        "target_reference_bbox": [ORIGINAL_MIN, ORIGINAL_MAX],
        "uniform_scale": scale,
        "offset": offsets,
        "magazine_source_positions": clip_movements,
        "source_gun_actions": {r: actions[(0, r)].name if actions[(0, r)] else None
                               for r in ("idle", "fire", "reload", "equip", "unequip")},
        "source_hand_actions": {r: actions[(1, r)].name if actions[(1, r)] else None
                                for r in ("idle", "fire", "reload", "equip", "unequip")},
    }


def write_mdl(path, poses, st, tris):
    all_points = [p for frame in poses for p in frame]
    mins = [min(v[i] for v in all_points) for i in range(3)]
    maxs = [max(v[i] for v in all_points) for i in range(3)]
    scales = [max((maxs[i] - mins[i]) / 255, 0.00001) for i in range(3)]
    radius = max(math.sqrt(sum(v[i] ** 2 for i in range(3))) for v in poses[0])
    header = struct.pack("<ii3f3ff3f8if", 0x4F504449, 6,
        *scales, *mins, radius, 0., 0., 0.,
        2, SKIN_W, SKIN_H, len(st), len(tris), len(poses), 0, 0, radius)
    with path.open("wb") as f:
        f.write(header)
        # Fallback skins are monochrome; proper external TGA atlas overrides.
        for _ in range(2):
            f.write(struct.pack("<i", 0))
            f.write(bytes([128]) * (SKIN_W * SKIN_H))
        for onseam, u, v in st:
            f.write(struct.pack("<iii", onseam, u, v))
        for t in tris:
            f.write(struct.pack("<iiii", 1, *t))
        for i, positions in enumerate(poses):
            encoded = []
            for p in positions:
                encoded.append(tuple(max(0, min(255, round((p[j] - mins[j]) / scales[j])))
                                     for j in range(3)))
            lower = [min(v[j] for v in encoded) for j in range(3)]
            upper = [max(v[j] for v in encoded) for j in range(3)]
            f.write(struct.pack("<i", 0))
            f.write(bytes(lower) + b"\0" + bytes(upper) + b"\0")
            name = ("frame%d" % (i + 1)).encode("ascii")[:15]
            f.write(name + bytes(16 - len(name)))
            for v in encoded:
                f.write(bytes(v) + b"\0")
    return {"file_size": path.stat().st_size, "frames": len(poses),
            "vertices": len(st), "triangles": len(tris),
            "quantization_units": scales}


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) != 3:
        fail("need gun.glb hands.glb outdir")
    gun_path, hands_path, outdir = map(Path, args)
    for path in (gun_path, hands_path):
        if not path.is_file() or path.stat().st_size < 30000:
            fail(f"source asset unavailable: {path}")
    outdir.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    _, guns, gun_meshes = imported(gun_path)
    _, hands, hand_meshes = imported(hands_path)
    gun_arm, hand_arm = armature_with(guns, "j_gun"), armature_with(hands, "tag_weapon")
    if "j_clip" not in gun_arm.pose.bones:
        fail("source MP40 skeleton missing animated magazine j_clip")
    meshes = gun_meshes + hand_meshes
    # An MDL has classic Quake-era limits; make a temporary test LOD.
    # NEVER change the original source GLBs.
    decimate(meshes, desired_total=1220)
    refs, st, tris = topology([gun_meshes, hand_meshes])
    poses, timeline, extra = bake_frames(gun_meshes, hand_meshes, gun_arm, hand_arm, refs)
    result = write_mdl(outdir / "v_mp40.mdl", poses, st, tris)
    result.update({
        "status": "EXPERIMENTAL_VISUAL_REVIEW_REQUIRED",
        "original_source_gun": str(gun_path),
        "original_source_hands": str(hands_path),
        "source_actions": extra,
        "timeline": timeline,
        "limitations": [
            "Model is decimated to old Quake MDL limits, not modern PBR.",
            "Hands tactical reload sourced from full empty-reload PSA; requires visual review.",
            "No proven sprint animation; idle placeholder for frames 39-46.",
            "No automatic mirroring; source tag_weapon drives attached gun.",
            "External atlas textures required; MDL fallback skin is flat."
        ],
    })
    (outdir / "bake-report.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print("VRIL_MP40_46_FRAMES_BAKED_VISUAL_RED", result["vertices"], result["triangles"])


if __name__ == "__main__":
    main()
