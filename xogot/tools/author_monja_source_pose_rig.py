import bpy, json, math, sys
from pathlib import Path

try:
    import numpy as np
except Exception as exc:
    raise SystemExit("numpy required: %r" % (exc,))

from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]

def _tool_args():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = {}
    i = 0
    while i < len(raw):
        key = raw[i]
        if key.startswith("--") and i + 1 < len(raw):
            out[key[2:]] = raw[i + 1]
            i += 2
        else:
            i += 1
    return out

ARGS = _tool_args()
PROFILE = ARGS.get("profile", "normal").strip().lower()
MONJA = Path(ARGS.get("source", str(ROOT / "assets/zombies/monja_basica.glb"))).resolve()
DONOR = ROOT / "assets/zombie_mocap/retarget/UAL2_Standard.glb"
OUT = Path(ARGS.get("output-dir", str(ROOT / "build/monja-source-pose-rig"))).resolve()
OUT.mkdir(parents=True, exist_ok=True)
OUT_GLB = OUT / ARGS.get(
    "output-name",
    "monja_black_white_clean_rig.glb" if PROFILE == "elite" else "monja_basica_clean_rig.glb",
)
REPORT = OUT / "report.json"

# The clips come from the humanoid motion-capture donor.  The elite keeps the
# same locomotion grammar so networking/gameplay remains compatible, but gets a
# heavier hook attack.  Both variants now carry hit/death clips so the runtime
# can actually show those states instead of deleting the model immediately.
if PROFILE == "elite":
    CLIPS = {
        "Zombie_Idle_Clean": "Zombie_Idle_Loop",
        "Zombie_Walk_Clean": "Zombie_Walk_Fwd_Loop",
        "Zombie_Attack_Clean": "Melee_Hook",
        "Zombie_Hit_Clean": "Hit_Knockback",
        "Zombie_Death_Clean": "LayToIdle",
    }
else:
    CLIPS = {
        "Zombie_Idle_Clean": "Zombie_Idle_Loop",
        "Zombie_Walk_Clean": "Zombie_Walk_Fwd_Loop",
        "Zombie_Attack_Clean": "Zombie_Scratch",
        "Zombie_Hit_Clean": "Hit_Knockback",
        "Zombie_Death_Clean": "LayToIdle",
    }

MAJOR_BONES = [
    "root","pelvis","spine_01","spine_02","spine_03","neck_01","Head",
    "clavicle_l","upperarm_l","lowerarm_l","hand_l",
    "clavicle_r","upperarm_r","lowerarm_r","hand_r",
    "thigh_l","calf_l","foot_l","ball_l",
    "thigh_r","calf_r","foot_r","ball_r",
]
DEFORM_BONES = [
    "pelvis","spine_01","spine_02","spine_03","neck_01","Head",
    "upperarm_l","lowerarm_l","hand_l","upperarm_r","lowerarm_r","hand_r",
    "thigh_l","calf_l","foot_l","thigh_r","calf_r","foot_r",
    "skirt_l","skirt_r",
]

def fail(msg):
    print("XZOGOT_MONJA_SOURCE_POSE_FAIL", msg)
    raise SystemExit(2)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def objs(kind=None):
    out=list(bpy.context.scene.objects)
    return [o for o in out if kind is None or o.type==kind]

def snapshot():
    return set(bpy.context.scene.objects)

def get_world_vertices(mesh_objects):
    chunks=[]
    owners=[]
    for oi,o in enumerate(mesh_objects):
        n=len(o.data.vertices)
        raw=np.empty(n*3,dtype=np.float32)
        o.data.vertices.foreach_get("co",raw)
        p=raw.reshape((-1,3)).astype(np.float64)
        M=np.array(o.matrix_world,dtype=np.float64)
        homo=np.concatenate([p,np.ones((len(p),1),dtype=np.float64)],axis=1)
        world=(homo @ M.T)[:,:3]
        chunks.append(world)
        owners.append((o,len(p)))
    return np.concatenate(chunks,axis=0), owners

def bounds_np(v):
    return v.min(axis=0), v.max(axis=0)

def robust_center(v, mask, fallback):
    pts=v[mask]
    if len(pts)<32:
        return np.array(fallback,dtype=np.float64)
    return np.median(pts,axis=0)

