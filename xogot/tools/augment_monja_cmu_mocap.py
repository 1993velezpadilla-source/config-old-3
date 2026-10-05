import bpy, json, math
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"assets/zombies/monja_clean/monja_basica_clean_rig.glb"
RAW=ROOT/"assets/zombie_mocap/raw"
OUT=ROOT/"build/monja-cmu-mocap"
OUT.mkdir(parents=True,exist_ok=True)
OUT_GLB=OUT/"monja_basica_cmu_rig.glb"
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
source_vertices=sum(len(o.data.vertices) for o in target_meshes)
source_polygons=sum(len(o.data.polygons) for o in target_meshes)
base_actions=target_existing_actions(target)
if not any("Zombie_Walk_Clean".lower() in x.lower() for x in base_actions):
    fail("base clean Monja does not expose expected clean walk action")

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

export_target(target,target_meshes)
if not OUT_GLB.is_file(): fail("CMU augmented GLB missing")
out_bytes=OUT_GLB.stat().st_size

# Validate exported deliverable.
reset()
bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
out_mesh=meshes(); out_arm=arms()
out_actions=sorted(a.name for a in bpy.data.actions)
out_vertices=sum(len(o.data.vertices) for o in out_mesh)
out_polygons=sum(len(o.data.polygons) for o in out_mesh)
expected=[n for n,_ in CLIPS]
missing=[n for n in expected if not any(n.lower() in a.lower() for a in out_actions)]

report={
    "schema":1,
    "pipeline":"monja_source_pose_plus_cmu_human_mocap_v1",
    "base":"assets/zombies/monja_clean/monja_basica_clean_rig.glb",
    "source_vertices":source_vertices,
    "source_polygons":source_polygons,
    "output_vertices":out_vertices,
    "output_polygons":out_polygons,
    "geometry_conserved":source_vertices==out_vertices and source_polygons==out_polygons,
    "armatures":len(out_arm),
    "bones":len(out_arm[0].data.bones) if out_arm else 0,
    "base_actions":base_actions,
    "baked_cmu":baked,
    "output_actions":out_actions,
    "missing_cmu_actions":missing,
    "output_bytes":out_bytes,
    "mocap_provenance":{
        "provider":"Carnegie Mellon University Graphics Lab Motion Capture Database",
        "capture":"human marker-based Vicon motion capture",
        "use":"free for all uses; commercial products permitted; direct resale of dataset prohibited",
        "url":"https://mocap.cs.cmu.edu/",
    },
}
REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")

if not report["geometry_conserved"]: fail("geometry changed during CMU augmentation")
if len(out_arm)!=1 or report["bones"]<20: fail("target skeleton lost")
if missing: fail("missing exported CMU actions: "+repr(missing))
if len(baked)!=9: fail("expected nine CMU clips")

print("XZOGOT_MONJA_CMU_GEOMETRY_GREEN",out_vertices,out_polygons)
print("XZOGOT_MONJA_CMU_9_REAL_MOCAP_CLIPS_GREEN",expected)
print("XZOGOT_MONJA_CMU_RIG_GREEN",report["bones"],out_bytes)
