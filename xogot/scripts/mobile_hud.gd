extends Control

func _ready() -> void:
	set_process(true)
	queue_redraw()

func _process(_delta: float) -> void:
	queue_redraw()

func _draw() -> void:
	var s := size
	var white := Color(1.0, 1.0, 1.0, 0.72)
	var dim := Color(1.0, 1.0, 1.0, 0.13)
	var warm := Color(1.0, 0.42, 0.12, 0.24)

	# Crosshair.
	var c := s * 0.5
	draw_line(c + Vector2(-9, 0), c + Vector2(-3, 0), white, 2.0)
	draw_line(c + Vector2(3, 0), c + Vector2(9, 0), white, 2.0)
	draw_line(c + Vector2(0, -9), c + Vector2(0, -3), white, 2.0)
	draw_line(c + Vector2(0, 3), c + Vector2(0, 9), white, 2.0)

	# Touch regions: left stick and jump target.
	draw_circle(Vector2(s.x * 0.15, s.y * 0.79), min(s.x, s.y) * 0.075, dim)
	draw_circle(Vector2(s.x * 0.88, s.y * 0.82), min(s.x, s.y) * 0.055, warm)
