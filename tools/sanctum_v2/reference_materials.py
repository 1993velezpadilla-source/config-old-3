"""Reference-driven Sanctum PBR material library.

The numeric palette/roughness targets were measured from the user-supplied
Sanctum reference boards (wet flagstone, aged masonry, Gothic wood, burgundy
cloth, stained glass and candle/brass closeups).  The source images are visual
references, not baked game textures: this module recreates the look with
procedural, resolution-independent nodes so the map keeps full material detail
without importing baked lighting from the reference photography.
"""
import bpy

PALETTE = {
    "floor_dark": (0.095, 0.060, 0.045, 1.0),
    "floor_warm": (0.255, 0.145, 0.085, 1.0),
    "floor_mortar": (0.025, 0.020, 0.018, 1.0),
    "stone_dark": (0.115, 0.082, 0.060, 1.0),
    "stone_warm": (0.355, 0.205, 0.120, 1.0),
    "wood_dark": (0.050, 0.018, 0.009, 1.0),
    "wood_warm": (0.285, 0.105, 0.035, 1.0),
    "cloth_dark": (0.110, 0.008, 0.012, 1.0),
    "cloth_warm": (0.360, 0.032, 0.030, 1.0),
    "gold": (0.545, 0.270, 0.055, 1.0),
    "wax": (0.860, 0.610, 0.310, 1.0),
    "iron": (0.028, 0.022, 0.019, 1.0),
}

def _mat(name):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True
    nt=m.node_tree
    nt.nodes.clear()
    out=nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf=nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"],out.inputs["Surface"])
    return m,nt,bsdf

def _map_nodes(nt, scale=(1.0,1.0,1.0)):
    tc=nt.nodes.new("ShaderNodeTexCoord")
    mapping=nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value=scale
    nt.links.new(tc.outputs["Object"],mapping.inputs["Vector"])
    return mapping

def _noise(nt, vector, scale, detail=5.0, rough=0.65, distortion=0.0):
    n=nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value=scale
    n.inputs["Detail"].default_value=detail
    n.inputs["Roughness"].default_value=rough
    if "Distortion" in n.inputs:
        n.inputs["Distortion"].default_value=distortion
    nt.links.new(vector,n.inputs["Vector"])
    return n

def _ramp(nt, fac, points):
    r=nt.nodes.new("ShaderNodeValToRGB")
    cr=r.color_ramp
    while len(cr.elements)>2:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position=points[0][0]
    cr.elements[0].color=points[0][1]
    cr.elements[1].position=points[-1][0]
    cr.elements[1].color=points[-1][1]
    for pos,col in points[1:-1]:
        e=cr.elements.new(pos)
        e.color=col
    nt.links.new(fac,r.inputs["Fac"])
    return r

