import bpy
import bmesh
import json
import math
import os
import re
import struct
import hashlib
from pathlib import Path
from mathutils import Vector

MASTER = os.environ.get("CHURCH_GAMEPLAY_BLEND", "church/out/church_zombies_gameplay_v1.blend")
PLAN_PATH = Path(os.environ.get("CHURCH_PLAN", "church/out/zombies_map_plan.json"))
OUTDIR = Path(os.environ.get("CHURCH_OUT", "church/out"))
RUNTIME_ROOT = OUTDIR / "vril_static"
MODEL_DIR = RUNTIME_ROOT / "models" / "xziel" / "sanctum"
TEXTURE_DIR = RUNTIME_ROOT / "textures" / "xziel" / "sanctum"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
TEXTURE_DIR.mkdir(parents=True, exist_ok=True)

TARGET_TRIS = int(os.environ.get("XZIEL_STATIC_TARGET_TRIS", "600000"))
TEXTURE_MAX = int(os.environ.get("XZIEL_STATIC_TEXTURE_MAX", "2048"))
MAX_TRIS_PER_BATCH = 18000
QUAKE_SCALE = 39.3700787402
XZSM_VERSION = 2

# XZSM v2 keeps the photogrammetry albedo intact but adds a compact baked
# per-vertex light/tint term. Vril multiplies this with the texture, giving
# Sanctum depth/mood without converting the church to BSP visuals or requiring
# heavyweight realtime PBR on the current Android harness.
MOON_DIR = Vector((-0.32, 0.18, 0.93)).normalized()

# Cleanup is deliberately conservative. The scan is the visual authority, so
# disconnected photogrammetry is not assumed to be junk merely because it is
# small in face count. Only centimeter-scale micro-shards may be removed, and
# even those are subject to a hard global face budget.
TINY_ISLAND_MAX_FACES = int(os.environ.get("XZIEL_SCAN_TINY_MAX_FACES", "4"))
TINY_ISLAND_MAX_DIAGONAL_M = float(os.environ.get("XZIEL_SCAN_TINY_MAX_DIAGONAL_M", "0.03"))
MAX_CLEANUP_FRACTION = float(os.environ.get("XZIEL_SCAN_MAX_CLEANUP_FRACTION", "0.0025"))

bpy.ops.wm.open_mainfile(filepath=MASTER)
scene = bpy.context.scene
plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

lod_col = bpy.data.collections.get("GAME_CHURCH_LOD0")
if not lod_col:
    raise RuntimeError("GAME_CHURCH_LOD0 missing")
church_source_objects = [o for o in lod_col.objects if o.type == "MESH"]
if not church_source_objects:
    raise RuntimeError("GAME_CHURCH_LOD0 contains no meshes")
dressing_col = bpy.data.collections.get("SANCTUM_DRESSING_V1")
dressing_source_objects = [o for o in dressing_col.objects if o.type == "MESH"] if dressing_col else []
source_objects = church_source_objects

# Match the exact origin transform used by export_nzp_harness.py.
zones = [v for k,v in plan["zones"].items() if k != "other"]
global_min = Vector((
    min(v["min"][0] for v in zones),
    min(v["min"][1] for v in zones),
    min(v["min"][2] for v in zones),
))
global_max = Vector((
    max(v["max"][0] for v in zones),
    max(v["max"][1] for v in zones),
    max(v["max"][2] for v in zones),
))
center = (global_min + global_max) * 0.5

def mesh_triangles(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)

source_tris = sum(mesh_triangles(o) for o in source_objects)

