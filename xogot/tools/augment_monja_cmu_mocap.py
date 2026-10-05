import bpy, json, math, sys
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]

def _tool_args():
    raw=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    out={}
    i=0
    while i<len(raw):
        if raw[i].startswith("--") and i+1<len(raw):
            out[raw[i][2:]]=raw[i+1]
            i+=2
        else:
            i+=1
    return out

ARGS=_tool_args()
PROFILE=ARGS.get("profile","normal").strip().lower()
BASE=Path(ARGS.get("base",str(ROOT/"assets/zombies/monja_clean/monja_basica_clean_rig.glb"))).resolve()
RAW=ROOT/"assets/zombie_mocap/raw"
OUT=Path(ARGS.get("output-dir",str(ROOT/"build/monja-cmu-mocap"))).resolve()
OUT.mkdir(parents=True,exist_ok=True)
OUT_GLB=OUT/ARGS.get(
    "output-name",
    "monja_black_white_cmu_rig.glb" if PROFILE=="elite" else "monja_basica_cmu_rig.glb",
)
REPORT=OUT/"report.json"

CLIPS=[
    ("CMU_ZombieWalk_104_41", RAW/"walk/zombie_walk__104_41.fbx"),
    ("CMU_DragBadLeg_105_25", RAW/"walk/drag_bad_leg__105_25.fbx"),
    ("CMU_StiffWalk_74_01", RAW/"walk/stiff_A__74_01.fbx"),
    ("CMU_WoundedLeg_139_19", RAW/"walk/wounded_leg_139_A__139_19.fbx"),
    ("CMU_Strike_02_05", RAW/"attack/strike_A__02_05.fbx"),
    ("CMU_PunchKick_111_19", RAW/"attack/punch_kick__111_19.fbx"),
    ("CMU_Crawl_111_03", RAW/"crawl/crawl_A__111_03.fbx"),
    ("CMU_FallOnFace_90_16", RAW/"death/fall_on_face_90__90_16.fbx"),
    ("CMU_GetUpFaceDown_140_01", RAW/"getup/face_down_A__140_01.fbx"),
]

# CMU FBX skeleton -> clean Monja skeleton.  Only real captured joints are
# transferred; synthetic finger/eye helpers are intentionally ignored.
BONE_MAP={
    "pelvis":"hip",
    "spine_01":"abdomen",
    "spine_03":"chest",
    "neck_01":"neck",
    "Head":"head",
    "clavicle_l":"lCollar",
    "upperarm_l":"lShldr",
    "lowerarm_l":"lForeArm",
    "hand_l":"lHand",
    "clavicle_r":"rCollar",
    "upperarm_r":"rShldr",
    "lowerarm_r":"rForeArm",
    "hand_r":"rHand",
    "thigh_l":"lThigh",
    "calf_l":"lShin",
    "foot_l":"lFoot",
    "thigh_r":"rThigh",
    "calf_r":"rShin",
    "foot_r":"rFoot",
}

def fail(msg):
    print("XZOGOT_MONJA_CMU_FAIL",msg)
    raise SystemExit(2)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def scene_objects():
    return list(bpy.context.scene.objects)

def snapshot():
    return set(scene_objects())

def meshes(objs=None):
    if objs is None: objs=scene_objects()
    return [o for o in objs if o.type=="MESH"]

def arms(objs=None):
    if objs is None: objs=scene_objects()
    return [o for o in objs if o.type=="ARMATURE"]

def find_primary_armature(objects):
    aa=arms(objects)
    if not aa: fail("armature missing")
    return max(aa,key=lambda a:len(a.data.bones))

def action_for_armature(arm):
    if arm.animation_data and arm.animation_data.action:
        return arm.animation_data.action
    # FBX importer normally creates one action per imported armature.
    candidates=[]
    for action in bpy.data.actions:
        if "|" in action.name or action.name.lower().startswith(arm.name.lower()):
            candidates.append(action)
    if not candidates:
        candidates=list(bpy.data.actions)
    if not candidates: fail("FBX action missing for "+arm.name)
    return max(candidates,key=lambda a:len(a.fcurves))

