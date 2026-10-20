extends CharacterBody3D
## New Godot FPS controller. No imported old Virin/Bukkbeek mechanics.
var game
var level
var hud
var head: Node3D
var camera: Camera3D
var health: int = 100
var magazine: int = 32
var reserve_ammo: int = 128
var reload_active: bool = false
var reload_left: float = 0.0
var fire_left: float = 0.0
var shot_flash: float = 0.0
var ads_toggled: bool = false
var ads_toggle_mode: bool = true
var gyro_ads_only: bool = true
var aim_sensitivity: float = 0.0031
var gyro_sensitivity: float = 0.65
var pitch: float = 0.0
var sprint_speed: float = 8.0
var walk_speed: float = 4.8
var ads_walk_speed: float = 2.9
var fire_interval: float = 0.105
var reload_seconds: float = 2.65
var gravity: float = 23.0
var jump_velocity: float = 5.0
var slide_left: float = 0.0
var hurt_left: float = 0.0

func _ready() -> void:
    collision_layer = 1
    collision_mask = 1
    var capsule := CapsuleShape3D.new()
    capsule.radius = 0.31
    capsule.height = 1.70
    var collider := CollisionShape3D.new()
    collider.name = "PlayerCollision"
    collider.shape = capsule
    collider.position.y = 0.85
    add_child(collider)
    head = Node3D.new()
    head.name = "Eyes"
    head.position.y = 1.57
    add_child(head)
    camera = Camera3D.new()
    camera.name = "Camera"
    camera.fov = 77.0
    camera.current = true
    head.add_child(camera)
    add_to_group("iglesia_player")

func ads_active() -> bool:
    return ads_toggled or Input.is_action_pressed("ads")

func toggle_ads() -> void:
    ads_toggled = not ads_toggled

func look_delta(delta_pixels: Vector2) -> void:
    rotate_y(-delta_pixels.x * aim_sensitivity)
    pitch = clampf(pitch - delta_pixels.y * aim_sensitivity, -1.37, 1.37)
    if head != null:
        head.rotation.x = pitch

func _unhandled_input(event: InputEvent) -> void:
    if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
        look_delta((event as InputEventMouseMotion).relative)
    if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
        Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _physics_process(delta: float) -> void:
    fire_left = maxf(0.0, fire_left - delta)
    shot_flash = maxf(0.0, shot_flash - delta)
    hurt_left = maxf(0.0, hurt_left - delta)
    if reload_active:
        reload_left -= delta
        if reload_left <= 0.0:
            _finish_reload()
    var axis := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
    if hud != null:
        var touch_axis: Vector2 = hud.get_move_axis()
        if touch_axis.length_squared() > 0.004:
            axis = touch_axis
    var ads: bool = ads_active()
    if gyro_ads_only and ads and OS.has_feature("mobile"):
        var gyro: Vector3 = Input.get_gyroscope()
        rotate_y(-gyro.y * gyro_sensitivity * delta)
        pitch = clampf(pitch + gyro.x * gyro_sensitivity * delta, -1.37, 1.37)
        head.rotation.x = pitch
    var speed: float = ads_walk_speed if ads else walk_speed
    var sprinting: bool = Input.is_action_pressed("sprint") and not ads
    if hud != null and hud.get_move_axis().y < -0.90 and not ads:
        sprinting = true
    if sprinting:
        speed = sprint_speed
    if Input.is_action_just_pressed("slide") and is_on_floor() and speed > 4.5:
        slide_left = 0.44
    if slide_left > 0.0:
        slide_left -= delta
        speed = maxf(speed, 9.0)
    if Input.is_action_just_pressed("jump") and is_on_floor():
        velocity.y = jump_velocity
    elif not is_on_floor():
        velocity.y -= gravity * delta
    var direction := (transform.basis * Vector3(axis.x, 0.0, axis.y)).normalized()
    velocity.x = move_toward(velocity.x, direction.x * speed, 21.0 * delta)
    velocity.z = move_toward(velocity.z, direction.z * speed, 21.0 * delta)
    move_and_slide()
    if Input.is_action_pressed("fire"):
        _try_fire()
    if Input.is_action_just_pressed("reload") or (magazine == 0 and reserve_ammo > 0):
        _start_reload()
    if camera != null:
        camera.fov = lerpf(camera.fov, 55.0 if ads else 77.0, minf(delta * 11.0, 1.0))

func _try_fire() -> void:
    if reload_active or fire_left > 0.0:
        return
    if magazine == 0:
        _start_reload()
        return
    fire_left = fire_interval
    shot_flash = 0.065
    magazine -= 1
    var origin: Vector3 = camera.global_transform.origin
    var direction: Vector3 = -camera.global_transform.basis.z
    var request := PhysicsRayQueryParameters3D.create(origin, origin + direction * 120.0)
    request.exclude = [get_rid()]
    var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(request)
    if not hit.is_empty():
        var victim: Object = hit.get("collider")
        if victim is Node and (victim as Node).is_in_group("iglesia_zombies"):
            var hit_position: Vector3 = hit.get("position", Vector3.ZERO)
            var is_headshot: bool = hit_position.y > (victim as Node3D).global_position.y + 1.25
            (victim as Node).call("take_damage", 80.0 if is_headshot else 33.0, hit_position)
            if game != null:
                game.points += 10
    if hud != null:
        hud.weapon_shot()

func _start_reload() -> void:
    if reload_active or magazine >= 32 or reserve_ammo <= 0:
        return
    reload_active = true
    reload_left = reload_seconds
    # Sprint does NOT cancel this timer, intentionally.

func _finish_reload() -> void:
    var delta_ammo: int = mini(32 - magazine, reserve_ammo)
    reserve_ammo -= delta_ammo
    magazine += delta_ammo
    reload_active = false
    reload_left = 0.0

func apply_zombie_damage(amount: int) -> void:
    if hurt_left > 0.0:
        return
    health = maxi(0, health - amount)
    hurt_left = 0.56
    if hud != null:
        hud.flash_hurt()
