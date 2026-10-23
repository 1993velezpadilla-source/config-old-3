extends CharacterBody3D
## Iglesia 2.5D enemy: source-rendered PNGs only (no runtime nun 3D model).
## Attack damage is synchronized to the actual attack PNG sequence; death is
## non-looping and the last corpse image remains briefly before queue_free.
signal killed(reward: int)

enum CombatState { WALK, ATTACK, DEATH }

const SPRITE_ROOT := "res://assets/enemies/gothic_nun_2d/"
const ROLE_COUNTS := {"idle": 2, "walk": 4, "attack": 6, "death": 8}
const ROLE_FPS := {"idle": 4.0, "walk": 8.0, "attack": 6.0, "death": 7.0}
const ATTACK_DAMAGE_FRAME := 3
const ATTACK_RANGE := 1.22
const ATTACK_DAMAGE := 27
const DEATH_HOLD_SECONDS := 0.65

var target
var level
var health: float = 70.0
var move_speed: float = 1.45
var chase_tick: float = 0.0
var next_waypoint: Vector3 = Vector3.ZERO
var art_sprite: Sprite3D
var clip_time: float = 0.0
var clip_role: String = "walk"
var state: CombatState = CombatState.WALK
var attack_hit_sent: bool = false
var death_hold_left: float = DEATH_HOLD_SECONDS
var death_started: bool = false
static var cached_clips: Dictionary = {}

func _ready() -> void:
    collision_layer = 4
    collision_mask = 1
    add_to_group("iglesia_zombies")
    var capsule := CapsuleShape3D.new()
    capsule.height = 1.95
    capsule.radius = 0.35
    var collider := CollisionShape3D.new()
    collider.name = "NunCapsule"
    collider.shape = capsule
    collider.position.y = 0.98
    add_child(collider)
    _set_sprite()
    next_waypoint = global_position

func _set_sprite() -> void:
    art_sprite = Sprite3D.new()
    art_sprite.name = "NunEnemy_2D_PNG_Only"
    art_sprite.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
    art_sprite.pixel_size = 0.003
    art_sprite.position.y = 0.96
    art_sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
    art_sprite.shaded = false
    add_child(art_sprite)
    _load_clips()
    _show_frame("walk", 0)
    if art_sprite.texture == null:
        push_warning("IGLESIA_NUN_2D_ART_PENDING; no rectangular placeholder")

func _load_clips() -> void:
    if not cached_clips.is_empty():
        return
    for role in ["idle", "walk", "attack", "death"]:
        var images: Array[Texture2D] = []
        for frame in range(int(ROLE_COUNTS[role])):
            var file := "%s%s_%02d.png" % [SPRITE_ROOT, role, frame]
            if not ResourceLoader.exists(file):
                break
            var texture := load(file) as Texture2D
            if texture == null:
                break
            images.append(texture)
        cached_clips[role] = images
        if images.size() != int(ROLE_COUNTS[role]):
            push_warning("IGLESIA_NUN_SOURCE_CLIP_INCOMPLETE_%s %d/%d" %
                [role, images.size(), int(ROLE_COUNTS[role])])

func _show_frame(role: String, index: int) -> void:
    var images: Array = cached_clips.get(role, [])
    if images.is_empty() and role != "walk":
        # Preview fallback is real, owner-source walk, never a generated block.
        # Art acceptance gate must still reject missing authentic attack/death.
        images = cached_clips.get("walk", [])
    if images.is_empty():
        art_sprite.visible = false
        return
    art_sprite.texture = images[clampi(index, 0, images.size() - 1)]
    art_sprite.visible = true

func _frame_index(role: String) -> int:
    var images: Array = cached_clips.get(role, [])
    if images.is_empty():
        return 0
    var frame := int(floor(clip_time * float(ROLE_FPS[role])))
    return clampi(frame, 0, images.size() - 1)

func _set_role(role: String) -> void:
    if clip_role != role:
        clip_role = role
        clip_time = 0.0

func _advance_role(delta: float, role: String, loop: bool) -> bool:
    _set_role(role)
    var images: Array = cached_clips.get(role, [])
    var authored_count: int = int(ROLE_COUNTS[role])
    var total_frames: int = images.size() if not images.is_empty() else authored_count
    var fps: float = float(ROLE_FPS[role])
    var raw_index: int = int(floor(clip_time * fps))
    var index: int = raw_index % total_frames if loop else mini(raw_index, total_frames - 1)
    _show_frame(role, index)
    clip_time += delta
    return not loop and clip_time >= float(total_frames) / fps

func _start_attack() -> void:
    state = CombatState.ATTACK
    clip_role = "attack"
    clip_time = 0.0
    attack_hit_sent = false
    _show_frame("attack", 0)

func _start_death() -> void:
    state = CombatState.DEATH
    death_started = true
    death_hold_left = DEATH_HOLD_SECONDS
    clip_role = "death"
    clip_time = 0.0
    velocity = Vector3.ZERO
    collision_layer = 0
    collision_mask = 0
    remove_from_group("iglesia_zombies")
    _show_frame("death", 0)
    killed.emit(100)

func _physics_process(delta: float) -> void:
    if state == CombatState.DEATH:
        velocity = Vector3.ZERO
        if _advance_role(delta, "death", false):
            death_hold_left -= delta
            if death_hold_left <= 0.0:
                queue_free()
        return
    if target == null or not is_instance_valid(target):
        state = CombatState.WALK
        velocity = Vector3.ZERO
        _advance_role(delta, "idle", true)
        return
    var offset: Vector3 = target.global_position - global_position
    offset.y = 0.0
    if offset.length() <= ATTACK_RANGE:
        velocity.x = 0.0
        velocity.z = 0.0
        if state != CombatState.ATTACK:
            _start_attack()
        _advance_role(delta, "attack", false)
        var now_frame: int = _frame_index("attack")
        if not attack_hit_sent and now_frame >= ATTACK_DAMAGE_FRAME:
            if is_instance_valid(target) and global_position.distance_to(target.global_position) <= ATTACK_RANGE + 0.25:
                target.apply_zombie_damage(ATTACK_DAMAGE)
            attack_hit_sent = true
        if clip_time >= float(ROLE_COUNTS["attack"]) / float(ROLE_FPS["attack"]):
            # Next attack is a new 6-frame cycle with one damage event.
            _start_attack()
    else:
        state = CombatState.WALK
        _advance_role(delta, "walk", true)
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
    if state == CombatState.DEATH:
        return
    health -= amount
    if health <= 0.0:
        health = 0.0
        _start_death()