def rest_global(arm,bone_name):
    return arm.data.bones[bone_name].matrix_local.copy()

def pose_global(arm,bone_name):
    return arm.pose.bones[bone_name].matrix.copy()

def armature_height(arm):
    zs=[]
    for b in arm.data.bones:
        zs.extend([b.head_local.z,b.tail_local.z])
    return max(zs)-min(zs)

def target_existing_actions(target):
    names=set()
    if target.animation_data:
        if target.animation_data.action:
            names.add(target.animation_data.action.name)
        for track in target.animation_data.nla_tracks:
            for strip in track.strips:
                if strip.action:
                    names.add(strip.action.name)
    return sorted(names)

def bake_cmu_clip(target,src,src_action,new_name):
    for tgt,source in BONE_MAP.items():
        if target.pose.bones.get(tgt) is None:
            fail(f"target missing bone {tgt}")
        if src.pose.bones.get(source) is None:
            fail(f"{new_name}: CMU source missing {source}")

    src.animation_data_create()
    src.animation_data.action=src_action
    target.animation_data_create()
    new_action=bpy.data.actions.new(new_name)
    target.animation_data.action=new_action

    lo=int(math.floor(src_action.frame_range[0]))
    hi=int(math.ceil(src_action.frame_range[1]))
    source_h=max(armature_height(src),1e-5)
    target_h=max(armature_height(target),1e-5)
    scale=target_h/source_h

    src_rest={s:rest_global(src,s) for s in BONE_MAP.values()}
    tgt_rest={t:rest_global(target,t) for t in BONE_MAP.keys()}
    src_hip_rest=src_rest["hip"].translation.copy()

    # Preserve source FPS. FBX CMU captures are typically 120Hz; Blender import
    # may represent them at scene FPS. We key every imported frame to avoid
    # inventing interpolation.
    for frame in range(lo,hi+1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        hip_pose=pose_global(src,"hip")
        root_delta=(hip_pose.translation-src_hip_rest)*scale
        # CharacterBody owns horizontal locomotion; keep animation in-place but
        # retain vertical body motion for limps/crawl/fall/get-up.
        root_delta.x=0.0
        root_delta.y=0.0

        for tgt_name,src_name in BONE_MAP.items():
            src_r=src_rest[src_name]
            src_p=pose_global(src,src_name)
            # Global rotational delta from captured rest -> captured pose.
            delta_q=src_p.to_quaternion() @ src_r.to_quaternion().inverted()
            tgt_r=tgt_rest[tgt_name]
            desired_q=delta_q @ tgt_r.to_quaternion()
            desired_loc=tgt_r.translation.copy()+root_delta

            pb=target.pose.bones[tgt_name]
            desired=desired_q.to_matrix().to_4x4()
            desired.translation=desired_loc
            pb.matrix=desired
            pb.rotation_mode='QUATERNION'
            pb.keyframe_insert(data_path="location",frame=frame,group=tgt_name)
            pb.keyframe_insert(data_path="rotation_quaternion",frame=frame,group=tgt_name)
            pb.keyframe_insert(data_path="scale",frame=frame,group=tgt_name)

    target.animation_data.action=None
    src.animation_data.action=None
    tr=target.animation_data.nla_tracks.new()
    tr.name="NLA_"+new_name
    strip=tr.strips.new(new_name,lo,new_action)
    strip.name=new_name
    new_action.use_fake_user=True
    print("XZOGOT_MONJA_CMU_CLIP_GREEN",new_name,lo,hi,len(BONE_MAP))
    return {
        "name":new_name,
        "source_action":src_action.name,
        "frames":[lo,hi],
        "mapped_bones":len(BONE_MAP),
        "height_scale":scale,
    }

def mesh_surface_stats(mesh_objects):
    depsgraph=bpy.context.evaluated_depsgraph_get()
    total_triangles=0
    total_area=0.0
    degenerate=0
    bounds_min=None
    bounds_max=None
    for obj in mesh_objects:
        eval_obj=obj.evaluated_get(depsgraph)
        mesh=eval_obj.to_mesh()
        try:
            mesh.calc_loop_triangles()
            tri_n=len(mesh.loop_triangles)
            total_triangles += tri_n
            if len(mesh.vertices)==0:
                continue
            raw=np.empty(len(mesh.vertices)*3,dtype=np.float32)
            mesh.vertices.foreach_get("co",raw)
            local=raw.reshape((-1,3)).astype(np.float64)
            M=np.array(eval_obj.matrix_world,dtype=np.float64)
            homo=np.concatenate([local,np.ones((len(local),1),dtype=np.float64)],axis=1)
            world=(homo @ M.T)[:,:3]
            mn=world.min(axis=0)
            mx=world.max(axis=0)
            bounds_min=mn if bounds_min is None else np.minimum(bounds_min,mn)
            bounds_max=mx if bounds_max is None else np.maximum(bounds_max,mx)
            if tri_n:
                idx=np.empty(tri_n*3,dtype=np.int32)
                mesh.loop_triangles.foreach_get("vertices",idx)
                tri=world[idx.reshape((-1,3))]
                cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
                areas=0.5*np.linalg.norm(cross,axis=1)
                total_area += float(areas.sum())
                degenerate += int(np.count_nonzero(areas <= 1e-12))
        finally:
            eval_obj.to_mesh_clear()
    if bounds_min is None:
        bounds_min=np.zeros(3,dtype=np.float64)
        bounds_max=np.zeros(3,dtype=np.float64)
    return {
        "triangles":int(total_triangles),
        "surface_area":float(total_area),
        "degenerate_triangles":int(degenerate),
        "bounds_min":[float(x) for x in bounds_min],
        "bounds_max":[float(x) for x in bounds_max],
    }

def triangle_count(mesh_objects):
    return mesh_surface_stats(mesh_objects)["triangles"]

def export_target(target,target_meshes):
    bpy.ops.object.select_all(action='DESELECT')
    target.select_set(True)
    for o in target_meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=target
    props=set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys())
    kwargs={
        "filepath":str(OUT_GLB),
        "export_format":"GLB",
        "use_selection":True,
        "export_animations":True,
        "export_skins":True,
        "export_apply":False,
    }
    if "export_animation_mode" in props:
        prop=bpy.ops.export_scene.gltf.get_rna_type().properties["export_animation_mode"]
        modes={x.identifier for x in prop.enum_items}
        if "NLA_TRACKS" in modes: kwargs["export_animation_mode"]="NLA_TRACKS"
        elif "ACTIONS" in modes: kwargs["export_animation_mode"]="ACTIONS"
    if "export_nla_strips" in props: kwargs["export_nla_strips"]=True
    if "export_force_sampling" in props: kwargs["export_force_sampling"]=True
    if "export_def_bones" in props: kwargs["export_def_bones"]=True
    bpy.ops.export_scene.gltf(**kwargs)