def wet_flagstone(name="SANCTUM_REF_WET_FLAGSTONE"):
    m,nt,b= _mat(name)
    mapping=_map_nodes(nt,(1.15,1.15,1.0))
    brick=nt.nodes.new("ShaderNodeTexBrick")
    brick.offset=0.5
    brick.offset_frequency=2
    brick.squash=1.0
    brick.inputs["Color1"].default_value=PALETTE["floor_dark"]
    brick.inputs["Color2"].default_value=(0.19,0.105,0.065,1.0)
    brick.inputs["Mortar"].default_value=PALETTE["floor_mortar"]
    brick.inputs["Scale"].default_value=1.9
    brick.inputs["Mortar Size"].default_value=0.035
    brick.inputs["Mortar Smooth"].default_value=0.015
    nt.links.new(mapping.outputs["Vector"],brick.inputs["Vector"])

    coarse=_noise(nt,mapping.outputs["Vector"],3.6,7.0,0.72,0.15)
    fine=_noise(nt,mapping.outputs["Vector"],32.0,5.0,0.68,0.05)

    mix=nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type="MULTIPLY"
    mix.inputs[0].default_value=0.44
    nt.links.new(brick.outputs["Color"],mix.inputs[1])
    coarse_ramp=_ramp(nt,coarse.outputs["Fac"],[
        (0.20,(0.50,0.34,0.27,1.0)),
        (0.55,(0.92,0.70,0.55,1.0)),
        (0.82,(1.14,0.90,0.68,1.0)),
    ])
    nt.links.new(coarse_ramp.outputs["Color"],mix.inputs[2])
    nt.links.new(mix.outputs["Color"],b.inputs["Base Color"])

    bump=nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=0.30
    bump.inputs["Distance"].default_value=0.055
    nt.links.new(fine.outputs["Fac"],bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"],b.inputs["Normal"])

    # Wet patches: reference reads roughly 0.10-0.35 roughness with dry islands.
    rr=nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["From Min"].default_value=0.24
    rr.inputs["From Max"].default_value=0.80
    rr.inputs["To Min"].default_value=0.10
    rr.inputs["To Max"].default_value=0.36
    nt.links.new(coarse.outputs["Fac"],rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"],b.inputs["Roughness"])
    b.inputs["Metallic"].default_value=0.0
    return m

def aged_masonry(name="SANCTUM_REF_AGED_MASONRY"):
    m,nt,b=_mat(name)
    mapping=_map_nodes(nt,(0.72,0.72,0.72))
    brick=nt.nodes.new("ShaderNodeTexBrick")
    brick.offset=0.5
    brick.offset_frequency=2
    brick.inputs["Color1"].default_value=PALETTE["stone_dark"]
    brick.inputs["Color2"].default_value=PALETTE["stone_warm"]
    brick.inputs["Mortar"].default_value=(0.035,0.025,0.020,1.0)
    brick.inputs["Scale"].default_value=2.7
    brick.inputs["Mortar Size"].default_value=0.045
    nt.links.new(mapping.outputs["Vector"],brick.inputs["Vector"])
    noise=_noise(nt,mapping.outputs["Vector"],5.6,8.0,0.72,0.20)
    mix=nt.nodes.new("ShaderNodeMixRGB")
    mix.blend_type="MULTIPLY"
    mix.inputs[0].default_value=0.32
    nt.links.new(brick.outputs["Color"],mix.inputs[1])
    ramp=_ramp(nt,noise.outputs["Fac"],[
        (0.18,(0.55,0.47,0.42,1.0)),
        (0.60,(1.00,0.78,0.58,1.0)),
        (0.86,(1.18,0.92,0.70,1.0)),
    ])
    nt.links.new(ramp.outputs["Color"],mix.inputs[2])
    nt.links.new(mix.outputs["Color"],b.inputs["Base Color"])
    fine=_noise(nt,mapping.outputs["Vector"],27.0,5.0,0.65,0.05)
    bump=nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=0.38
    bump.inputs["Distance"].default_value=0.095
    nt.links.new(fine.outputs["Fac"],bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"],b.inputs["Normal"])
    b.inputs["Roughness"].default_value=0.58
    return m

def gothic_wood(name="SANCTUM_REF_GOTHIC_WOOD", vertical=False):
    m,nt,b=_mat(name)
    scale=(6.0,6.0,0.32) if vertical else (0.32,6.0,6.0)
    mapping=_map_nodes(nt,scale)
    grain=_noise(nt,mapping.outputs["Vector"],3.0,8.0,0.72,0.18)
    pores=_noise(nt,mapping.outputs["Vector"],34.0,4.0,0.68,0.02)
    ramp=_ramp(nt,grain.outputs["Fac"],[
        (0.16,PALETTE["wood_dark"]),
        (0.46,(0.105,0.035,0.014,1.0)),
        (0.70,PALETTE["wood_warm"]),
        (0.88,(0.42,0.17,0.055,1.0)),
    ])
    nt.links.new(ramp.outputs["Color"],b.inputs["Base Color"])
    bump=nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=0.26
    bump.inputs["Distance"].default_value=0.038
    nt.links.new(pores.outputs["Fac"],bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"],b.inputs["Normal"])
    rr=nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["From Min"].default_value=0.20
    rr.inputs["From Max"].default_value=0.82
    rr.inputs["To Min"].default_value=0.27
    rr.inputs["To Max"].default_value=0.52
    nt.links.new(grain.outputs["Fac"],rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"],b.inputs["Roughness"])
    return m

def burgundy_cloth(name="SANCTUM_REF_BURGUNDY_CLOTH"):
    m,nt,b=_mat(name)
    mapping=_map_nodes(nt,(1.0,1.0,1.0))
    large=_noise(nt,mapping.outputs["Vector"],5.5,6.0,0.75,0.05)
    fiber=_noise(nt,mapping.outputs["Vector"],95.0,3.0,0.58,0.0)
    ramp=_ramp(nt,large.outputs["Fac"],[
        (0.22,PALETTE["cloth_dark"]),
        (0.60,(0.235,0.018,0.023,1.0)),
        (0.85,PALETTE["cloth_warm"]),
    ])
    nt.links.new(ramp.outputs["Color"],b.inputs["Base Color"])
    bump=nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=0.18
    bump.inputs["Distance"].default_value=0.018
    nt.links.new(fiber.outputs["Fac"],bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"],b.inputs["Normal"])
    b.inputs["Roughness"].default_value=0.64
    if "Sheen Weight" in b.inputs:
        b.inputs["Sheen Weight"].default_value=0.22
    return m

def aged_gold(name="SANCTUM_REF_AGED_GOLD"):
    m,nt,b=_mat(name)
    b.inputs["Base Color"].default_value=PALETTE["gold"]
    b.inputs["Metallic"].default_value=0.82
    b.inputs["Roughness"].default_value=0.29
    mapping=_map_nodes(nt,(1.0,1.0,1.0))
    n=_noise(nt,mapping.outputs["Vector"],22.0,4.0,0.62,0.02)
    bump=nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=0.12
    bump.inputs["Distance"].default_value=0.014
    nt.links.new(n.outputs["Fac"],bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"],b.inputs["Normal"])
    return m

def candle_wax(name="SANCTUM_REF_CANDLE_WAX"):
    m,nt,b=_mat(name)
    b.inputs["Base Color"].default_value=PALETTE["wax"]
    b.inputs["Roughness"].default_value=0.50
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value=0.07
    mapping=_map_nodes(nt,(1.0,1.0,1.0))
    n=_noise(nt,mapping.outputs["Vector"],28.0,4.0,0.62,0.04)
    bump=nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=0.10
    bump.inputs["Distance"].default_value=0.018
    nt.links.new(n.outputs["Fac"],bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"],b.inputs["Normal"])
    return m

def black_iron(name="SANCTUM_REF_BLACK_IRON"):
    m,nt,b=_mat(name)
    b.inputs["Base Color"].default_value=PALETTE["iron"]
    b.inputs["Metallic"].default_value=0.86
    b.inputs["Roughness"].default_value=0.30
    return m

def material_set():
    return {
        "floor":wet_flagstone(),
        "stone":aged_masonry(),
        "wood_h":gothic_wood("SANCTUM_REF_GOTHIC_WOOD_H",False),
        "wood_v":gothic_wood("SANCTUM_REF_GOTHIC_WOOD_V",True),
        "cloth":burgundy_cloth(),
        "gold":aged_gold(),
        "wax":candle_wax(),
        "iron":black_iron(),
    }
