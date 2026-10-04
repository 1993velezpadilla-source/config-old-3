extends Control

const CONFIG_PATH := "user://xogot_mobile_settings.cfg"

var ads_toggle_mode: bool = false
var gyro_mode: int = 1 # 0=OFF, 1=ALWAYS, 2=ADS ONLY
var gyro_invert_x: bool = false
var gyro_invert_y: bool = false
var gyro_sensitivity_x: float = 0.70
var gyro_sensitivity_y: float = 0.70
var gyro_ads_multiplier: float = 0.65
var gyro_deadzone: float = 0.05
var gyro_smoothing: float = 0.18
var auto_knife: bool = true
var knife_button_range_only: bool = true
var knife_range_m: float = 1.65
var auto_rebuild: bool = true
var repair_repeat_interval: float = 0.45
var hud_opacity: float = 0.82

var _panel: PanelContainer
var _rows: Dictionary = {}

func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_load_settings()
	_build_ui()
	visible = false
	call_deferred("_apply_to_player")
	print("XZOGOT_MOBILE_SETTINGS_READY")

func _load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(CONFIG_PATH) != OK:
		return
	ads_toggle_mode = bool(cfg.get_value("aim", "ads_toggle_mode", ads_toggle_mode))
	gyro_mode = int(cfg.get_value("gyro", "mode", gyro_mode))
	gyro_invert_x = bool(cfg.get_value("gyro", "invert_x", gyro_invert_x))
	gyro_invert_y = bool(cfg.get_value("gyro", "invert_y", gyro_invert_y))
	gyro_sensitivity_x = float(cfg.get_value("gyro", "sensitivity_x", gyro_sensitivity_x))
	gyro_sensitivity_y = float(cfg.get_value("gyro", "sensitivity_y", gyro_sensitivity_y))
	gyro_ads_multiplier = float(cfg.get_value("gyro", "ads_multiplier", gyro_ads_multiplier))
	gyro_deadzone = float(cfg.get_value("gyro", "deadzone", gyro_deadzone))
	gyro_smoothing = float(cfg.get_value("gyro", "smoothing", gyro_smoothing))
	auto_knife = bool(cfg.get_value("gameplay", "auto_knife", auto_knife))
	knife_button_range_only = bool(cfg.get_value("gameplay", "knife_button_range_only", knife_button_range_only))
	knife_range_m = float(cfg.get_value("gameplay", "knife_range_m", knife_range_m))
	auto_rebuild = bool(cfg.get_value("gameplay", "auto_rebuild", auto_rebuild))
	repair_repeat_interval = float(cfg.get_value("gameplay", "repair_repeat_interval", repair_repeat_interval))
	hud_opacity = float(cfg.get_value("hud", "opacity", hud_opacity))

func _save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("aim", "ads_toggle_mode", ads_toggle_mode)
	cfg.set_value("gyro", "mode", gyro_mode)
	cfg.set_value("gyro", "invert_x", gyro_invert_x)
	cfg.set_value("gyro", "invert_y", gyro_invert_y)
	cfg.set_value("gyro", "sensitivity_x", gyro_sensitivity_x)
	cfg.set_value("gyro", "sensitivity_y", gyro_sensitivity_y)
	cfg.set_value("gyro", "ads_multiplier", gyro_ads_multiplier)
	cfg.set_value("gyro", "deadzone", gyro_deadzone)
	cfg.set_value("gyro", "smoothing", gyro_smoothing)
	cfg.set_value("gameplay", "auto_knife", auto_knife)
	cfg.set_value("gameplay", "knife_button_range_only", knife_button_range_only)
	cfg.set_value("gameplay", "knife_range_m", knife_range_m)
	cfg.set_value("gameplay", "auto_rebuild", auto_rebuild)
	cfg.set_value("gameplay", "repair_repeat_interval", repair_repeat_interval)
	cfg.set_value("hud", "opacity", hud_opacity)
	cfg.save(CONFIG_PATH)

func _add_button(vbox: VBoxContainer, key: String, text_value: String) -> Button:
	var button := Button.new()
	button.name = "Setting_" + key
	button.text = text_value
	button.custom_minimum_size = Vector2(0.0, 50.0)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_child(button)
	_rows[key] = button
	return button

