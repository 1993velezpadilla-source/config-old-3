extends Node3D
## Real first-person MP40 + skinned hands from source GLBs already in GitHub.
## One camera-space rig for hip/ADS/fire/reload, rather than nine mismatched
## 2D pictures. Hands are an interim skinned base with a Nun-specific palette;
## the actual bare-finger silhouette still needs owner visual approval.

var player: CharacterBody3D
var source_ready: bool = false
var gun: Node3D
var hands: Node3D
var motion_root: Node3D
var gun_animation: AnimationPlayer
var hands_animation: AnimationPlayer
var last_role: String = ""
var ads_fraction: float = 0.0
var style_surface_roles: Dictionary = {}
var source_animation_roles: Dictionary = {}
var weapon_mount: BoneAttachment3D
var source_hand_skeleton: Skeleton3D
var viewmodel_diagnostic: Dictionary = {}
var source_unit_correction: float = 1.0
var provenance: String = "GitHub-owned Aether MP40 gun + T4 113-bone skinned hand GLBs"

# Existing MP40 weapon datatable: converted Unreal centimetres to Godot metres.
# Published: xogot/data/weapon_viewmodel_source_presentation.json / MP40 row 5.
const HIP_POSITION := Vector3(0.08, -0.33, -0.68)
const SOURCE_HAND_TAG := Vector3(-0.05178748, -0.06636865, -0.09194843)
const ADS_DELTA := Vector3(-0.09142, 0.0604, -0.02045)
const ADS_IN_SECONDS := 0.20

func _ready() -> void:
    const ROOT := "res://assets/weapons/mp40_nun/"
    if not ResourceLoader.exists(ROOT + "gun.glb") or not ResourceLoader.exists(ROOT + "viewhands.glb"):
        push_error("NUN_MP40_SOURCE_RIG_GLBS_NOT_STAGED")
        return
    var gun_asset = load(ROOT + "gun.glb")
    var hand_asset = load(ROOT + "viewhands.glb")
    if not (gun_asset is PackedScene) or not (hand_asset is PackedScene):
        push_error("NUN_MP40_SOURCE_NOT_PACKED_SCENES")
        return
    motion_root = Node3D.new()
    motion_root.name = "SourceAuthoritativeCameraPose"
    motion_root.position = HIP_POSITION
    # Both ActorX meshes were authored with Unreal's X-forward gun axis.
    # Convert that SOURCE frame to Godot camera-forward (-Z) ONCE for both
    # the hands and the MP40. The previous build left its barrel pointing
    # horizontally across the screen and obscured the iron sights.
    motion_root.rotation.y = PI * 0.5
    add_child(motion_root)
    gun = (gun_asset as PackedScene).instantiate() as Node3D
    hands = (hand_asset as PackedScene).instantiate() as Node3D
    if gun == null or hands == null:
        push_error("NUN_MP40_SOURCE_GUN_OR_HANDS_NOT_NODE3D")
        return
    gun.name = "AuthenticatedMP40"
    hands.name = "NunPaleHandsBlackHabit_SourceSkin"
    # Authored glTF rigs share metres and skeleton clips; do not independently
    # normalize mesh size per animation, as prior sprite passes did.
    motion_root.add_child(hands)
    hands.position = Vector3.ZERO
    hands.scale = Vector3.ONE
    # The prior fixed offset was copied from a single idle PSA frame, so the
    # gun stayed detached whenever hands animated. Attach to the actual
    # tag_weapon bone, which follows the 113-joint hand skeleton in every pose.
    source_hand_skeleton = _source_skeleton(hands)
    if source_hand_skeleton == null:
        push_error("NUN_MP40_HAND_SKELETON_NOT_FOUND")
        return
    if source_hand_skeleton.find_bone("tag_weapon") < 0:
        push_error("NUN_MP40_REAL_TAG_WEAPON_BONE_MISSING")
        return
    weapon_mount = BoneAttachment3D.new()
    weapon_mount.name = "GUN_FOLLOWS_SKINNED_TAG_WEAPON"
    weapon_mount.bone_name = "tag_weapon"
    source_hand_skeleton.add_child(weapon_mount)
    weapon_mount.add_child(gun)
    gun.position = Vector3.ZERO
    gun.scale = Vector3.ONE
    # Source provenance audit: the original GLB imports in metres but the
    # imported weapon mesh is about 6 millimetres long on camera. Screenshot
    # report (build 39842178312) proves it was NOT the intended MP40 scale.
    # Calibrate the one gun mesh to its approximately 0.62 m source physical
    # length while never resizing the animated hand skeleton.
    var source_bounds: Dictionary = _camera_geometry_diagnostic()
    var unscaled: Dictionary = source_bounds.get("gun_camera_aabb", {})
    var gun_longest: float = maxf(maxf(float(unscaled.get("extent_x", 0.0)),
        float(unscaled.get("extent_y", 0.0))), float(unscaled.get("extent_z", 0.0)))
    if gun_longest < 0.001 or gun_longest > 0.03:
        push_error("NUN_MP40_SOURCE_UNITS_UNEXPECTED_LENGTH " + str(gun_longest))
        return
    var unit_correction: float = clampf(0.62 / gun_longest, 10.0, 160.0)
    gun.scale = Vector3.ONE * unit_correction
    source_unit_correction = unit_correction
    print("IGLESIA_MP40_SOURCE_UNITS_CALIBRATED source_m=", gun_longest,
        " corrected_scale=", unit_correction)
    var ink: Shader = load("res://shaders/nun_mp40_source_ink.gdshader")
    var gun_atlas: Texture2D = load(ROOT + "gun_color.png")
    var hands_atlas: Texture2D = load(ROOT + "hands_atlas.png")
    if ink == null or gun_atlas == null or hands_atlas == null:
        push_error("NUN_MP40_PROTAGONIST_SHADER_OR_TEXTURE_MISSING")
        return
    _set_surface_palette(gun, ink, gun_atlas, true)
    _set_surface_palette(hands, ink, hands_atlas, false)
    gun_animation = _animation_player(gun)
    hands_animation = _animation_player(hands)
    if gun_animation == null or hands_animation == null:
        push_error("NUN_MP40_SOURCE_ANIM_PLAYER_NOT_FOUND")
        return
    for role in ["idle","fire","reload"]:
        if _source_clip(gun_animation,role).is_empty() or _source_clip(hands_animation,role).is_empty():
            push_error("NUN_MP40_AUTHORED_CLIP_MISSING_" + role)
            return
    source_ready = true
    _switch_animation("idle")
    # Capture evidence from the actual model rather than trusting clip counts.
    viewmodel_diagnostic = _camera_geometry_diagnostic()
    var gun_bounds: Dictionary = viewmodel_diagnostic.get("gun_camera_aabb", {})
    var gun_visible_length: float = maxf(maxf(float(gun_bounds.get("extent_x", 0.0)),
        float(gun_bounds.get("extent_y", 0.0))), float(gun_bounds.get("extent_z", 0.0)))
    if gun_visible_length < 0.35 or gun_visible_length > 1.1:
        push_error("IGLESIA_MP40_AFTER_SCALE_STILL_NOT_PHYSICAL " + str(gun_visible_length))
        source_ready = false
        return
    viewmodel_diagnostic["source_unit_correction"] = unit_correction
    viewmodel_diagnostic["calibrated_gun_length_m"] = gun_visible_length
    print("IGLESIA_MP40_CAMERA_GEOMETRY ", JSON.stringify(viewmodel_diagnostic))
    print("IGLESIA_NUN_MP40_REAL_RIG_READY gun=",gun_animation.get_animation_list().size(),
        " hands=",hands_animation.get_animation_list().size(),
        " surfaces=",style_surface_roles.size())