runtime_col = bpy.data.collections.get("VRIL_STATIC_RUNTIME")
if runtime_col:
    for o in list(runtime_col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(runtime_col)
runtime_col = bpy.data.collections.new("VRIL_STATIC_RUNTIME")
scene.collection.children.link(runtime_col)

cleanup_face_budget = max(32, int(source_tris * MAX_CLEANUP_FRACTION))
cleanup_stats = {
    "removedIslands": 0,
    "removedFaces": 0,
    "candidateIslands": 0,
    "faceBudget": cleanup_face_budget,
    "maxFacesPerIsland": TINY_ISLAND_MAX_FACES,
    "maxDiagonalMeters": TINY_ISLAND_MAX_DIAGONAL_M,
}

def component_world_diagonal(obj, comp):
    mn = Vector((1e30, 1e30, 1e30))
    mx = Vector((-1e30, -1e30, -1e30))
    seen = set()
    for face in comp:
        for vert in face.verts:
            if vert.index in seen:
                continue
            seen.add(vert.index)
            p = obj.matrix_world @ vert.co
            mn.x = min(mn.x, p.x); mn.y = min(mn.y, p.y); mn.z = min(mn.z, p.z)
            mx.x = max(mx.x, p.x); mx.y = max(mx.y, p.y); mx.z = max(mx.z, p.z)
    return (mx - mn).length if seen else 0.0

def remove_tiny_scan_islands(obj):
    # The photogrammetry scan is authoritative visual geometry. Never classify
    # a component as debris solely from a percentage-of-object threshold: that
    # deleted real architecture on fragmented scans. A removable shard must be
    # BOTH <= a few faces AND centimeter-scale in world space, with a hard
    # global cap on total deleted faces.
    remaining_budget = cleanup_face_budget - cleanup_stats["removedFaces"]
    if remaining_budget <= 0:
        return

    mesh = obj.data
    if len(mesh.polygons) < 300:
        return

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    unseen = set(bm.faces)
    components = []
    while unseen:
        seed = unseen.pop()
        comp = [seed]
        stack = [seed]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for other in edge.link_faces:
                    if other in unseen:
                        unseen.remove(other)
                        stack.append(other)
                        comp.append(other)
        components.append(comp)

    if len(components) <= 1:
        bm.free()
        return

    # Examine the smallest connected components first. Large but disconnected
    # architectural pieces (stairs, trim, roof/tower fragments) are untouched.
    components.sort(key=len)
    to_delete = []
    removed_islands = 0
    for comp in components:
        if len(comp) > TINY_ISLAND_MAX_FACES:
            break
        if len(to_delete) + len(comp) > remaining_budget:
            break
        if component_world_diagonal(obj, comp) > TINY_ISLAND_MAX_DIAGONAL_M:
            continue
        cleanup_stats["candidateIslands"] += 1
        to_delete.extend(comp)
        removed_islands += 1

    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context="FACES")
        bm.to_mesh(mesh)
        mesh.update()
        cleanup_stats["removedIslands"] += removed_islands
        cleanup_stats["removedFaces"] += len(to_delete)
    bm.free()

# Work only on derived copies; the GAME_CHURCH_LOD0 source and Blender master
# are never modified by runtime cleanup/decimation.
runtime_objects = []
for src in source_objects:
    dup = src.copy()
    dup.data = src.data.copy()
    dup.name = "XZSM_" + src.name
    runtime_col.objects.link(dup)
    remove_tiny_scan_islands(dup)
    runtime_objects.append(dup)

cleaned_tris = sum(mesh_triangles(o) for o in runtime_objects)
if source_tris >= TARGET_TRIS and cleaned_tris < TARGET_TRIS:
    raise RuntimeError(
        f"Sanctum cleanup removed authoritative geometry below target: "
        f"source={source_tris} cleaned={cleaned_tris} target={TARGET_TRIS} "
        f"cleanup={cleanup_stats}"
    )

# Decimation is calculated AFTER cleanup. The old order used the pre-cleanup
# ratio and then applied it to an already-reduced mesh, compounding the loss.
ratio = min(1.0, TARGET_TRIS / max(cleaned_tris, 1))
if ratio < 0.995:
    for dup in runtime_objects:
        if mesh_triangles(dup) <= 500:
            continue
        mod = dup.modifiers.new("XZSM_MOBILE_DECIMATE", "DECIMATE")
        mod.ratio = max(0.025, ratio)
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = dup
        dup.select_set(True)
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception as exc:
            print("WARN decimate", dup.name, exc)
        dup.select_set(False)

runtime_tris = sum(mesh_triangles(o) for o in runtime_objects)
runtime_floor = min(source_tris, int(TARGET_TRIS * 0.95))
if runtime_tris < runtime_floor:
    raise RuntimeError(
        f"Sanctum runtime geometry regressed: runtime={runtime_tris} "
        f"floor={runtime_floor} source={source_tris} target={TARGET_TRIS}"
    )

# Dressing is additive visual geometry. It is never counted against the 640k
# church quality floor and is not decimated with the photogrammetry mesh.
dressing_runtime_objects = []
for src in dressing_source_objects:
    dup = src.copy()
    dup.data = src.data.copy()
    dup.name = "XZSM_DRESS_" + src.name
    runtime_col.objects.link(dup)
    dressing_runtime_objects.append(dup)
