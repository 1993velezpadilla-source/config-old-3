import bpy
import json
import os
from pathlib import Path
from mathutils import Vector

OUT=Path(os.environ.get("SANCTUM_REFERENCE_FIT_OUT","sanctum-reference-fit"))
OUT.mkdir(parents=True,exist_ok=True)
PROFILE=Path(os.environ.get("SANCTUM_REFERENCE_SILHOUETTES","docs/sanctum-reference-silhouettes.v1.json"))
data=json.loads(PROFILE.read_text(encoding="utf-8"))

def fail(msg):
    raise SystemExit("SANCTUM_REFERENCE_FIT_FAIL: "+msg)

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        if block.users==0:
            bpy.data.meshes.remove(block)

def guide_material():
    m=bpy.data.materials.get("SANCTUM_REFERENCE_HULL") or bpy.data.materials.new("SANCTUM_REFERENCE_HULL")
    m.use_nodes=True
    b=m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value=(0.08,0.32,0.62,1.0)
        b.inputs["Metallic"].default_value=0.0
        b.inputs["Roughness"].default_value=0.38
    return m

MAT=guide_material()

def prism_from_xz(points,width,height,depth,name):
    # front-sheet normalized (u,z) -> XZ; extrude through target depth on Y.
    ring=[((u-0.5)*width, -depth*0.5, z*height) for u,z in points]
    verts=ring+[(x,depth*0.5,z) for x,_,z in ring]
    n=len(ring)
    faces=[]
    # Caps. Reverse one cap so normals face out.
    faces.append(tuple(range(n-1,-1,-1)))
    faces.append(tuple(range(n,2*n)))
    for i in range(n):
        j=(i+1)%n
        faces.append((i,j,n+j,n+i))
    me=bpy.data.meshes.new(name+"_MESH")
    me.from_pydata(verts,[],faces)
    me.update()
    o=bpy.data.objects.new(name,me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(MAT)
    o["xziel_role"]="reference_fit_proxy"
    o["xziel_collision"]=False
    return o

def prism_from_yz(points,width,height,depth,name):
    # side-sheet normalized (u,z) -> YZ; extrude through target width on X.
    ring=[(-width*0.5,(u-0.5)*depth,z*height) for u,z in points]
    verts=ring+[(width*0.5,y,z) for _,y,z in ring]
    n=len(ring)
    faces=[]
    faces.append(tuple(range(n-1,-1,-1)))
    faces.append(tuple(range(n,2*n)))
    for i in range(n):
        j=(i+1)%n
        faces.append((i,j,n+j,n+i))
    me=bpy.data.meshes.new(name+"_MESH")
    me.from_pydata(verts,[],faces)
    me.update()
    o=bpy.data.objects.new(name,me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(MAT)
    o["xziel_role"]="reference_fit_proxy"
    o["xziel_collision"]=False
    return o

def world_bounds(obj):
    pts=[obj.matrix_world@Vector(c) for c in obj.bound_box]
    mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mn,mx

def mesh_volume(obj):
    # Signed tetrahedral volume; robust enough to detect an empty boolean result.
    me=obj.data
    total=0.0
    for poly in me.polygons:
        if len(poly.vertices)<3:
            continue
        ids=list(poly.vertices)
        a=me.vertices[ids[0]].co
        for i in range(1,len(ids)-1):
            b=me.vertices[ids[i]].co
            c=me.vertices[ids[i+1]].co
            total += a.dot(b.cross(c))/6.0
    return abs(total)

def export_glb(obj,path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_viewport=False
    obj.hide_render=False
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_extras=True,
    )
    if not path.is_file() or path.stat().st_size<1000:
        fail(f"GLB export failed: {path}")

def build_one(key,front_key,side_key,offset_x):
    p=data[key]
    dims=p["target_dimensions_m"]
    width=float(dims["width"])
    depth=float(dims["depth"])
    height=float(dims["height"])
    front_pts=p[front_key]["points"]
    side_pts=p[side_key]["points"]

    front=prism_from_xz(front_pts,width,height,depth,f"SANCTUM_{key.upper()}_FRONT_PRISM")
    side=prism_from_yz(side_pts,width,height,depth,f"SANCTUM_{key.upper()}_SIDE_PRISM")

    bpy.context.view_layer.objects.active=front
    front.select_set(True)
    side.select_set(False)
    mod=front.modifiers.new("SANCTUM_REFERENCE_VISUAL_HULL","BOOLEAN")
    mod.operation="INTERSECT"
    mod.solver="EXACT"
    mod.object=side
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception as exc:
        fail(f"{key} visual-hull boolean failed: {exc}")

    bpy.data.objects.remove(side,do_unlink=True)
    front.name=f"SANCTUM_{key.upper()}_REFERENCE_HULL"
    front.location.x=offset_x
    front["reference_profile"]=str(PROFILE)
    front["reference_asset"]=key
    front["reference_method"]="front_side_silhouette_visual_hull"

    bpy.context.view_layer.update()
    mn,mx=world_bounds(front)
    size=mx-mn
    volume=mesh_volume(front)
    if len(front.data.vertices)<8 or len(front.data.polygons)<6 or volume<=1e-5:
        fail(f"{key} visual hull collapsed: verts={len(front.data.vertices)} polys={len(front.data.polygons)} volume={volume}")

    glb=OUT/f"{key}-reference-hull.glb"
    export_glb(front,glb)
    return front,{
        "status":"PASS",
        "object":front.name,
        "vertices":len(front.data.vertices),
        "polygons":len(front.data.polygons),
        "volume_m3":volume,
        "bounds_min":[float(x) for x in mn],
        "bounds_max":[float(x) for x in mx],
        "measured_size_m":[float(x) for x in size],
        "target_dimensions_m":dims,
        "front_points":len(front_pts),
        "side_points":len(side_pts),
        "glb":glb.name,
        "glb_bytes":glb.stat().st_size,
    }

clear_scene()
pew,pew_report=build_one("pew","front","side_left",-3.0)
altar,altar_report=build_one("altar","front_body","side_left",3.5)

report={
    "status":"PASS",
    "profile":str(PROFILE),
    "method":"orthographic silhouette visual hull",
    "purpose":"geometry guide for reference-locked pew/altar reconstruction",
    "pew":pew_report,
    "altar":altar_report,
}
(OUT/"reference-fit-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")

# Save a blend with both hulls so future headless passes can overlay/draw on them.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"sanctum-reference-hulls.blend"))

print("SANCTUM_REFERENCE_FIT_PASS")
print(json.dumps({
    "pew_vertices":pew_report["vertices"],
    "pew_polygons":pew_report["polygons"],
    "altar_vertices":altar_report["vertices"],
    "altar_polygons":altar_report["polygons"],
},indent=2))
