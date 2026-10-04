extends Control

const MobileLayout = preload("res://scripts/mobile_layout.gd")

# Exact Sep-29 Touch+Gyro artwork restored from the historical APK contract.
const HUD_ADS = preload("res://assets/hud/latest_12/hud_ads.webp")
const HUD_ADSFIRE = preload("res://assets/hud/latest_12/hud_ads_fire.webp")
const HUD_CLAW = preload("res://assets/hud/latest_12/hud_claw.webp")
const HUD_CROUCH = preload("res://assets/hud/latest_12/hud_crouch.webp")
const HUD_FIRE = preload("res://assets/hud/latest_12/hud_fire.png")
const HUD_GRENADE = preload("res://assets/hud/latest_12/hud_grenade.webp")
const HUD_KNIFE = preload("res://assets/hud/latest_12/hud_knife.webp")
const HUD_PRONE = preload("res://assets/hud/latest_12/hud_prone.webp")
const HUD_RELOAD = preload("res://assets/hud/latest_12/hud_reload.webp")
const HUD_SLIDE = preload("res://assets/hud/latest_12/hud_slide.webp")
const HUD_SPRINT = preload("res://assets/hud/latest_12/hud_sprint.webp")
const HUD_SWAP = preload("res://assets/hud/latest_12/hud_swap.webp")

# Sep-29 set intentionally had no Jump/Vault face; this is the last authored
# project PNG for Jump/Vault, restored from the prior official pack.
const HUD_JUMP = preload("res://assets/hud/latest_12/hud_jump.png")

# The latest 12-pack did not replace joystick art. Keep the established XZIEL
# joystick only; action buttons below are all restored latest artwork.
const TEX_JOY_RING = preload("res://assets/hud/official/joystick_ring.svg")
const TEX_JOY_KNOB = preload("res://assets/hud/official/joystick_knob.svg")
const TEX_JOY_KNOB_ACTIVE = preload("res://assets/hud/official/joystick_knob_active.svg")

const IDLE_ALPHA := 210.0 / 255.0
const PRESSED_ALPHA := 246.0 / 255.0

var _hud_opacity: float = 0.82

@onready var _player: Node = get_node_or_null("../../Player")
@onready var _weapon: Node = get_node_or_null("../../Player/Weapon")
@onready var _round_manager: Node = get_node_or_null("../../RoundManager")

func _ready() -> void:
	set_process(true)
	var settings: Node = get_node_or_null("../MobileSettings")
	if settings != null:
		apply_mobile_settings(settings)
	queue_redraw()
	print("XZOGOT_HUD_V8_READY")
	print("XZOGOT_LATEST_12_SKINS_READY")
	print("XZOGOT_FIRE_SKIN_VALID_PNG_READY")

func _process(_delta: float) -> void:
	queue_redraw()

func _screen(center: Vector2) -> Vector2:
	return MobileLayout.screen_point(center, size)

func apply_mobile_settings(settings: Node) -> void:
	if settings != null and settings.has_method("get_setting_value"):
		_hud_opacity = clampf(float(settings.call("get_setting_value", "hud_opacity")), 0.25, 1.0)
	queue_redraw()

func _draw_pause_button() -> void:
	var center: Vector2 = _screen(MobileLayout.PAUSE_CENTER)
	var radius: float = MobileLayout.PAUSE_RADIUS * size.y
	var alpha: float = _hud_opacity
	draw_circle(center, radius, Color(0.04, 0.04, 0.05, 0.64 * alpha))
	draw_arc(center, radius * 0.88, 0.0, TAU, 32, Color(1.0, 1.0, 1.0, 0.34 * alpha), 1.6)
	var bar_w: float = radius * 0.22
	var bar_h: float = radius * 0.82
	var gap: float = radius * 0.18
	draw_rect(
		Rect2(center + Vector2(-gap - bar_w, -bar_h * 0.5), Vector2(bar_w, bar_h)),
		Color(1.0, 1.0, 1.0, 0.86 * alpha),
		true
	)
	draw_rect(
		Rect2(center + Vector2(gap, -bar_h * 0.5), Vector2(bar_w, bar_h)),
		Color(1.0, 1.0, 1.0, 0.86 * alpha),
		true
	)