dressing_tris = sum(mesh_triangles(o) for o in dressing_runtime_objects)
all_runtime_objects = runtime_objects + dressing_runtime_objects

def safe_name(s):
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s or "material")
    return s[:40] or "material"

def visual_zone(obj):
    # Dressing objects span multiple zones but use shared materials. Derive a
    # reasonable lighting zone from the nearest authored zone center.
    if obj.name.startswith("XZSM_DRESS_"):
        p = obj.matrix_world.translation
        candidates = [(name, Vector(info["center"])) for name, info in plan["zones"].items() if name != "other"]
        if candidates:
            return min(candidates, key=lambda it:(p-it[1]).length_squared)[0]
    mats = " ".join(m.name.lower() for m in obj.data.materials if m)
    name = obj.name.lower()
    s = name + " " + mats
    if "boiler" in s: return "boiler"
    if "clockchamber" in s or "clock_chamber" in s: return "clock_chamber"
    if "officecorridor" in s or "office_corridor" in s: return "office_corridor"
    if "office" in s: return "office"
    if "ringingchamber" in s or "ringing_chamber" in s: return "ringing_chamber"
    if "roofchamber" in s or "roof_chamber" in s: return "roof_chamber"
    if "towerstairs" in s or "tower_stairs" in s: return "tower_stairs"
    if "towertop" in s or "tower_top" in s or "turret" in s: return "tower_top"
    if "exterior" in s: return "exterior"
    return "main_church"

ZONE_TINT = {
    "exterior": (0.82, 0.88, 1.00),
    "main_church": (1.00, 0.95, 0.88),
    "office": (0.92, 0.83, 0.72),
    "office_corridor": (0.88, 0.82, 0.76),
    "boiler": (1.00, 0.72, 0.56),
    "tower_stairs": (0.78, 0.82, 0.92),
    "ringing_chamber": (0.92, 0.82, 0.70),
    "clock_chamber": (0.78, 0.84, 0.96),
    "roof_chamber": (0.70, 0.80, 1.00),
    "tower_top": (0.66, 0.78, 1.00),
}

# Warm practical-light centers are derived from real scan zones. The term is
# deliberately subtle because the photogrammetry textures already contain
# real-world shading; this pass adds readable nighttime shape, not fake neon.
warm_lights = []
for zone_name, radius, strength in [
    ("main_church", 13.0, 0.28),
    ("office", 6.0, 0.21),
    ("boiler", 7.0, 0.26),
    ("ringing_chamber", 6.0, 0.23),
]:
    info = plan["zones"].get(zone_name)
    if info:
        warm_lights.append((Vector(info["center"]), radius, strength))

def baked_vertex_rgba(obj, world_pos, world_normal):
    zone = visual_zone(obj)
    tint = ZONE_TINT.get(zone, (0.86, 0.86, 0.88))
    ndl = max(0.0, float(world_normal.dot(MOON_DIR)))
    upward = max(0.0, float(world_normal.z))

    # Mobile SDR readability pass. The scan albedo already contains baked
    # real-world shadowing, so multiplying it by the old 0.34 floor crushed
    # large interior regions to near-black in the Android harness. Keep the
    # night mood and directional shaping, but preserve midtone information.
    # Safe mobile night grade: keep enough headroom for dramatic cool/warm
    # shaping without ever crushing the authored albedo back into black.
    level = 0.80 + 0.12 * ndl + 0.06 * upward
    for light_pos, radius, strength in warm_lights:
        d = (world_pos - light_pos).length
        if d < radius:
            level += min(0.14,strength) * (1.0 - d / radius)
    level = max(0.72, min(1.0, level))

    rgb = [max(0, min(255, int(round(255.0 * level * tint[i])))) for i in range(3)]
    return (rgb[0], rgb[1], rgb[2], 255)

def linked_image_from_socket(sock, visited=None):
    # Follow the Base Color graph instead of assuming Image Texture is wired
    # directly into Principled BSDF. Imported GLB/Sketchfab materials often
    # contain mapping, color-mix or conversion nodes in between.
    if not sock or not getattr(sock, "is_linked", False):
        return None
    if visited is None:
        visited = set()
    for link in sock.links:
        node = link.from_node
        if not node or node.as_pointer() in visited:
            continue
        visited.add(node.as_pointer())
        if getattr(node, "type", "") == "TEX_IMAGE" and node.image:
            return node.image
        for inp in getattr(node, "inputs", []):
            img = linked_image_from_socket(inp, visited)
            if img:
                return img
    return None

