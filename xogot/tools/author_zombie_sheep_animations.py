import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector

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
SOURCE_DIR = ROOT / "assets" / "zombies" / "sheep" / "source"
OUT = Path(ARGS.get("output-dir", str(ROOT / "build" / "sheep-animated"))).resolve()
OUT.mkdir(parents=True, exist_ok=True)

SOURCES = {
    "sheep_runner": Path(ARGS.get("runner-source", str(SOURCE_DIR / "sheep_runner.glb"))).resolve(),
    "sheep_brute": Path(ARGS.get("brute-source", str(SOURCE_DIR / "sheep_brute.glb"))).resolve(),
}

REQUIRED = ["Sheep_Idle", "Sheep_Run", "Sheep_Attack", "Sheep_Death"]

def fail(msg):
    print("XZOGOT_SHEEP_AUTHOR_FAIL", msg)
    raise SystemExit(2)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def meshes():
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]

def armatures():
    return [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]

def tri_count(objs):
    total = 0
    for o in objs:
        for p in o.data.polygons:
            total += max(1, len(p.vertices) - 2)
    return total

def clear_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)

def key_pose(pb, frame, rot=(0.0,0.0,0.0), loc=None):
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = rot
    if loc is not None:
        pb.location = loc
    pb.keyframe_insert(data_path="rotation_euler", frame=frame, group=pb.name)
    if loc is not None:
        pb.keyframe_insert(data_path="location", frame=frame, group=pb.name)

def pb(arm, name):
    p = arm.pose.bones.get(name)
    if p is None:
        fail("Missing sheep bone " + name)
    return p

def find_optional(arm, names):
    for name in names:
        p = arm.pose.bones.get(name)
        if p is not None:
            return p
    return None

def create_action(arm, name):
    if arm.animation_data is None:
        arm.animation_data_create()
    action = bpy.data.actions.new(name=name)
    arm.animation_data.action = action
    clear_pose(arm)
    return action

def stash_action(arm, action, start_frame):
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = None
    track = arm.animation_data.nla_tracks.new()
    track.name = "NLA_" + action.name
    strip = track.strips.new(action.name, start_frame, action)
    strip.action_frame_start = action.frame_range[0]
    strip.action_frame_end = action.frame_range[1]
    return track

def author_idle(arm):
    action = create_action(arm, "Sheep_Idle")
    spine = find_optional(arm, ["tripo::Spine_1", "tripo::Spine_2", "tripo::Spine_0"])
    head = find_optional(arm, ["tripo::Head_0", "tripo::Head_1"])
    frames = [1, 18, 36, 54]
    for frame, sign in zip(frames, [0.0, 1.0, -1.0, 0.0]):
        if spine: key_pose(spine, frame, (math.radians(1.6)*sign, 0.0, 0.0))
        if head: key_pose(head, frame, (math.radians(-1.2)*sign, 0.0, math.radians(2.0)*sign))
    return action

def author_run(arm, brute=False):
    action = create_action(arm, "Sheep_Run")
    names = {
        "fl": "tripo::0_Left_Limb_0",
        "fr": "tripo::0_Right_Limb_0",
        "rl": "tripo::1_Left_Limb_0",
        "rr": "tripo::1_Right_Limb_0",
        "fl1": "tripo::0_Left_Limb_1",
        "fr1": "tripo::0_Right_Limb_1",
        "rl1": "tripo::1_Left_Limb_1",
        "rr1": "tripo::1_Right_Limb_1",
    }
    bones = {k: pb(arm, v) for k,v in names.items()}
    spine = find_optional(arm, ["tripo::Spine_1", "tripo::Spine_2"])
    head = find_optional(arm, ["tripo::Head_0", "tripo::Head_1"])
    amp = math.radians(22.0 if brute else 30.0)
    knee = math.radians(13.0 if brute else 18.0)
    for frame, phase in [(1,0.0),(7,math.pi/2),(13,math.pi),(19,3*math.pi/2),(25,2*math.pi)]:
        s = math.sin(phase)
        c = math.cos(phase)
        # Diagonal gait: FL + RR oppose FR + RL.
        key_pose(bones["fl"], frame, (0.0,0.0, amp*s))
        key_pose(bones["rr"], frame, (0.0,0.0, amp*s))
        key_pose(bones["fr"], frame, (0.0,0.0,-amp*s))
        key_pose(bones["rl"], frame, (0.0,0.0,-amp*s))
        key_pose(bones["fl1"], frame, (0.0,0.0,-knee*s))
        key_pose(bones["rr1"], frame, (0.0,0.0,-knee*s))
        key_pose(bones["fr1"], frame, (0.0,0.0, knee*s))
        key_pose(bones["rl1"], frame, (0.0,0.0, knee*s))
        if spine: key_pose(spine, frame, (math.radians(2.5)*c,0.0,0.0))
        if head: key_pose(head, frame, (math.radians(-2.0)*c,0.0,math.radians(1.2)*s))
    return action

def author_attack(arm, brute=False):
    action = create_action(arm, "Sheep_Attack")
    spine = find_optional(arm, ["tripo::Spine_2", "tripo::Spine_1"])
    head = find_optional(arm, ["tripo::Head_0", "tripo::Head_1"])
    front = [
        find_optional(arm, ["tripo::0_Left_Limb_0"]),
        find_optional(arm, ["tripo::0_Right_Limb_0"]),
    ]
    for frame, pitch, leg in [(1,0.0,0.0),(5,-10.0,10.0),(9,18.0,-18.0),(14,8.0,-8.0),(22,0.0,0.0)]:
        if spine: key_pose(spine, frame, (math.radians(pitch*0.45),0.0,0.0))
        if head: key_pose(head, frame, (math.radians(pitch),0.0,0.0))
        for i,b in enumerate(front):
            if b: key_pose(b, frame, (0.0,0.0,math.radians(leg if i==0 else -leg)))
    return action

