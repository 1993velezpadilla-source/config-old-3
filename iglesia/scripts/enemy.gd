extends CharacterBody3D
## 2.5D camera-facing sprite enemy with NEW grid-navigation AI.
## Only user-approved 2.5D Nun PNG animation. No blocky procedural silhouette.
signal killed(reward: int)
var target
var level
var health: float = 70.0
var move_speed: float = 1.45
var chase_tick: float = 0.0
var next_waypoint: Vector3 = Vector3.ZERO
var attack_clock: float = 0.0
var art_sprite: Sprite3D
var clip_time: float = 0.0
var clip_role: String = "walk"
static var cached_clips: Dictionary = {}

func _ready() -> void:
    collision_layer = 4
    collision_mask = 1
    add_to_group("iglesia_zombies")
    var shape := CapsuleShape3D.new()
    shape.height = 1.95
    shape.radius = 0.35
    var collider := CollisionShape3D.new()
    collider.shape = shape
    collider.position.y = 0.98
    add_child(collider)
    _set_sprite()
    next_waypoint = global_position

func _set_sprite() -> void:
    art_sprite = Sprite3D.new()
    art_sprite.name = "NunEnemy_2D_PNG_Only"
    art_sprite.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
    art_sprite.pixel_size = 0.008  # 240 pixels ≈ 1.92 m world height.
    art_sprite.position.y = 0.96
    art_sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
    add_child(art_sprite)
    _load_clips()
    _show_frame("walk", 0)
    if art_sprite.texture == null:
        art_sprite.visible = false
        push_warning("IGLESIA_NUN_ENEMY_ART_BLOCKER: no approved PNGs; forbidden debug rectangle removed")

func _load_clips() -> void:
    if not cached_clips.is_empty():
        return
    for role in ["idle", "walk", "attack", "death"]:
        var sequence: Array[Texture2D] = []
        for index in range(24):
            var path := "res://assets/enemies/gothic_nun_2d/%s_%02d.png" % [role, index]
            if not ResourceLoader.exists(path):
                break
            var texture := load(path) as Texture2D
            if texture == null:
                break
            sequence.append(texture)
        cached_clips[role] = sequence

func _show_frame(role: String, index: int) -> void:
    var images: Array = cached_clips.get(role, [])
    if images.is_empty():
        art_sprite.visible = false
        return
    art_sprite.texture = images[index % images.size()]
    art_sprite.visible = true

func _advance_sprite(delta: float, role: String) -> void:
    if role != clip_role:
        clip_time = 0.0
        clip_role = role
    clip_time += delta
    var fps: float = 8.0 if role == "walk" else 6.0
    _show_frame(role, int(clip_time * fps))

func _physics_process(delta: float) -> void:
    if target == null or not is_instance_valid(target):
        velocity = Vector3.ZERO
        return
    var offset: Vector3 = target.global_position - global_position
    offset.y = 0.0
    if offset.length() < 1.22:
        _advance_sprite(delta, "attack")
        velocity.x = 0.0
        velocity.z = 0.0
        attack_clock -= delta
        if attack_clock <= 0.0:
            target.apply_zombie_damage(27)
            attack_clock = 1.15
    else:
        _advance_sprite(delta, "walk")
        chase_tick -= delta
        if chase_tick <= 0.0 and level != null:
            next_waypoint = level.next_step(global_position, target.global_position)
            chase_tick = 0.35
        var step: Vector3 = next_waypoint - global_position
        step.y = 0.0
        if step.length() < 0.17:
            velocity.x = 0.0
            velocity.z = 0.0
        else:
            var desired := step.normalized() * move_speed
            velocity.x = move_toward(velocity.x, desired.x, 9.0 * delta)
            velocity.z = move_toward(velocity.z, desired.z, 9.0 * delta)
    if not is_on_floor():
        velocity.y -= 24.0 * delta
    else:
        velocity.y = -0.1
    move_and_slide()

func take_damage(amount: float, _hit_at: Vector3) -> void:
    if health <= 0.0:
        return
    health -= amount
    if health <= 0.0:
        remove_from_group("iglesia_zombies")
        killed.emit(100)
        queue_free()
