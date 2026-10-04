extends Control

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const CONFIG_PATH := "user://xogot_mobile_settings.cfg"

# Intentional: the DEV lab is present in optimized Release builds too so the
# exact shipping-performance binary can be play-tested. For a public store
# package this single flag can be turned off without touching gameplay code.
@export var dev_menu_visible_in_release: bool = true

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

# DEV flags deliberately do NOT persist between launches.
var dev_infinite_health: bool = false
var dev_infinite_points: bool = false
var dev_infinite_ammo: bool = false
var dev_no_zombies: bool = false
var dev_noclip: bool = false
var dev_speed_boost: bool = false

var _panel: PanelContainer
var _page_pause: VBoxContainer
var _page_settings: VBoxContainer
var _page_dev: VBoxContainer
var _rows: Dictionary = {}
var _dev_rows: Dictionary = {}
var _current_page: String = "pause"

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_load_settings()
	_build_ui()
	visible = false
	call_deferred("_apply_to_player")
	print("XZOGOT_MOBILE_SETTINGS_READY")
	print("XZOGOT_RELEASE_DEV_MENU_READY ", dev_menu_visible_in_release)

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

func _button(vbox: VBoxContainer, name_value: String, text_value: String) -> Button:
	var button := Button.new()
	button.name = name_value
	button.text = text_value
	button.custom_minimum_size = Vector2(0.0, 50.0)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_child(button)
	return button

func _title(vbox: VBoxContainer, text_value: String, subtitle: String = "") -> void:
	var title := Label.new()
	title.text = text_value
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 30)
	vbox.add_child(title)
	if not subtitle.is_empty():
		var sub := Label.new()
		sub.text = subtitle
		sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		sub.modulate = Color(0.72, 0.76, 0.80)
		vbox.add_child(sub)

func _page_container(parent: Control, page_name: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = page_name + "Scroll"
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	parent.add_child(scroll)
	var vbox := VBoxContainer.new()
	vbox.name = page_name
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 8)
	scroll.add_child(vbox)
	return vbox

func _build_ui() -> void:
	var shade := ColorRect.new()
	shade.name = "PauseShade"
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.color = Color(0.008, 0.009, 0.014, 0.92)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(shade)

	_panel = PanelContainer.new()
	_panel.name = "PausePanel"
	_panel.anchor_left = 0.14
	_panel.anchor_top = 0.07
	_panel.anchor_right = 0.86
	_panel.anchor_bottom = 0.93
	_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_panel)

	var pages := Control.new()
	pages.name = "Pages"
	pages.custom_minimum_size = Vector2(760, 760)
	pages.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_panel.add_child(pages)

	_page_pause = _page_container(pages, "PausePage")
	_page_settings = _page_container(pages, "SettingsPage")
	_page_dev = _page_container(pages, "DevPage")

	_build_pause_page()
	_build_settings_page()
	_build_dev_page()
	_show_page("pause")
	_refresh_labels()
	_refresh_dev_labels()

func _build_pause_page() -> void:
	_title(_page_pause, "PAUSED", "YOU WON'T WIN")
	var resume := _button(_page_pause, "Resume", "RESUME")
	resume.pressed.connect(close_menu)
	var settings := _button(_page_pause, "OpenSettings", "SETTINGS")
	settings.pressed.connect(func(): _show_page("settings"))
	if dev_menu_visible_in_release:
		var dev := _button(_page_pause, "OpenDev", "DEV LAB")
		dev.pressed.connect(func(): _show_page("dev"))
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(0, 24)
	_page_pause.add_child(spacer)
	var info := Label.new()
	info.text = "Release-performance test menu. DEV tools add no overlay or profiler overhead while disabled."
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	info.modulate = Color(0.62, 0.66, 0.70)
	_page_pause.add_child(info)

func _add_setting(key: String, callback: Callable) -> void:
	var b := _button(_page_settings, "Setting_" + key, "")
	b.pressed.connect(callback)
	_rows[key] = b

func _build_settings_page() -> void:
	_title(_page_settings, "SETTINGS", "Touch, aim, gyroscope and mobile assists")
	_add_setting("ads_mode", _cycle_ads_mode)
	_add_setting("gyro_mode", _cycle_gyro_mode)
	_add_setting("gyro_invert_x", _toggle_gyro_invert_x)
	_add_setting("gyro_invert_y", _toggle_gyro_invert_y)
	_add_setting("gyro_sensitivity_x", _cycle_gyro_sensitivity_x)
	_add_setting("gyro_sensitivity_y", _cycle_gyro_sensitivity_y)
	_add_setting("gyro_ads_multiplier", _cycle_gyro_ads_multiplier)
	_add_setting("gyro_deadzone", _cycle_gyro_deadzone)
	_add_setting("gyro_smoothing", _cycle_gyro_smoothing)
	_add_setting("auto_knife", _toggle_auto_knife)
	_add_setting("knife_button_range_only", _toggle_knife_button_visibility)
	_add_setting("auto_rebuild", _toggle_auto_rebuild)
	_add_setting("hud_opacity", _cycle_hud_opacity)
	var back := _button(_page_settings, "SettingsBack", "BACK")
	back.pressed.connect(func(): _show_page("pause"))