def material_image(mat):
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        img = linked_image_from_socket(bsdf.inputs.get("Base Color"))
        if img:
            return img
    # Last resort for imported materials whose shader graph is unconventional:
    # prefer a color/albedo-looking image, then any image at all.
    candidates = [
        node.image for node in mat.node_tree.nodes
        if getattr(node, "type", "") == "TEX_IMAGE" and node.image
    ]
    for img in candidates:
        n = (img.name or "").lower()
        if any(tag in n for tag in ("basecolor", "base_color", "albedo", "diffuse", "color")):
            return img
    return candidates[0] if candidates else None

def material_color(mat):
    if mat and mat.use_nodes and mat.node_tree:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf and bsdf.inputs.get("Base Color"):
            c = bsdf.inputs["Base Color"].default_value
            return tuple(float(x) for x in c[:4])
    if mat:
        return tuple(float(x) for x in mat.diffuse_color)
    return (0.55, 0.55, 0.55, 1.0)

texture_records = {}
texture_paths = {}
texture_digest_paths = {}
church_material_names = {
    m.name
    for o in runtime_objects
    for m in o.data.materials
    if m
}
fallback_materials = set()
missing_uv_objects = set()

def save_material_texture(mat):
    key = mat.name if mat else "__fallback__"
    if key in texture_paths:
        return texture_paths[key]

    idx = len(texture_paths)
    # Vril's legacy image loader builds paths in MAX_QPATH-sized buffers.
    # Long semantic material names silently truncate and fail to open, leaving
    # otherwise valid meshes white. Keep runtime filenames intentionally tiny;
    # human-readable material names remain in the JSON report.
    stem = f"t{idx:03d}"
    rel_no_ext = f"textures/xziel/sanctum/{stem}"
    dst = TEXTURE_DIR / f"{stem}.png"

    img = material_image(mat)
    if img and img.size[0] > 0 and img.size[1] > 0:
        copy = img.copy()
        max_dim = TEXTURE_MAX
        w, h = int(copy.size[0]), int(copy.size[1])
        if max(w,h) > max_dim:
            s = max_dim / float(max(w,h))
            copy.scale(max(1,int(round(w*s))), max(1,int(round(h*s))))
        copy.file_format = "PNG"
        # Preserve source albedo. save_render() applies scene/view transforms
        # and was darkening already-shadowed photogrammetry on Android.
        try:
            copy.filepath_raw = str(dst)
            copy.save()
        except Exception:
            copy.save_render(filepath=str(dst), scene=scene)
        bpy.data.images.remove(copy)
        source_desc = img.name
    else:
        rgba = material_color(mat)
        gen = bpy.data.images.new(stem, width=8, height=8, alpha=True, float_buffer=False)
        gen.pixels = list(rgba) * 64
        gen.file_format = "PNG"
        gen.filepath_raw = str(dst)
        try:
            gen.save()
        except Exception:
            gen.save_render(filepath=str(dst), scene=scene)
        bpy.data.images.remove(gen)
        source_desc = "generated_base_color"
        fallback_materials.add(key)

    if not dst.exists():
        raise RuntimeError(f"texture write failed for {key}: {dst}")

    digest = hashlib.sha256(dst.read_bytes()).hexdigest()
    canonical = texture_digest_paths.get(digest)
    duplicate_of = None
    if canonical is not None:
        duplicate_of = canonical
        dst.unlink()
        rel_no_ext = canonical
    else:
        texture_digest_paths[digest] = rel_no_ext

    texture_paths[key] = rel_no_ext
    texture_records[key] = {
        "path": rel_no_ext + ".png",
        "source": source_desc,
        "bytes": (TEXTURE_DIR / (Path(rel_no_ext).name + ".png")).stat().st_size,
        "sha256": digest,
        "duplicateOf": duplicate_of,
    }
    return rel_no_ext

# Gather triangles by spatial object/material group. Dressing is clustered
# per fitted barricade (plus one altar cluster), so frustum culling does not
# keep all 708 props alive just because one distant prop is visible.
def dressing_cluster_name(obj):
    n = obj.name
    m = re.search(r"(?:BAR|NAIL|RUBBLE_BAR)_(\d{2})", n)
    if m:
        return "DRESS_BARRICADE_" + m.group(1)
    if "ALTAR_" in n:
        return "DRESS_ALTAR"
    return "DRESS_MISC_" + safe_name(n)