def render_preview(target,target_meshes,action_name,label):
    action=bpy.data.actions.get(action_name)
    if action is None:return
    previous_pose_position=target.data.pose_position
    target.data.pose_position='POSE'
    target.animation_data_create(); target.animation_data.action=action
    mid=int((action.frame_range[0]+action.frame_range[1])*0.5)
    bpy.context.scene.frame_set(mid); bpy.context.view_layer.update()

    pts=[]
    for o in target_meshes:
        pts.extend([o.matrix_world @ Vector(c) for c in o.bound_box])
    mn=Vector(pts[0]); mx=Vector(pts[0])
    for p in pts[1:]:
        mn.x=min(mn.x,p.x); mn.y=min(mn.y,p.y); mn.z=min(mn.z,p.z)
        mx.x=max(mx.x,p.x); mx.y=max(mx.y,p.y); mx.z=max(mx.z,p.z)
    size=mx-mn; center=(mn+mx)*0.5; dist=max(size)*2.8

    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=900; scene.render.resolution_y=1200
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    if scene.world is None: scene.world=bpy.data.worlds.new("CMUPreviewWorld")
    scene.world.color=(0.08,0.08,0.08)
    cd=bpy.data.cameras.new("CMUPreviewCamera")
    cam=bpy.data.objects.new("CMUPreviewCamera",cd); bpy.context.collection.objects.link(cam)
    cd.type='ORTHO'; cd.ortho_scale=max(size.z*1.08,size.x*1.75)
    cam.location=Vector((center.x,center.y-dist,center.z))
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=cam
    for nm,loc,energy in [
        ("CMUKey",center+Vector((size.x,-dist*.4,size.z*.45)),1400),
        ("CMUFill",center+Vector((-size.x,-dist*.25,size.z*.20)),800),
    ]:
        ld=bpy.data.lights.new(nm,type='AREA'); ld.energy=energy; ld.size=max(size)*1.3
        lo=bpy.data.objects.new(nm,ld); bpy.context.collection.objects.link(lo); lo.location=loc
    scene.render.filepath=str(OUT/(label+".png"))
    bpy.ops.render.render(write_still=True)
    target.animation_data.action=None
    target.data.pose_position=previous_pose_position