func _draw_tex_center(
	texture: Texture2D,
	center: Vector2,
	diameter: float,
	alpha: float = 1.0
) -> void:
	if texture == null:
		return
	var d := Vector2(diameter, diameter)
	draw_texture_rect(
		texture,
		Rect2(center - d * 0.5, d),
		false,
		Color(1.0, 1.0, 1.0, alpha)
	)

func _draw_latest_control(
	center_norm: Vector2,
	radius_h: float,
	texture: Texture2D,
	pressed: bool,
	visual_scale: float = 1.0
) -> void:
	var center: Vector2 = _screen(center_norm)
	var press_scale: float = 1.06 if pressed else 1.0
	var diameter: float = radius_h * size.y * 2.20 * visual_scale * press_scale
	var alpha: float = (PRESSED_ALPHA if pressed else IDLE_ALPHA) * _hud_opacity
	_draw_tex_center(texture, center, diameter, alpha)

func _draw_joystick() -> void:
	var center: Vector2 = _screen(MobileLayout.JOY_CENTER)
	var ring_radius: float = MobileLayout.JOY_VISUAL_RADIUS * size.y
	var ring_diameter: float = ring_radius * 2.12
	_draw_tex_center(TEX_JOY_RING, center, ring_diameter, 0.78)

	var move_vector := Vector2.ZERO
	var active := false
	if _player != null:
		if _player.has_method("get_move_vector"):
			move_vector = _player.call("get_move_vector") as Vector2
		if _player.has_method("is_move_touch_active"):
			active = bool(_player.call("is_move_touch_active"))

	var knob_center: Vector2 = center + move_vector * ring_radius * 0.72
	var knob_diameter: float = 0.042 * size.y * 2.18
	_draw_tex_center(
		TEX_JOY_KNOB_ACTIVE if active else TEX_JOY_KNOB,
		knob_center,
		knob_diameter,
		0.88
	)