func _add_dev_toggle(key: String, callback: Callable) -> void:
	var b := _button(_page_dev, "Dev_" + key, "")
	b.pressed.connect(callback)
	_dev_rows[key] = b

func _build_dev_page() -> void:
	_title(
		_page_dev,
		"DEV LAB",
		"Release-safe gameplay switches. Green means active. Nothing is drawn on the player HUD."
	)
	_add_dev_toggle("infinite_health", func(): _set_dev_flag("infinite_health", not dev_infinite_health))
	_add_dev_toggle("infinite_points", func(): _set_dev_flag("infinite_points", not dev_infinite_points))
	_add_dev_toggle("infinite_ammo", func(): _set_dev_flag("infinite_ammo", not dev_infinite_ammo))
	_add_dev_toggle("no_zombies", func(): _set_dev_flag("no_zombies", not dev_no_zombies))
	_add_dev_toggle("noclip", func(): _set_dev_flag("noclip", not dev_noclip))
	_add_dev_toggle("speed_boost", func(): _set_dev_flag("speed_boost", not dev_speed_boost))

	var unlock := _button(_page_dev, "UnlockAll", "OPEN ALL DOORS / OBSTACLES")
	unlock.pressed.connect(_dev_unlock_all)
	var kill := _button(_page_dev, "KillAllZombies", "CLEAR ALL ZOMBIES")
	kill.pressed.connect(_dev_clear_all_zombies)
	var spawn := _button(_page_dev, "SpawnZombie", "SPAWN ONE TEST ZOMBIE")
	spawn.pressed.connect(_dev_spawn_one_zombie)

	var power_fx := _button(_page_dev, "TestPowerLights", "TEST POWER LIGHT STARTUP")
	power_fx.pressed.connect(_dev_test_power_lights)
	var candle_fx := _button(_page_dev, "TestCandleFlicker", "TEST CANDLE FLICKER")
	candle_fx.pressed.connect(_dev_test_candle_flicker)

	var divider := HSeparator.new()
	_page_dev.add_child(divider)
	var weapon_title := Label.new()
	weapon_title.text = "WEAPON LAB — WALL BUYS + MYSTERY BOX"
	weapon_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	weapon_title.add_theme_font_size_override("font_size", 22)
	_page_dev.add_child(weapon_title)

	var wall_set: Dictionary = {}
	for id: String in WeaponCatalog.WALL_BUY_ORDER:
		wall_set[id] = true
	var mystery_set: Dictionary = {}
	for id: String in WeaponCatalog.mystery_pool_ids():
		mystery_set[id] = true

	var weapon_ids: Array[String] = []
	for id_var: Variant in WeaponCatalog.WEAPONS.keys():
		weapon_ids.append(str(id_var))
	weapon_ids.sort()

	for id: String in weapon_ids:
		var def: Dictionary = WeaponCatalog.get_weapon(id)
		var tags: Array[String] = []
		if wall_set.has(id):
			tags.append("WALL")
		if mystery_set.has(id):
			tags.append("BOX")
		if id == WeaponCatalog.STARTING_WEAPON_ID:
			tags.append("START")
		var model_ok: bool = ResourceLoader.exists(str(def.get("model_path", "")))
		var fire_ok: bool = ResourceLoader.exists(str(def.get("fire_audio", "")))
		var tag_text: String = "CATALOG"
		if not tags.is_empty():
			tag_text = "/".join(PackedStringArray(tags))
		var status := "%s | MODEL %s | SFX %s" % [
			tag_text,
			"OK" if model_ok else "PENDING",
			"OK" if fire_ok else "PENDING"
		]
		var wb := _button(
			_page_dev,
			"Weapon_" + id,
			"%s  [%s]" % [str(def.get("display_name", id)).to_upper(), status]
		)
		wb.pressed.connect(_dev_equip_weapon.bind(id))

	var back := _button(_page_dev, "DevBack", "BACK")
	back.pressed.connect(func(): _show_page("pause"))

func _show_page(page: String) -> void:
	_current_page = page
	_page_pause.get_parent().visible = page == "pause"
	_page_settings.get_parent().visible = page == "settings"
	_page_dev.get_parent().visible = page == "dev"
	if page == "dev":
		_refresh_dev_labels()

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