def glb_animation_motion(path):
    import struct
    data=Path(path).read_bytes()
    if len(data)<20 or data[:4]!=b"glTF":
        fail("CMU exported GLB header invalid")
    pos=12
    doc=None
    bin_blob=None
    while pos+8<=len(data):
        chunk_len,chunk_type=struct.unpack_from("<II",data,pos)
        chunk=data[pos+8:pos+8+chunk_len]
        if chunk_type==0x4E4F534A:
            doc=json.loads(chunk.decode("utf-8").rstrip("\x00 \t\r\n"))
        elif chunk_type==0x004E4942:
            bin_blob=chunk
        pos += 8 + chunk_len
    if doc is None or bin_blob is None:
        fail("CMU exported GLB missing JSON/BIN")

    dtypes={5120:np.int8,5121:np.uint8,5122:np.int16,5123:np.uint16,5125:np.uint32,5126:np.float32}
    dims={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}
    def read_accessor(index):
        acc=doc["accessors"][index]
        bv=doc["bufferViews"][acc["bufferView"]]
        dtype=dtypes[acc["componentType"]]
        width=dims[acc["type"]]
        off=int(bv.get("byteOffset",0))+int(acc.get("byteOffset",0))
        stride=int(bv.get("byteStride",np.dtype(dtype).itemsize*width))
        count=int(acc["count"])
        item_bytes=np.dtype(dtype).itemsize*width
        if stride==item_bytes:
            return np.frombuffer(bin_blob,dtype=dtype,count=count*width,offset=off).reshape((count,width)).copy()
        out=np.empty((count,width),dtype=dtype)
        for i in range(count):
            out[i]=np.frombuffer(bin_blob,dtype=dtype,count=width,offset=off+i*stride)
        return out

    motion={}
    for anim in doc.get("animations",[]):
        name=anim.get("name","Animation")
        varying=0
        sampled=0
        max_range=0.0
        for channel in anim.get("channels",[]):
            target_path=channel.get("target",{}).get("path")
            if target_path not in ("translation","rotation","scale"):
                continue
            sampler=anim["samplers"][int(channel["sampler"])]
            values=read_accessor(int(sampler["output"])).astype(np.float64)
            if len(values)<2:
                continue
            sampled += 1
            r=float(np.max(np.max(values,axis=0)-np.min(values,axis=0)))
            max_range=max(max_range,r)
            if r>1e-5:
                varying += 1
        motion[name]={
            "sampled_channels":int(sampled),
            "varying_channels":int(varying),
            "max_component_range":float(max_range),
        }
    return motion

# -------- main --------
if not BASE.is_file(): fail("base source-pose Monja missing")
for _,p in CLIPS:
    if not p.is_file(): fail("CMU source missing: "+str(p))

reset()
bpy.ops.import_scene.gltf(filepath=str(BASE))
base_objs=scene_objects()
target=find_primary_armature(base_objs)
target_meshes=meshes(base_objs)
if not target_meshes: fail("base Monja mesh missing")
target.data.pose_position='REST'
if target.animation_data:
    target.animation_data.action=None
