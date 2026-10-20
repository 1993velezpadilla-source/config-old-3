#!/usr/bin/env python3
"""Bake *existing* user Tripo GLBs into XZIEL's XZSM v2 mobile static format.
Run inside Blender (background mode), NEVER generate replacement blocky props.
Input models are already checked in under xogot/assets/environment/church/.
"""
import bpy
import json
import math
import os
import struct
from collections import defaultdict
from pathlib import Path
from mathutils import Vector

SOURCE=Path(os.environ.get("TRIPO_CHURCH_INPUT","xogot/assets/environment/church"))
OUT=Path(os.environ.get("TRIPO_CHURCH_OUTPUT","build/church_mini/nzp"))
TEXTURE_DIR=OUT/"textures/xziel/sanctum_mini"
MODEL_DIR=OUT/"models/xziel/sanctum_mini"
TEXTURE_DIR.mkdir(parents=True,exist_ok=True)
MODEL_DIR.mkdir(parents=True,exist_ok=True)
META=[]
BATCHES=[]
BATCH_LIMIT=10000
MAX_TOTAL_TRIANGLES=155000
SCALE_RATIO=0.006  # mobile ~0.6% LOD on copies; originals never modified
POSITIONS_BENCH=[(-171,y,27) for y in (-220,-80,60,200)]+[(171,y,27) for y in (-220,-80,60,200)]
PLACEMENTS={
    "bench":(POSITIONS_BENCH,(180,52,50)),
    "altar":([(0,410,67)],(135,78,94)),
}

def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

def get_image(material):
    if not material or not material.use_nodes:
        return None
    principals=[n for n in material.node_tree.nodes if n.type=="BSDF_PRINCIPLED"]
    if principals:
        socket=principals[0].inputs.get("Base Color")
        if socket and socket.is_linked:
            todo=[socket.links[0].from_node]
            seen=set()
            while todo:
                node=todo.pop()
                if node.name in seen:
                    continue
                seen.add(node.name)
                if node.type=="TEX_IMAGE" and node.image:
                    return node.image
                todo.extend(link.from_node for item in node.inputs for link in item.links)
    for node in material.node_tree.nodes:
        if node.type=="TEX_IMAGE" and node.image and ("base" in node.image.name.lower() or "color" in node.image.name.lower()):
            return node.image
    return None

def bake_basecolor(kind,idx,material):
    stem="%s_%03d"%(kind,idx)
    path=TEXTURE_DIR/(stem+".png")
    texture=get_image(material)
    if texture is not None and texture.has_data:
        try:
            texture=texture.copy()  # preserve source image datablock
            w,h=texture.size
            if w<1 or h<1:
                raise ValueError("empty image")
            maxsize=512
            factor=min(1.0,float(maxsize)/max(w,h))
            if factor<1.0:
                texture.scale(max(1,round(w*factor)),max(1,round(h*factor)))
            texture.filepath_raw=str(path.resolve())
            texture.file_format="PNG"
            texture.save()
            assert path.stat().st_size>32
            return "textures/xziel/sanctum_mini/"+stem
        except Exception as exc:
            print("TRIPO_TEXTURE_FALLBACK",kind,idx,str(exc))
    image=bpy.data.images.new(stem+"_fallback",width=8,height=8,alpha=True)
    color=(0.30,0.16,0.09,1.0) if kind=="bench" else (0.48,0.39,0.27,1.0)
    image.pixels[:]=list(color)*64
    image.filepath_raw=str(path.resolve())
    image.file_format="PNG"
    image.save()
    return "textures/xziel/sanctum_mini/"+stem

def simplify(obj):
    if obj.type!="MESH" or not obj.data.polygons:
        return
    triangles=sum(max(len(p.vertices)-2,0) for p in obj.data.polygons)
    if triangles<15:
        return
    modifier=obj.modifiers.new("XZIEL_MOBILE_LOD_COPY","DECIMATE")
    modifier.ratio=SCALE_RATIO
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    try:
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    except RuntimeError as exc:
        obj.modifiers.remove(modifier)
        print("TRIPO_DECIMATE_SKIP",obj.name,exc)

def bounds(objects):
    coords=[]
    for obj in objects:
        # bounding box from evaluated post-decimate meshes
        for corner in obj.bound_box:
            coords.append(obj.matrix_world @ Vector(corner))
    if not coords:
        raise RuntimeError("Tripo GLB did not contain mesh vertices")
    lo=Vector(tuple(min(c[i] for c in coords) for i in range(3)))
    hi=Vector(tuple(max(c[i] for c in coords) for i in range(3)))
    return lo,hi

def flush(texture, verts, inds):
    if not inds:
        return
    if len(verts)>65535 or len(inds)>65535:
        raise RuntimeError("XZSM uint16 limits exceeded")
    xs=[v[0] for v in verts];ys=[v[1] for v in verts];zs=[v[2] for v in verts]
    BATCHES.append(dict(texture=texture,vertices=verts,indices=inds,
                        bounds=(min(xs),min(ys),min(zs),max(xs),max(ys),max(zs))))

