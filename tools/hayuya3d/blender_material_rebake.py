#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


SUPPORTED_CHANNELS={"normal","occlusion"}


def parse_args():
    argv=sys.argv
    argv=argv[argv.index("--")+1:] if "--" in argv else []
    p=argparse.ArgumentParser(description="HAYUYA topology-dependent material rebake.")
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--target",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--channel",action="append",default=[])
    p.add_argument("--size",type=int,default=2048)
    return p.parse_args(argv)


def import_glb(path:Path):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    return [o for o in bpy.data.objects if o not in before]


def world_bounds(objects):
    pts=[]
    for obj in objects:
        if obj.type!="MESH":
            continue
        pts.extend(obj.matrix_world @ Vector(c) for c in obj.bound_box)
    if not pts:
        raise RuntimeError("no_mesh_bounds")
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx


def select_only(objects,active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=active or (objects[-1] if objects else None)


def join_target(meshes):
    if not meshes:
        raise RuntimeError("target_has_no_mesh")
    if len(meshes)==1:
        return meshes[0]
    select_only(meshes,meshes[0])
    bpy.ops.object.join()
    return bpy.context.object


def target_materials(target):
    if not target.data.uv_layers:
        raise RuntimeError("target_has_no_uv")
    target.data.uv_layers.active_index=0

    if not target.material_slots:
        material=bpy.data.materials.new("HAYUYA_RebakeMaterial")
        material.use_nodes=True
        target.data.materials.append(material)

    materials=[]
    seen=set()
    for slot in target.material_slots:
        material=slot.material
        if material is None:
            material=bpy.data.materials.new("HAYUYA_RebakeMaterial")
            material.use_nodes=True
            slot.material=material
        material.use_nodes=True
        if material.as_pointer() not in seen:
            seen.add(material.as_pointer())
            materials.append(material)
    return materials


def active_image_node(material,image,name):
    nodes=material.node_tree.nodes
    for node in nodes:
        node.select=False
    tex=nodes.new("ShaderNodeTexImage")
    tex.name=name
    tex.label=name.replace("_"," ")
    tex.image=image
    tex.interpolation="Linear"
    tex.select=True
    nodes.active=tex
    return tex


def principled(material):
    nodes=material.node_tree.nodes
    node=next((n for n in nodes if n.type=="BSDF_PRINCIPLED"),None)
    if node is None:
        node=nodes.new("ShaderNodeBsdfPrincipled")
    return node


def prepare_normal_bake(materials,image):
    for material in materials:
        active_image_node(material,image,"HAYUYA_NORMAL_BAKE_TARGET")


def configure_normal(materials,image):
    for material in materials:
        nodes=material.node_tree.nodes
        links=material.node_tree.links
        tex=next(
            (
                node for node in nodes
                if node.type=="TEX_IMAGE" and node.image is image
                and node.name=="HAYUYA_NORMAL_BAKE_TARGET"
            ),
            None,
        )
        if tex is None:
            tex=active_image_node(material,image,"HAYUYA_NORMAL_BAKE_TARGET")
        tex.name="HAYUYA_REBAKED_NORMAL"
        tex.label="HAYUYA Rebaked Normal"
        normal=nodes.new("ShaderNodeNormalMap")
        normal.name="HAYUYA_REBAKED_NORMAL_MAP"
        normal.space="TANGENT"
        links.new(tex.outputs["Color"],normal.inputs["Color"])
        links.new(normal.outputs["Normal"],principled(material).inputs["Normal"])


def gltf_output_group():
    name="glTF Material Output"
    group=bpy.data.node_groups.get(name)
    if group is None:
        group=bpy.data.node_groups.new(name,"ShaderNodeTree")
        if hasattr(group,"interface"):
            group.interface.new_socket(
                name="Occlusion",
                in_out="INPUT",
                socket_type="NodeSocketFloat",
            )
        else:
            group.inputs.new("NodeSocketFloat","Occlusion")
    return group


def configure_ao_emission_bake(materials,image,distance):
    """Temporarily route explicit AO shader output through emission for baking."""
    restore=[]
    for material in materials:
        nodes=material.node_tree.nodes
        links=material.node_tree.links
        tex=active_image_node(material,image,"HAYUYA_REBAKED_OCCLUSION")

        output=next((n for n in nodes if n.type=="OUTPUT_MATERIAL" and n.is_active_output),None)
        if output is None:
            output=next((n for n in nodes if n.type=="OUTPUT_MATERIAL"),None)
        if output is None:
            output=nodes.new("ShaderNodeOutputMaterial")

        old_surface=None
        if output.inputs.get("Surface") and output.inputs["Surface"].is_linked:
            old_surface=output.inputs["Surface"].links[0].from_socket
            links.remove(output.inputs["Surface"].links[0])

        ao=nodes.new("ShaderNodeAmbientOcclusion")
        ao.name="HAYUYA_AO_BAKE"
        ao.inputs["Distance"].default_value=max(1e-6,float(distance))
        try:
            ao.samples=32
        except Exception:
            pass
        try:
            ao.only_local=True
        except Exception:
            pass

        emission=nodes.new("ShaderNodeEmission")
        emission.name="HAYUYA_AO_EMISSION_BAKE"
        links.new(ao.outputs["AO"],emission.inputs["Color"])
        links.new(emission.outputs["Emission"],output.inputs["Surface"])
        restore.append((material,output,old_surface,ao,emission,tex))
    return restore


def restore_after_ao_bake(restore):
    for material,output,old_surface,ao,emission,tex in restore:
        nodes=material.node_tree.nodes
        links=material.node_tree.links
        if output.inputs.get("Surface") and output.inputs["Surface"].is_linked:
            for link in list(output.inputs["Surface"].links):
                links.remove(link)
        if old_surface is not None:
            links.new(old_surface,output.inputs["Surface"])
        # Keep the image node; configure_occlusion will attach it to glTF output.
        # Blender 4 bpy_prop_collection.__contains__ accepts names, not node objects.
        if nodes.get(ao.name) is ao:
            nodes.remove(ao)
        if nodes.get(emission.name) is emission:
            nodes.remove(emission)


def _hemisphere_directions(normal:Vector,count:int=16):
    """Deterministic cosine-weighted-ish hemisphere directions around a normal."""
    n=normal.normalized()
    helper=Vector((0.0,0.0,1.0)) if abs(n.z)<0.95 else Vector((0.0,1.0,0.0))
    tangent=n.cross(helper).normalized()
    bitangent=n.cross(tangent).normalized()
    golden=2.399963229728653
    directions=[]
    for i in range(count):
        u=(i+0.5)/count
        z=max(0.08,u)
        radius=max(0.0,1.0-z*z)**0.5
        angle=golden*i
        local=Vector((radius*__import__("math").cos(angle),radius*__import__("math").sin(angle),z))
        world=(tangent*local.x + bitangent*local.y + n*local.z).normalized()
        directions.append(world)
    return directions


def geometric_vertex_ao(target,diag:float,ray_count:int=16):
    """Compute topology AO directly from the runtime mesh using a BVH."""
    mesh=target.data
    matrix=target.matrix_world
    normal_matrix=matrix.to_3x3()
    world_vertices=[matrix @ vertex.co for vertex in mesh.vertices]
    polygons=[tuple(poly.vertices) for poly in mesh.polygons]
    bvh=BVHTree.FromPolygons(world_vertices,polygons,all_triangles=False,epsilon=0.0)

    max_distance=max(1e-5,float(diag)*0.35)
    epsilon=max(1e-6,float(diag)*1e-5)
    values=[]
    for vertex in mesh.vertices:
        position=matrix @ vertex.co
        normal=(normal_matrix @ vertex.normal).normalized()
        origin=position + normal*epsilon
        hits=0
        for direction in _hemisphere_directions(normal,ray_count):
            location,hit_normal,index,distance=bvh.ray_cast(
                origin,direction,max_distance
            )
            if index is not None:
                hits+=1
        values.append(max(0.0,min(1.0,1.0-hits/max(1,ray_count))))
    return values


def rasterize_vertex_ao_to_image(target,values,image):
    """Rasterize interpolated per-vertex AO directly into the active UV atlas.

    This intentionally bypasses Blender's bake operators. On Blender 4.0 headless
    those operators can return an all-zero image even when the BVH AO values are
    demonstrably non-uniform.
    """
    from array import array

    mesh=target.data
    uv_layer=mesh.uv_layers.active
    if uv_layer is None:
        raise RuntimeError("target_has_no_active_uv_for_ao_raster")
    width,height=image.size
    if width<2 or height<2:
        raise RuntimeError("invalid_ao_image_size")

    pixel_count=width*height
    # AO defaults to fully unoccluded white. UV overlaps use the darker value,
    # which is conservative and prevents one surface from hiding another's AO.
    grayscale=array("f",[1.0])*pixel_count

    mesh.calc_loop_triangles()
    painted=0
    for tri in mesh.loop_triangles:
        loop_ids=tri.loops
        vertex_ids=tri.vertices
        uvs=[uv_layer.data[int(loop_id)].uv.copy() for loop_id in loop_ids]
        # Production UV atlases should live in 0..1. Clamp tiny numerical drift
        # while still allowing valid boundary coordinates.
        pts=[
            (
                max(0.0,min(1.0,float(uv.x)))*(width-1),
                max(0.0,min(1.0,float(uv.y)))*(height-1),
            )
            for uv in uvs
        ]
        (x0,y0),(x1,y1),(x2,y2)=pts
        denom=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(denom)<1e-12:
            continue

        min_x=max(0,int(__import__("math").floor(min(x0,x1,x2))))
        max_x=min(width-1,int(__import__("math").ceil(max(x0,x1,x2))))
        min_y=max(0,int(__import__("math").floor(min(y0,y1,y2))))
        max_y=min(height-1,int(__import__("math").ceil(max(y0,y1,y2))))
        v0=float(values[int(vertex_ids[0])])
        v1=float(values[int(vertex_ids[1])])
        v2=float(values[int(vertex_ids[2])])

        for py in range(min_y,max_y+1):
            sy=py+0.5
            row=py*width
            for px in range(min_x,max_x+1):
                sx=px+0.5
                w0=((y1-y2)*(sx-x2)+(x2-x1)*(sy-y2))/denom
                w1=((y2-y0)*(sx-x2)+(x0-x2)*(sy-y2))/denom
                w2=1.0-w0-w1
                if w0>=-1e-6 and w1>=-1e-6 and w2>=-1e-6:
                    value=max(0.0,min(1.0,w0*v0+w1*v1+w2*v2))
                    index=row+px
                    if value<grayscale[index]:
                        grayscale[index]=value
                    painted+=1

    if painted<=0:
        raise RuntimeError("ao_uv_raster_painted_no_pixels")

    rgba=array("f",[1.0])*(pixel_count*4)
    for index,value in enumerate(grayscale):
        offset=index*4
        rgba[offset]=value
        rgba[offset+1]=value
        rgba[offset+2]=value
        rgba[offset+3]=1.0
    image.pixels.foreach_set(rgba)
    image.update()
    return {
        "painted_samples":painted,
        "triangle_count":len(mesh.loop_triangles),
        "width":width,
        "height":height,
    }


def prepare_geometric_ao_attribute(target,values):
    """Store per-vertex AO as a POINT color attribute for interpolation in bake."""
    mesh=target.data
    name="HAYUYA_AO_VERTEX"
    if hasattr(mesh,"color_attributes"):
        existing=mesh.color_attributes.get(name)
        if existing is not None:
            mesh.color_attributes.remove(existing)
        attr=mesh.color_attributes.new(
            name=name,
            type="FLOAT_COLOR",
            domain="POINT",
        )
        for index,value in enumerate(values):
            attr.data[index].color=(value,value,value,1.0)
        return name
    raise RuntimeError("mesh_color_attributes_unavailable")


def configure_attribute_emission_bake(materials,image,attribute_name):
    """Bake an interpolated vertex AO attribute through emission."""
    restore=[]
    for material in materials:
        nodes=material.node_tree.nodes
        links=material.node_tree.links
        tex=active_image_node(material,image,"HAYUYA_GEOMETRIC_AO_BAKE_TARGET")
        output=next((n for n in nodes if n.type=="OUTPUT_MATERIAL" and n.is_active_output),None)
        if output is None:
            output=next((n for n in nodes if n.type=="OUTPUT_MATERIAL"),None)
        if output is None:
            output=nodes.new("ShaderNodeOutputMaterial")

        old_surface=None
        if output.inputs.get("Surface") and output.inputs["Surface"].is_linked:
            old_surface=output.inputs["Surface"].links[0].from_socket
            links.remove(output.inputs["Surface"].links[0])

        attr=nodes.new("ShaderNodeVertexColor")
        attr.name="HAYUYA_GEOMETRIC_AO_ATTRIBUTE"
        attr.layer_name=attribute_name
        emission=nodes.new("ShaderNodeEmission")
        emission.name="HAYUYA_GEOMETRIC_AO_EMISSION"
        links.new(attr.outputs["Color"],emission.inputs["Color"])
        links.new(emission.outputs["Emission"],output.inputs["Surface"])
        restore.append((material,output,old_surface,attr,emission,tex))
    return restore


def restore_after_attribute_bake(restore):
    for material,output,old_surface,attr,emission,tex in restore:
        nodes=material.node_tree.nodes
        links=material.node_tree.links
        if output.inputs.get("Surface") and output.inputs["Surface"].is_linked:
            for link in list(output.inputs["Surface"].links):
                links.remove(link)
        if old_surface is not None:
            links.new(old_surface,output.inputs["Surface"])
        if nodes.get(attr.name) is attr:
            nodes.remove(attr)
        if nodes.get(emission.name) is emission:
            nodes.remove(emission)


def configure_occlusion(materials,image):
    group=gltf_output_group()
    for material in materials:
        nodes=material.node_tree.nodes
        links=material.node_tree.links
        tex=active_image_node(material,image,"HAYUYA_REBAKED_OCCLUSION")
        output=next(
            (
                n for n in nodes
                if n.type=="GROUP" and n.node_tree is not None
                and n.node_tree.name=="glTF Material Output"
            ),
            None,
        )
        if output is None:
            output=nodes.new("ShaderNodeGroup")
            output.name="HAYUYA_GLTF_MATERIAL_OUTPUT"
            output.node_tree=group
        socket=output.inputs.get("Occlusion")
        if socket is None:
            raise RuntimeError("gltf_occlusion_socket_missing")
        links.new(tex.outputs["Color"],socket)


def image_signal_stats(image,channel_index=0,max_samples=65536):
    """Sample a baked image without materializing a multi-4K pixel list."""
    pixels=image.pixels
    pixel_count=max(0,len(pixels)//4)
    if pixel_count<=0:
        return {"samples":0,"min":None,"max":None,"mean":None,"stddev":None}
    stride=max(1,pixel_count//max_samples)
    count=0
    mean=0.0
    m2=0.0
    mn=float("inf")
    mx=float("-inf")
    for pixel_index in range(0,pixel_count,stride):
        value=float(pixels[pixel_index*4+channel_index])
        count+=1
        delta=value-mean
        mean+=delta/count
        m2+=delta*(value-mean)
        mn=min(mn,value)
        mx=max(mx,value)
    variance=m2/max(1,count-1)
    return {
        "samples":count,
        "min":round(mn,6),
        "max":round(mx,6),
        "mean":round(mean,6),
        "stddev":round(variance**0.5,6),
    }


def image_rgb_signal_stats(image,max_samples=65536):
    channels={
        name:image_signal_stats(image,index,max_samples)
        for index,name in enumerate(("r","g","b"))
    }
    stddevs=[
        float(stats["stddev"])
        for stats in channels.values()
        if stats.get("stddev") is not None
    ]
    return {
        "channels":channels,
        "combined_stddev":round(sum(stddevs)/len(stddevs),6) if stddevs else None,
        "combined_range":round(
            sum(
                max(0.0,float(stats["max"])-float(stats["min"]))
                for stats in channels.values()
                if stats.get("max") is not None and stats.get("min") is not None
            )/max(1,len(channels)),
            6,
        ),
    }


def new_noncolor_image(name,size,fill):
    image=bpy.data.images.new(
        name,
        width=size,
        height=size,
        alpha=False,
        float_buffer=False,
    )
    image.generated_color=fill
    try:
        image.colorspace_settings.name="Non-Color"
    except Exception:
        pass
    return image


def main():
    a=parse_args()
    channels=sorted(set(a.channel or ["normal"]))
    unknown=sorted(set(channels)-SUPPORTED_CHANNELS)
    if unknown:
        raise RuntimeError("unsupported_channels:"+",".join(unknown))
    if a.size<64 or a.size>8192:
        raise RuntimeError(f"invalid_bake_size:{a.size}")

    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.report.parent.mkdir(parents=True,exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    source_objects=import_glb(a.source)
    source_meshes=[o for o in source_objects if o.type=="MESH"]
    if not source_meshes:
        raise RuntimeError("source_has_no_mesh")

    target_objects=import_glb(a.target)
    target_meshes=[o for o in target_objects if o.type=="MESH"]
    target=join_target(target_meshes)
    materials=target_materials(target)

    mn,mx=world_bounds([*source_meshes,target])
    diag=max((mx-mn).length,1e-6)

    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.render.bake.use_clear=True
    if scene.world is None:
        scene.world=bpy.data.worlds.new("HAYUYA_RebakeWorld")
    light_settings=getattr(scene.world,"light_settings",None)
    if light_settings is not None:
        if hasattr(light_settings,"use_ambient_occlusion"):
            light_settings.use_ambient_occlusion=True
        if hasattr(light_settings,"ao_factor"):
            light_settings.ao_factor=1.0
        if hasattr(light_settings,"distance"):
            light_settings.distance=max(1e-6,diag*0.35)
    scene.render.bake.margin=max(4,min(32,a.size//128))
    scene.render.bake.cage_extrusion=diag*0.003
    scene.render.bake.max_ray_distance=diag*0.04

    resolved=[]
    images={}

    if "normal" in channels:
        normal_image=new_noncolor_image(
            "HAYUYA_Rebaked_Normal",a.size,(0.5,0.5,1.0,1.0)
        )
        prepare_normal_bake(materials,normal_image)
        scene.render.bake.use_selected_to_active=True
        scene.render.bake.normal_space="TANGENT"
        select_only([*source_meshes,target],target)
        bpy.ops.object.bake(type="NORMAL")
        configure_normal(materials,normal_image)
        normal_stats=image_rgb_signal_stats(normal_image)
        normal_image.pack()
        images["normal"]={"name":normal_image.name,"signal":normal_stats}
        print("HAYUYA_REBAKE_SIGNAL normal "+json.dumps(normal_stats,sort_keys=True))
        resolved.append("normal")

    if "occlusion" in channels:
        # AO is topology-dependent runtime shading. The high-poly/source meshes
        # are only normal-bake evidence and must not contaminate target AO.
        for source_obj in source_meshes:
            source_obj.hide_render=True
        scene.render.bake.use_selected_to_active=False
        if hasattr(scene.render.bake,"target"):
            scene.render.bake.target="IMAGE_TEXTURES"

        ao_attempts=[]
        ao_image=None
        ao_method=None

        # Attempt 1: native Cycles AO bake with explicit World AO settings.
        native_image=new_noncolor_image(
            "HAYUYA_Rebaked_Occlusion_cycles_native_ao_target_only_v6",
            a.size,
            (1.0,1.0,1.0,1.0),
        )
        for material in materials:
            active_image_node(
                material,
                native_image,
                "HAYUYA_AO_BAKE_TARGET_cycles_native_ao_target_only_v6",
            )
        select_only([target],target)
        bpy.ops.object.bake(type="AO")
        native_stats=image_signal_stats(native_image,0)
        native_range=(
            float(native_stats["max"])-float(native_stats["min"])
            if native_stats.get("max") is not None
            and native_stats.get("min") is not None
            else 0.0
        )
        native_attempt={
            "method":"cycles_native_ao_target_only_v6",
            "signal":native_stats,
            "signal_range":round(native_range,6),
            "signal_valid":native_range>1e-4,
        }
        ao_attempts.append(native_attempt)
        print(
            "HAYUYA_REBAKE_SIGNAL occlusion_attempt "
            + json.dumps(native_attempt,sort_keys=True)
        )
        if native_attempt["signal_valid"]:
            ao_image=native_image
            ao_method=native_attempt["method"]

        # Attempt 2: explicit AO shader -> emission, target-local only.
        if ao_image is None:
            shader_image=new_noncolor_image(
                "HAYUYA_Rebaked_Occlusion_shader_emit_v6",
                a.size,
                (1.0,1.0,1.0,1.0),
            )
            ao_restore=configure_ao_emission_bake(
                materials,
                shader_image,
                distance=max(1e-6,diag*0.35),
            )
            select_only([target],target)
            bpy.ops.object.bake(type="EMIT")
            restore_after_ao_bake(ao_restore)
            shader_stats=image_signal_stats(shader_image,0)
            shader_range=(
                float(shader_stats["max"])-float(shader_stats["min"])
                if shader_stats.get("max") is not None
                and shader_stats.get("min") is not None
                else 0.0
            )
            shader_attempt={
                "method":"ao_shader_emit_target_local_v6",
                "signal":shader_stats,
                "signal_range":round(shader_range,6),
                "signal_valid":shader_range>1e-4,
                "distance":max(1e-6,diag*0.35),
            }
            ao_attempts.append(shader_attempt)
            print(
                "HAYUYA_REBAKE_SIGNAL occlusion_attempt "
                + json.dumps(shader_attempt,sort_keys=True)
            )
            if shader_attempt["signal_valid"]:
                ao_image=shader_image
                ao_method=shader_attempt["method"]

        # Attempt 3: deterministic geometry-only BVH AO. This bypasses
        # Blender 4 AO bake paths that can return all-zero images on valid meshes.
        if ao_image is None:
            # AO detail does not need to match a 4K hero albedo one-for-one.
            # Cap the deterministic raster at 2048 to keep offline GamePrep bounded
            # while preserving substantially more resolution than mobile AO needs.
            ao_raster_size=min(a.size,2048)
            geometric_image=new_noncolor_image(
                "HAYUYA_Rebaked_Occlusion_geometric_bvh_uv_v8",
                ao_raster_size,
                (1.0,1.0,1.0,1.0),
            )
            ao_values=geometric_vertex_ao(target,diag,ray_count=32)
            raster_info=rasterize_vertex_ao_to_image(
                target,ao_values,geometric_image
            )
            geometric_stats=image_signal_stats(geometric_image,0)
            geometric_range=(
                float(geometric_stats["max"])-float(geometric_stats["min"])
                if geometric_stats.get("max") is not None
                and geometric_stats.get("min") is not None
                else 0.0
            )
            vertex_range=(
                max(ao_values)-min(ao_values)
                if ao_values else 0.0
            )
            geometric_attempt={
                "method":"geometric_bvh_uv_raster_v8",
                "signal":geometric_stats,
                "signal_range":round(geometric_range,6),
                "vertex_range":round(vertex_range,6),
                "vertex_min":round(min(ao_values),6) if ao_values else None,
                "vertex_max":round(max(ao_values),6) if ao_values else None,
                "signal_valid":geometric_range>1e-4 and vertex_range>1e-4,
                "ray_count":32,
                "distance":max(1e-6,diag*0.35),
                "raster":raster_info,
            }
            ao_attempts.append(geometric_attempt)
            print(
                "HAYUYA_REBAKE_SIGNAL occlusion_attempt "
                + json.dumps(geometric_attempt,sort_keys=True)
            )
            if geometric_attempt["signal_valid"]:
                ao_image=geometric_image
                ao_method=geometric_attempt["method"]

        ao_signal_valid=ao_image is not None
        images["occlusion"]={
            "signal_valid":ao_signal_valid,
            "method":ao_method,
            "attempts":ao_attempts,
        }
        if ao_signal_valid:
            configure_occlusion(materials,ao_image)
            ao_image.pack()
            images["occlusion"]["name"]=ao_image.name
            resolved.append("occlusion")
        print(
            "HAYUYA_REBAKE_SIGNAL occlusion "
            + json.dumps(images["occlusion"],sort_keys=True)
        )

    select_only([target],target)
    bpy.ops.export_scene.gltf(
        filepath=str(a.output.resolve()),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )
    if not a.output.is_file() or a.output.read_bytes()[:4]!=b"glTF":
        raise RuntimeError("material_rebake_export_invalid")

    report={
        "schema":2,
        "source":str(a.source),
        "target":str(a.target),
        "output":str(a.output),
        "size":a.size,
        "requested_channels":channels,
        "resolved_channels":resolved,
        "images":images,
        "material_count":len(materials),
        "method":"blender_cycles_topology_material_rebake_v2",
        "cage_extrusion":diag*0.003,
        "max_ray_distance":diag*0.04,
    }
    a.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_MATERIAL_REBAKE_READY",a.output,a.size,",".join(resolved))


if __name__=="__main__":
    main()