def author_death(arm, brute=False):
    action = create_action(arm, "Sheep_Death")
    root = find_optional(arm, ["tripo::Root", "tripo::Spine_0"])
    spine = find_optional(arm, ["tripo::Spine_1", "tripo::Spine_2"])
    head = find_optional(arm, ["tripo::Head_0", "tripo::Head_1"])
    for frame, roll, pitch in [(1,0.0,0.0),(8,18.0,8.0),(18,58.0,20.0),(30,82.0,26.0)]:
        if root: key_pose(root, frame, (math.radians(pitch*0.25),0.0,math.radians(roll)))
        if spine: key_pose(spine, frame, (math.radians(pitch),0.0,math.radians(roll*0.15)))
        if head: key_pose(head, frame, (math.radians(-pitch*0.45),0.0,math.radians(-roll*0.08)))
    return action

def bounds(objs):
    pts=[]
    for o in objs:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    mn=Vector(pts[0]); mx=Vector(pts[0])
    for p in pts[1:]:
        mn.x=min(mn.x,p.x); mn.y=min(mn.y,p.y); mn.z=min(mn.z,p.z)
        mx.x=max(mx.x,p.x); mx.y=max(mx.y,p.y); mx.z=max(mx.z,p.z)
    return mn,mx,mx-mn

def render_preview(label, arm, action, frame):
    arm.animation_data.action = action
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    objs=meshes()
    mn,mx,size=bounds(objs)
    center=(mn+mx)*0.5
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=960
    scene.render.resolution_y=720
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    if scene.world is None:
        scene.world=bpy.data.worlds.new("SheepWorld")
    scene.world.color=(0.08,0.08,0.08)
    cam_data=bpy.data.cameras.new("SheepCamera")
    cam=bpy.data.objects.new("SheepCamera",cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera=cam
    cam_data.type='ORTHO'
    cam_data.ortho_scale=max(size.x,size.y,size.z)*1.35
    # Imported glTF is Z-up in Blender; view along -Y.
    cam.location=center+Vector((0.0,-max(size)*2.8,max(size)*0.25))
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    for nm,loc,energy in [
        ("Key",center+Vector((max(size),-max(size),max(size))),1200),
        ("Fill",center+Vector((-max(size),-max(size)*0.4,max(size)*0.4)),700),
    ]:
        ld=bpy.data.lights.new(nm,type='AREA'); ld.energy=energy; ld.size=max(size)*1.3
        lo=bpy.data.objects.new(nm,ld); bpy.context.collection.objects.link(lo); lo.location=loc
    scene.render.filepath=str(OUT/f"{label}_run_mid.png")
    bpy.ops.render.render(write_still=True)
    arm.animation_data.action=None

def build_one(label, source_path):
    if not source_path.is_file():
        fail("Missing source " + str(source_path))
    reset()
    bpy.ops.import_scene.gltf(filepath=str(source_path))
    ms=meshes(); ars=armatures()
    if len(ars)!=1: fail(f"{label}: expected 1 armature, got {len(ars)}")
    arm=ars[0]
    if len(arm.data.bones)<20: fail(f"{label}: skeleton too small")
    src_tris=tri_count(ms)
    src_verts=sum(len(o.data.vertices) for o in ms)

    actions=[
        author_idle(arm),
        author_run(arm, brute=label=="sheep_brute"),
        author_attack(arm, brute=label=="sheep_brute"),
        author_death(arm, brute=label=="sheep_brute"),
    ]
    for action in actions:
        stash_action(arm, action, int(action.frame_range[0]))

    render_preview(label, arm, bpy.data.actions["Sheep_Run"], 7)

    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    for o in ms:o.select_set(True)
    bpy.context.view_layer.objects.active=arm
    out_glb=OUT/f"{label}_animated.glb"
    kwargs=dict(
        filepath=str(out_glb),
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
    bpy.ops.export_scene.gltf(**kwargs)

    if not out_glb.is_file(): fail(f"{label}: export missing")
    out_bytes=out_glb.stat().st_size

    reset()
    bpy.ops.import_scene.gltf(filepath=str(out_glb))
    out_ms=meshes(); out_ars=armatures()
    out_actions=[a.name for a in bpy.data.actions]
    out_tris=tri_count(out_ms)
    missing=[n for n in REQUIRED if not any(n.lower() in a.lower() for a in out_actions)]
    if missing: fail(f"{label}: missing actions {missing}; got {out_actions}")
    if out_tris != src_tris: fail(f"{label}: triangle mismatch {out_tris}/{src_tris}")
    if len(out_ars)!=1: fail(f"{label}: armature lost")

    rec={
        "id":label,
        "source":str(source_path.relative_to(ROOT)),
        "source_vertices":src_verts,
        "source_triangles":src_tris,
        "output_triangles":out_tris,
        "bones":len(out_ars[0].data.bones),
        "actions":out_actions,
        "output":out_glb.name,
        "output_bytes":out_bytes,
    }
    print("XZOGOT_SHEEP_VARIANT_GREEN",json.dumps(rec))
    return rec

reports=[]
for label,path in SOURCES.items():
    reports.append(build_one(label,path))

report={"schema":1,"pipeline":"zombie_sheep_blender_animation_v1","variants":reports}
(OUT/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print("XZOGOT_SHEEP_ANIMATIONS_GREEN", REQUIRED)
print("XZOGOT_SHEEP_PAIR_GREEN", [r["id"] for r in reports])