bpy.context.scene.frame_set(0)
bpy.context.view_layer.update()
source_vertices=sum(len(o.data.vertices) for o in target_meshes)
source_polygons=sum(len(o.data.polygons) for o in target_meshes)
source_surface=mesh_surface_stats(target_meshes)
source_triangles=source_surface["triangles"]
base_actions=target_existing_actions(target)
if not any("Zombie_Walk_Clean".lower() in x.lower() for x in base_actions):
    fail("base clean Monja does not expose expected clean walk action")

target.data.pose_position='POSE'
baked=[]
for new_name,fbx in CLIPS:
    before=snapshot()
    actions_before=set(bpy.data.actions.keys())
    bpy.ops.import_scene.fbx(filepath=str(fbx),automatic_bone_orientation=False,use_anim=True)
    imported=list(snapshot()-before)
    src=find_primary_armature(imported)
    new_action_names=list(set(bpy.data.actions.keys())-actions_before)
    if src.animation_data and src.animation_data.action:
        src_action=src.animation_data.action
    elif new_action_names:
        src_action=max((bpy.data.actions[n] for n in new_action_names),key=lambda a:len(a.fcurves))
    else:
        src_action=action_for_armature(src)
    baked.append(bake_cmu_clip(target,src,src_action,new_name))

    # Delete imported CMU objects after baking, but leave the baked target action.
    for o in imported:
        if bpy.data.objects.get(o.name):
            bpy.data.objects.remove(bpy.data.objects.get(o.name),do_unlink=True)
    for action_name in new_action_names:
        a=bpy.data.actions.get(action_name)
        if a is not None and a.name!=new_name and a.users==0:
            bpy.data.actions.remove(a)

render_preview(target,target_meshes,"CMU_ZombieWalk_104_41","cmu_zombie_walk_mid")
render_preview(target,target_meshes,"CMU_DragBadLeg_105_25","cmu_drag_bad_leg_mid")
render_preview(target,target_meshes,"CMU_Crawl_111_03","cmu_crawl_mid")
render_preview(target,target_meshes,"CMU_Strike_02_05","cmu_strike_mid")

target.data.pose_position='POSE'
if target.animation_data:
    target.animation_data.action=None
export_target(target,target_meshes)
if not OUT_GLB.is_file(): fail("CMU augmented GLB missing")
out_bytes=OUT_GLB.stat().st_size
raw_animation_motion=glb_animation_motion(OUT_GLB)
expected_motion={}
for name,_ in CLIPS:
    matches=[(anim,metric) for anim,metric in raw_animation_motion.items() if name.lower() in anim.lower()]
    expected_motion[name]=matches[0][1] if matches else None
raw_animation_motion_valid=all(
    metric is not None
    and metric["varying_channels"]>=3
    and metric["max_component_range"]>1e-4
    for metric in expected_motion.values()
)
print("XZOGOT_MONJA_CMU_RAW_ANIMATION_MOTION",json.dumps(expected_motion,sort_keys=True))

# Validate exported deliverable.
reset()
bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
out_mesh=meshes(); out_arm=arms()
out_actions=sorted(a.name for a in bpy.data.actions)
for out_rig in out_arm:
    out_rig.data.pose_position='REST'
    if out_rig.animation_data:
        out_rig.animation_data.action=None
bpy.context.scene.frame_set(0)
bpy.context.view_layer.update()
out_vertices=sum(len(o.data.vertices) for o in out_mesh)
out_polygons=sum(len(o.data.polygons) for o in out_mesh)
out_surface=mesh_surface_stats(out_mesh)
out_triangles=out_surface["triangles"]
extra_triangles=out_triangles-source_triangles
area_delta=abs(out_surface["surface_area"]-source_surface["surface_area"])
area_tolerance=max(source_surface["surface_area"]*1e-5,1e-8)
bounds_delta=max(
    max(abs(a-b) for a,b in zip(out_surface["bounds_min"],source_surface["bounds_min"])),
    max(abs(a-b) for a,b in zip(out_surface["bounds_max"],source_surface["bounds_max"])),
)
source_extent=max(
    source_surface["bounds_max"][i]-source_surface["bounds_min"][i]
    for i in range(3)
)
bounds_tolerance=max(source_extent*1e-5,1e-6)
geometry_conserved=(
    extra_triangles>=0
    and extra_triangles<=256
    and area_delta<=area_tolerance
    and bounds_delta<=bounds_tolerance
)
expected=[n for n,_ in CLIPS]
missing=[n for n in expected if not any(n.lower() in a.lower() for a in out_actions)]

