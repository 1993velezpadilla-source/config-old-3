import bpy, json, math
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]
MONJA=ROOT/"assets/zombies/monja_basica.glb"
DONOR=ROOT/"assets/zombie_mocap/retarget/UAL2_Standard.glb"
OUT=ROOT/"build/monja-clean-blender-rig"
OUT.mkdir(parents=True,exist_ok=True)
OUT_GLB=OUT/"monja_basica_clean_rig.glb"
REPORT=OUT/"report.json"

REQUIRED={
    "idle":"Zombie_Idle_Loop",
    "walk":"Zombie_Walk_Fwd_Loop",
    "attack":"Zombie_Scratch",
}
BIND_TOKEN="A_TPose"

def fail(msg):
    print("XZOGOT_MONJA_CLEAN_RIG_FAIL",msg)
    raise SystemExit(2)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def scene_objects():
    return list(bpy.context.scene.objects)

def meshes(objs=None):
    if objs is None: objs=scene_objects()
    return [o for o in objs if o.type=="MESH"]

def arms(objs=None):
    if objs is None: objs=scene_objects()
    return [o for o in objs if o.type=="ARMATURE"]

def snapshot():
    return set(bpy.context.scene.objects)

def bounds(objs):
    pts=[]
    for o in objs:
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts: fail("No bounds")
    mn=Vector(pts[0]); mx=Vector(pts[0])
    for p in pts[1:]:
        mn.x=min(mn.x,p.x); mn.y=min(mn.y,p.y); mn.z=min(mn.z,p.z)
        mx.x=max(mx.x,p.x); mx.y=max(mx.y,p.y); mx.z=max(mx.z,p.z)
    size=mx-mn
    order=sorted(range(3),key=lambda i:size[i],reverse=True)
    return mn,mx,size,order

def find_action(token):
    hits=[a for a in bpy.data.actions if token.lower() in a.name.lower()]
    if not hits:
        fail("Missing action token "+token+"; have="+str([a.name for a in bpy.data.actions]))
    return hits[0]

def armature_weighted_mesh(donor_meshes):
    weighted=[]
    for o in donor_meshes:
        if o.vertex_groups and any(m.type=="ARMATURE" for m in o.modifiers):
            weighted.append(o)
    if not weighted:
        weighted=[o for o in donor_meshes if o.vertex_groups]
    if not weighted: fail("Donor has no weighted mesh")
    return max(weighted,key=lambda o:len(o.data.vertices))

def align_monja(monja_meshes,donor_meshes):
    mmn,mmx,msize,morder=bounds(monja_meshes)
    dmn,dmx,dsize,dorder=bounds(donor_meshes)
    mup=morder[0]; dup=dorder[0]
    if mup != dup:
        axes=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
        q=axes[mup].rotation_difference(axes[dup])
        rot=q.to_matrix().to_4x4()
        for o in monja_meshes:
            o.matrix_world=rot @ o.matrix_world
        mmn,mmx,msize,morder=bounds(monja_meshes)
        mup=morder[0]
        if mup != dup: fail(f"Could not align up axis monja={mup} donor={dup}")

    scale=float(dsize[dup]/max(msize[mup],1e-8))
    mcenter=(mmn+mmx)*0.5
    dcenter=(dmn+dmx)*0.5
    scaled_center=mcenter*scale
    scaled_min=mmn*scale
    delta=dcenter-scaled_center
    delta[dup]=dmn[dup]-scaled_min[dup]
    xf=Matrix.Translation(delta) @ Matrix.Scale(scale,4)
    for o in monja_meshes:
        o.matrix_world=xf @ o.matrix_world

    amn,amx,asize,aorder=bounds(monja_meshes)
    return {
        "scale":scale,
        "translation":[float(x) for x in delta],
        "monja_source_size":[float(x) for x in msize],
        "donor_size":[float(x) for x in dsize],
        "aligned_size":[float(x) for x in asize],
        "up_axis":dup,
    }

