import bpy, json, math
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
MONJA=ROOT/"assets/zombies/monja_basica.glb"
DONOR=ROOT/"assets/zombie_mocap/retarget/UAL2_Standard.glb"
RAW=ROOT/"assets/zombie_mocap/raw"
OUT=ROOT/"build/monja-blender-bindpose-inspect"
OUT.mkdir(parents=True,exist_ok=True)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def meshes():
    return [o for o in bpy.context.scene.objects if o.type=="MESH"]

def arms():
    return [o for o in bpy.context.scene.objects if o.type=="ARMATURE"]

def bounds(objs):
    pts=[]
    for o in objs:
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn=Vector(pts[0]); mx=Vector(pts[0])
    for p in pts[1:]:
        mn.x=min(mn.x,p.x); mn.y=min(mn.y,p.y); mn.z=min(mn.z,p.z)
        mx.x=max(mx.x,p.x); mx.y=max(mx.y,p.y); mx.z=max(mx.z,p.z)
    size=mx-mn
    order=sorted(range(3),key=lambda i:size[i],reverse=True)
    return mn,mx,size,order

def bone_dump(arm):
    rows=[]
    for b in arm.data.bones:
        rows.append({
            "name":b.name,
            "parent":b.parent.name if b.parent else None,
            "head_local":[round(float(x),6) for x in b.head_local],
            "tail_local":[round(float(x),6) for x in b.tail_local],
            "roll":round(float(b.matrix_local.to_euler().y),6),
            "length":round(float(b.length),6),
        })
    return rows

def setup_render(objs,label):
    mn,mx,size,order=bounds(objs)
    up=order[0]
    side=order[1]
    depth=order[2]
    center=(mn+mx)*0.5
    # Neutral world + simple studio lighting.
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=900
    scene.render.resolution_y=1200
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.world.color=(0.10,0.10,0.10)

    def add_light(name,loc,energy,size_l):
        data=bpy.data.lights.new(name=name,type='AREA')
        data.energy=energy
        data.size=size_l
        obj=bpy.data.objects.new(name,data)
        bpy.context.collection.objects.link(obj)
        obj.location=loc
        return obj

    # Camera basis is chosen from detected principal bbox axes.
    axes=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
    up_v=axes[up]; side_v=axes[side]; depth_v=axes[depth]
    if depth_v.z > 0.5 and up_v.y > 0.5:
        depth_v = Vector((0,0,1))
    cam_data=bpy.data.cameras.new("BindPoseCamera")
    cam=bpy.data.objects.new("BindPoseCamera",cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera=cam
    cam_data.type='ORTHO'
    cam_data.ortho_scale=max(size[up]*1.08,size[side]*1.45)

    dist=max(size)*2.5
    def point_camera(direction,outname):
        cam.location=center + direction*dist
        # Local -Z points to target, local Y should approximate up axis.
        q=(center-cam.location).to_track_quat('-Z','Y')
        cam.rotation_euler=q.to_euler()
        scene.render.filepath=str(OUT/outname)
        bpy.ops.render.render(write_still=True)

    add_light("Key",center + depth_v*dist*0.55 + side_v*size[side]*0.8 + up_v*size[up]*0.4,1800,max(size)*1.2)
    add_light("Fill",center + depth_v*dist*0.35 - side_v*size[side]*0.9 + up_v*size[up]*0.1,1000,max(size)*1.0)
    add_light("Top",center + up_v*size[up]*1.5,1200,max(size)*0.8)

    point_camera(depth_v,f"{label}_front.png")
    point_camera(side_v,f"{label}_side.png")
    return {
        "min":[round(float(x),6) for x in mn],
        "max":[round(float(x),6) for x in mx],
        "size":[round(float(x),6) for x in size],
        "up_axis":up,
        "side_axis":side,
        "depth_axis":depth,
        "center":[round(float(x),6) for x in center],
    }

report={"monja":{},"donor":{},"mocap":[]}

reset()
bpy.ops.import_scene.gltf(filepath=str(MONJA))
m=meshes(); a=arms()
mb=setup_render(m,"monja_source")
report["monja"]={
    "file":str(MONJA.relative_to(ROOT)),
    "mesh_count":len(m),
    "armature_count":len(a),
    "vertices":sum(len(o.data.vertices) for o in m),
    "polygons":sum(len(o.data.polygons) for o in m),
    "bounds":mb,
    "objects":[{"name":o.name,"type":o.type} for o in bpy.context.scene.objects],
    "mesh_info":[{
        "name":o.name,
        "vertices":len(o.data.vertices),
        "polygons":len(o.data.polygons),
        "vertex_groups":len(o.vertex_groups),
        "armature_modifiers":[mod.object.name if mod.object else None for mod in o.modifiers if mod.type=="ARMATURE"],
    } for o in m],
}
print("XZOGOT_MONJA_SOURCE_INSPECT",json.dumps(report["monja"]["bounds"]))

reset()
bpy.ops.import_scene.gltf(filepath=str(DONOR))
dm=meshes(); da=arms()
if not da:
    raise SystemExit("Donor missing armature")
arm=da[0]
mn,mx,size,order=bounds(dm)
report["donor"]={
    "file":str(DONOR.relative_to(ROOT)),
    "mesh_count":len(dm),
    "armature_count":len(da),
    "bounds":{
        "min":[round(float(x),6) for x in mn],
        "max":[round(float(x),6) for x in mx],
        "size":[round(float(x),6) for x in size],
        "axis_order":order,
    },
    "bone_count":len(arm.data.bones),
    "bones":bone_dump(arm),
    "actions":[{
        "name":ac.name,
        "start":float(ac.frame_range[0]),
        "end":float(ac.frame_range[1]),
        "fcurves":len(ac.fcurves),
    } for ac in bpy.data.actions],
}
print("XZOGOT_MONJA_DONOR_BONES",report["donor"]["bone_count"])
print("XZOGOT_MONJA_DONOR_ACTIONS",len(report["donor"]["actions"]))

for fbx in sorted(RAW.rglob("*.fbx")):
    reset()
    rec={"path":str(fbx.relative_to(ROOT))}
    try:
        bpy.ops.import_scene.fbx(filepath=str(fbx),automatic_bone_orientation=False,use_anim=True)
        aa=arms()
        rec["armature_count"]=len(aa)
        rec["bone_count"]=len(aa[0].data.bones) if aa else 0
        rec["bones"]=bone_dump(aa[0]) if aa else []
        rec["actions"]=[{
            "name":ac.name,
            "start":float(ac.frame_range[0]),
            "end":float(ac.frame_range[1]),
            "fcurves":len(ac.fcurves),
        } for ac in bpy.data.actions]
    except Exception as exc:
        rec["error"]=repr(exc)
    report["mocap"].append(rec)
    print("XZOGOT_MONJA_MOCAP_INSPECT",fbx.name,rec.get("bone_count",0),len(rec.get("actions",[])))

(OUT/"inspect.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")

if report["monja"]["armature_count"] != 0:
    print("XZOGOT_MONJA_NOTE_SOURCE_ALREADY_RIGGED")
if report["donor"]["bone_count"] < 20:
    raise SystemExit("Donor skeleton unexpectedly small")
if len(report["mocap"]) < 5 or any(x.get("armature_count",0)<1 for x in report["mocap"]):
    raise SystemExit("Mocap inspection incomplete")

print("XZOGOT_MONJA_BLENDER_BINDPOSE_INSPECT_GREEN",len(report["mocap"]))