func _source_skeleton(root_node: Node3D) -> Skeleton3D:
    for node in root_node.find_children("*", "Skeleton3D", true, false):
        if node is Skeleton3D:
            var skeleton := node as Skeleton3D
            if skeleton.find_bone("tag_weapon") >= 0:
                return skeleton
    return null

func _camera_geometry_diagnostic() -> Dictionary:
    var result: Dictionary = {
        "bone_attachment_active": weapon_mount != null,
        "tag_weapon_index": source_hand_skeleton.find_bone("tag_weapon") if source_hand_skeleton != null else -1,
        "root_yaw_deg": rad_to_deg(motion_root.rotation.y),
        "gun_mesh_nodes": 0,
        "hand_mesh_nodes": 0,
        "source_unit_correction": source_unit_correction
    }
    var camera_node: Camera3D = get_parent() as Camera3D
    if camera_node == null:
        return result
    for piece in [{"root": gun, "key": "gun"}, {"root": hands, "key": "hands"}]:
        var source_node: Node3D = piece["root"]
        var bounding_box := AABB()
        var have_bound := false
        var count := 0
        for node in source_node.find_children("*", "MeshInstance3D", true, false):
            var mesh_item: MeshInstance3D = node as MeshInstance3D
            if mesh_item.mesh == null:
                continue
            count += 1
            var camera_relative: Transform3D = camera_node.global_transform.affine_inverse() * mesh_item.global_transform
            var mesh_bound: AABB = camera_relative * mesh_item.get_aabb()
            if have_bound:
                bounding_box = bounding_box.merge(mesh_bound)
            else:
                bounding_box = mesh_bound
                have_bound = true
        result[str(piece["key"]) + "_mesh_nodes"] = count
        if have_bound:
            result[str(piece["key"]) + "_camera_aabb"] = {
                "center_x": snappedf(bounding_box.get_center().x, 0.001),
                "center_y": snappedf(bounding_box.get_center().y, 0.001),
                "center_z": snappedf(bounding_box.get_center().z, 0.001),
                "extent_x": snappedf(bounding_box.size.x, 0.001),
                "extent_y": snappedf(bounding_box.size.y, 0.001),
                "extent_z": snappedf(bounding_box.size.z, 0.001)
            }
    return result