func _dev_value(key: String) -> bool:
	match key:
		"infinite_health": return dev_infinite_health
		"infinite_points": return dev_infinite_points
		"infinite_ammo": return dev_infinite_ammo
		"no_zombies": return dev_no_zombies
		"noclip": return dev_noclip
		"speed_boost": return dev_speed_boost
	return false

func _dev_label(key: String) -> String:
	match key:
		"infinite_health": return "INFINITE HEALTH"
		"infinite_points": return "INFINITE POINTS"
		"infinite_ammo": return "INFINITE AMMO"
		"no_zombies": return "NO ZOMBIES"
		"noclip": return "NOCLIP"
		"speed_boost": return "SPEED BOOST"
	return key.to_upper()

func _refresh_dev_labels() -> void:
	for key: String in _dev_rows.keys():
		var enabled: bool = _dev_value(key)
		var b := _dev_rows[key] as Button
		b.text = ("%s  %s — %s" % ["●" if enabled else "○", _dev_label(key), "ON" if enabled else "OFF"])
		b.modulate = Color(0.40, 1.00, 0.52) if enabled else Color(0.88, 0.90, 0.94)

func _set_dev_flag(key: String, enabled: bool) -> void:
	match key:
		"infinite_health": dev_infinite_health = enabled
		"infinite_points": dev_infinite_points = enabled
		"infinite_ammo": dev_infinite_ammo = enabled
		"no_zombies": dev_no_zombies = enabled
		"noclip": dev_noclip = enabled
		"speed_boost": dev_speed_boost = enabled
	_apply_dev_flags()
	_refresh_dev_labels()
	print("XZOGOT_DEV_FLAG ", key, "=", enabled)

func _apply_dev_flags() -> void:
	var player: Node = get_node_or_null("../../Player")
	if player != null and player.has_method("apply_dev_flags"):
		player.call(
			"apply_dev_flags",
			dev_infinite_health,
			dev_infinite_points,
			dev_noclip,
			dev_speed_boost
		)
	var weapon: Node = get_node_or_null("../../Player/Weapon")
	if weapon != null and weapon.has_method("set_dev_infinite_ammo"):
		weapon.call("set_dev_infinite_ammo", dev_infinite_ammo)
	var rounds: Node = get_node_or_null("../../RoundManager")
	if rounds != null and rounds.has_method("set_dev_no_zombies"):
		rounds.call("set_dev_no_zombies", dev_no_zombies)

func _dev_unlock_all() -> void:
	var count: int = 0
	for node: Node in get_tree().get_nodes_in_group("zombie_interactable"):
		if node.has_method("dev_force_open"):
			if bool(node.call("dev_force_open")):
				count += 1
	print("XZOGOT_DEV_UNLOCK_ALL ", count)

func _dev_clear_all_zombies() -> void:
	var rounds: Node = get_node_or_null("../../RoundManager")
	if rounds != null and rounds.has_method("dev_clear_zombies"):
		rounds.call("dev_clear_zombies")

func _dev_spawn_one_zombie() -> void:
	var rounds: Node = get_node_or_null("../../RoundManager")
	if rounds != null and rounds.has_method("dev_spawn_one"):
		rounds.call("dev_spawn_one")

func _dev_test_power_lights() -> void:
	var triggered: int = 0
	for node: Node in get_tree().get_nodes_in_group("xz_power_light_rig"):
		if node.has_method("dev_trigger_startup"):
			node.call("dev_trigger_startup")
			triggered += 1
	print("XZOGOT_DEV_TEST_POWER_LIGHTS ", triggered)
	close_menu()

func _dev_test_candle_flicker() -> void:
	var triggered: int = 0
	for node: Node in get_tree().get_nodes_in_group("xz_candle_manager"):
		if node.has_method("_trigger_candle_event"):
			node.call("_trigger_candle_event", "DEV_FLICKER", 2.0, 0.78)
			triggered += 1
	print("XZOGOT_DEV_TEST_CANDLE_FLICKER ", triggered)
	close_menu()

func _dev_equip_weapon(id: String) -> void:
	var weapon: Node = get_node_or_null("../../Player/Weapon")
	if weapon != null and weapon.has_method("equip_weapon"):
		if bool(weapon.call("equip_weapon", id, true)):
			print("XZOGOT_DEV_WEAPON_EQUIP ", id)
			close_menu()

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

func toggle_pause_menu() -> void:
	if visible:
		close_menu()
	else:
		open_pause_menu()

func toggle_menu() -> void:
	toggle_pause_menu()

func open_pause_menu() -> void:
	_show_page("pause")
	visible = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	print("XZOGOT_PAUSE_MENU OPEN")

func close_menu() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	get_tree().paused = false
	_apply_to_player()
	_apply_dev_flags()
	print("XZOGOT_PAUSE_MENU CLOSED")

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