def transfer_weights(source,target,target_arm):
    src_groups=[g.name for g in source.vertex_groups]
    for name in src_groups:
        if target.vertex_groups.get(name) is None:
            target.vertex_groups.new(name=name)

    bpy.context.view_layer.objects.active=target
    target.select_set(True)
    mod=target.modifiers.new(name="CleanRig_WeightTransfer",type="DATA_TRANSFER")
    mod.object=source
    mod.use_vert_data=True
    mod.data_types_verts={'VGROUP_WEIGHTS'}
    mod.vert_mapping='POLYINTERP_NEAREST'
    mod.layers_vgroup_select_src='ALL'
    mod.layers_vgroup_select_dst='NAME'
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Standard manual-rig cleanup equivalents: normalize, cap influences.
    try:
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL',limit=4)
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    except Exception as exc:
        print("XZOGOT_MONJA_WEIGHT_CLEANUP_WARN",repr(exc))

    arm_mod=target.modifiers.new(name="CleanRig_Armature",type="ARMATURE")
    arm_mod.object=target_arm
    world=target.matrix_world.copy()
    target.parent=target_arm
    target.matrix_parent_inverse=target_arm.matrix_world.inverted()
    target.matrix_world=world
    target.select_set(False)

    weighted=sum(1 for v in target.data.vertices if len(v.groups)>0)
    return {
        "mesh":target.name,
        "vertices":len(target.data.vertices),
        "polygons":len(target.data.polygons),
        "groups":len(target.vertex_groups),
        "weighted":weighted,
        "coverage":weighted/max(1,len(target.data.vertices)),
    }

def clear_pose(arm):
    if arm.animation_data:
        arm.animation_data.action=None
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()

def apply_bind_pose_as_rest(target_arm,bind_action):
    target_arm.animation_data_create()
    target_arm.animation_data.action=bind_action
    start=int(round(bind_action.frame_range[0]))
    bpy.context.scene.frame_set(start)
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action='DESELECT')
    target_arm.select_set(True)
    bpy.context.view_layer.objects.active=target_arm
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    target_arm.animation_data.action=None
    clear_pose(target_arm)
    bpy.context.view_layer.update()
    print("XZOGOT_MONJA_BIND_POSE_APPLIED",bind_action.name,start)