func _build_ui() -> void:
	var shade := ColorRect.new()
	shade.name = "SettingsShade"
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.color = Color(0.01, 0.01, 0.015, 0.90)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(shade)

	_panel = PanelContainer.new()
	_panel.name = "SettingsPanel"
	_panel.anchor_left = 0.12
	_panel.anchor_top = 0.06
	_panel.anchor_right = 0.88
	_panel.anchor_bottom = 0.94
	_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_panel)

	var scroll := ScrollContainer.new()
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_panel.add_child(scroll)

	var vbox := VBoxContainer.new()
	vbox.name = "SettingsRows"
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 8)
	scroll.add_child(vbox)

	var title := Label.new()
	title.text = "MOBILE SETTINGS"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 30)
	vbox.add_child(title)

	var ads := _add_button(vbox, "ads_mode", "")
	ads.pressed.connect(_cycle_ads_mode)

	var gyro := _add_button(vbox, "gyro_mode", "")
	gyro.pressed.connect(_cycle_gyro_mode)

	var invx := _add_button(vbox, "gyro_invert_x", "")
	invx.pressed.connect(_toggle_gyro_invert_x)

	var invy := _add_button(vbox, "gyro_invert_y", "")
	invy.pressed.connect(_toggle_gyro_invert_y)

	var sensx := _add_button(vbox, "gyro_sensitivity_x", "")
	sensx.pressed.connect(_cycle_gyro_sensitivity_x)

	var sensy := _add_button(vbox, "gyro_sensitivity_y", "")
	sensy.pressed.connect(_cycle_gyro_sensitivity_y)

	var adsmult := _add_button(vbox, "gyro_ads_multiplier", "")
	adsmult.pressed.connect(_cycle_gyro_ads_multiplier)

	var deadzone := _add_button(vbox, "gyro_deadzone", "")
	deadzone.pressed.connect(_cycle_gyro_deadzone)

	var smoothing := _add_button(vbox, "gyro_smoothing", "")
	smoothing.pressed.connect(_cycle_gyro_smoothing)

	var autoknife := _add_button(vbox, "auto_knife", "")
	autoknife.pressed.connect(_toggle_auto_knife)

	var knifebutton := _add_button(vbox, "knife_button_range_only", "")
	knifebutton.pressed.connect(_toggle_knife_button_visibility)

	var autorebuild := _add_button(vbox, "auto_rebuild", "")
	autorebuild.pressed.connect(_toggle_auto_rebuild)

	var opacity := _add_button(vbox, "hud_opacity", "")
	opacity.pressed.connect(_cycle_hud_opacity)

	var close := Button.new()
	close.name = "CloseSettings"
	close.text = "BACK TO GAME"
	close.custom_minimum_size = Vector2(0.0, 58.0)
	close.pressed.connect(close_menu)
	vbox.add_child(close)

	_refresh_labels()

func _refresh_labels() -> void:
	if _rows.is_empty():
		return
	(_rows["ads_mode"] as Button).text = "ADS MODE: " + ("TAP / TOGGLE" if ads_toggle_mode else "HOLD")
	var gyro_names := ["OFF", "ALWAYS ON", "ADS ONLY"]
	(_rows["gyro_mode"] as Button).text = "GYROSCOPE: " + gyro_names[clampi(gyro_mode, 0, 2)]
	(_rows["gyro_invert_x"] as Button).text = "GYRO INVERT X: " + ("ON" if gyro_invert_x else "OFF")
	(_rows["gyro_invert_y"] as Button).text = "GYRO INVERT Y: " + ("ON" if gyro_invert_y else "OFF")
	(_rows["gyro_sensitivity_x"] as Button).text = "GYRO HORIZONTAL: %.2f" % gyro_sensitivity_x
	(_rows["gyro_sensitivity_y"] as Button).text = "GYRO VERTICAL: %.2f" % gyro_sensitivity_y
	(_rows["gyro_ads_multiplier"] as Button).text = "GYRO ADS MULTIPLIER: %.2f" % gyro_ads_multiplier
	(_rows["gyro_deadzone"] as Button).text = "GYRO DEADZONE: %.2f" % gyro_deadzone
	(_rows["gyro_smoothing"] as Button).text = "GYRO SMOOTHING: %.2f" % gyro_smoothing
	(_rows["auto_knife"] as Button).text = "AUTO KNIFE: " + ("ENABLED" if auto_knife else "DISABLED")
	(_rows["knife_button_range_only"] as Button).text = "KNIFE BUTTON: " + ("IN RANGE" if knife_button_range_only else "ALWAYS")
	(_rows["auto_rebuild"] as Button).text = "AUTO REBUILD BARRIERS: " + ("ENABLED" if auto_rebuild else "DISABLED")
	(_rows["hud_opacity"] as Button).text = "HUD OPACITY: %d%%" % int(round(hud_opacity * 100.0))