def qpoint(mn,mx,xn,yn,zn):
    return mn + (mx-mn)*np.array([xn,yn,zn],dtype=np.float64)

def landmarks_from_geometry(v):
    mn,mx=bounds_np(v)
    size=mx-mn
    c=(mn+mx)*0.5
    nx=(v[:,0]-c[0])/max(size[0]*0.5,1e-8)
    ny=(v[:,1]-c[1])/max(size[1]*0.5,1e-8)
    nz=(v[:,2]-mn[2])/max(size[2],1e-8)

    # The source is Z-up, X left/right, Y front/back.  Use robust medians from
    # semantic bands rather than assuming an A/T-pose.
    pelvis=robust_center(v,(nz>0.52)&(nz<0.62)&(np.abs(nx)<0.34),qpoint(mn,mx,.5,.5,.57))
    chest=robust_center(v,(nz>0.69)&(nz<0.76)&(np.abs(nx)<0.30),qpoint(mn,mx,.5,.5,.73))
    neck=robust_center(v,(nz>0.77)&(nz<0.83)&(np.abs(nx)<0.28),qpoint(mn,mx,.5,.5,.80))
    head=robust_center(v,(nz>0.84)&(nz<0.96)&(np.abs(nx)<0.36),qpoint(mn,mx,.5,.5,.90))

    lm={
        "pelvis":pelvis,
        "spine1":pelvis*0.70+chest*0.30,
        "spine2":pelvis*0.43+chest*0.57,
        "spine3":chest,
        "neck":neck,
        "head":head,
    }

    for side,sgn in (("l",-1.0),("r",1.0)):
        side_mask=(nx*sgn>0.20)
        shoulder=robust_center(
            v,(nz>0.68)&(nz<0.78)&side_mask&(np.abs(nx)<0.70),
            [c[0]+sgn*size[0]*0.23,c[1],mn[2]+size[2]*0.73]
        )
        wrist=robust_center(
            v,(nz>0.40)&(nz<0.58)&side_mask&(np.abs(nx)>0.42),
            [c[0]+sgn*size[0]*0.34,c[1]-size[1]*0.10,mn[2]+size[2]*0.49]
        )
        # Elbow from the source cloud near the middle of the actual arm.
        arm_mid=(shoulder+wrist)*0.5
        elbow=robust_center(
            v,(nz>0.54)&(nz<0.69)&side_mask&(np.abs(nx)>0.30),
            arm_mid
        )
        hand=robust_center(
            v,(nz>0.37)&(nz<0.54)&side_mask&(np.abs(nx)>0.48),
            wrist + (wrist-elbow)*0.16
        )

        hip=np.array([pelvis[0]+sgn*size[0]*0.085,pelvis[1],mn[2]+size[2]*0.54])
        low=(nz<0.15)&side_mask
        low_pts=v[low]
        if len(low_pts)>=32:
            # Feet/shoes protrude in depth beyond the robe.  Bias to depth extrema,
            # then use the robust median so the skirt hem does not become the ankle.
            depth_dev=np.abs(low_pts[:,1]-c[1])
            keep=low_pts[depth_dev>=np.percentile(depth_dev,65.0)]
            foot_center=np.median(keep,axis=0) if len(keep)>=16 else np.median(low_pts,axis=0)
        else:
            foot_center=np.array([c[0]+sgn*size[0]*0.10,c[1],mn[2]+size[2]*0.055])
        ankle=foot_center.copy()
        ankle[2]=mn[2]+size[2]*0.075
        toe=foot_center.copy()
        # Preserve whichever Y direction the source boot protrudes toward.
        dy=foot_center[1]-c[1]
        if abs(dy)<size[1]*0.04:
            dy=-size[1]*0.10
        toe[1]=foot_center[1]+math.copysign(size[1]*0.075,dy)
        toe[2]=mn[2]+size[2]*0.045
        knee=hip*0.48+ankle*0.52
        # Slight forward knee bias follows the source stance without overfitting robe.
        knee[1]=(hip[1]*0.35+ankle[1]*0.65)

        lm["shoulder_"+side]=shoulder
        lm["elbow_"+side]=elbow
        lm["wrist_"+side]=wrist
        lm["hand_"+side]=hand
        lm["hip_"+side]=hip
        lm["knee_"+side]=knee
        lm["ankle_"+side]=ankle
        lm["toe_"+side]=toe

    # Basic semantic plausibility gates.
    h=size[2]
    for side in ("l","r"):
        if not (lm["shoulder_"+side][2] > lm["elbow_"+side][2] > lm["hand_"+side][2]-h*0.08):
            fail("arm landmark order invalid "+side+" "+repr({k:lm[k].tolist() for k in ("shoulder_"+side,"elbow_"+side,"hand_"+side)}))
        if not (lm["hip_"+side][2] > lm["knee_"+side][2] > lm["ankle_"+side][2]):
            fail("leg landmark order invalid "+side)
    return lm,mn,mx

