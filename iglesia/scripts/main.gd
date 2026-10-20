extends Node3D
## New Iglesia Godot 4.6 runtime. No previous map/engine script is used.
const LevelScript = preload("res://scripts/level.gd")
const PlayerScript = preload("res://scripts/player.gd")
const EnemyScript = preload("res://scripts/enemy.gd")
const HUDScript = preload("res://scripts/hud.gd")

var level: Node3D
var player: CharacterBody3D
var hud: CanvasLayer
var points: int = 500
var round_number: int = 1
var round_remaining: int = 0
var spawn_delay: float = 0.7
var spawn_clock: float = 0.0
var between_rounds: float = -1.0
var game_over: bool = false
var spawn_cursor: int = 0
var spawn_positions: Array[Vector3] = [
    Vector3(-6.0, 0.15, -11.0), Vector3(6.0, 0.15, -11.0),
    Vector3(-6.0, 0.15, 7.0), Vector3(6.0, 0.15, 7.0),
    Vector3(0.0, 0.15, -12.5)
]

func _ready() -> void:
    _create_lighting()
    level = LevelScript.new()
    level.name = "NewIglesiaNave"
    add_child(level)
    player = PlayerScript.new()
    player.name = "NunPlayerFPS"
    add_child(player)
    player.position = Vector3(0.0, 0.2, 11.1)
    player.game = self
    player.level = level
    hud = HUDScript.new()
    hud.name = "OfficialTouchHUD"
    add_child(hud)
    hud.game = self
    hud.player = player
    player.hud = hud
    _begin_round()
    Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if not OS.has_feature("mobile") else Input.MOUSE_MODE_VISIBLE

func _create_lighting() -> void:
    var world := WorldEnvironment.new()
    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.012, 0.018, 0.030)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.18, 0.21, 0.30)
    env.ambient_light_energy = 0.42
    env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
    world.environment = env
    add_child(world)
    var moon := DirectionalLight3D.new()
    moon.light_color = Color(0.56, 0.69, 1.0)
    moon.light_energy = 0.30
    moon.rotation_degrees = Vector3(-47.0, -31.0, 0.0)
    add_child(moon)
    var altar_light := OmniLight3D.new()
    altar_light.position = Vector3(0.0, 5.5, -12.0)
    altar_light.light_color = Color(1.0, 0.51, 0.24)
    altar_light.light_energy = 2.5
    altar_light.omni_range = 10.0
    altar_light.shadow_enabled = true
    add_child(altar_light)

func _begin_round() -> void:
    # Intentionally no maximum round. Spawn cap protects Android memory.
    round_remaining = mini(5 + round_number * 2, 120)
    spawn_clock = 0.0
    spawn_delay = maxf(0.35, 1.15 - float(round_number) * 0.025)
    hud.show_notice("RONDA %d" % round_number)

func _process(delta: float) -> void:
    if game_over:
        return
    if player.health <= 0:
        game_over = true
        hud.show_notice("HAS CAÍDO — REINICIAR")
        return
    if between_rounds > 0.0:
        between_rounds -= delta
        if between_rounds <= 0.0:
            round_number += 1
            _begin_round()
    elif round_remaining > 0:
        spawn_clock -= delta
        if spawn_clock <= 0.0 and get_tree().get_nodes_in_group("iglesia_zombies").size() < 12:
            _spawn_zombie()
            round_remaining -= 1
            spawn_clock = spawn_delay
    elif get_tree().get_nodes_in_group("iglesia_zombies").is_empty():
        between_rounds = 5.0
        points += 100
        hud.show_notice("RONDA SUPERADA +100")
    if Input.is_action_just_pressed("interact"):
        buy_wall_ammo()
    hud.update_stats(player.health, player.magazine, player.reserve_ammo, round_number, points, player.reload_active)

func _spawn_zombie() -> void:
    var zombie := EnemyScript.new()
    zombie.position = spawn_positions[spawn_cursor % spawn_positions.size()]
    spawn_cursor += 1
    zombie.target = player
    zombie.level = level
    zombie.health = 65.0 + float(round_number - 1) * 18.0
    zombie.move_speed = minf(4.3, 1.3 + float(round_number - 1) * 0.08)
    zombie.killed.connect(_on_enemy_killed)
    add_child(zombie)

func _on_enemy_killed(reward: int) -> void:
    points += reward

func buy_wall_ammo() -> void:
    if player.global_position.distance_to(Vector3(7.0, 0.0, 8.0)) > 2.8:
        return
    if points < 500:
        hud.show_notice("NO TIENES 500 PUNTOS")
        return
    points -= 500
    player.reserve_ammo += 96
    hud.show_notice("MP40 — MUNICIÓN +96")

func restart_game() -> void:
    get_tree().reload_current_scene()
