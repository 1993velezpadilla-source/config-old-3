import bpy
import json
import math
import os
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("CHURCH_V1_OUT", ROOT / "church_v1/out"))
MANIFEST = Path(os.environ.get(
    "CHURCH_AD_MANIFEST",
    ROOT / "church_v1/spec/intrinsic_ads_v1.json",
))
SOURCE_BLEND = OUT / "church_v1_nave_art_v1.blend"

if not SOURCE_BLEND.is_file():
    raise RuntimeError(f"missing source blend: {SOURCE_BLEND}")
if not MANIFEST.is_file():
    raise RuntimeError(f"missing intrinsic ad manifest: {MANIFEST}")

spec = json.loads(MANIFEST.read_text(encoding="utf-8"))
placements = spec.get("placements", [])
if len(placements) != 6:
    raise RuntimeError(f"expected 6 intrinsic placements, got {len(placements)}")

bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))

old = bpy.data.collections.get("INTRINSIC_ADS_V1")
if old is not None:
    for obj in list(old.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(old)

ads = bpy.data.collections.new("INTRINSIC_ADS_V1")
bpy.context.scene.collection.children.link(ads)

def move_to_ads(obj):
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    ads.objects.link(obj)
    obj["xziel_stage"] = "intrinsic_ads_v1"

def make_material(name, base, roughness=0.55, metallic=0.0, emission=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission is not None:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 0.18
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (*emission, 1.0)
    return mat

FRAME = make_material("AD_FRAME_DARK_BRASS", (0.10, 0.055, 0.018), 0.38, 0.68)
TV_BODY = make_material("AD_TV_BODY", (0.018, 0.020, 0.024), 0.42, 0.48)
RADIO_BODY = make_material("AD_RADIO_BODY", (0.055, 0.030, 0.018), 0.62, 0.12)
RADIO_METAL = make_material("AD_RADIO_METAL", (0.055, 0.060, 0.065), 0.34, 0.72)

surface_materials = [
    make_material("AD_PLACEHOLDER_FRAME_01", (0.10, 0.18, 0.24), 0.48, 0.0, (0.03, 0.06, 0.10)),
    make_material("AD_PLACEHOLDER_FRAME_02", (0.22, 0.12, 0.055), 0.52, 0.0, (0.08, 0.03, 0.01)),
    make_material("AD_PLACEHOLDER_FRAME_03", (0.12, 0.20, 0.10), 0.50, 0.0, (0.03, 0.07, 0.02)),
    make_material("AD_PLACEHOLDER_POSTER", (0.19, 0.16, 0.10), 0.58, 0.0),
    make_material("AD_PLACEHOLDER_TV", (0.035, 0.060, 0.10), 0.24, 0.0, (0.04, 0.08, 0.16)),
]

def add_cube(name, loc, dims, material, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        mod = obj.modifiers.new("AD_EDGE_BEVEL", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.materials.append(material)
    move_to_ads(obj)
    return obj

def tag_surface(obj, placement):
    obj["xziel_ad_kind"] = "surface"
    obj["xziel_ad_placement_id"] = int(placement["placementId"])
    obj["xziel_ad_format"] = placement["format"]
    obj["xziel_ad_placeholder_texture"] = placement["placeholderTexture"]
    obj["xziel_ad_max_view_distance_m"] = float(placement["maxViewDistanceMeters"])
    obj["xziel_ad_min_facing_cosine"] = float(placement["minimumFacingCosine"])
    obj["xziel_ad_min_screen_coverage"] = float(placement["minimumScreenCoverage"])
    obj["xziel_ad_impression_seconds"] = float(placement["impressionViewSeconds"])
    obj["xziel_ad_cooldown_seconds"] = float(placement["cooldownSeconds"])
    obj["xziel_ad_session_cap"] = int(placement["maxImpressionsPerSession"])
    obj["xziel_ad_no_auto_click"] = True
    obj["xziel_ad_no_impression_on_load"] = True

def add_surface(placement, material):
    x, y, z = [float(v) for v in placement["center"]]
    width = float(placement["width"])
    height = float(placement["height"])
    axis = placement["wallAxis"]
    name = placement["name"].upper()

    if axis == "x":
        inward = 1.0 if x < 0.0 else -1.0
        backing_loc = (x, y, z)
        surface_loc = (x + inward * 0.095, y, z)
        backing_dims = (0.16, width + 0.30, height + 0.30)
        surface_dims = (0.055, width, height)
    elif axis == "y":
        inward = -1.0
        backing_loc = (x, y, z)
        surface_loc = (x, y + inward * 0.095, z)
        backing_dims = (width + 0.30, 0.16, height + 0.30)
        surface_dims = (width, 0.055, height)
    else:
        raise RuntimeError(f"unsupported wallAxis {axis}")

    frame_mat = TV_BODY if placement["format"] == "video" else FRAME
    add_cube(f"{name}_FRAME", backing_loc, backing_dims, frame_mat, 0.055)
    surface = add_cube(
        f"{name}_AD_SURFACE",
        surface_loc,
        surface_dims,
        material,
        0.018,
    )
    tag_surface(surface, placement)
    return surface

surface_index = 0
surface_objects = []
audio_objects = []

for placement in placements:
    kind = placement["kind"]
    if kind == "surface":
        surface = add_surface(
            placement,
            surface_materials[surface_index],
        )
        surface_index += 1
        surface_objects.append(surface)
        continue

    if kind != "audio":
        raise RuntimeError(f"unknown placement kind {kind}")

    x, y, z = [float(v) for v in placement["center"]]
    shelf = add_cube(
        "ENTRY_RADIO_SHELF",
        (x, y, z - 0.52),
        (1.65, 0.72, 0.12),
        FRAME,
        0.035,
    )
    radio = add_cube(
        "ENTRY_RADIO_AD_AUDIO_EMITTER",
        (x, y, z),
        (1.25, 0.48, 0.72),
        RADIO_BODY,
        0.065,
    )
    add_cube(
        "ENTRY_RADIO_SPEAKER_GRILLE",
        (x - 0.31, y - 0.255, z),
        (0.48, 0.035, 0.48),
        RADIO_METAL,
        0.02,
    )
    add_cube(
        "ENTRY_RADIO_DIAL",
        (x + 0.35, y - 0.265, z + 0.12),
        (0.18, 0.05, 0.18),
        RADIO_METAL,
        0.025,
    )

    radio["xziel_ad_kind"] = "audio_emitter"
    radio["xziel_ad_placement_id"] = int(placement["placementId"])
    radio["xziel_ad_placeholder_audio"] = placement["placeholderAudio"]
    radio["xziel_ad_min_distance_m"] = float(placement["minimumDistanceMeters"])
    radio["xziel_ad_max_distance_m"] = float(placement["maximumDistanceMeters"])
    radio["xziel_ad_max_gain"] = float(placement["maximumGain"])
    radio["xziel_ad_impression_seconds"] = float(placement["impressionListenSeconds"])
    radio["xziel_ad_cooldown_seconds"] = float(placement["cooldownSeconds"])
    radio["xziel_ad_session_cap"] = int(placement["maxImpressionsPerSession"])
    radio["xziel_ad_no_auto_click"] = True
    audio_objects.append(radio)

if len(surface_objects) != 5 or len(audio_objects) != 1:
    raise RuntimeError("intrinsic placement type count mismatch")

# Export all authored geometry plus ad marker geometry. Extras preserve placement
# metadata in the GLB for downstream XZIEL conversion/auditing.
bpy.ops.object.select_all(action="DESELECT")
export_meshes = [
    obj for obj in bpy.context.scene.objects
    if obj.type == "MESH" and obj.name != "NAVE_VOLUME"
]
for obj in export_meshes:
    obj.select_set(True)
if export_meshes:
    bpy.context.view_layer.objects.active = export_meshes[0]

ads_glb = OUT / "church_v1_nave_art_ads_v1.glb"
bpy.ops.export_scene.gltf(
    filepath=str(ads_glb),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_extras=True,
)

def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

scene = bpy.context.scene
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

bpy.ops.object.camera_add(location=(0.0, -11.8, 1.62))
camera = bpy.context.object
camera.name = "INTRINSIC_AD_PREVIEW_CAMERA"
camera.data.lens = 24
look_at(camera, (-4.2, 1.5, 3.25))
scene.camera = camera
scene.render.filepath = str(OUT / "intrinsic_ads_player.png")
bpy.ops.render.render(write_still=True)
bpy.data.objects.remove(camera, do_unlink=True)

report = {
    "stage": "INTRINSIC_ADS_V1",
    "mapId": spec["mapId"],
    "placementCount": len(placements),
    "surfaceCount": len(surface_objects),
    "audioEmitterCount": len(audio_objects),
    "placementIds": [int(p["placementId"]) for p in placements],
    "uniquePlacementIds": len({int(p["placementId"]) for p in placements}),
    "hudOverlayAds": bool(spec["rules"]["hudOverlayAds"]),
    "automaticClicks": bool(spec["rules"]["automaticClicks"]),
    "impressionOnLoad": bool(spec["rules"]["impressionOnLoad"]),
    "provider": spec["rules"]["provider"],
    "exportedGlb": ads_glb.name,
}
(OUT / "intrinsic_ads_v1_report.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8",
)

bpy.ops.wm.save_as_mainfile(
    filepath=str(OUT / "church_v1_nave_art_ads_v1.blend")
)

print("CHURCH_INTRINSIC_ADS_V1_OK", report)