groups = {}
bounds_min = Vector((1e30,1e30,1e30))
bounds_max = Vector((-1e30,-1e30,-1e30))

for obj in all_runtime_objects:
    mesh = obj.data
    mesh.calc_loop_triangles()
    active_uv = mesh.uv_layers.active if mesh.uv_layers.active else (mesh.uv_layers[0] if len(mesh.uv_layers) else None)
    uv_layer = active_uv.data if active_uv else None
    world = obj.matrix_world
    normal_matrix = world.to_3x3().inverted().transposed()
    for tri in mesh.loop_triangles:
        poly = mesh.polygons[tri.polygon_index]
        mat = obj.material_slots[poly.material_index].material if poly.material_index < len(obj.material_slots) else None
        mat_img = material_image(mat)
        if mat_img and uv_layer is None and not obj.name.startswith("XZSM_DRESS_"):
            missing_uv_objects.add(obj.name)
        tex = save_material_texture(mat)
        group_name = dressing_cluster_name(obj) if obj.name.startswith("XZSM_DRESS_") else obj.name
        group_key = (group_name, tex)
        group = groups.setdefault(group_key, [])
        verts = []
        for loop_index in tri.loops:
            vi = mesh.loops[loop_index].vertex_index
            p_world = world @ mesh.vertices[vi].co
            n_world = normal_matrix @ mesh.vertices[vi].normal
            if n_world.length > 1e-8:
                n_world.normalize()
            else:
                n_world = Vector((0.0, 0.0, 1.0))
            rgba = baked_vertex_rgba(obj, p_world, n_world)
            p = (p_world - center) * QUAKE_SCALE
            if uv_layer:
                uv = uv_layer[loop_index].uv
                u = float(uv.x)
                v = 1.0 - float(uv.y)
            else:
                u = v = 0.0
            verts.append((float(p.x), float(p.y), float(p.z), u, v, *rgba))
            bounds_min.x=min(bounds_min.x,p.x); bounds_min.y=min(bounds_min.y,p.y); bounds_min.z=min(bounds_min.z,p.z)
            bounds_max.x=max(bounds_max.x,p.x); bounds_max.y=max(bounds_max.y,p.y); bounds_max.z=max(bounds_max.z,p.z)
        group.append(verts)

# Split each object/material group into <=18k triangles so uint16 indices
# remain safe, but deduplicate identical position/UV tuples inside each batch.
# The old exporter emitted three brand-new vertices per triangle, which wasted
# RAM/bandwidth at HQ without adding any visual information.
batches = []
raw_vertex_count = 0
for (object_name, tex), tris in groups.items():
    for start in range(0, len(tris), MAX_TRIS_PER_BATCH):
        chunk = tris[start:start+MAX_TRIS_PER_BATCH]
        raw_vertex_count += len(chunk) * 3
        vertices = []
        indices = []
        vertex_map = {}
        mn = Vector((1e30,1e30,1e30)); mx = Vector((-1e30,-1e30,-1e30))
        for tri in chunk:
            for vtx in tri:
                idx = vertex_map.get(vtx)
                if idx is None:
                    idx = len(vertices)
                    if idx >= 65535:
                        raise RuntimeError(
                            f"XZSM batch exceeded uint16 vertex limit for {object_name}"
                        )
                    vertex_map[vtx] = idx
                    vertices.append(vtx)
                    x,y,z,u,v = vtx[:5]
                    mn.x=min(mn.x,x); mn.y=min(mn.y,y); mn.z=min(mn.z,z)
                    mx.x=max(mx.x,x); mx.y=max(mx.y,y); mx.z=max(mx.z,z)
                indices.append(idx)
        batches.append({
            "object": object_name,
            "texture": tex,
            "vertices": vertices,
            "indices": indices,
            "mins": mn,
            "maxs": mx,
        })

# Architectural photogrammetry must never silently degrade to a flat material
# or a single sampled texel. Dressing intentionally uses generated materials,
# so only source-church materials are fatal here.
church_fallbacks = sorted(m for m in fallback_materials if m in church_material_names)
if church_fallbacks:
    raise RuntimeError(
        "Sanctum architectural materials lost their source texture: " +
        ", ".join(church_fallbacks)
    )
