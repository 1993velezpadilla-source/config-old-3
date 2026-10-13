extends "res://scripts/zombie_dummy.gd"
## Lab-only actor: shares the REAL chase, attacks, hitzones and death logic
## without changing production zombie selection or introducing a fake fallback.
## A mesh with no skeleton stays a stationary *visual* specimen.

@export var lab_asset_path: String = ""
@export var lab_model_id: String = "unconfigured"
@export var lab_forward_degrees: float = 0.0
@export var lab_source_waw: bool = false

func _build_body() -> void:
    var collider := CollisionShape3D.new()
    collider.name = "ZombieCollider"
    var capsule := CapsuleShape3D.new()
    capsule.radius = collider_radius
    capsule.height = collider_height
    collider.shape = capsule
    collider.position.y = collider_height * 0.5
    add_child(collider)

    set_meta("zombie_lab_visual_loaded", false)
    set_meta("zombie_rig_ready", false)
    set_meta("zombie_source_waw", false)
    set_meta("zombie_model", "MISSING:" + lab_model_id)
    if lab_asset_path.is_empty() or not ResourceLoader.exists(lab_asset_path):
        push_warning("ZOMBIE_LAB_ASSET_MISSING " + lab_asset_path)
        return  # NEVER silently mount an unrelated old zombie.

    var packed := load(lab_asset_path) as PackedScene
    if packed == null:
        push_warning("ZOMBIE_LAB_ASSET_NOT_SCENE " + lab_asset_path)
        return
    var source := packed.instantiate() as Node3D
    if source == null:
        push_warning("ZOMBIE_LAB_ASSET_NO_NODE3D " + lab_asset_path)
        return

    var wrapper := Node3D.new()
    wrapper.name = "LabModelPivot"
    add_child(wrapper)
    _visual_root = wrapper
    source.name = "SourceModel"
    wrapper.add_child(source)
    source.rotation_degrees.y = lab_forward_degrees

    # Uniform scale preserves proportions (no stretched faces/bodies).
    var points: Array[Vector3] = []
    _collect_mesh_bounds(source, Transform3D.IDENTITY, points)
    if points.is_empty():
        push_warning("ZOMBIE_LAB_MESH_EMPTY " + lab_asset_path)
        wrapper.queue_free()
        _visual_root = null
        return
    var low: Vector3 = points[0]
    var high: Vector3 = points[0]
    for point: Vector3 in points:
        low = low.min(point)
        high = high.max(point)
    var size: Vector3 = high - low
    if size.y <= 0.0001:
        push_warning("ZOMBIE_LAB_INVALID_BOUNDS " + lab_asset_path)
        wrapper.queue_free()
        _visual_root = null
        return
    var uniform_scale: float = target_visual_height / size.y
    wrapper.scale = Vector3.ONE * uniform_scale
    wrapper.position = Vector3(
        -(low.x + high.x) * 0.5 * uniform_scale,
        -low.y * uniform_scale,
        -(low.z + high.z) * 0.5 * uniform_scale
    )
    _animation_player = _find_animation_player(source)
    var animated: bool = _animation_player != null and not _animation_player.get_animation_list().is_empty()
    set_meta("zombie_lab_visual_loaded", true)
    set_meta("zombie_lab_asset_path", lab_asset_path)
    set_meta("zombie_rig_ready", animated)
    set_meta("zombie_source_waw", lab_source_waw and animated)
    set_meta("zombie_model", lab_model_id)
    set_meta("zombie_visual_forward_fix_deg", lab_forward_degrees)
    set_meta("zombie_visual_scale_xyz", Vector3.ONE * uniform_scale)
    set_meta("zombie_visual_centered_on_feet", true)
    set_meta("zombie_lab_has_animation", animated)
    if animated:
        _play_motion_state("idle")
        print("ZOMBIE_LAB_ANIMATED_ASSET_READY ", lab_model_id)
    else:
        set_meta("zombie_lab_gate", "RIG_REQUIRED_NO_ANIMATION")
        print("ZOMBIE_LAB_RAW_PREVIEW_ONLY ", lab_model_id, " (no rig/animation)")
