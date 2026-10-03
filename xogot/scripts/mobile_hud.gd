extends Control

@onready var _weapon: Node = get_node_or_null("../../Player/Weapon")

func _ready() -> void:
	set_process(true)
	queue_redraw()
	print("XZOGOT_HUD_V3_READY")

func _process(_delta: float) -> void:
	queue_redraw()

func _draw() -> void:
	var s: Vector2 = size
	var white := Color(1.0, 1.0, 1.0, 0.72)
	var dim := Color(1.0, 1.0, 1.0, 0.13)
	var warm := Color(1.0, 0.42, 0.12, 0.24)
	var cool := Color(0.42, 0.68, 1.0, 0.22)
	var combat := Color(1.0, 0.16, 0.12, 0.28)

	# Crosshair.
	var c: Vector2 = s * 0.5
	draw_line(c + Vector2(-9, 0), c + Vector2(-3, 0), white, 2.0)
	draw_line(c + Vector2(3, 0), c + Vector2(9, 0), white, 2.0)
	draw_line(c + Vector2(0, -9), c + Vector2(0, -3), white, 2.0)
	draw_line(c + Vector2(0, 3), c + Vector2(0, 9), white, 2.0)

	var min_dim: float = minf(s.x, s.y)
	var move_center := Vector2(s.x * 0.15, s.y * 0.79)
	var crouch_center := Vector2(s.x * 0.76, s.y * 0.82)
	var jump_center := Vector2(s.x * 0.90, s.y * 0.82)
	var reload_center := Vector2(s.x * 0.76, s.y * 0.60)
	var fire_center := Vector2(s.x * 0.90, s.y * 0.60)

	# Touch regions.
	draw_circle(move_center, min_dim * 0.075, dim)
	draw_circle(crouch_center, min_dim * 0.050, cool)
	draw_circle(jump_center, min_dim * 0.055, warm)
	draw_circle(reload_center, min_dim * 0.044, dim)
	draw_circle(fire_center, min_dim * 0.060, combat)

	# Jump glyph.
	draw_line(jump_center + Vector2(-10, 5), jump_center + Vector2(0, -7), white, 3.0)
	draw_line(jump_center + Vector2(0, -7), jump_center + Vector2(10, 5), white, 3.0)

	# Crouch / slide glyph.
	draw_line(crouch_center + Vector2(-12, 7), crouch_center + Vector2(10, 7), white, 3.0)
	draw_line(crouch_center + Vector2(-4, -7), crouch_center + Vector2(7, 1), white, 3.0)
	draw_circle(crouch_center + Vector2(-9, -9), 3.2, white)

	# Fire glyph.
	draw_circle(fire_center, 10.0, white, false, 2.5)
	draw_circle(fire_center, 3.0, white)

	# Reload glyph.
	draw_arc(reload_center, 12.0, 0.25, 5.15, 22, white, 2.5)
	draw_line(reload_center + Vector2(-10, -7), reload_center + Vector2(-2, -12), white, 2.5)
	draw_line(reload_center + Vector2(-10, -7), reload_center + Vector2(-11, -15), white, 2.5)

	# Ammo bar: magazine percentage over a faint reserve rail.
	if _weapon != null and _weapon.has_method("get_magazine"):
		var magazine: int = int(_weapon.call("get_magazine"))
		var capacity: int = int(_weapon.get("magazine_size"))
		var ratio: float = float(magazine) / maxf(float(capacity), 1.0)
		var bar_size := Vector2(s.x * 0.14, 7.0)
		var bar_pos := Vector2(s.x * 0.79, s.y * 0.50)
		draw_rect(Rect2(bar_pos, bar_size), Color(1.0, 1.0, 1.0, 0.10), true)
		draw_rect(Rect2(bar_pos, Vector2(bar_size.x * ratio, bar_size.y)), white, true)

	# Right-side look area hint kept intentionally subtle.
	draw_arc(Vector2(s.x * 0.73, s.y * 0.38), min_dim * 0.045, -0.8, 0.8, 18, Color(1,1,1,0.08), 2.0)