func _draw() -> void:
	var s: Vector2 = size
	var white := Color(1.0, 1.0, 1.0, 0.72)
	var warm := Color(1.0, 0.42, 0.12, 0.24)
	var combat := Color(1.0, 0.16, 0.12, 0.28)

	# Small COD-style center reticle.
	var c: Vector2 = s * 0.5
	draw_line(c + Vector2(-8, 0), c + Vector2(-3, 0), white, 1.8)
	draw_line(c + Vector2(3, 0), c + Vector2(8, 0), white, 1.8)
	draw_line(c + Vector2(0, -8), c + Vector2(0, -3), white, 1.8)
	draw_line(c + Vector2(0, 3), c + Vector2(0, 8), white, 1.8)

	_draw_joystick()

	var fire_pressed := false
	var ads_pressed := false
	var adsfire_pressed := false
	var stance_pressed := false
	var sprinting := false
	var sliding := false
	if _player != null:
		if _player.has_method("is_fire_pressed"):
			fire_pressed = bool(_player.call("is_fire_pressed"))
		if _player.has_method("is_ads_pressed"):
			ads_pressed = bool(_player.call("is_ads_pressed"))
		if _player.has_method("is_adsfire_pressed"):
			adsfire_pressed = bool(_player.call("is_adsfire_pressed"))
		if _player.has_method("is_slide_pressed"):
			stance_pressed = bool(_player.call("is_slide_pressed"))
		if _player.has_method("is_sprinting"):
			sprinting = bool(_player.call("is_sprinting"))
		if _player.has_method("is_sliding"):
			sliding = bool(_player.call("is_sliding"))

	var reload_pressed := false
	if _weapon != null and _weapon.has_method("is_reloading"):
		reload_pressed = bool(_weapon.call("is_reloading"))

	_draw_latest_control(
		MobileLayout.FIRE_CENTER,
		MobileLayout.FIRE_RADIUS,
		HUD_FIRE,
		fire_pressed
	)
	_draw_latest_control(
		MobileLayout.ADSFIRE_CENTER,
		MobileLayout.ADSFIRE_RADIUS,
		HUD_ADSFIRE,
		adsfire_pressed
	)
	_draw_latest_control(
		MobileLayout.ADS_CENTER,
		MobileLayout.ADS_RADIUS,
		HUD_ADS,
		ads_pressed
	)
	_draw_latest_control(
		MobileLayout.RELOAD_CENTER,
		MobileLayout.RELOAD_RADIUS,
		HUD_RELOAD,
		reload_pressed
	)
	_draw_latest_control(
		MobileLayout.USE_CENTER,
		MobileLayout.USE_RADIUS,
		HUD_CLAW,
		false
	)
	_draw_latest_control(
		MobileLayout.JUMP_CENTER,
		MobileLayout.JUMP_RADIUS,
		HUD_JUMP,
		false
	)

	var show_knife: bool = true
	var knife_pressed: bool = false
	if _player != null:
		if bool(_player.get("knife_button_range_only")) and _player.has_method("is_knife_target_near"):
			show_knife = bool(_player.call("is_knife_target_near"))
		if _player.has_method("is_knifing"):
			knife_pressed = bool(_player.call("is_knifing"))
	if show_knife:
		_draw_latest_control(
			MobileLayout.KNIFE_CENTER,
			MobileLayout.KNIFE_RADIUS,
			HUD_KNIFE,
			knife_pressed
		)

	_draw_pause_button()

	# Same gameplay button: crouch at normal pace, tactical slide while sprinting.
	var stance_texture: Texture2D = HUD_SLIDE if (sprinting or sliding) else HUD_CROUCH
	_draw_latest_control(
		MobileLayout.SLIDE_CENTER,
		MobileLayout.SLIDE_RADIUS,
		stance_texture,
		stance_pressed
	)

	# Historical requirement: auto-sprint icon is an indicator, not another hit target.
	if sprinting:
		var sprint_center := Vector2(
			MobileLayout.JOY_CENTER.x,
			MobileLayout.JOY_CENTER.y - 0.145
		)
		_draw_latest_control(sprint_center, 0.034, HUD_SPRINT, true, 0.94)

	# Ammo bar.
	if _weapon != null and _weapon.has_method("get_magazine"):
		var magazine: int = int(_weapon.call("get_magazine"))
		var capacity: int = int(_weapon.get("magazine_size"))
		var ratio: float = float(magazine) / maxf(float(capacity), 1.0)
		var bar_size := Vector2(s.x * 0.14, 7.0)
		var bar_pos := Vector2(s.x * 0.79, s.y * 0.50)
		draw_rect(Rect2(bar_pos, bar_size), Color(1.0, 1.0, 1.0, 0.10), true)
		draw_rect(Rect2(bar_pos, Vector2(bar_size.x * ratio, bar_size.y)), white, true)

	# Points + health rails.
	if _player != null and _player.has_method("get_points"):
		var points: int = int(_player.call("get_points"))
		var point_ratio: float = clampf(float(points) / 5000.0, 0.0, 1.0)
		var points_size := Vector2(s.x * 0.16, 6.0)
		var points_pos := Vector2(s.x * 0.05, s.y * 0.92)
		draw_rect(Rect2(points_pos, points_size), Color(1.0, 1.0, 1.0, 0.10), true)
		draw_rect(Rect2(points_pos, Vector2(points_size.x * point_ratio, points_size.y)), warm, true)

	if _player != null and _player.has_method("get_health"):
		var health: float = float(_player.call("get_health"))
		var max_health: float = float(_player.get("max_health"))
		var health_ratio: float = clampf(health / maxf(max_health, 1.0), 0.0, 1.0)
		var health_size := Vector2(s.x * 0.16, 6.0)
		var health_pos := Vector2(s.x * 0.05, s.y * 0.89)
		draw_rect(Rect2(health_pos, health_size), Color(1.0, 1.0, 1.0, 0.10), true)
		draw_rect(Rect2(health_pos, Vector2(health_size.x * health_ratio, health_size.y)), combat, true)

	if _round_manager != null and _round_manager.has_method("get_round"):
		var current_round: int = int(_round_manager.call("get_round"))
		var round_ratio: float = clampf(float(current_round) / 10.0, 0.0, 1.0)
		var round_size := Vector2(s.x * 0.12, 5.0)
		var round_pos := Vector2(s.x * 0.44, s.y * 0.06)
		draw_rect(Rect2(round_pos, round_size), Color(1.0, 1.0, 1.0, 0.10), true)
		draw_rect(Rect2(round_pos, Vector2(round_size.x * round_ratio, round_size.y)), white, true)