def bake_source_action(source_arm,target_arm,source_action,new_name):
    source_arm.data.pose_position='POSE'
    target_arm.data.pose_position='POSE'
    source_arm.animation_data_create()
    target_arm.animation_data_create()
    source_arm.animation_data.action=source_action

    action=bpy.data.actions.new(name=new_name)
    target_arm.animation_data.action=action
    for pb in target_arm.pose.bones:
        pb.rotation_mode='QUATERNION'

    lo=int(math.floor(source_action.frame_range[0]))
    hi=int(math.ceil(source_action.frame_range[1]))
    common=[name for name in target_arm.pose.bones.keys() if source_arm.pose.bones.get(name)]
    if len(common)<20:
        fail(f"Too few matching bones for {new_name}: {len(common)}")

    for frame in range(lo,hi+1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        for name in common:
            src=source_arm.pose.bones[name]
            dst=target_arm.pose.bones[name]
            dst.matrix_basis=src.matrix_basis.copy()
            dst.keyframe_insert(data_path="location",frame=frame,group=name)
            dst.keyframe_insert(data_path="rotation_quaternion",frame=frame,group=name)
            dst.keyframe_insert(data_path="scale",frame=frame,group=name)

    target_arm.animation_data.action=None
    source_arm.animation_data.action=None

    # Stash as its own NLA track so glTF exporter sees discrete clips.
    tr=target_arm.animation_data.nla_tracks.new()
    tr.name="NLA_"+new_name
    tr.strips.new(new_name,lo,action)
    print("XZOGOT_MONJA_ACTION_BAKED",new_name,lo,hi,len(common))
    return {"name":new_name,"frames":[lo,hi],"bones":len(common)}

def render_preview(target_arm,monja_meshes,action,label,frame):
    target_arm.animation_data_create()
    target_arm.animation_data.action=action
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()

    mn,mx,size,order=bounds(monja_meshes)
    up=order[0]; side=order[1]; depth=order[2]
    axes=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
    upv=axes[up]; sidev=axes[side]; depthv=axes[depth]
    center=(mn+mx)*0.5

    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=900
    scene.render.resolution_y=1200
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    if scene.world is None:
        scene.world=bpy.data.worlds.new("CleanRigWorld")
    scene.world.color=(0.08,0.08,0.08)

    # Reuse/create camera and lights.
    cam=bpy.data.objects.get("CleanRigCamera")
    if cam is None:
        cd=bpy.data.cameras.new("CleanRigCamera")
        cam=bpy.data.objects.new("CleanRigCamera",cd)
        bpy.context.collection.objects.link(cam)
    scene.camera=cam
    cam.data.type='ORTHO'
    cam.data.ortho_scale=max(size[up]*1.10,size[side]*1.55)
    dist=max(size)*2.6
    cam.location=center+depthv*dist
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()

    if bpy.data.objects.get("CleanRigKey") is None:
        for name,loc,energy,sz in [
            ("CleanRigKey",center+depthv*dist*.5+sidev*size[side],1600,max(size)),
            ("CleanRigFill",center+depthv*dist*.35-sidev*size[side],900,max(size)),
            ("CleanRigTop",center+upv*size[up]*1.35,1000,max(size)*.8),
        ]:
            ld=bpy.data.lights.new(name=name,type='AREA'); ld.energy=energy; ld.size=sz
            lo=bpy.data.objects.new(name,ld); bpy.context.collection.objects.link(lo); lo.location=loc

    scene.render.filepath=str(OUT/(label+".png"))
    bpy.ops.render.render(write_still=True)
    target_arm.animation_data.action=None

def export_selected(target_arm,monja_meshes):
    bpy.ops.object.select_all(action='DESELECT')
    target_arm.select_set(True)
    for o in monja_meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=target_arm
    kwargs=dict(
        filepath=str(OUT_GLB),
        export_format='GLB',
        use_selection=True,
        export_animations=True,
        export_skins=True,
        export_apply=False,
    )
    props=bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    if 'export_nla_strips' in props: kwargs['export_nla_strips']=True
    if 'export_all_actions' in props: kwargs['export_all_actions']=True
    if 'export_force_sampling' in props: kwargs['export_force_sampling']=True
    if 'export_def_bones' in props: kwargs['export_def_bones']=True
    bpy.ops.export_scene.gltf(**kwargs)

# -------- build --------
reset()

# Import donor first; preserve it as animation source.
before=snapshot()
bpy.ops.import_scene.gltf(filepath=str(DONOR))
donor_objs=list(snapshot()-before)
donor_arms=arms(donor_objs)
donor_meshes=meshes(donor_objs)
if not donor_arms: fail("Donor armature missing")
source_arm=donor_arms[0]
source_arm.name="Mocap_Source_Armature"
source_arm.data.pose_position='REST'
if source_arm.animation_data:
    source_arm.animation_data.action=None
    for tr in source_arm.animation_data.nla_tracks: tr.mute=True
source_weight_mesh=armature_weighted_mesh(donor_meshes)

# Clean target armature starts as an independent copy of the known humanoid donor.
target_arm=source_arm.copy()
target_arm.data=source_arm.data.copy()
target_arm.name="Monja_Clean_Humanoid_Rig"
bpy.context.collection.objects.link(target_arm)
target_arm.animation_data_clear()
target_arm.data.pose_position='REST'

# Static Monja source.
before=snapshot()
bpy.ops.import_scene.gltf(filepath=str(MONJA))
monja_objs=list(snapshot()-before)
monja_meshes=meshes(monja_objs)
if not monja_meshes: fail("Monja mesh missing")
source_poly=sum(len(o.data.polygons) for o in monja_meshes)
source_vert=sum(len(o.data.vertices) for o in monja_meshes)

alignment=align_monja(monja_meshes,donor_meshes)
transfers=[transfer_weights(source_weight_mesh,o,target_arm) for o in monja_meshes]
if any(r["coverage"]<0.98 for r in transfers):
    fail("Weight coverage below 98%: "+str(transfers))

# Move character into the donor's authored clean reference pose and make it the
# target skeleton rest pose. This is the step missing from the old pipeline.
bind_action=find_action(BIND_TOKEN)
apply_bind_pose_as_rest(target_arm,bind_action)

# Bake clean zombie clips from untouched source rig into the new rest skeleton.
baked=[]
for role,token in REQUIRED.items():
    src=find_action(token)
    baked.append(bake_source_action(source_arm,target_arm,src,"Zombie_"+role.capitalize()+"_Clean"))

# Render actual Blender previews before source cleanup.
render_preview(target_arm,monja_meshes,None,"bind_pose",0)
walk_action=bpy.data.actions.get("Zombie_Walk_Clean")
if walk_action:
    mid=int((walk_action.frame_range[0]+walk_action.frame_range[1])*0.5)
    render_preview(target_arm,monja_meshes,walk_action,"walk_mid",mid)

# Remove donor visible geometry + source armature; keep clean target only.
for o in donor_meshes:
    if bpy.data.objects.get(o.name): bpy.data.objects.remove(bpy.data.objects.get(o.name),do_unlink=True)
if bpy.data.objects.get(source_arm.name): bpy.data.objects.remove(bpy.data.objects.get(source_arm.name),do_unlink=True)

clear_pose(target_arm)
target_arm.data.pose_position='REST'
export_selected(target_arm,monja_meshes)
if not OUT_GLB.is_file(): fail("GLB export missing")
size_bytes=OUT_GLB.stat().st_size

# Reimport actual output and verify geometry/rig/animations.
reset()
bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
out_mesh=meshes(); out_arm=arms()
out_actions=[a.name for a in bpy.data.actions]
out_poly=sum(len(o.data.polygons) for o in out_mesh)
out_vert=sum(len(o.data.vertices) for o in out_mesh)

report={
    "pipeline":"clean_blender_bindpose_rig_v1",
    "source":"assets/zombies/monja_basica.glb",
    "donor":"assets/zombie_mocap/retarget/UAL2_Standard.glb",
    "source_vertices":source_vert,
    "source_polygons":source_poly,
    "output_vertices":out_vert,
    "output_polygons":out_poly,
    "geometry_conserved":out_poly==source_poly,
    "armatures":len(out_arm),
    "bones":len(out_arm[0].data.bones) if out_arm else 0,
    "actions":out_actions,
    "alignment":alignment,
    "weight_transfer":transfers,
    "baked":baked,
    "output_bytes":size_bytes,
    "rig_mode":"smooth_weighted_humanoid_bind_pose",
    "old_rigid_region_parenting":False,
}
REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")

if not report["geometry_conserved"]: fail(f"Geometry changed {out_poly}/{source_poly}")
if len(out_arm)!=1 or report["bones"]<20: fail("Clean rig missing humanoid skeleton")
for role in ("Idle","Walk","Attack"):
    if not any(("Zombie_"+role+"_Clean").lower() in x.lower() for x in out_actions):
        fail("Missing baked action "+role)

print("XZOGOT_MONJA_CLEAN_BINDPOSE_GREEN",report["bones"])
print("XZOGOT_MONJA_CLEAN_WEIGHTS_GREEN",transfers)
print("XZOGOT_MONJA_CLEAN_ACTIONS_GREEN",out_actions)
print("XZOGOT_MONJA_CLEAN_GEOMETRY_GREEN",out_poly)
print("XZOGOT_MONJA_CLEAN_RIG_GREEN",size_bytes)
