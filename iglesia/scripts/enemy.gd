extends CharacterBody3D
## 2.5D camera-facing sprite enemy with NEW grid-navigation AI.
## DEBUG ART is visibly marked until the approved multi-direction nun sprites exist.
signal killed(reward: int)
var target: CharacterBody3D
var level: Node3D
var health: float = 70.0
var move_speed: float = 1.45
var chase_tick: float = 0.0
var next_waypoint: Vector3 = Vector3.ZERO
var attack_clock: float = 0.0
var art_sprite: Sprite3D

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
    art_sprite.name = "Nun25DBillboard"
    art_sprite.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
    art_sprite.pixel_size = 0.017
    art_sprite.position.y = 1.0
    var owner_frame := "res://assets/zombies/nun_walk_00.png"
    if ResourceLoader.exists(owner_frame):
        art_sprite.texture = load(owner_frame)
    else:
        # Explicit dev-only stand-in. This is NOT FMF2-quality final zombie art.
        art_sprite.texture = _debug_texture()
        push_warning("IGLESIA_ZOMBIE_ART_PENDING: approved HD 2.5D nun sprite sheet")
    add_child(art_sprite)

func _debug_texture() -> Texture2D:
    var im := Image.create(96, 160, false, Image.FORMAT_RGBA8)
    im.fill(Color(0.0, 0.0, 0.0, 0.0))
    _paint(im, Rect2i(29, 11, 38, 35), Color(0.80, 0.77, 0.72))
    _paint(im, Rect2i(22, 38, 52, 89), Color(0.13, 0.14, 0.16))
    _paint(im, Rect2i(37, 43, 23, 25), Color(0.64, 0.49, 0.43))
    _paint(im, Rect2i(30, 73, 9, 65), Color(0.21, 0.20, 0.23))
    _paint(im, Rect2i(58, 73, 9, 65), Color(0.21, 0.20, 0.23))
    _paint(im, Rect2i(44, 51, 6, 4), Color(0.90, 0.16, 0.10))
    return ImageTexture.create_from_image(im)

func _paint(im: Image, rect: Rect2i, color: Color) -> void:
    for x in range(rect.position.x, rect.end.x):
        for y in range(rect.position.y, rect.end.y):
            im.set_pixel(x, y, color)

func _physics_process(delta: float) -> void:
    if target == null or not is_instance_valid(target):
        velocity = Vector3.ZERO
        return
    var offset: Vector3 = target.global_position - global_position
    offset.y = 0.0
    if offset.length() < 1.22:
        velocity.x = 0.0
        velocity.z = 0.0
        attack_clock -= delta
        if attack_clock <= 0.0:
            target.apply_zombie_damage(27)
            attack_clock = 1.15
    else:
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
