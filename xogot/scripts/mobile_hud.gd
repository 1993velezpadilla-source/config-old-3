extends Control

func _ready() -> void:
	set_process(true)
	queue_redraw()
	print("XZOGOT_HUD_V2_READY")

func _process(_delta: float) -> void:
	queue_redraw()

func _draw() -> void:
	var s := size
	var white := Color(1.0, 1.0, 1.0, 0.72)
	var dim := Color(1.0, 1.0, 1.0, 0.13)
	var warm := Color(1.0, 0.42, 0.12, 0.24)
	var cool := Color(0.42, 0.68, 1.0, 0.22)

	# Crosshair.
	var c := s * 0.5
	draw_line(c + Vector2(-9, 0), c + Vector2(-3, 0), white, 2.0)
	draw_line(c + Vector2(3, 0), c + Vector2(9, 0), white, 2.0)
	draw_line(c + Vector2(0, -9), c + Vector2(0, -3), white, 2.0)
	draw_line(c + Vector2(0, 3), c + Vector2(0, 9), white, 2.0)

	var min_dim: float = minf(s.x, s.y)
	var move_center := Vector2(s.x * 0.15, s.y * 0.79)
	var crouch_center := Vector2(s.x * 0.76, s.y * 0.82)
	var jump_center := Vector2(s.x * 0.90, s.y * 0.82)

	# Touch regions.
	draw_circle(move_center, min_dim * 0.075, dim)
	draw_circle(crouch_center, min_dim * 0.050, cool)
	draw_circle(jump_center, min_dim * 0.055, warm)

	# Jump glyph.
	draw_line(jump_center + Vector2(-10, 5), jump_center + Vector2(0, -7), white, 3.0)
	draw_line(jump_center + Vector2(0, -7), jump_center + Vector2(10, 5), white, 3.0)

	# Crouch / slide glyph.
	draw_line(crouch_center + Vector2(-12, 7), crouch_center + Vector2(10, 7), white, 3.0)
	draw_line(crouch_center + Vector2(-4, -7), crouch_center + Vector2(7, 1), white, 3.0)
	draw_circle(crouch_center + Vector2(-9, -9), 3.2, white)

	# Right-side look area hint kept intentionally subtle.
	draw_arc(Vector2(s.x * 0.73, s.y * 0.43), min_dim * 0.045, -0.8, 0.8, 18, Color(1,1,1,0.08), 2.0)