def add_bone(arm, name, head, tail, parent=None, deform=True):
    eb=arm.data.edit_bones.new(name)
    eb.head=Vector(head)
    eb.tail=Vector(tail)
    if (eb.tail-eb.head).length<1e-4:
        eb.tail=eb.head+Vector((0,0,0.01))
    if parent:
        eb.parent=arm.data.edit_bones.get(parent)
    eb.use_deform=deform
    try:
        eb.align_roll(Vector((0.0,-1.0,0.0)))
    except Exception:
        pass
    return eb

def build_armature(lm,mn,mx):
    data=bpy.data.armatures.new("Monja_SourcePose_ArmatureData")
    arm=bpy.data.objects.new("Monja_SourcePose_Rig",data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')

    root_head=np.array([lm["pelvis"][0],lm["pelvis"][1],mn[2]])
    add_bone(arm,"root",root_head,lm["pelvis"],None,False)
    add_bone(arm,"pelvis",lm["pelvis"],lm["spine1"],"root")
    add_bone(arm,"spine_01",lm["spine1"],lm["spine2"],"pelvis")
    add_bone(arm,"spine_02",lm["spine2"],lm["spine3"],"spine_01")
    add_bone(arm,"spine_03",lm["spine3"],lm["neck"],"spine_02")
    add_bone(arm,"neck_01",lm["neck"],lm["head"],"spine_03")
    head_tail=lm["head"]+np.array([0.0,0.0,(mx[2]-mn[2])*0.075])
    add_bone(arm,"Head",lm["head"],head_tail,"neck_01")

    for side in ("l","r"):
        sh=lm["shoulder_"+side]; el=lm["elbow_"+side]; wr=lm["wrist_"+side]; hand=lm["hand_"+side]
        clav_head=lm["spine3"]*0.88+sh*0.12
        add_bone(arm,"clavicle_"+side,clav_head,sh,"spine_03")
        add_bone(arm,"upperarm_"+side,sh,el,"clavicle_"+side)
        add_bone(arm,"lowerarm_"+side,el,wr,"upperarm_"+side)
        hand_tail=hand+(hand-wr)*0.65
        add_bone(arm,"hand_"+side,wr,hand_tail,"lowerarm_"+side)

        hip=lm["hip_"+side]; knee=lm["knee_"+side]; ankle=lm["ankle_"+side]; toe=lm["toe_"+side]
        add_bone(arm,"thigh_"+side,hip,knee,"pelvis")
        add_bone(arm,"calf_"+side,knee,ankle,"thigh_"+side)
        add_bone(arm,"foot_"+side,ankle,toe,"calf_"+side)
        ball_tail=toe+(toe-ankle)*0.45
        add_bone(arm,"ball_"+side,toe,ball_tail,"foot_"+side)

    skirt_z=mn[2]+(mx[2]-mn[2])*0.25
    skirt_tail_z=mn[2]+(mx[2]-mn[2])*0.05
    for side,sgn in (("l",-1.0),("r",1.0)):
        sh=np.array([lm["pelvis"][0]+sgn*(mx[0]-mn[0])*0.10,lm["pelvis"][1],skirt_z])
        st=np.array([lm["pelvis"][0]+sgn*(mx[0]-mn[0])*0.18,lm["pelvis"][1],skirt_tail_z])
        add_bone(arm,"skirt_"+side,sh,st,"pelvis")

    bpy.ops.object.mode_set(mode='OBJECT')
    arm.data.pose_position='REST'
    return arm

def point_segment_distance(points,a,b):
    ab=b-a
    denom=float(np.dot(ab,ab))
    if denom<1e-12:
        return np.linalg.norm(points-a,axis=1)
    t=np.clip(((points-a)@ab)/denom,0.0,1.0)
    q=a+t[:,None]*ab
    return np.linalg.norm(points-q,axis=1)

def bone_segment(arm,name):
    b=arm.data.bones[name]
    return np.array(b.head_local,dtype=np.float64),np.array(b.tail_local,dtype=np.float64)

def assign_quantized_group(obj,group_name,global_weights,offset,count,levels=12):
    w=np.clip(global_weights[offset:offset+count],0.0,1.0)
    q=np.rint(w*levels).astype(np.int16)
    vg=obj.vertex_groups.new(name=group_name)
    for lvl in range(1,levels+1):
        ids=np.flatnonzero(q==lvl)
        if len(ids):
            vg.add(ids.tolist(),float(lvl)/float(levels),'REPLACE')

def build_weights(v,owners,arm,lm,mn,mx):
    n=len(v)
    W={name:np.zeros(n,dtype=np.float32) for name in DEFORM_BONES}
    size=mx-mn; c=(mn+mx)*0.5
    nx=(v[:,0]-c[0])/max(size[0]*0.5,1e-8)
    nz=(v[:,2]-mn[2])/max(size[2],1e-8)

    # Head + neck.
    head_t=np.clip((nz-0.78)/0.18,0,1)
    W["Head"] += (head_t**1.3).astype(np.float32)
    W["neck_01"] += (np.clip(1.0-np.abs(nz-0.79)/0.08,0,1)*0.75).astype(np.float32)

    # Torso vertical blend. Restrict progressively as vertices move into sleeves.
    torso_gate=np.clip(1.15-np.maximum(np.abs(nx)-0.30,0)*1.55,0.15,1.0)
    centers=[("pelvis",0.55,0.085),("spine_01",0.61,0.075),("spine_02",0.68,0.075),("spine_03",0.74,0.070)]
    for name,zc,wid in centers:
        W[name] += (np.clip(1.0-np.abs(nz-zc)/wid,0,1)*torso_gate).astype(np.float32)

    # Arms: distance to source-pose bones, gated by side and upper-body band.
    diag=max(float(np.linalg.norm(size)),1e-6)
    for side,sgn in (("l",-1.0),("r",1.0)):
        side_gate=np.clip((nx*sgn-0.10)/0.42,0,1)
        z_gate=np.clip((nz-0.34)/0.18,0,1)*np.clip((0.82-nz)/0.14,0,1)
        gate=side_gate*z_gate
        names=["upperarm_"+side,"lowerarm_"+side,"hand_"+side]
        d=[]
        for name in names:
            a,b=bone_segment(arm,name)
            d.append(point_segment_distance(v,a,b))
        D=np.stack(d,axis=1)
        score=np.exp(-((D/(diag*0.085))**2))*gate[:,None]
        ss=score.sum(axis=1)+1e-8
        score=score/ss[:,None]
        for j,name in enumerate(names):
            W[name]+=score[:,j].astype(np.float32)*gate.astype(np.float32)

    # Lower robe stays mostly pelvis/skirt; only vertices near leg/foot segments get leg weights.
    lower=(nz<0.55).astype(np.float32)
    leftmix=np.clip((-nx+0.12)/0.7,0,1)
    rightmix=np.clip((nx+0.12)/0.7,0,1)
    W["skirt_l"] += lower*leftmix*0.90
    W["skirt_r"] += lower*rightmix*0.90
    W["pelvis"] += lower*0.18

    for side,sgn in (("l",-1.0),("r",1.0)):
        side_gate=np.clip((nx*sgn+0.10)/0.65,0,1)
        names=["thigh_"+side,"calf_"+side,"foot_"+side]
        d=[]
        for name in names:
            a,b=bone_segment(arm,name)
            d.append(point_segment_distance(v,a,b))
        D=np.stack(d,axis=1)
        # Tight radius prevents the wide dress from being split between legs.
        score=np.exp(-((D/(diag*0.045))**2))*side_gate[:,None]
        leg_gate=np.clip((0.54-nz)/0.30,0,1)
        score*=leg_gate[:,None]
        ssum=score.sum(axis=1)
        near=np.clip(ssum*2.5,0,0.92)
        norm=score/(ssum[:,None]+1e-8)
        for j,name in enumerate(names):
            W[name]+=norm[:,j].astype(np.float32)*near.astype(np.float32)

    # Normalize and guarantee every vertex has a stable owner.
    stack=np.stack([W[n] for n in DEFORM_BONES],axis=1)
    sums=stack.sum(axis=1)
    unowned=sums<1e-5
    stack[unowned,DEFORM_BONES.index("pelvis")]=1.0
    sums=stack.sum(axis=1)
    stack/=sums[:,None]

    # Production skinning gate: keep at most four bone influences per vertex.
    # The first source-pose attempt kept tiny non-zero weights on many groups,
    # which made Blender spend tens of minutes assigning ~1M vertices.  Top-4
    # preserves smooth deformation while matching normal real-time skinning.
    if stack.shape[1] > 4:
        top4=np.argpartition(stack,-4,axis=1)[:,-4:]
        keep=np.zeros_like(stack,dtype=bool)
        rows=np.arange(stack.shape[0])[:,None]
        keep[rows,top4]=True
        stack=np.where(keep,stack,0.0)
    stack[stack<0.025]=0.0
    sums=stack.sum(axis=1)
    zero=sums<1e-6
    stack[zero,DEFORM_BONES.index("pelvis")]=1.0
    sums=stack.sum(axis=1)
    stack/=sums[:,None]

    influences=(stack>0.0).sum(axis=1)
    max_influences=int(influences.max())
    mean_influences=float(influences.mean())
    if max_influences>4:
        fail("weight influence cap failed")
    print("XZOGOT_MONJA_TOP4_WEIGHTS_GREEN",max_influences,round(mean_influences,4))

    for j,name in enumerate(DEFORM_BONES):
        W[name]=stack[:,j].astype(np.float32)

    # Attach groups per mesh preserving original topology exactly.
    offset=0
    reports=[]
    for obj,count in owners:
        for name in DEFORM_BONES:
            assign_quantized_group(obj,name,W[name],offset,count)
        mod=obj.modifiers.new("Monja_SourcePose_Armature","ARMATURE")
        mod.object=arm
        world=obj.matrix_world.copy()
        obj.parent=arm
        obj.matrix_parent_inverse=arm.matrix_world.inverted()
        obj.matrix_world=world
        # Coverage = vertices with at least one quantized group.
        covered=sum(1 for vert in obj.data.vertices if len(vert.groups)>0)
        reports.append({
            "mesh":obj.name,
            "vertices":count,
            "covered":covered,
            "coverage":covered/max(1,count),
            "groups":len(obj.vertex_groups),
        })
        offset+=count
    return reports

def rest_local(arm,name):
    b=arm.data.bones[name]
    if b.parent:
        return b.parent.matrix_local.inverted() @ b.matrix_local
    return b.matrix_local.copy()

def pose_local(arm,name):
    p=arm.pose.bones[name]
    if p.parent:
        return p.parent.matrix.inverted() @ p.matrix
    return p.matrix.copy()

def find_action(token):
    hits=[a for a in bpy.data.actions if token.lower() in a.name.lower()]
    if not hits:
        fail("missing donor action "+token)
    return hits[0]

def retarget_action(source,target,source_action,new_name,height_scale):
    source.animation_data_create()
    target.animation_data_create()
    source.animation_data.action=source_action
    action=bpy.data.actions.new(new_name)
    target.animation_data.action=action
    lo=int(math.floor(source_action.frame_range[0]))
    hi=int(math.ceil(source_action.frame_range[1]))

    common=[n for n in MAJOR_BONES if source.pose.bones.get(n) and target.pose.bones.get(n)]
    if len(common)<20:
        fail("too few common retarget bones "+str(common))

    src_rest={n:rest_local(source,n) for n in common}
    tgt_rest={n:rest_local(target,n) for n in common}

    # Evaluate hierarchy top-down by data bone order.
    ordered=[b.name for b in target.data.bones if b.name in common]
    for frame in range(lo,hi+1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        target_world={}
        for name in ordered:
            s_local=pose_local(source,name)
            delta=src_rest[name].inverted() @ s_local
            # In-place locomotion: keep root planted. Pelvis gets scaled vertical bob only.
            if name=="root":
                delta.translation=Vector((0.0,0.0,0.0))
            elif name=="pelvis":
                tr=delta.translation
                delta.translation=Vector((0.0,0.0,tr.z*height_scale))
            desired_local=tgt_rest[name] @ delta
            tb=target.pose.bones[name]
            parent_name=tb.parent.name if tb.parent and tb.parent.name in target_world else None
            desired_world=(target_world[parent_name] @ desired_local) if parent_name else desired_local
            tb.matrix=desired_world
            target_world[name]=desired_world.copy()
            tb.keyframe_insert(data_path="location",frame=frame,group=name)
            if tb.rotation_mode!='QUATERNION':
                tb.rotation_mode='QUATERNION'
            tb.keyframe_insert(data_path="rotation_quaternion",frame=frame,group=name)
            tb.keyframe_insert(data_path="scale",frame=frame,group=name)

    source.animation_data.action=None
    target.animation_data.action=None
    tr=target.animation_data.nla_tracks.new()
    tr.name="NLA_"+new_name
    tr.strips.new(new_name,lo,action)
    print("XZOGOT_MONJA_SOURCE_POSE_CLIP_GREEN",new_name,lo,hi,len(common))
    return {"name":new_name,"frames":[lo,hi],"bones":len(common)}

def triangle_count(mesh_objects):
    return sum(mesh_surface_stats(mesh_objects)["triangles"] for _ in [0])

def mesh_surface_stats(mesh_objects):
    total_triangles=0
    total_area=0.0
    degenerate=0
    for obj in mesh_objects:
        mesh=obj.data
        mesh.calc_loop_triangles()
        tri_n=len(mesh.loop_triangles)
        total_triangles += tri_n
        if tri_n==0:
            continue
        raw=np.empty(len(mesh.vertices)*3,dtype=np.float32)
        mesh.vertices.foreach_get("co",raw)
        local=raw.reshape((-1,3)).astype(np.float64)
        M=np.array(obj.matrix_world,dtype=np.float64)
        homo=np.concatenate([local,np.ones((len(local),1),dtype=np.float64)],axis=1)
        world=(homo @ M.T)[:,:3]
        idx=np.empty(tri_n*3,dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices",idx)
        tri=world[idx.reshape((-1,3))]
        cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        areas=0.5*np.linalg.norm(cross,axis=1)
        total_area += float(areas.sum())
        degenerate += int(np.count_nonzero(areas <= 1e-12))
    return {
        "triangles":int(total_triangles),
        "surface_area":float(total_area),
        "degenerate_triangles":int(degenerate),
    }

def render_preview(arm,mesh_objects,action,label,frame):
    arm.animation_data_create()
    arm.animation_data.action=action
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    v,_=get_world_vertices(mesh_objects)
    mn,mx=bounds_np(v); size=mx-mn; center=(mn+mx)*0.5

    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=600 if PROFILE=="elite" else 900
    scene.render.resolution_y=800 if PROFILE=="elite" else 1200
    scene.render.resolution_percentage=100
    if PROFILE=="elite" and hasattr(scene,"eevee"):
        try:
            scene.eevee.taa_render_samples=24
        except Exception:
            pass
    scene.render.image_settings.file_format='PNG'
    if scene.world is None:
        scene.world=bpy.data.worlds.new("MonjaSourcePoseWorld")
    scene.world.color=(0.08,0.08,0.08)

    cam_data=bpy.data.cameras.new("MonjaSourcePoseCamera")
    cam=bpy.data.objects.new("MonjaSourcePoseCamera",cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera=cam
    cam_data.type='ORTHO'
    cam_data.ortho_scale=max(size[2]*1.08,size[0]*1.75)
    dist=max(size)*2.8
    # True front = look along -Y, Z stays vertical.
    cam.location=Vector((center[0],center[1]-dist,center[2]))
    cam.rotation_euler=(Vector(center)-cam.location).to_track_quat('-Z','Y').to_euler()

    for nm,loc,energy in [
        ("Key",Vector((center[0]+size[0],center[1]-dist*0.4,center[2]+size[2]*0.45)),1500),
        ("Fill",Vector((center[0]-size[0],center[1]-dist*0.25,center[2]+size[2]*0.20)),850),
    ]:
        ld=bpy.data.lights.new(nm,type='AREA'); ld.energy=energy; ld.size=max(size)*1.3
        lo=bpy.data.objects.new(nm,ld); bpy.context.collection.objects.link(lo); lo.location=loc

    scene.render.filepath=str(OUT/(label+".png"))
    bpy.ops.render.render(write_still=True)
    arm.animation_data.action=None

def export_selected(arm,mesh_objects):
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    for o in mesh_objects:o.select_set(True)
    bpy.context.view_layer.objects.active=arm
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
    if 'export_all_actions' in props: kwargs['export_all_actions']=False
    if 'export_force_sampling' in props: kwargs['export_force_sampling']=True
    if 'export_def_bones' in props: kwargs['export_def_bones']=True
    bpy.ops.export_scene.gltf(**kwargs)

# ---- main ----
reset()

before=snapshot()
bpy.ops.import_scene.gltf(filepath=str(MONJA))
monja_objs=list(snapshot()-before)
monja_meshes=[o for o in monja_objs if o.type=="MESH"]
if not monja_meshes: fail("monja mesh missing")
source_vertices=sum(len(o.data.vertices) for o in monja_meshes)
source_polygons=sum(len(o.data.polygons) for o in monja_meshes)
source_surface=mesh_surface_stats(monja_meshes)
source_triangles=source_surface["triangles"]
v,owners=get_world_vertices(monja_meshes)
lm,mn,mx=landmarks_from_geometry(v)
source_height=float(mx[2]-mn[2])

arm=build_armature(lm,mn,mx)
weights=build_weights(v,owners,arm,lm,mn,mx)
if any(r["coverage"]<0.995 for r in weights):
    fail("source-pose weight coverage low "+repr(weights))

# Geometry in REST must be byte-for-byte topology-equivalent and spatially unchanged.
rest_v,_=get_world_vertices(monja_meshes)
rest_rms=float(np.sqrt(np.mean(np.sum((rest_v-v)**2,axis=1))))
rest_max=float(np.sqrt(np.max(np.sum((rest_v-v)**2,axis=1))))
pose_match_validated=rest_max < max(source_height*1e-5,1e-6)

# Donor animation source.
before=snapshot()
bpy.ops.import_scene.gltf(filepath=str(DONOR))
donor_objs=list(snapshot()-before)
donor_arms=[o for o in donor_objs if o.type=="ARMATURE"]
donor_meshes=[o for o in donor_objs if o.type=="MESH"]
if not donor_arms: fail("donor armature missing")
source_arm=donor_arms[0]
source_arm.name="Mocap_Source_Armature"
source_height_donor=source_arm.data.bones["Head"].tail_local.z-source_arm.data.bones["root"].head_local.z
height_scale=source_height/max(abs(source_height_donor),1e-5)

baked=[]
for new_name,token in CLIPS.items():
    baked.append(retarget_action(source_arm,arm,find_action(token),new_name,height_scale))

# Hide donor so previews contain only the nun.
for o in donor_meshes+[source_arm]:
    o.hide_render=True
    o.hide_viewport=True

render_preview(arm,monja_meshes,None,"bind_pose",0)
walk=bpy.data.actions.get("Zombie_Walk_Clean")
if walk:
    mid=int((walk.frame_range[0]+walk.frame_range[1])*0.5)
    render_preview(arm,monja_meshes,walk,"walk_mid",mid)

# Remove donor objects before export.
for o in donor_meshes+[source_arm]:
    if bpy.data.objects.get(o.name):
        bpy.data.objects.remove(bpy.data.objects.get(o.name),do_unlink=True)

# Purge donor actions before glTF export. On high-density meshes Blender 4.0's
# exporter otherwise tries to remap every donor finger/toe curve onto the
# 23-bone gameplay rig, emitting thousands of "pose.bones[...] not found"
# warnings and spending tens of minutes on actions that must not ship anyway.
# Keep only actions referenced by the target Monja's NLA strips.
keep_action_names=set()
if arm.animation_data:
    if arm.animation_data.action:
        keep_action_names.add(arm.animation_data.action.name)
    for track in arm.animation_data.nla_tracks:
        for strip in track.strips:
            if strip.action:
                keep_action_names.add(strip.action.name)
for action in list(bpy.data.actions):
    if action.name not in keep_action_names:
        bpy.data.actions.remove(action)
print("XZOGOT_MONJA_DONOR_ACTIONS_PURGED_GREEN",sorted(keep_action_names),len(bpy.data.actions))

arm.data.pose_position='REST'
if arm.animation_data:
    arm.animation_data.action=None
export_selected(arm,monja_meshes)
if not OUT_GLB.is_file(): fail("output glb missing")

# Reimport exported file and validate actual deliverable.
reset()
bpy.ops.import_scene.gltf(filepath=str(OUT_GLB))
out_mesh=objs("MESH"); out_arm=objs("ARMATURE")
out_actions=[a.name for a in bpy.data.actions]
out_vertices=sum(len(o.data.vertices) for o in out_mesh)
out_polygons=sum(len(o.data.polygons) for o in out_mesh)
out_surface=mesh_surface_stats(out_mesh)
out_triangles=out_surface["triangles"]
extra_triangles=out_triangles-source_triangles
area_delta=abs(out_surface["surface_area"]-source_surface["surface_area"])
area_tolerance=max(source_surface["surface_area"]*1e-5,1e-8)
geometry_conserved=(
    extra_triangles>=0
    and extra_triangles<=256
    and area_delta<=area_tolerance
)

report={
    "schema":1,
    "pipeline":"source_pose_manual_humanoid_rig_v2",
    "source":str(MONJA.relative_to(ROOT)) if ROOT in MONJA.parents else str(MONJA),
    "profile":PROFILE,
    "donor":"assets/zombie_mocap/retarget/UAL2_Standard.glb",
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
    "geometry_conserved":geometry_conserved,
    "geometry_gate":"no_triangle_loss_plus_surface_area_conservation",
    "export_reindexed_vertices":out_vertices!=source_vertices,
    "export_triangulated_nontri_faces":out_polygons!=source_polygons,
    "armatures":len(out_arm),
    "bones":len(out_arm[0].data.bones) if out_arm else 0,
    "actions":out_actions,
    "weight_transfer":weights,
    "baked":baked,
    "output_bytes":OUT_GLB.stat().st_size,
    "rig_mode":"source_pose_smooth_weighted_humanoid",
    "old_rigid_region_parenting":False,
    "pose_match":{
        "validated":bool(pose_match_validated),
        "strategy":"rig_built_on_original_source_pose_no_geometry_repose",
        "rest_vertex_rms":rest_rms,
        "rest_vertex_max":rest_max,
    },
    "landmarks":{k:[round(float(x),6) for x in val] for k,val in lm.items()},
}
REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")

if not report["geometry_conserved"]:
    fail(
        f"surface geometry changed tris={out_triangles}/{source_triangles} "
        f"delta={extra_triangles} area_delta={area_delta} tol={area_tolerance}"
    )
if not report["pose_match"]["validated"]: fail("rest pose moved source geometry")
if len(out_arm)!=1 or report["bones"]<20: fail("humanoid skeleton missing")
for token in ("Idle_Clean","Walk_Clean","Attack_Clean","Hit_Clean","Death_Clean"):
    if not any(token.lower() in n.lower() for n in out_actions):
        fail("missing exported action "+token)

print("XZOGOT_MONJA_SOURCE_POSE_LANDMARKS_GREEN",json.dumps(report["landmarks"]))
print("XZOGOT_MONJA_SOURCE_POSE_WEIGHTS_GREEN",json.dumps(weights))
print("XZOGOT_MONJA_SOURCE_POSE_MATCH_GREEN",rest_rms,rest_max)
print("XZOGOT_MONJA_SOURCE_POSE_ANIMS_GREEN",out_actions)
print("XZOGOT_MONJA_SOURCE_POSE_GEOMETRY_GREEN",out_vertices,out_polygons,out_triangles)
print("XZOGOT_MONJA_SOURCE_POSE_PROFILE_GREEN",PROFILE)
print("XZOGOT_MONJA_SOURCE_POSE_RIG_GREEN",report["bones"],report["output_bytes"])
