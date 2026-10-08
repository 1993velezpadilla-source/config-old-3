extends Control

## Native, paused touch HUD editor. Rendering and gameplay input share the
## same normalized positions; the player never moves while this overlay handles
## touch events, and the original layout can always be restored with CANCEL.
signal editor_finished(saved: bool)

const MobileLayout = preload("res://scripts/mobile_layout.gd")
const INACTIVE_TOUCH := -999

var _before: Dictionary = {}
var _picked: String = ""
var _pointer: int = INACTIVE_TOUCH

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	mouse_filter = Control.MOUSE_FILTER_STOP
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

	var hint := Label.new()
	hint.name = "EditorHint"
	hint.anchor_left = 0.12
	hint.anchor_right = 0.88
	hint.anchor_top = 0.01
	hint.anchor_bottom = 0.07
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	hint.text = "DRAG ANY CONTROL  •  SAVE / RESET / CANCEL"
	hint.add_theme_font_size_override("font_size", 20)
	hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(hint)

	var bar := HBoxContainer.new()
	bar.name = "EditorActions"
	bar.anchor_left = 0.16
	bar.anchor_right = 0.84
	bar.anchor_top = 0.91
	bar.anchor_bottom = 0.99
	bar.add_theme_constant_override("separation", 8)
	add_child(bar)

	_make_action(bar, "SAVE", _save)
	_make_action(bar, "RESET", _reset)
	_make_action(bar, "CANCEL", _cancel)
	visible = false

func _make_action(bar: HBoxContainer, label: String, callback: Callable) -> void:
	var button := Button.new()
	button.name = label.capitalize()
	button.text = label
	button.custom_minimum_size = Vector2(0, 50)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.pressed.connect(callback)
	bar.add_child(button)

func begin_edit() -> void:
	_before = MobileLayout.snapshot()
	_pointer = INACTIVE_TOUCH
	_picked = ""
	visible = true
	queue_redraw()

func _finish(saved: bool) -> void:
	if saved:
		var result: Error = MobileLayout.save_centers()
		if result != OK:
			push_error("HUD_EDITOR: failed saving user layout: " + str(result))
			saved = false
	if not saved:
		MobileLayout.restore_snapshot(_before)
	_pointer = INACTIVE_TOUCH
	_picked = ""
	visible = false
	editor_finished.emit(saved)

func _save() -> void:
	_finish(true)

func _reset() -> void:
	MobileLayout.reset_centers()
	queue_redraw()

func _cancel() -> void:
	_finish(false)

func _pick_key(pixel: Vector2) -> String:
	var nearest: String = ""
	var nearest_distance := INF
	for key: String in MobileLayout.control_keys():
		var center: Vector2 = MobileLayout.screen_point(MobileLayout.center_for(key), size)
		var radius := MobileLayout.control_radius(key) * size.y
		var distance := pixel.distance_to(center)
		if distance <= radius + 20.0 and distance < nearest_distance:
			nearest = key
			nearest_distance = distance
	return nearest

func _move_selected(pixel: Vector2) -> void:
	if _picked.is_empty() or size.x <= 1.0 or size.y <= 1.0:
		return
	var normalized := Vector2(pixel.x / size.x, pixel.y / size.y)
	if MobileLayout.set_center(_picked, normalized):
		queue_redraw()
		var hud := get_node_or_null("../MobileHUD") as Control
		if hud != null:
			hud.queue_redraw()

func _gui_input(event: InputEvent) -> void:
	if not visible:
		return
	if event is InputEventScreenTouch:
		var touch := event as InputEventScreenTouch
		if touch.pressed and _pointer == INACTIVE_TOUCH:
			_picked = _pick_key(touch.position)
			if not _picked.is_empty():
				_pointer = touch.index
		elif not touch.pressed and touch.index == _pointer:
			_pointer = INACTIVE_TOUCH
			_picked = ""
		accept_event()
	elif event is InputEventScreenDrag:
		var drag := event as InputEventScreenDrag
		if drag.index == _pointer and not _picked.is_empty():
			_move_selected(drag.position)
		accept_event()
	elif event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if button.button_index == MOUSE_BUTTON_LEFT:
			if button.pressed and _pointer == INACTIVE_TOUCH:
				_picked = _pick_key(button.position)
				if not _picked.is_empty():
					_pointer = -2
			elif not button.pressed and _pointer == -2:
				_pointer = INACTIVE_TOUCH
				_picked = ""
			accept_event()
	elif event is InputEventMouseMotion:
		if _pointer == -2 and not _picked.is_empty():
			_move_selected((event as InputEventMouseMotion).position)
			accept_event()

func _draw() -> void:
	if not visible:
		return
	var font: Font = ThemeDB.fallback_font
	var font_size := maxi(13, mini(21, roundi(size.y * 0.025)))
	for key: String in MobileLayout.control_keys():
		var center := MobileLayout.screen_point(MobileLayout.center_for(key), size)
		var radius := MobileLayout.control_radius(key) * size.y
		var active := key == _picked
		var edge := Color(0.99, 0.69, 0.25, 0.98) if active else Color(0.64, 0.87, 1.0, 0.86)
		draw_circle(center, radius, Color(0.02, 0.04, 0.06, 0.40))
		draw_arc(center, radius, 0.0, TAU, 36, edge, 2.3)
		draw_string(
			font, center + Vector2(-radius, 4.0), key.to_upper(),
			HORIZONTAL_ALIGNMENT_CENTER, radius * 2.0, font_size, Color.WHITE
		)
