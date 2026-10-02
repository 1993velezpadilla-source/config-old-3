import bpy
import bmesh
import json
import math
import os
from pathlib import Path
from mathutils import Vector, Matrix

OUT=Path(os.environ.get("SANCTUM_V2_RELIEF_OUT","sanctum-v2-relief-glass"))
ASSETS=Path(os.environ.get("SANCTUM_V2_RELIEF_ASSETS","sanctum-v2-relief-assets"))
MANIFEST=ASSETS/"SOURCE_MANIFEST.json"
SHADER_LIB=Path(os.environ["SANCTUM_V2_GLASS_SHADER_LIB"])
SHADER_NAME="Crown Glass for windows"
INTERIOR_SOURCE=Path(os.environ["SANCTUM_V2_INTERIOR_SOURCE"])
OUT.mkdir(parents=True,exist_ok=True)

TARGET="Catehdral"
UV_NAME="UVMap"
REQUIRED={"GroundFloorWalls","FakeRoof","BeamFakeTextureVertical","RoundWindwos"}

def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))

def tile_meters(manifest,asset):
    dims=manifest["polyhaven"][asset]["dimensions_mm"]
    vals=[float(v)/1000.0 for v in dims[:2] if float(v)>0]
    if len(vals)<2:
        raise SystemExit(f"Missing 2D physical dimensions for {asset}: {dims}")
    return math.sqrt(vals[0]*vals[1])

def load_image(path,noncolor=False):
    img=bpy.data.images.load(str(path),check_existing=True)
    if noncolor:
        img.colorspace_settings.name="Non-Color"
    return img

def box_tex(nodes,img):
    n=nodes.new("ShaderNodeTexImage")
    n.image=img
    n.extension="REPEAT"
    n.projection="BOX"
    n.projection_blend=0.2
    return n

def build_relief_box_material(mat,diffuse,roughness,displacement,tile_m,resolution):
    mat.use_nodes=True
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    nodes.clear()

    out=nodes.new("ShaderNodeOutputMaterial")
    bsdf=nodes.new("ShaderNodeBsdfPrincipled")
    texcoord=nodes.new("ShaderNodeTexCoord")
    mapping=nodes.new("ShaderNodeMapping")

    repeat=1.0/tile_m
    mapping.inputs["Scale"].default_value=(repeat,repeat,repeat)

    diff=box_tex(nodes,load_image(diffuse,False))
    rough=box_tex(nodes,load_image(roughness,True))
    disp=box_tex(nodes,load_image(displacement,True))
    bump=nodes.new("ShaderNodeBump")

    # Physical, data-derived bump distance: one source texel in world units.
    bump.inputs["Distance"].default_value=tile_m/float(resolution)

    links.new(texcoord.outputs["Object"],mapping.inputs["Vector"])
    for n in (diff,rough,disp):
        links.new(mapping.outputs["Vector"],n.inputs["Vector"])

    links.new(diff.outputs["Color"],bsdf.inputs["Base Color"])
    links.new(rough.outputs["Color"],bsdf.inputs["Roughness"])
    links.new(disp.outputs["Color"],bump.inputs["Height"])
    links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"],out.inputs["Surface"])

def build_world_relief_box_material(mat,diffuse,roughness,displacement,tile_m,resolution):
    mat.use_nodes=True
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    nodes.clear()

    out=nodes.new("ShaderNodeOutputMaterial")
    bsdf=nodes.new("ShaderNodeBsdfPrincipled")
    geom=nodes.new("ShaderNodeNewGeometry")
    mapping=nodes.new("ShaderNodeMapping")

    repeat=1.0/tile_m
    mapping.inputs["Scale"].default_value=(repeat,repeat,repeat)

    diff=box_tex(nodes,load_image(diffuse,False))
    rough=box_tex(nodes,load_image(roughness,True))
    disp=box_tex(nodes,load_image(displacement,True))
    bump=nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value=tile_m/float(resolution)

    # World-space position keeps physical texel scale stable even though the
    # imported props retain different authored object transforms.
    links.new(geom.outputs["Position"],mapping.inputs["Vector"])
    for n in (diff,rough,disp):
        links.new(mapping.outputs["Vector"],n.inputs["Vector"])

    links.new(diff.outputs["Color"],bsdf.inputs["Base Color"])
    links.new(rough.outputs["Color"],bsdf.inputs["Roughness"])
    links.new(disp.outputs["Color"],bump.inputs["Height"])
    links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    links.new(bsdf.outputs["BSDF"],out.inputs["Surface"])

