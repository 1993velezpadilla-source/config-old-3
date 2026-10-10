"""Black Pines Forge: original deterministic procedural PBR surface maps.

All sources generated mathematically in Blender itself, no internet, no paid
services, no downloaded copyrighted textures. Small, reusable atlases shared
per MATERIAL across the entire GLB, not unique high-res textures per object.
"""
from array import array
import math
import bpy

# Original per-material tileable aged surfaces. 512px wall/floor textures,
# 256px metal/stains. Shared texture memory remains modest for Android.
SURFACES = {
    "plaster": 512,
    "medical": 512,
    "industrial": 512,
    "lobby": 512,
    "snow": 256,
    "rust": 256,
    "dark_metal": 256,
}
IMAGES = {}


def _hash(x, y, seed):
    # Integer-only, deterministic on any OS; stable across Blender versions.
    n = (x * 1664525 + y * 1013904223 + seed * 73471) & 0xFFFFFFFF
    n ^= n >> 15
    n = (n * 2246822519) & 0xFFFFFFFF
    n ^= n >> 13
    return float(n & 65535) / 65535.0


def _sample(name, x, y, width, seed):
    # Seamless tileability: all frequencies divide power-of-two dimensions.
    # Combine wide weathering with fine freckling and faint water streaks.
    wide = _hash((x // 64) % (width // 64),
                 (y // 64) % (width // 64), seed)
    mid = _hash((x // 16) % (width // 16),
                (y // 16) % (width // 16), seed + 37)
    fine = _hash(x % width, y % width, seed + 71)
    grain = (wide - .5) * .24 + (mid - .5) * .13 + (fine - .5) * .08
    drip = max(0.0, math.sin((x % width) * math.tau / 128.0)) ** 12
    scratch = (1.0 if (x+seed) % 103 == 0 else 0.0)
    if name == "plaster":
        return grain - drip * .055
    if name == "medical":
        # Slightly desaturated mildew; never a fake photographic texture.
        return grain * .60 - drip * .040
    if name == "industrial":
        return grain * .95 - scratch * .08
    if name == "lobby":
        return grain * .55 - drip * .045
    if name == "snow":
        return grain * .82
    if name == "rust":
        return grain * 1.22 - scratch * .10
    return grain * .72 - scratch * .07


def apply(api):
    IMAGES.clear()
    for name, width in SURFACES.items():
        if name not in api.PALETTE:
            raise RuntimeError("FORGE_PBR_RED palette missing "+name)
        m = api.mat(name)
        old = bpy.data.images.get("BP_SourceWear_"+name)
        if old is not None:
            bpy.data.images.remove(old, do_unlink=True)
        im = bpy.data.images.new("BP_SourceWear_"+name,
                                 width=width, height=width, alpha=True,
                                 float_buffer=False)
        base = api.PALETTE[name]
        seed = sum(ord(ch) for ch in name) + 2026
        values = array("f", [0.0]) * (width * width * 4)
        for y in range(width):
            for x in range(width):
                g = _sample(name,x,y,width,seed)
                # All channels respond similarly, preserving authored palette.
                # Input map is sRGB; keep contrast restrained under mobile
                # lights instead of inventing bright neon grain.
                i = (y*width + x)*4
                for k in range(3):
                    channel = base[k] * (1.0+g)
                    values[i+k] = min(.96,max(.012,channel))
                values[i+3] = 1.0
        im.pixels.foreach_set(values)
        im.update()
        # Generated pictures MUST be packed with the blend and embedded in
        # the GLB. Never depend on a machine-specific external file path.
        im.pack(as_png=True)
        im.colorspace_settings.name = "sRGB"
        tree = m.node_tree
        bsdf = tree.nodes.get("Principled BSDF")
        if bsdf is None:
            raise RuntimeError("FORGE_PBR_RED principled missing "+name)
        tex = tree.nodes.new("ShaderNodeTexImage")
        tex.name = "BP_Fidelity_Wear_"+name
        tex.label = "Original Black Pines procedural wear map"
        tex.image = im
        tex.interpolation = 'Linear'
        tree.links.new(tex.outputs["Color"],bsdf.inputs["Base Color"])
        IMAGES[name] = im
    print("BLACK_PINES_FORGE_PBR_MATERIALS_GREEN",
          "textures=",len(IMAGES),
          "max_texture_px=",max(SURFACES.values()),
          "source=original_procedural_in_blender")
    return {
        "source": "Original procedural textures authored in Blender",
        "textureCount":len(IMAGES),
        "resolutions":dict(SURFACES),
        "maxTextureSize":max(SURFACES.values()),
        "allEmbedded":all(bool(im.packed_file) for im in IMAGES.values()),
        "paidAPI":False,
        "copyrightedExternalTextures":False,
        "physicalAndroidFPSProven":False
    }


def fidelity_gate():
    issues = []
    for name, side in SURFACES.items():
        im = bpy.data.images.get("BP_SourceWear_"+name)
        mat = bpy.data.materials.get("BP_"+name)
        if im is None or im.size[0] != side or im.size[1] != side:
            issues.append("missing source PBR map "+name)
        elif not im.packed_file:
            issues.append("source texture not embedded "+name)
        if mat is None or not mat.use_nodes or not any(
                node.type == 'TEX_IMAGE' and node.image == im
                for node in mat.node_tree.nodes):
            issues.append("material lacks original texture node "+name)
    return issues