func _animation_player(node: Node) -> AnimationPlayer:
    for child in node.find_children("*","AnimationPlayer",true,false):
        if child is AnimationPlayer:
            return child as AnimationPlayer
    return null

func _source_clip(ap: AnimationPlayer, mode: String) -> String:
    # Track names come from real WaW ActorX PSA animation sources and are
    # stored in original GLBs, not procedurally invented 2D poses.
    var terms: Array[String] = []
    if mode == "idle":
        terms = ["handidlemp40","idle"]
    elif mode == "fire":
        terms = ["viewmodel_mp40_fire","fire"]
    elif mode == "reload_empty":
        terms = ["viewmodel_mp40_reload_empty","reload_empty","reload"]
    elif mode == "reload":
        terms = ["mp40reloadhands","viewmodel_mp40_reload","reload"]
    else:
        terms = [mode]
    var clips: PackedStringArray = ap.get_animation_list()
    for token in terms:
        for clip in clips:
            if token in clip.to_lower():
                return clip
    return ""

func _set_surface_palette(model: Node3D, shader: Shader, atlas: Texture2D, is_gun: bool) -> void:
    for node in model.find_children("*","MeshInstance3D",true,false):
        var mesh_node: MeshInstance3D = node as MeshInstance3D
        if mesh_node.mesh == null:
            continue
        mesh_node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
        mesh_node.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
        for surface_index in range(mesh_node.mesh.get_surface_count()):
            var src_mat: Material = mesh_node.mesh.surface_get_material(surface_index)
            var mat_name := ""
            if src_mat != null:
                mat_name = src_mat.resource_name.to_lower()
            var role := 0
            if not is_gun:
                # The original source hand export includes skin, cloth and
                # buttons as separate materials. Preserve mesh boundaries.
                if "cloth" in mat_name or "fabric" in mat_name or "sleeve" in mat_name:
                    role = 2
                elif "button" in mat_name or "trim" in mat_name:
                    role = 3
                else:
                    role = 1
            var stylized := ShaderMaterial.new()
            stylized.shader = shader
            stylized.set_shader_parameter("source_map",atlas)
            stylized.set_shader_parameter("surface_role",role)
            mesh_node.set_surface_override_material(surface_index,stylized)
            style_surface_roles[mesh_node.name+"_"+str(surface_index)] = {
                "role":role,"original_material":mat_name,
                "verified_semantics":is_gun or ("skin" in mat_name or "cloth" in mat_name or "button" in mat_name)
            }

func _switch_animation(role: String) -> void:
    if not source_ready or role == last_role:
        return
    last_role = role
    for animator in [gun_animation, hands_animation]:
        if animator == null:
            continue
        var clip: String = _source_clip(animator,role)
        if clip.is_empty():
            clip = _source_clip(animator,"idle")
        if clip.is_empty():
            continue
        var animation: Animation = animator.get_animation(clip)
        if animation != null:
            animation.loop_mode = Animation.LOOP_LINEAR if role == "idle" else Animation.LOOP_NONE
        var speed := 1.0
        if role.begins_with("reload") and animation != null and player != null:
            speed = maxf(0.05, animation.length/maxf(0.01,player.reload_seconds))
        animator.play(clip,0.05,speed)
        source_animation_roles[animator.name] = {"mode":role,"source_clip":clip}

func _process(delta: float) -> void:
    if not source_ready or player == null:
        return
    var target: float = 1.0 if player.ads_active() else 0.0
    ads_fraction = move_toward(ads_fraction,target,delta/ADS_IN_SECONDS)
    motion_root.position = HIP_POSITION + ADS_DELTA * ads_fraction
    # The authored source ADS quaternion in the MP40 row is near-identity.
    # Preserve the source X-forward-to-camera transform throughout ADS.
    motion_root.rotation = Vector3(-0.009857, PI * 0.5 + 0.002472, 0.012176) * ads_fraction + Vector3(0.0, PI * 0.5, 0.0) * (1.0 - ads_fraction)
    var role := "idle"
    if player.reload_active:
        role = "reload_empty" if player.magazine == 0 else "reload"
    elif player.shot_flash > 0.0:
        role = "fire"
    _switch_animation(role)