def export(kind,filename):
    path=SOURCE/filename
    if not path.is_file():
        raise FileNotFoundError("Missing exact Tripo model: "+str(path))
    reset_scene()
    bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    objects=[o for o in bpy.context.scene.objects if o.type=="MESH" and len(o.data.vertices)]
    if not objects:
        raise RuntimeError("Empty imported Tripo asset: "+filename)
    source_tris=sum(len(o.data.polygons) for o in objects)
    for obj in objects:
        simplify(obj)
    lo,hi=bounds(objects)
    extent=hi-lo
    target_xyz=PLACEMENTS[kind][1]
    # Uniform scale: never squash Tripo geometry to approximate shapes.
    scale=min(target_xyz[i]/max(extent[i],0.001) for i in range(3))
    origin=(lo+hi)*0.5
    centers=PLACEMENTS[kind][0]
    groups=defaultdict(list)
    tris_kept=0
    mats={}
    for obj in objects:
        mesh=obj.data
        mesh.calc_loop_triangles()
        uv_layer=mesh.uv_layers.active
        for face in mesh.loop_triangles:
            poly=mesh.polygons[face.polygon_index]
            material=mesh.materials[poly.material_index] if poly.material_index<len(mesh.materials) else None
            key=(material.name if material else "default")
            mats[key]=material
            tri=[]
            for li in face.loops:
                loop=mesh.loops[li]
                world=obj.matrix_world @ mesh.vertices[loop.vertex_index].co
                p=(world-origin)*scale
                uv=uv_layer.data[li].uv if uv_layer else (0.0,0.0)
                tri.append((float(p.x),float(p.y),float(p.z),
                            float(uv[0]),float(1.0-uv[1]),255,255,255,255))
            groups[key].append(tuple(tri))
            tris_kept+=1
    if tris_kept==0 or tris_kept>70000:
        raise RuntimeError("Mobile budget invalid for "+kind+": "+str(tris_kept))
    # Material textures are decoded directly from Tripo GLB, never synthetically textured.
    for idx, material_key in enumerate(sorted(groups)):
        texture=bake_basecolor(kind,idx,mats[material_key])
        for placement in centers:
            verts=[];indices=[];index_of={}
            for triangle in groups[material_key]:
                if len(indices)+3>30000 or len(verts)+3>30000:
                    flush(texture,verts,indices)
                    verts=[];indices=[];index_of={}
                for v in triangle:
                    p=(v[0]+placement[0],v[1]+placement[1],v[2]+placement[2],
                        v[3],v[4],v[5],v[6],v[7],v[8])
                    index=index_of.get(p)
                    if index is None:
                        index=len(verts)
                        verts.append(p);index_of[p]=index
                    indices.append(index)
            flush(texture,verts,indices)
    META.append({"source":str(path),"kind":kind,"originalMeshObjects":len(objects),
                 "originalPolygons":source_tris,"lodTrianglesPerInstance":tris_kept,
                 "instances":len(centers),"materials":len(groups),"uniformScale":scale})
    print("TRIPO_BAKED",json.dumps(META[-1]))

export("bench","bench.glb")
export("altar","altar.glb")
total_vertices=sum(len(b["vertices"]) for b in BATCHES)
total_indices=sum(len(b["indices"]) for b in BATCHES)
if not 0<len(BATCHES)<=512 or total_vertices>3000000 or total_indices>3500000:
    raise RuntimeError("XZSM capacity overflow")
if total_indices//3>MAX_TOTAL_TRIANGLES:
    raise RuntimeError("Too many Tripo triangles for mini Android scene")
fpath=MODEL_DIR/"sanctum_mini.xzsm"
with fpath.open("wb") as f:
    f.write(struct.pack("<4sIIII",b"XZSM",2,len(BATCHES),total_vertices,total_indices))
    for b in BATCHES:
        t=b["texture"].encode("utf-8")
        if len(t)>95:
            raise RuntimeError("Texture path exceeds XZSM 96 bytes")
        bmin=b["bounds"][:3];bmax=b["bounds"][3:]
        f.write(struct.pack("<II96s6f",len(b["vertices"]),len(b["indices"]),
                            t,*bmin,*bmax))
        for v in b["vertices"]:
            f.write(struct.pack("<5f4B",*v))
        f.write(struct.pack("<%dH"%len(b["indices"]),*b["indices"]))
report={"format":"XZSM v2","mesh":str(fpath),"assetSources":META,
        "batchCount":len(BATCHES),"vertices":total_vertices,
        "triangles":total_indices//3,"textureCount":len(list(TEXTURE_DIR.glob("*.png")))}
(OUT/"tripo_mini_export.json").write_text(json.dumps(report,indent=2)+"\n")
print("XZIEL_TRIPO_MINI_EXPORT_GREEN",json.dumps(report))