func _commit() -> void:
	_save_settings()
	_refresh_labels()
	_apply_to_player()
	var hud: Node = get_node_or_null("../MobileHUD")
	if hud != null and hud.has_method("apply_mobile_settings"):
		hud.call("apply_mobile_settings", self)

func _apply_to_player() -> void:
	var player: Node = get_node_or_null("../../Player")
	if player != null and player.has_method("apply_mobile_settings"):
		player.call("apply_mobile_settings", self)

func toggle_menu() -> void:
	visible = not visible
	mouse_filter = Control.MOUSE_FILTER_STOP if visible else Control.MOUSE_FILTER_IGNORE
	if visible:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	print("XZOGOT_SETTINGS_MENU ", "OPEN" if visible else "CLOSED")

func close_menu() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_apply_to_player()

func is_menu_open() -> bool:
	return visible

func get_setting_value(key: String) -> Variant:
	match key:
		"ads_toggle_mode": return ads_toggle_mode
		"gyro_mode": return gyro_mode
		"gyro_invert_x": return gyro_invert_x
		"gyro_invert_y": return gyro_invert_y
		"gyro_sensitivity_x": return gyro_sensitivity_x
		"gyro_sensitivity_y": return gyro_sensitivity_y
		"gyro_ads_multiplier": return gyro_ads_multiplier
		"gyro_deadzone": return gyro_deadzone
		"gyro_smoothing": return gyro_smoothing
		"auto_knife": return auto_knife
		"knife_button_range_only": return knife_button_range_only
		"knife_range_m": return knife_range_m
		"auto_rebuild": return auto_rebuild
		"repair_repeat_interval": return repair_repeat_interval
		"hud_opacity": return hud_opacity
	return null

func _cycle_ads_mode() -> void:
	ads_toggle_mode = not ads_toggle_mode
	_commit()

func _cycle_gyro_mode() -> void:
	gyro_mode = (gyro_mode + 1) % 3
	_commit()

func _toggle_gyro_invert_x() -> void:
	gyro_invert_x = not gyro_invert_x
	_commit()

func _toggle_gyro_invert_y() -> void:
	gyro_invert_y = not gyro_invert_y
	_commit()

func _cycle_value(value: float, step: float, minimum: float, maximum: float) -> float:
	var next: float = value + step
	if next > maximum + 0.0001:
		next = minimum
	return snappedf(next, step)

func _cycle_gyro_sensitivity_x() -> void:
	gyro_sensitivity_x = _cycle_value(gyro_sensitivity_x, 0.10, 0.20, 1.50)
	_commit()

func _cycle_gyro_sensitivity_y() -> void:
	gyro_sensitivity_y = _cycle_value(gyro_sensitivity_y, 0.10, 0.20, 1.50)
	_commit()

func _cycle_gyro_ads_multiplier() -> void:
	gyro_ads_multiplier = _cycle_value(gyro_ads_multiplier, 0.05, 0.30, 1.00)
	_commit()

func _cycle_gyro_deadzone() -> void:
	gyro_deadzone = _cycle_value(gyro_deadzone, 0.01, 0.00, 0.12)
	_commit()

func _cycle_gyro_smoothing() -> void:
	gyro_smoothing = _cycle_value(gyro_smoothing, 0.05, 0.00, 0.40)
	_commit()

func _toggle_auto_knife() -> void:
	auto_knife = not auto_knife
	_commit()

func _toggle_knife_button_visibility() -> void:
	knife_button_range_only = not knife_button_range_only
	_commit()

func _toggle_auto_rebuild() -> void:
	auto_rebuild = not auto_rebuild
	_commit()

func _cycle_hud_opacity() -> void:
	hud_opacity = _cycle_value(hud_opacity, 0.10, 0.40, 1.00)
	_commit()