if missing_uv_objects:
    raise RuntimeError(
        "Sanctum textured architecture is missing UVs: " +
        ", ".join(sorted(missing_uv_objects))
    )

model_path = MODEL_DIR / "sanctum.xzsm"
with model_path.open("wb") as f:
    f.write(struct.pack("<4sIIII", b"XZSM", XZSM_VERSION, len(batches),
                        sum(len(b["vertices"]) for b in batches),
                        sum(len(b["indices"]) for b in batches)))
    for b in batches:
        tex_bytes = b["texture"].encode("utf-8")[:95]
        tex_field = tex_bytes + b"\0" * (96-len(tex_bytes))
        f.write(struct.pack(
            "<II96s6f",
            len(b["vertices"]), len(b["indices"]), tex_field,
            b["mins"].x,b["mins"].y,b["mins"].z,
            b["maxs"].x,b["maxs"].y,b["maxs"].z,
        ))
        for vert in b["vertices"]:
            f.write(struct.pack("<5f4B", *vert))
        f.write(struct.pack("<" + "H"*len(b["indices"]), *b["indices"]))

report = {
    "format":"XZSM",
    "version":XZSM_VERSION,
    "sourceTriangles":source_tris,
    "cleanedTriangles":cleaned_tris,
    "runtimeTriangles":runtime_tris,
    "dressingTriangles":dressing_tris,
    "runtimeTotalTriangles":runtime_tris + dressing_tris,
    "dressingObjectCount":len(dressing_runtime_objects),
    "dressingClusters":len({dressing_cluster_name(o) for o in dressing_runtime_objects}),
    "targetTriangles":TARGET_TRIS,
    "textureMaxDimension":TEXTURE_MAX,
    "decimateRatio":ratio,
    "batching":"object_material_spatial",
    "vertexLighting":"mobile_safe_moon_warm_grade_v2",
    "vertexStrideBytes":24,
    "scanCleanup":cleanup_stats,
    "batchCount":len(batches),
    "textureCount":len(texture_records),
    "uniqueTextureCount":len(texture_digest_paths),
    "deduplicatedTextureCount":len(texture_records)-len(texture_digest_paths),
    "runtimeTextureNameMode":"short_qpath_safe_ids",
    "textureSourceMode":"raw_albedo_preserve",
    "fallbackMaterials":sorted(fallback_materials),
    "churchFallbackMaterials":church_fallbacks,
    "missingUvObjects":sorted(missing_uv_objects),
    "totalVertices":sum(len(b["vertices"]) for b in batches),
    "totalIndices":sum(len(b["indices"]) for b in batches),
    "rawTriangleVertices":raw_vertex_count,
    "vertexReuseRatio":(
        1.0 - (sum(len(b["vertices"]) for b in batches) / max(raw_vertex_count, 1))
    ),
    "modelBytes":model_path.stat().st_size,
    "boundsMin":list(bounds_min),
    "boundsMax":list(bounds_max),
    "quakeScale":QUAKE_SCALE,
    "centerMeters":list(center),
    "textures":texture_records,
}
(OUTDIR/"vril_static_mesh_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
(RUNTIME_ROOT/"ATTRIBUTION.txt").write_text(
    "SANCTUM OF ASH development visual mesh\n"
    "St Giles Cripplegate scan by artfletch — Creative Commons Attribution (CC BY).\n"
    "Runtime mesh/textures are transformed derivatives generated by Xziel's Blender pipeline.\n",
    encoding="utf-8"
)

print("XZSM_EXPORT_OK", json.dumps({
    "sourceTriangles":source_tris,
    "runtimeTriangles":runtime_tris,
    "dressingTriangles":dressing_tris,
    "runtimeTotalTriangles":runtime_tris + dressing_tris,
    "dressingObjectCount":len(dressing_runtime_objects),
    "dressingClusters":len({dressing_cluster_name(o) for o in dressing_runtime_objects}),
    "batchCount":len(batches),
    "textureCount":len(texture_records),
    "modelBytes":model_path.stat().st_size,
    "textureMaxDimension":TEXTURE_MAX,
    "scanCleanup":cleanup_stats,
    "vertexReuseRatio":(
        1.0 - (sum(len(b["vertices"]) for b in batches) / max(raw_vertex_count, 1))
    ),
}))