report={
    "schema":1,
    "pipeline":"monja_source_pose_plus_cmu_human_mocap_v1",
    "base":str(BASE.relative_to(ROOT)) if ROOT in BASE.parents else str(BASE),
    "profile":PROFILE,
    "source_vertices":source_vertices,
    "source_polygons":source_polygons,
    "source_triangles":source_triangles,
    "source_surface_area":source_surface["surface_area"],
    "source_degenerate_triangles":source_surface["degenerate_triangles"],
    "output_vertices":out_vertices,
    "output_polygons":out_polygons,
    "output_triangles":out_triangles,
    "output_surface_area":out_surface["surface_area"],
    "output_degenerate_triangles":out_surface["degenerate_triangles"],
    "triangle_delta":extra_triangles,
    "surface_area_delta":area_delta,
    "surface_area_tolerance":area_tolerance,
    "source_bounds_min":source_surface["bounds_min"],
    "source_bounds_max":source_surface["bounds_max"],
    "output_bounds_min":out_surface["bounds_min"],
    "output_bounds_max":out_surface["bounds_max"],
    "bounds_delta":bounds_delta,
    "bounds_tolerance":bounds_tolerance,
    "geometry_conserved":geometry_conserved,
    "geometry_gate":"no_triangle_loss_plus_surface_area_conservation",
    "export_reindexed_vertices":source_vertices!=out_vertices,
    "export_triangulated_nontri_faces":source_polygons!=out_polygons,
    "armatures":len(out_arm),
    "bones":len(out_arm[0].data.bones) if out_arm else 0,
    "base_actions":base_actions,
    "baked_cmu":baked,
    "output_actions":out_actions,
    "missing_cmu_actions":missing,
    "output_bytes":out_bytes,
    "raw_glb_animation_motion":expected_motion,
    "raw_glb_animation_motion_valid":bool(raw_animation_motion_valid),
    "mocap_provenance":{
        "provider":"Carnegie Mellon University Graphics Lab Motion Capture Database",
        "capture":"human marker-based Vicon motion capture",
        "use":"free for all uses; commercial products permitted; direct resale of dataset prohibited",
        "url":"https://mocap.cs.cmu.edu/",
    },
}
REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")

if not report["geometry_conserved"]:
    fail(
        f"surface geometry changed during CMU augmentation tris={out_triangles}/{source_triangles} "
        f"delta={extra_triangles} area_delta={area_delta} tol={area_tolerance} "
        f"bounds_delta={bounds_delta} bounds_tol={bounds_tolerance}"
    )
if len(out_arm)!=1 or report["bones"]<20: fail("target skeleton lost")
if not report["raw_glb_animation_motion_valid"]:
    fail("exported CMU animation channels are static "+repr(expected_motion))
if missing: fail("missing exported CMU actions: "+repr(missing))
if len(baked)!=9: fail("expected nine CMU clips")

print("XZOGOT_MONJA_CMU_GEOMETRY_GREEN",out_vertices,out_polygons,out_triangles)
print("XZOGOT_MONJA_CMU_9_REAL_MOCAP_CLIPS_GREEN",expected)
print("XZOGOT_MONJA_CMU_ANIMATION_MOTION_GREEN",json.dumps(expected_motion,sort_keys=True))
print("XZOGOT_MONJA_CMU_PROFILE_GREEN",PROFILE)
print("XZOGOT_MONJA_CMU_RIG_GREEN",report["bones"],out_bytes)