def object_bounds_single(o):
    pts=[o.matrix_world @ Vector(c) for c in o.bound_box]
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def normalize_cross_scale(props):
    crosses=[o for o in props if o.name=="Cross" or o.name.startswith("Cross.")]
    if len(crosses)<2:
        return {"cross_count":len(crosses),"applied":False,"reason":"fewer than two crosses"}

    rows=[]
    for o in crosses:
        mn,mx=object_bounds_single(o)
        rows.append((o,mn,mx,mx.z-mn.z))
    heights=sorted(float(r[3]) for r in rows)
    n=len(heights)
    median_h=heights[n//2] if n%2 else (heights[n//2-1]+heights[n//2])*0.5
    largest=max(rows,key=lambda r:r[3])
    o,old_mn,old_mx,old_h=largest
    cap_h=median_h*2.0
    applied=old_h>cap_h+1e-6
    factor=1.0
    if applied:
        factor=cap_h/old_h
        old_anchor=Vector(((old_mn.x+old_mx.x)*0.5,(old_mn.y+old_mx.y)*0.5,old_mn.z))
        o.scale=o.scale*factor
        bpy.context.view_layer.update()
        new_mn,new_mx=object_bounds_single(o)
        new_anchor=Vector(((new_mn.x+new_mx.x)*0.5,(new_mn.y+new_mx.y)*0.5,new_mn.z))
        o.location += old_anchor-new_anchor
        bpy.context.view_layer.update()

    final_rows=[]
    for x in crosses:
        mn,mx=object_bounds_single(x)
        final_rows.append({"name":x.name,"size":list(mx-mn)})
    final_heights=sorted(r["size"][2] for r in final_rows)
    return {
        "cross_count":len(crosses),
        "median_height_before_m":median_h,
        "largest_height_before_m":float(old_h),
        "cap_rule":"largest cross height <= 2x median cross height",
        "cap_height_m":cap_h,
        "applied":applied,
        "scale_factor":factor,
        "adjusted_object":o.name if applied else None,
        "preserve_anchor":"world bounds bottom-center",
        "final_crosses":final_rows,
        "largest_to_median_after":max(final_heights)/(sorted(final_heights)[len(final_heights)//2] if final_heights else 1.0),
    }

def restore_authored_legacy_prop_shaders(props):
    restored=[]
    seen=set()
    packed_images=[]
    for o in props:
        # Wood-remapped church furniture deliberately uses the new PBR material.
        if (o.name=="pew" or o.name.startswith("pew.") or
            o.name=="altar" or o.name.startswith("altar.") or
            o.name=="Cross" or o.name.startswith("Cross.")):
            continue
        for slot in o.material_slots:
            m=slot.material
            if m is None or m.as_pointer() in seen or not m.use_nodes or not m.node_tree:
                continue
            seen.add(m.as_pointer())
            nodes=m.node_tree.nodes
            links=m.node_tree.links
            outputs=[n for n in nodes if n.type=="OUTPUT_MATERIAL"]
            active=next((n for n in outputs if getattr(n,"is_active_output",False)),None)
            if active is None or active.inputs.get("Surface") is None:
                continue

            active_src=(active.inputs["Surface"].links[0].from_node if active.inputs["Surface"].is_linked else None)
            if active_src is None or active_src.type!="BSDF_PRINCIPLED":
                continue

            candidates=[]
            for out in outputs:
                if out==active or out.inputs.get("Surface") is None or not out.inputs["Surface"].is_linked:
                    continue
                link=out.inputs["Surface"].links[0]
                src=link.from_node
                if src.type=="BSDF_PRINCIPLED":
                    continue
                score=0
                if out.name=="Material Output":
                    score+=100
                if src.type in ("MIX_SHADER","BSDF_GLASS"):
                    score+=50
                if src.type=="BSDF_DIFFUSE":
                    score+=20
                candidates.append((score,out,link))
            if not candidates:
                continue
            _,legacy_out,legacy_link=max(candidates,key=lambda x:x[0])

            for old in list(active.inputs["Surface"].links):
                links.remove(old)
            links.new(legacy_link.from_socket,active.inputs["Surface"])

            if active.inputs.get("Displacement") is not None and legacy_out.inputs.get("Displacement") is not None and legacy_out.inputs["Displacement"].is_linked:
                for old in list(active.inputs["Displacement"].links):
                    links.remove(old)
                links.new(legacy_out.inputs["Displacement"].links[0].from_socket,active.inputs["Displacement"])

            images=[]
            for n in nodes:
                if n.type=="TEX_IMAGE" and n.image is not None:
                    row={
                        "material":m.name,
                        "node":n.name,
                        "packed":bool(n.image.packed_file),
                        "size":list(n.image.size),
                    }
                    images.append(row)
                    if row["packed"]:
                        packed_images.append(row)

            restored.append({
                "material":m.name,
                "objects":[x.name for x in props if any(s.material==m for s in x.material_slots)],
                "active_output":active.name,
                "legacy_output":legacy_out.name,
                "legacy_surface_node":legacy_link.from_node.name,
                "legacy_surface_type":legacy_link.from_node.type,
                "images":images,
            })
    return {
        "restored_count":len(restored),
        "materials":restored,
        "packed_image_count":len(packed_images),
        "packed_images":packed_images,
        "rule":"restore authored pre-Principled surface graph into Blender 5.2 active output for non-wood CC0 props",
    }

def upgrade_cc0_interior_materials(props,manifest,resolution):
    wood_asset="wood_planks"
    wood_tile=tile_meters(manifest,wood_asset)
    wood=bpy.data.materials.get("XZIEL_CC0_WoodPBR")
    if wood is None:
        wood=bpy.data.materials.new("XZIEL_CC0_WoodPBR")
    build_world_relief_box_material(
        wood,
        ASSETS/wood_asset/"diffuse.png",
        ASSETS/wood_asset/"rough.png",
        ASSETS/wood_asset/"displacement.png",
        wood_tile,
        resolution,
    )

    remapped=[]
    kept_authored=[]
    for o in props:
        wood_object=(o.name=="pew" or o.name.startswith("pew.") or
                     o.name=="altar" or o.name.startswith("altar.") or
                     o.name=="Cross" or o.name.startswith("Cross."))
        if wood_object:
            if len(o.data.materials)==0:
                o.data.materials.append(wood)
            else:
                for i in range(len(o.data.materials)):
                    o.data.materials[i]=wood
            remapped.append(o.name)
        else:
            kept_authored.append(o.name)

    return {
        "wood_pbr":{
            "asset":wood_asset,
            "provider":"Poly Haven",
            "license":"CC0",
            "mapping":"world-space BOX triplanar",
            "physical_tile_m":wood_tile,
            "texture_resolution":resolution,
            "bump_distance_m":wood_tile/float(resolution),
            "objects":remapped,
            "object_count":len(remapped),
        },
        "kept_authored_material_objects":kept_authored,
        "rule":"replace only source flat-gray pew/altar/cross material with verified CC0 wood PBR; preserve authored pipe/candle/bible material slots",
    }

def build_cathedral_floor_overlay(source_obj,manifest,resolution,scene_floor_z):
    asset="monastery_stone_floor"
    tile=tile_meters(manifest,asset)
    mat=bpy.data.materials.get("XZIEL_MonasteryStoneFloorPBR")
    if mat is None:
        mat=bpy.data.materials.new("XZIEL_MonasteryStoneFloorPBR")
    build_world_relief_box_material(
        mat,
        ASSETS/asset/"diffuse.png",
        ASSETS/asset/"rough.png",
        ASSETS/asset/"displacement.png",
        tile,
        resolution,
    )

    # Data-driven floor-only brightness correction. A dedicated audit of the
    # exact Poly Haven 4K diffuse measured p50=0.3372549. Preserve the authored
    # texture contrast while raising the median toward 0.45 so the stone reads
    # under Sanctum's deliberately dark interior lighting.
    source_median_luma=0.33725490196078434
    target_median_luma=0.45
    albedo_value_boost=target_median_luma/source_median_luma
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    bsdf=next(n for n in nodes if n.bl_idname=="ShaderNodeBsdfPrincipled")
    diff=next(
        n for n in nodes
        if n.bl_idname=="ShaderNodeTexImage"
        and n.image is not None
        and Path(bpy.path.abspath(n.image.filepath)).name=="diffuse.png"
    )
    for link in list(bsdf.inputs["Base Color"].links):
        links.remove(link)
    color_boost=nodes.new("ShaderNodeHueSaturation")
    color_boost.inputs["Hue"].default_value=0.5
    color_boost.inputs["Saturation"].default_value=0.94
    color_boost.inputs["Value"].default_value=albedo_value_boost
    links.new(diff.outputs["Color"],color_boost.inputs["Color"])
    links.new(color_boost.outputs["Color"],bsdf.inputs["Base Color"])

    # The earlier face-extraction pass covered only 58.8897 m² inside a
    # 961.8336 m² XY footprint (6.12%), proving those upward GroundFloorWalls
    # faces are ledges/fragments rather than the visible nave floor. Build one
    # continuous floor slab from the evaluated cathedral XY bounds instead.
    st=evaluated_stats(source_obj)
    mn=Vector(st["min"])
    mx=Vector(st["max"])
    footprint_size=mx-mn

    # Keep the slab under the wall shell. Half one authored physical tile on
    # every side is a data-derived safety inset, not an eyeballed wall offset.
    inset=tile*0.5
    x0=mn.x+inset
    x1=mx.x-inset
    y0=mn.y+inset
    y1=mx.y-inset
    if x1<=x0 or y1<=y0:
        raise SystemExit(f"Invalid cathedral floor footprint after inset: {list(mn)} {list(mx)} inset={inset}")

    z=float(scene_floor_z)+0.006
    verts=[
        (x0,y0,z),
        (x1,y0,z),
        (x1,y1,z),
        (x0,y1,z),
    ]
    faces=[(0,1,2,3)]
    mesh=bpy.data.meshes.new("XZIEL_CathedralFloorOverlayMesh")
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    overlay=bpy.data.objects.new("XZIEL_CathedralFloorOverlay",mesh)
    bpy.context.scene.collection.objects.link(overlay)
    overlay.data.materials.append(mat)

    slab_area=(x1-x0)*(y1-y0)
    bbox_area=footprint_size.x*footprint_size.y
    coverage_ratio=(slab_area/bbox_area) if bbox_area>0 else 0.0

    return overlay,{
        "asset":asset,
        "provider":"Poly Haven",
        "license":"CC0",
        "source_material_audit":{
            "fragment_face_count":965,
            "fragment_area_m2":58.88974427450465,
            "fragment_bbox_xy_area_m2":961.833611277325,
            "fragment_coverage_ratio":0.06122654020823671,
            "decision":"fragment extraction rejected; use continuous evaluated-cathedral XY footprint",
        },
        "footprint_bounds":{
            "source_min":list(mn),
            "source_max":list(mx),
            "source_size":list(footprint_size),
            "inset_m":inset,
            "slab_min":[x0,y0,z],
            "slab_max":[x1,y1,z],
            "slab_size":[x1-x0,y1-y0,0.0],
        },
        "face_count":len(mesh.polygons),
        "area_m2_object_space":slab_area,
        "bbox_xy_area_m2":bbox_area,
        "coverage_ratio":coverage_ratio,
        "z_fight_offset_m":0.006,
        "mapping":"world-space BOX triplanar",
        "physical_tile_m":tile,
        "texture_resolution":resolution,
        "bump_distance_m":tile/float(resolution),
        "albedo_luminance_audit":{
            "source_mean_luma":0.34727313775642243,
            "source_p10":0.2784313725490196,
            "source_p50":source_median_luma,
            "source_p90":0.42745098039215684,
            "target_p50":target_median_luma,
            "value_boost":albedo_value_boost,
            "saturation":0.94,
            "rule":"floor-only authored diffuse correction; no global exposure change",
        },
    }

def load_authored_glass_shader():
    if not SHADER_LIB.is_file():
        raise SystemExit(f"Missing authored shader library: {SHADER_LIB}")
    with bpy.data.libraries.load(str(SHADER_LIB), link=False) as (data_from, data_to):
        if SHADER_NAME not in data_from.materials:
            raise SystemExit(f"Missing authored shader {SHADER_NAME!r}")
        data_to.materials=[SHADER_NAME]
    mat=bpy.data.materials.get(SHADER_NAME)
    if mat is None or not mat.use_nodes or not mat.node_tree:
        raise SystemExit(f"Authored shader {SHADER_NAME!r} has no node tree")
    nodes=[n for n in mat.node_tree.nodes if n.bl_idname=="ShaderNodeBsdfPrincipled"]
    if len(nodes)!=1:
        raise SystemExit(f"Expected one Principled BSDF in {SHADER_NAME!r}, got {len(nodes)}")
    return mat,nodes[0]

def copy_socket_default(dst,src):
    if not hasattr(src,"default_value") or not hasattr(dst,"default_value"):
        return
    v=src.default_value
    try:
        if hasattr(v,"__len__") and not isinstance(v,str):
            dst.default_value=tuple(v)
        else:
            dst.default_value=v
    except Exception as e:
        raise SystemExit(f"Could not copy authored socket {src.name!r}: {e}")

def apply_stained_glass_authored_shader(mat,color_path,normal_path,expected_size):
    if not mat.use_nodes or not mat.node_tree:
        raise SystemExit("RoundWindwos has no node tree")
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    bsdfs=[n for n in nodes if n.bl_idname=="ShaderNodeBsdfPrincipled"]
    if not bsdfs:
        raise SystemExit("RoundWindwos has no Principled BSDF")

    src_mat,src_bsdf=load_authored_glass_shader()

    # Copy authored Principled parameters from the external CC0 shader at runtime.
    copied={}
    for dst_bsdf in bsdfs:
        for src_in in src_bsdf.inputs:
            if src_in.is_linked:
                continue
            dst_in=dst_bsdf.inputs.get(src_in.name)
            if dst_in is None:
                continue
            copy_socket_default(dst_in,src_in)
            if src_in.name in ("IOR","Roughness","Transmission Weight","Specular IOR Level","Coat Roughness"):
                v=src_in.default_value
                try:
                    copied[src_in.name]=float(v)
                except Exception:
                    copied[src_in.name]=str(v)

    color_img=load_image(color_path,False)
    normal_img=load_image(normal_path,True)
    actual=list(color_img.size)
    normal_size=list(normal_img.size)
    if actual!=list(expected_size):
        raise SystemExit(f"Unexpected stained-glass color dimensions: {actual} expected={expected_size}")
    if normal_size!=actual:
        raise SystemExit(f"Stained-glass normal dimensions mismatch: color={actual} normal={normal_size}")

    uv=nodes.new("ShaderNodeUVMap")
    uv.uv_map=UV_NAME
    tex_color=nodes.new("ShaderNodeTexImage")
    tex_color.image=color_img
    tex_color.extension="REPEAT"
    tex_color.projection="FLAT"

    tex_normal=nodes.new("ShaderNodeTexImage")
    tex_normal.image=normal_img
    tex_normal.extension="REPEAT"
    tex_normal.projection="FLAT"
    nmap=nodes.new("ShaderNodeNormalMap")

    links.new(uv.outputs["UV"],tex_color.inputs["Vector"])
    links.new(uv.outputs["UV"],tex_normal.inputs["Vector"])
    links.new(tex_normal.outputs["Color"],nmap.inputs["Color"])

    for bsdf in bsdfs:
        links.new(tex_color.outputs["Color"],bsdf.inputs["Base Color"])
        links.new(nmap.outputs["Normal"],bsdf.inputs["Normal"])

    return {
        "source_library":str(SHADER_LIB),
        "source_material":src_mat.name,
        "copied_principled_defaults":copied,
    }

def evaluated_stats(obj):
    deps=bpy.context.evaluated_depsgraph_get()
    ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh()
    try:
        verts=[ev.matrix_world@v.co for v in mesh.vertices]
        mn=Vector((min(v.x for v in verts),min(v.y for v in verts),min(v.z for v in verts)))
        mx=Vector((max(v.x for v in verts),max(v.y for v in verts),max(v.z for v in verts)))
        return {
            "vertices":len(mesh.vertices),
            "polygons":len(mesh.polygons),
            "uv_layers":[x.name for x in mesh.uv_layers],
            "center":list((mn+mx)*0.5),
            "min":list(mn),
            "max":list(mx),
            "size":list(mx-mn),
        }
    finally:
        ev.to_mesh_clear()

def ensure_cam(scene):
    data=bpy.data.cameras.get("SANCTUM_V2_RELIEF_CAMERA_DATA") or bpy.data.cameras.new("SANCTUM_V2_RELIEF_CAMERA_DATA")
    cam=bpy.data.objects.get("SANCTUM_V2_RELIEF_CAMERA") or bpy.data.objects.new("SANCTUM_V2_RELIEF_CAMERA",data)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    scene.camera=cam
    cam.data.lens=38
    return cam

def point(cam,target):
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat("-Z","Y").to_euler()

def ensure_world(scene):
    if scene.world is None:
        scene.world=bpy.data.worlds.new("SANCTUM_V2_RELIEF_WORLD")
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value=(0.035,0.04,0.055,1)
        bg.inputs["Strength"].default_value=0.55

def ensure_lights(scene,center,size):
    lights=[]
    ext=max(size.x,size.y,size.z)
    configs=[
        ("KEY",Vector((0.7,-0.8,1.1)),2400,ext*0.5),
        ("FILL",Vector((-0.8,0.2,0.65)),1400,ext*0.7),
        ("RIM",Vector((0.1,0.8,1.3)),1800,ext*0.45),
    ]
    for name,off,energy,area in configs:
        ld=bpy.data.lights.get(f"SANCTUM_V2_RELIEF_{name}_DATA") or bpy.data.lights.new(f"SANCTUM_V2_RELIEF_{name}_DATA","AREA")
        lo=bpy.data.objects.get(f"SANCTUM_V2_RELIEF_{name}") or bpy.data.objects.new(f"SANCTUM_V2_RELIEF_{name}",ld)
        if lo.name not in scene.collection.objects:
            scene.collection.objects.link(lo)
        lo.location=center+off*ext
        ld.energy=energy
        ld.shape="DISK"
        ld.size=max(area,2.0)
        lo.rotation_euler=(center-lo.location).to_track_quat("-Z","Y").to_euler()
        lights.append(lo)
    return lights

def enable_raytraced_glass(scene,mat):
    applied={}
    if hasattr(scene,"eevee") and scene.eevee is not None:
        if hasattr(scene.eevee,"use_raytracing"):
            scene.eevee.use_raytracing=True
            applied["scene.eevee.use_raytracing"]=True
        if hasattr(scene.eevee,"ray_tracing_method"):
            scene.eevee.ray_tracing_method="SCREEN"
            applied["scene.eevee.ray_tracing_method"]="SCREEN"
    if hasattr(mat,"surface_render_method"):
        mat.surface_render_method="DITHERED"
        applied["material.surface_render_method"]="DITHERED"
    if hasattr(mat,"use_raytrace_refraction"):
        mat.use_raytrace_refraction=True
        applied["material.use_raytrace_refraction"]=True
    if hasattr(mat,"use_screen_refraction"):
        mat.use_screen_refraction=True
        applied["material.use_screen_refraction"]=True
    return applied

def ensure_window_backlights(scene,center,size):
    # Reuse the proven three-light review rig powers; only positions are moved inside
    # the cathedral so the glass receives illumination from behind.
    proven_powers=(2400.0,1400.0,1800.0)
    energy=sum(proven_powers)/len(proven_powers)
    z0=center.z
    offsets=(
        Vector((0,-size.y*0.22,0)),
        Vector((0,0,size.z*0.12)),
        Vector((0,size.y*0.22,0)),
    )
    lights=[]
    for idx,off in enumerate(offsets,1):
        ld=bpy.data.lights.get(f"SANCTUM_V2_GLASS_BACKLIGHT_{idx}_DATA") or bpy.data.lights.new(f"SANCTUM_V2_GLASS_BACKLIGHT_{idx}_DATA","POINT")
        lo=bpy.data.objects.get(f"SANCTUM_V2_GLASS_BACKLIGHT_{idx}") or bpy.data.objects.new(f"SANCTUM_V2_GLASS_BACKLIGHT_{idx}",ld)
        if lo.name not in scene.collection.objects:
            scene.collection.objects.link(lo)
        lo.location=center+off
        ld.energy=energy
        lights.append(lo)
    return lights,{"count":len(lights),"energy_each":energy,"source_powers":list(proven_powers)}

def build_emissive_window_backing(obj,source_material_name,color_path,physical_offset_m):
    deps=bpy.context.evaluated_depsgraph_get()
    ev=obj.evaluated_get(deps)
    mesh=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=deps)
    if mesh is None:
        raise SystemExit("Could not create evaluated backing mesh")

    # Convert to world-space geometry so the offset rule is in real scene units.
    mesh.transform(obj.matrix_world)

    material_indices=[
        i for i,m in enumerate(mesh.materials)
        if m is not None and (m.name==source_material_name or m.name.startswith(source_material_name+"."))
    ]
    if not material_indices:
        raise SystemExit(f"Evaluated mesh does not contain {source_material_name!r}")
    source_index=material_indices[0]

    bm=bmesh.new()
    bm.from_mesh(mesh)
    remove=[f for f in bm.faces if f.material_index!=source_index]
    bmesh.ops.delete(bm,geom=remove,context="FACES")

    bm.normal_update()
    kept_faces=len(bm.faces)
    if kept_faces<=0:
        bm.free()
        raise SystemExit("No evaluated window faces remained for emissive backing")

    for v in bm.verts:
        v.co -= v.normal * physical_offset_m

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    mat=bpy.data.materials.new("SANCTUM_V2_WINDOW_EMISSIVE_BACKING")
    mat.use_nodes=True
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    nodes.clear()

    out=nodes.new("ShaderNodeOutputMaterial")
    emission=nodes.new("ShaderNodeEmission")
    uv=nodes.new("ShaderNodeUVMap")
    uv.uv_map=UV_NAME
    tex=nodes.new("ShaderNodeTexImage")
    tex.image=load_image(color_path,False)
    tex.extension="REPEAT"
    tex.projection="FLAT"

    color_boost=nodes.new("ShaderNodeHueSaturation")
    # Authored MIT stained-glass correction from World-GAN/CyclesMineways:
    # saturation=2, value=8 because transparent stained-glass RGBA renders super dark.
    color_boost.inputs["Saturation"].default_value=2.0
    color_boost.inputs["Value"].default_value=8.0

    links.new(uv.outputs["UV"],tex.inputs["Vector"])
    links.new(tex.outputs["Color"],color_boost.inputs["Color"])
    links.new(color_boost.outputs["Color"],emission.inputs["Color"])
    # Keep Blender's Emission node default strength; brightness correction comes
    # from the authored stained-glass color transform above, not a tuned multiplier.
    emission_strength=float(emission.inputs["Strength"].default_value)
    links.new(emission.outputs["Emission"],out.inputs["Surface"])

    mesh.materials.clear()
    mesh.materials.append(mat)
    for p in mesh.polygons:
        p.material_index=0

    backing=bpy.data.objects.new("SANCTUM_V2_WINDOW_EMISSIVE_BACKING",mesh)
    bpy.context.scene.collection.objects.link(backing)

    return backing,{
        "source_material":source_material_name,
        "derived_window_faces":kept_faces,
        "offset_m":physical_offset_m,
        "offset_rule":"one Poly Haven stone 4K source texel",
        "emission_strength":emission_strength,
        "emission_strength_rule":"Blender Emission node default, not tuned",
        "authored_color_boost":{
            "source_repo":"Mawiszus/World-GAN",
            "source_file":"minecraft/blender_scripts/CyclesMineways.py",
            "license":"MIT",
            "shader":"Stained_Glass_Shader",
            "saturation":2.0,
            "value":8.0,
            "reason":"upstream shader compensates stained-glass RGBA becoming super dark in transparency",
        },
        "texture":"same OpenGameArt stained-glass color map as visible glass",
    }

def object_world_bounds(objects):
    pts=[]
    for o in objects:
        if o.type!="MESH":
            continue
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    if not pts:
        raise SystemExit("No mesh bounds for imported CC0 props")
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def axis_vector(index,sign=1.0):
    v=[0.0,0.0,0.0]
    v[index]=float(sign)
    return Vector(v)

def object_center_world(o):
    pts=[o.matrix_world @ Vector(c) for c in o.bound_box]
    return sum(pts,Vector())/len(pts)

def authored_world_matrix(o,cache=None):
    # Reconstruct the authored transform from stored object transforms instead of
    # trusting matrix_world immediately after library-appending a Scene. In
    # Blender background mode the appended Scene can have stale matrix_world
    # values until that Scene is evaluated by a view layer.
    if cache is None:
        cache={}
    key=o.as_pointer()
    if key in cache:
        return cache[key].copy()
    if o.parent is None:
        m=o.matrix_basis.copy()
    else:
        m=authored_world_matrix(o.parent,cache) @ o.matrix_parent_inverse @ o.matrix_basis
    cache[key]=m.copy()
    return m

def transformed_bounds(objects,matrix):
    pts=[]
    for o in objects:
        if o.type!="MESH":
            continue
        for c in o.bound_box:
            pts.append(matrix @ (o.matrix_world @ Vector(c)))
    if not pts:
        raise SystemExit("No transformed mesh bounds")
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def append_and_fit_cc0_interior_props(scene,target_min,target_max):
    if not INTERIOR_SOURCE.is_file():
        raise SystemExit(f"Missing CC0 interior source: {INTERIOR_SOURCE}")

    prefixes=("pew","candle","altar","Cross","bible","pipe")

    # Load the authored source Scene, not isolated mesh datablocks. The source
    # uses scene/parent transforms for placement; isolated object append loses
    # that layout. We read the real source matrix_world, then copy only approved
    # mesh props into Sanctum and bake their authored world transform.
    with bpy.data.libraries.load(str(INTERIOR_SOURCE),link=False) as (data_from,data_to):
        if not data_from.scenes:
            raise SystemExit("CC0 source contains no scenes")
        data_to.scenes=list(data_from.scenes)

    source_scenes=[s for s in data_to.scenes if s is not None]
    if not source_scenes:
        raise SystemExit("Could not load CC0 source scene")
    source_scene=source_scenes[0]

    source_props=[
        o for o in source_scene.objects
        if o.type=="MESH" and any(o.name==p or o.name.startswith(p+".") for p in prefixes)
    ]
    if not source_props:
        raise SystemExit("No approved interior prop objects found in CC0 source scene")

    props=[]
    authored_cache={}
    for src in source_props:
        o=src.copy()
        if src.data is not None:
            o.data=src.data.copy()
        authored_world=authored_world_matrix(src,authored_cache)
        o.parent=None
        o.matrix_parent_inverse=Matrix.Identity(4)
        o.matrix_world=authored_world
        scene.collection.objects.link(o)
        props.append(o)

    pews=[o for o in props if o.name=="pew" or o.name.startswith("pew.")]
    if len(pews)<2:
        raise SystemExit(f"Need multiple pews to infer source axes, got {len(pews)}")

    pew_centers=[object_center_world(o) for o in pews]
    pew_spans=[
        max(c[i] for c in pew_centers)-min(c[i] for c in pew_centers)
        for i in range(3)
    ]

    # Data-derived source up axis: all pews sit on one floor, so their centers
    # vary least along the source's vertical axis.
    source_up_index=min(range(3),key=lambda i:pew_spans[i])
    horizontal=[i for i in range(3) if i!=source_up_index]

    pew_mean=sum(pew_centers,Vector())/len(pew_centers)
    decor=[o for o in props if o not in pews and (o.name.startswith("candle") or o.name.startswith("Cross") or o.name=="altar" or o.name.startswith("altar."))]
    decor_mean=(sum((object_center_world(o) for o in decor),Vector())/len(decor)) if decor else pew_mean

    # Choose up sign from authored decor placement relative to pew floor.
    up_sign=1.0 if decor_mean[source_up_index]>=pew_mean[source_up_index] else -1.0

    # The source pew grid spans X and Y almost equally, so "largest pew span"
    # is ambiguous and previously picked the wrong nave axis. Use the authored
    # altar displacement from the pew centroid instead: the altar sits at the
    # longitudinal end of the nave and therefore identifies both the long axis
    # and its sign directly from source-scene placement.
    altar=next((o for o in props if o.name=="altar" or o.name.startswith("altar.")),None)
    if altar is None:
        raise SystemExit("CC0 source has no altar prop for nave-axis inference")
    altar_center=object_center_world(altar)
    altar_delta=altar_center-pew_mean
    source_long_index=max(horizontal,key=lambda i:abs(altar_delta[i]))
    if abs(altar_delta[source_long_index])<=1e-6:
        raise SystemExit(f"Ambiguous altar displacement for nave axis: {list(altar_delta)}")
    long_sign=1.0 if altar_delta[source_long_index]>=0 else -1.0

    src_up=axis_vector(source_up_index,up_sign)
    src_long=axis_vector(source_long_index,long_sign)
    src_cross=src_long.cross(src_up).normalized()

    tgt_size=target_max-target_min
    target_long_index=0 if tgt_size.x>=tgt_size.y else 1
    dst_up=Vector((0,0,1))
    dst_long=Vector((1,0,0)) if target_long_index==0 else Vector((0,1,0))
    dst_cross=dst_long.cross(dst_up).normalized()

    # Orthonormal basis mapping: source authored axes -> cathedral Z-up axes.
    src_basis=Matrix((src_cross,src_long,src_up)).transposed()
    dst_basis=Matrix((dst_cross,dst_long,dst_up)).transposed()
    rot3=dst_basis @ src_basis.transposed()
    rot=rot3.to_4x4()

    src_min,src_max=object_world_bounds(props)
    oriented_min,oriented_max=transformed_bounds(props,rot)
    oriented_size=oriented_max-oriented_min

    dims=[oriented_size.x,oriented_size.y,oriented_size.z]
    targets=[tgt_size.x,tgt_size.y,tgt_size.z]
    ratios=[targets[i]/dims[i] for i in range(3) if dims[i]>0]
    if len(ratios)!=3:
        raise SystemExit(f"Invalid oriented CC0 prop bounds: {list(oriented_size)}")
    uniform_scale=min(ratios)

    oriented_anchor=Vector((
        (oriented_min.x+oriented_max.x)*0.5,
        (oriented_min.y+oriented_max.y)*0.5,
        oriented_min.z,
    ))
    target_anchor=Vector((
        (target_min.x+target_max.x)*0.5,
        (target_min.y+target_max.y)*0.5,
        target_min.z,
    ))

    transform=(
        Matrix.Translation(target_anchor)
        @ Matrix.Scale(uniform_scale,4)
        @ Matrix.Translation(-oriented_anchor)
        @ rot
    )
    for o in props:
        o.matrix_world=transform @ o.matrix_world

    fitted_min,fitted_max=object_world_bounds(props)
    fitted_size=fitted_max-fitted_min

    # Hard gate: corrected import must fit the cathedral bounds in all 3 axes.
    eps=1e-4
    if fitted_size.x>tgt_size.x+eps or fitted_size.y>tgt_size.y+eps or fitted_size.z>tgt_size.z+eps:
        raise SystemExit(f"CC0 props overflow cathedral after corrected fit: fitted={list(fitted_size)} target={list(tgt_size)}")

    axis_names=("X","Y","Z")
    return props,{
        "source":"OpenGameArt Church",
        "author":"stereoscopic",
        "license":"CC0",
        "source_url":"https://opengameart.org/content/church-0",
        "object_count":len(props),
        "objects":[o.name for o in props],
        "source_bounds":{"min":list(src_min),"max":list(src_max),"size":list(src_max-src_min)},
        "target_bounds":{"min":list(target_min),"max":list(target_max),"size":list(tgt_size)},
        "transform_source":"authored CC0 source object hierarchy reconstructed from matrix_basis + matrix_parent_inverse, then baked onto selected prop copies",
        "source_scene":source_scene.name,
        "axis_inference":{
            "pew_count":len(pews),
            "pew_center_spans":pew_spans,
            "source_up_axis":axis_names[source_up_index],
            "source_up_sign":up_sign,
            "source_long_axis":axis_names[source_long_index],
            "source_long_sign":long_sign,
            "target_long_axis":axis_names[target_long_index],
            "altar_minus_pew_mean":list(altar_delta),
            "rule":"authored source-scene prop centers: pew minimum spread => source up; altar displacement from pew centroid => nave long axis and sign; decor selects up sign",
        },
        "oriented_bounds":{"min":list(oriented_min),"max":list(oriented_max),"size":list(oriented_size)},
        "uniform_scale":uniform_scale,
        "scale_rule":"minimum X/Y/Z fit ratio after data-derived axis correction",
        "placement_rule":"preserve authored source object hierarchy transforms independent of appended-scene matrix_world evaluation; infer source up from pew floor spread and source long axis/sign from authored altar displacement; map to cathedral Z-up/long axis; fit all three dimensions; center XY; align floor min-Z",
        "fitted_bounds":{"min":list(fitted_min),"max":list(fitted_max),"size":list(fitted_size)},
    }

def render(scene,cam,name,pos,look):
    cam.location=Vector(pos)
    point(cam,look)
    scene.render.filepath=str(OUT/name)
    bpy.ops.render.render(write_still=True)

scene=bpy.context.scene
obj=bpy.data.objects.get(TARGET)
if obj is None:
    raise SystemExit(f"Missing {TARGET!r}")

manifest=load_manifest()
mats={m.name:m for m in bpy.data.materials}
missing=sorted(REQUIRED-set(mats))
if missing:
    raise SystemExit(f"Missing materials: {missing}")

stone_tile=tile_meters(manifest,"stone_wall_04")
roof_tile=tile_meters(manifest,"roof_slates_03")
resolution=4096

for name in ("GroundFloorWalls","BeamFakeTextureVertical"):
    build_relief_box_material(
        mats[name],
        ASSETS/"stone_wall_04"/"diffuse.png",
        ASSETS/"stone_wall_04"/"rough.png",
        ASSETS/"stone_wall_04"/"displacement.png",
        stone_tile,
        resolution,
    )
build_relief_box_material(
    mats["FakeRoof"],
    ASSETS/"roof_slates_03"/"diffuse.png",
    ASSETS/"roof_slates_03"/"rough.png",
    ASSETS/"roof_slates_03"/"displacement.png",
    roof_tile,
    resolution,
)
sg=manifest["stained_glass"]
glass_shader_report=apply_stained_glass_authored_shader(
    mats["RoundWindwos"],
    ASSETS/"stained_glass"/"color.jpg",
    ASSETS/"stained_glass"/"normal.jpg",
    sg["source_dimensions"],
)

st=evaluated_stats(obj)
if UV_NAME not in st["uv_layers"]:
    raise SystemExit(f"Expected UV layer {UV_NAME!r}: {st['uv_layers']}")

center=Vector(st["center"])
mn=Vector(st["min"])
size=Vector(st["size"])
ext=max(size.x,size.y,size.z)

scene.render.engine="BLENDER_EEVEE"
raytrace_report=enable_raytraced_glass(scene,mats["RoundWindwos"])
scene.render.image_settings.media_type="IMAGE"
scene.render.image_settings.file_format="PNG"
scene.render.resolution_x=1280
scene.render.resolution_y=800
scene.render.resolution_percentage=100

ensure_world(scene)
cam=ensure_cam(scene)
lights=ensure_lights(scene,center,size)
backlights,backlight_report=ensure_window_backlights(scene,center,size)
backing_offset_m=stone_tile/float(resolution)
window_backing,window_backing_report=build_emissive_window_backing(
    obj,
    "RoundWindwos",
    ASSETS/"stained_glass"/"color.jpg",
    backing_offset_m,
)
cc0_props,cc0_props_report=append_and_fit_cc0_interior_props(
    scene,
    Vector(st["min"]),
    Vector(st["max"]),
)
cc0_props_report["cross_scale_normalization"]=normalize_cross_scale(cc0_props)
cc0_props_report["material_upgrade"]=upgrade_cc0_interior_materials(
    cc0_props,
    manifest,
    resolution,
)
cc0_props_report["legacy_shader_restore"]=restore_authored_legacy_prop_shaders(cc0_props)
floor_overlay,floor_overlay_report=build_cathedral_floor_overlay(
    obj,
    manifest,
    resolution,
    mn.z,
)
all_lights=[*lights,*backlights]
visible=[obj,cam,window_backing,floor_overlay,*cc0_props,*all_lights]
for o in scene.objects:
    if hasattr(o,"hide_render"):
        o.hide_render=o not in visible
obj.hide_render=False
cam.hide_render=False

interior_z=mn.z+max(1.7,size.z*0.08)
views=[
    ("01-interior-center-forward.png",Vector((center.x,center.y-size.y*0.22,interior_z)),Vector((center.x,center.y+size.y*0.22,interior_z+1.0))),
    ("02-interior-center-reverse.png",Vector((center.x,center.y+size.y*0.22,interior_z)),Vector((center.x,center.y-size.y*0.22,interior_z+1.0))),
    ("03-interior-left-forward.png",Vector((center.x-size.x*0.18,center.y-size.y*0.18,interior_z)),Vector((center.x,center.y+size.y*0.18,interior_z+0.8))),
    ("04-interior-right-forward.png",Vector((center.x+size.x*0.18,center.y-size.y*0.18,interior_z)),Vector((center.x,center.y+size.y*0.18,interior_z+0.8))),
    ("05-interior-altar-side.png",Vector((center.x-size.x*0.20,center.y+size.y*0.12,interior_z+0.3)),Vector((center.x,center.y+size.y*0.24,interior_z+0.7))),
    ("06-interior-high-overview.png",Vector((center.x,center.y+size.y*0.20,interior_z+size.z*0.10)),Vector((center.x,center.y-size.y*0.12,interior_z+0.35))),
]
for name,pos,look in views:
    render(scene,cam,name,pos,look)

report={
    "source_object":obj.name,
    "geometry_nodes":[m.node_group.name for m in obj.modifiers if m.type=="NODES" and m.node_group],
    "stats":st,
    "mapping":{
        "stone":"BOX/Object + Poly Haven physical dimensions",
        "roof":"BOX/Object + Poly Haven physical dimensions",
        "stained_glass":"existing UVMap + OpenGameArt seamless maps + external CC0 Crown Glass for windows shader",
    },
    "relief":{
        "source":"Poly Haven 4K displacement maps",
        "method":"Bump from displacement",
        "distance_rule":"one source texel in world units",
        "stone_bump_distance_m":stone_tile/resolution,
        "roof_bump_distance_m":roof_tile/resolution,
    },
    "cc0_interior_props":cc0_props_report,
    "floor_upgrade":floor_overlay_report,
    "stained_glass":{
        "source":"OpenGameArt Repeating Mini Windows - Stained Glass - Seamless texture with normalmap",
        "author":"Keith333",
        "license":"CC-BY 3.0",
        "source_dimensions":sg["source_dimensions"],
        "uses_authored_normal_map":True,
        "shader":glass_shader_report,
        "raytracing":raytrace_report,
        "backlighting":backlight_report,
        "emissive_backing":window_backing_report,
    },
        "renders":[v[0] for v in views],
}
(OUT/"relief-glass-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("SANCTUM_V2_CC0_INTERIOR_IMPORT_OK")
print(json.dumps(report,indent=2))

# SEAMLESS_CC0_SOURCE_GATE_V2

# SEAMLESS_CC0_SOURCE_GATE_V3
