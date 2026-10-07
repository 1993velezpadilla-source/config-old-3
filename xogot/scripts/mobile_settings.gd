extends Control

const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const WeaponAssetRegistry = preload("res://scripts/weapon_asset_registry.gd")
const CONFIG_PATH := "user://xogot_mobile_settings.cfg"

# Intentional: the DEV lab is present in optimized Release builds too so the
# exact shipping-performance binary can be play-tested. For a public store
# package this single flag can be turned off without touching gameplay code.
@export var dev_menu_visible_in_release: bool = true

var ads_toggle_mode: bool = false
var mobile_sprint_zone: float = 1.10
var gyro_mode: int = 2 # 0=OFF, 2=ADS ONLY
var gyro_invert_x: bool = false
var gyro_invert_y: bool = false
var gyro_sensitivity_x: float = 0.70
var gyro_sensitivity_y: float = 0.70
var gyro_ads_multiplier: float = 1.00
var gyro_deadzone: float = 0.05
var gyro_smoothing: float = 0.18
var auto_knife: bool = true
var knife_button_range_only: bool = true
var knife_range_m: float = 1.65
var auto_rebuild: bool = true
var repair_repeat_interval: float = 0.45
var hud_opacity: float = 0.82
var voice_input_enabled: bool = true
var voice_output_enabled: bool = true

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
var _page_network: VBoxContainer
var _page_dev: VBoxContainer
var _network_status: Label
var _network_roster: Label
var _network_share: Label
var _network_error: Label
var _network_found: Label
var _network_public: Label
var _network_match: Label
var _network_ready: Button
var _voice_status: Label
var _voice_mic_button: Button
var _voice_output_button: Button
var _voice_slot_buttons: Dictionary = {}
var _network_address: LineEdit
var _network_port: LineEdit
var _network_last_error: String = ""
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
	call_deferred("_bind_network_ui_signals")
	call_deferred("_apply_voice_settings")
	print("XZOGOT_MOBILE_SETTINGS_READY")
	print("XZOGOT_RELEASE_DEV_MENU_READY ", dev_menu_visible_in_release)

func _load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(CONFIG_PATH) != OK:
		return
	ads_toggle_mode = bool(cfg.get_value("aim", "ads_toggle_mode", ads_toggle_mode))
	mobile_sprint_zone = float(cfg.get_value("gameplay", "sprint_zone", mobile_sprint_zone))
	gyro_mode = int(cfg.get_value("gyro", "mode", gyro_mode))
	gyro_mode = 0 if gyro_mode == 0 else 2
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
	voice_input_enabled = bool(cfg.get_value("voice", "input_enabled", voice_input_enabled))
	voice_output_enabled = bool(cfg.get_value("voice", "output_enabled", voice_output_enabled))

func _save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("aim", "ads_toggle_mode", ads_toggle_mode)
	cfg.set_value("gameplay", "sprint_zone", mobile_sprint_zone)
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
	cfg.set_value("voice", "input_enabled", voice_input_enabled)
	cfg.set_value("voice", "output_enabled", voice_output_enabled)
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
	_page_network = _page_container(pages, "NetworkPage")
	_page_dev = _page_container(pages, "DevPage")

	_build_pause_page()
	_build_settings_page()
	_build_network_page()
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
	var multiplayer_button := _button(_page_pause, "OpenNetwork", "MULTIPLAYER")
	multiplayer_button.pressed.connect(func(): _show_page("network"))
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
	_add_setting("sprint_zone", _cycle_sprint_zone)
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

func _network_manager_node() -> Node:
	return get_node_or_null("../../NetworkManager")

func _voice_chat_node() -> Node:
	return get_node_or_null("../../VoiceChat")

func _apply_voice_settings() -> void:
	var voice := _voice_chat_node()
	if voice == null:
		return
	if voice.has_method("set_input_enabled"):
		voice.call("set_input_enabled", voice_input_enabled)
	if voice.has_method("set_output_enabled"):
		voice.call("set_output_enabled", voice_output_enabled)

func _bind_network_ui_signals() -> void:
	var network: Node = _network_manager_node()
	if network == null:
		return
	var state_cb := Callable(self, "_on_network_state_changed")
	var roster_cb := Callable(self, "_on_network_roster_changed")
	var error_cb := Callable(self, "_on_network_error")
	var match_cb := Callable(self, "_on_matchmaking_state_changed")
	if network.has_signal("session_state_changed") and not network.is_connected("session_state_changed", state_cb):
		network.connect("session_state_changed", state_cb)
	if network.has_signal("roster_changed") and not network.is_connected("roster_changed", roster_cb):
		network.connect("roster_changed", roster_cb)
	if network.has_signal("network_error") and not network.is_connected("network_error", error_cb):
		network.connect("network_error", error_cb)
	if network.has_signal("matchmaking_state_changed") and not network.is_connected("matchmaking_state_changed", match_cb):
		network.connect("matchmaking_state_changed", match_cb)
	print("XZOGOT_NETWORK_UI_SIGNALS_READY")

func _build_network_page() -> void:
	_title(
		_page_network,
		"MULTIPLAYER",
		"Host-authoritative 1–4 player ENet. Rounds, zombies, revive, economy and world state are synchronized."
	)

	_network_status = Label.new()
	_network_status.name = "NetworkStatus"
	_network_status.text = "OFFLINE"
	_network_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_network_status.add_theme_font_size_override("font_size", 22)
	_network_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_page_network.add_child(_network_status)

	_network_roster = Label.new()
	_network_roster.name = "NetworkRoster"
	_network_roster.text = "ROSTER  LOCAL  1/4"
	_network_roster.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_network_roster.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_network_roster.modulate = Color(0.86, 0.88, 0.90)
	_page_network.add_child(_network_roster)

	_network_match = Label.new()
	_network_match.name = "MatchmakingState"
	_network_match.text = ""
	_network_match.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_network_match.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_network_match.add_theme_font_size_override("font_size", 20)
	_network_match.modulate = Color(0.52, 0.92, 0.72)
	_page_network.add_child(_network_match)

	_network_ready = _button(_page_network, "MatchReady", "READY")
	_network_ready.visible = false
	_network_ready.pressed.connect(_network_toggle_ready)

	_voice_status = Label.new()
	_voice_status.name = "VoiceStatus"
	_voice_status.text = "PROXIMITY VOICE"
	_voice_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_voice_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_voice_status.modulate = Color(0.72, 0.88, 1.0)
	_page_network.add_child(_voice_status)

	_voice_mic_button = _button(_page_network, "VoiceMic", "MIC: ON")
	_voice_mic_button.pressed.connect(_voice_toggle_mic)
	_voice_output_button = _button(_page_network, "VoiceOutput", "VOICE OUTPUT: ON")
	_voice_output_button.pressed.connect(_voice_toggle_output)
	for slot in range(1, 5):
		var mute_button := _button(_page_network, "VoiceMuteP%d" % slot, "P%d VOICE: AUDIBLE" % slot)
		mute_button.pressed.connect(func(slot_value: int = slot): _voice_toggle_slot(slot_value))
		_voice_slot_buttons[slot] = mute_button

	_network_share = Label.new()
	_network_share.name = "NetworkShare"
	_network_share.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_network_share.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_network_share.modulate = Color(0.72, 0.78, 0.82)
	_page_network.add_child(_network_share)

	_network_error = Label.new()
	_network_error.name = "NetworkError"
	_network_error.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_network_error.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_network_error.modulate = Color(1.0, 0.52, 0.46)
	_page_network.add_child(_network_error)

	_network_address = LineEdit.new()
	_network_address.name = "JoinAddress"
	_network_address.placeholder_text = "HOST IP — example 192.168.1.25"
	_network_address.text = ""
	_network_address.custom_minimum_size = Vector2(0.0, 54.0)
	_network_address.virtual_keyboard_enabled = true
	_network_address.clear_button_enabled = true
	_page_network.add_child(_network_address)

	_network_port = LineEdit.new()
	_network_port.name = "JoinPort"
	_network_port.placeholder_text = "UDP PORT"
	_network_port.text = "7777"
	_network_port.custom_minimum_size = Vector2(0.0, 50.0)
	_network_port.virtual_keyboard_enabled = true
	_network_port.max_length = 5
	_page_network.add_child(_network_port)

	_network_found = Label.new()
	_network_found.name = "FoundMatches"
	_network_found.text = "LAN MATCHES: NOT SCANNING"
	_network_found.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_network_found.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_network_found.modulate = Color(0.76, 0.84, 0.78)
	_page_network.add_child(_network_found)

	_network_public = Label.new()
	_network_public.name = "PublicReachability"
	_network_public.text = "INTERNET PUBLIC: CHECKING"
	_network_public.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_network_public.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_network_public.modulate = Color(0.76, 0.80, 0.90)
	_page_network.add_child(_network_public)

	var host_private := _button(_page_network, "HostPrivate", "HOST PRIVATE — 1–4 PLAYERS")
	host_private.pressed.connect(func(): _network_host(true))
	var host_public := _button(_page_network, "HostPublic", "HOST PUBLIC / LAN — DISCOVERABLE")
	host_public.pressed.connect(func(): _network_host(false))
	var find_lan := _button(_page_network, "FindLan", "FIND MATCH — LAN")
	find_lan.pressed.connect(_network_find_lan)
	var join_found := _button(_page_network, "JoinFound", "JOIN FOUND LAN MATCH")
	join_found.pressed.connect(_network_join_found)
	var find_public := _button(_page_network, "FindPublic", "FIND MATCH — INTERNET")
	find_public.pressed.connect(_network_find_public)
	var join_public := _button(_page_network, "JoinPublic", "JOIN INTERNET MATCH")
	join_public.pressed.connect(_network_join_public)
	var join := _button(_page_network, "JoinDirect", "JOIN DIRECT IP")
	join.pressed.connect(_network_join)
	var leave := _button(_page_network, "LeaveNetwork", "LEAVE SESSION")
	leave.pressed.connect(_network_leave)

	var note := Label.new()
	note.name = "NetworkDirectoryNote"
	note.text = "LAN Find Match uses local UDP discovery. Internet Find Match tries public ENet first, then automatically falls back to the dedicated WSS server when direct reachability fails or no direct host is listed."
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	note.modulate = Color(0.68, 0.72, 0.76)
	_page_network.add_child(note)

	var back := _button(_page_network, "NetworkBack", "BACK")
	back.pressed.connect(func(): _show_page("pause"))
	_refresh_network_status()

func _network_port_value() -> int:
	if _network_port == null:
		return 7777
	var value: int = int(_network_port.text) if _network_port.text.is_valid_int() else 7777
	value = clampi(value, 1024, 65535)
	_network_port.text = str(value)
	return value

func _network_host(private_session: bool) -> void:
	var network: Node = _network_manager_node()
	if network == null or not network.has_method("host_game"):
		_network_last_error = "NETWORK MANAGER UNAVAILABLE"
		_refresh_network_status()
		return
	_network_last_error = ""
	var port: int = _network_port_value()
	var err: int = int(network.call("host_game", port, private_session))
	if err == OK:
		print("XZOGOT_NETWORK_UI_HOST private=", private_session, " port=", port)
	else:
		_network_last_error = "HOST FAILED: " + str(err)
	_refresh_network_status()

func _network_find_public() -> void:
	var network: Node = _network_manager_node()
	if network == null or not network.has_method("find_public_matches"):
		_network_last_error = "PUBLIC DIRECTORY UNAVAILABLE"
		_refresh_network_status()
		return
	_network_last_error = ""
	if bool(network.call("find_public_matches")):
		print("XZOGOT_NETWORK_UI_FIND_PUBLIC")
	else:
		_network_last_error = "PUBLIC DIRECTORY NOT CONFIGURED / UNREACHABLE"
	_refresh_network_status()

func _network_join_public() -> void:
	var network: Node = _network_manager_node()
	if network == null or not network.has_method("join_best_public_match"):
		_network_last_error = "PUBLIC DIRECTORY UNAVAILABLE"
		_refresh_network_status()
		return
	_network_last_error = ""
	var err: int = int(network.call("join_best_public_match"))
	if err == OK:
		print("XZOGOT_NETWORK_UI_JOIN_PUBLIC")
	else:
		_network_last_error = "NO JOINABLE INTERNET MATCH" if err == ERR_DOES_NOT_EXIST else ("JOIN INTERNET FAILED: " + str(err))
	_refresh_network_status()

func _network_find_lan() -> void:
	var network: Node = _network_manager_node()
	if network == null or not network.has_method("start_find_match"):
		_network_last_error = "LAN DISCOVERY UNAVAILABLE"
		_refresh_network_status()
		return
	_network_last_error = ""
	var err: int = int(network.call("start_find_match", 7778))
	if err == OK:
		print("XZOGOT_NETWORK_UI_FIND_LAN")
	else:
		_network_last_error = "FIND MATCH FAILED: " + str(err)
	_refresh_network_status()

func _network_join_found() -> void:
	var network: Node = _network_manager_node()
	if network == null or not network.has_method("join_best_lan_match"):
		_network_last_error = "LAN DISCOVERY UNAVAILABLE"
		_refresh_network_status()
		return
	_network_last_error = ""
	var err: int = int(network.call("join_best_lan_match"))
	if err == OK:
		print("XZOGOT_NETWORK_UI_JOIN_FOUND")
	else:
		_network_last_error = "NO JOINABLE LAN MATCH" if err == ERR_DOES_NOT_EXIST else ("JOIN FOUND FAILED: " + str(err))
	_refresh_network_status()

func _refresh_found_matches(network: Node) -> void:
	if _network_found == null:
		return
	if network == null or not network.has_method("get_discovered_matches"):
		_network_found.text = "LAN MATCHES: UNAVAILABLE"
		return
	var matches: Array = network.call("get_discovered_matches") as Array
	if matches.is_empty():
		_network_found.text = "LAN MATCHES: NONE FOUND"
		return
	var parts := PackedStringArray()
	for session_var: Variant in matches.slice(0, 4):
		var session := session_var as Dictionary
		parts.append(
			"%s  %d/%d  %s:%d" % [
				str(session.get("name", "MATCH")),
				int(session.get("players", 0)),
				int(session.get("max_players", 4)),
				str(session.get("ip", "?")),
				int(session.get("port", 7777)),
			]
		)
	_network_found.text = "LAN MATCHES:\n" + "\n".join(parts)

func _network_join() -> void:
	var network: Node = _network_manager_node()
	if network == null or not network.has_method("join_game"):
		_network_last_error = "NETWORK MANAGER UNAVAILABLE"
		_refresh_network_status()
		return
	var address: String = _network_address.text.strip_edges() if _network_address != null else ""
	if address.is_empty():
		address = "127.0.0.1"
		_network_address.text = address
	_network_last_error = ""
	var port: int = _network_port_value()
	var err: int = int(network.call("join_game", address, port))
	if err == OK:
		print("XZOGOT_NETWORK_UI_JOIN ", address, ":", port)
	else:
		_network_last_error = "JOIN FAILED: " + str(err)
	_refresh_network_status()

func _network_leave() -> void:
	var network: Node = _network_manager_node()
	if network != null and network.has_method("leave_game"):
		network.call("leave_game")
		print("XZOGOT_NETWORK_UI_LEAVE")
	_network_last_error = ""
	_refresh_network_status()

func _on_network_state_changed(_state: String) -> void:
	_network_last_error = ""
	_refresh_network_status()

func _on_network_roster_changed(_peer_ids: PackedInt32Array) -> void:
	_refresh_network_status()

func _on_network_error(message: String) -> void:
	_network_last_error = message
	_refresh_network_status()

func _on_matchmaking_state_changed(
	_phase: String,
	_ready_count: int,
	_player_count: int,
	_countdown: float
) -> void:
	_refresh_network_status()

func _voice_toggle_mic() -> void:
	voice_input_enabled = not voice_input_enabled
	_save_settings()
	_apply_voice_settings()
	_refresh_voice_controls()

func _voice_toggle_output() -> void:
	voice_output_enabled = not voice_output_enabled
	_save_settings()
	_apply_voice_settings()
	_refresh_voice_controls()

func _voice_toggle_slot(slot: int) -> void:
	var voice := _voice_chat_node()
	if voice == null or not voice.has_method("set_slot_muted"):
		return
	var muted := bool(voice.call("is_slot_muted", slot)) if voice.has_method("is_slot_muted") else false
	voice.call("set_slot_muted", slot, not muted)
	_refresh_voice_controls()

func _refresh_voice_controls() -> void:
	var voice := _voice_chat_node()
	if _voice_status != null:
		_voice_status.text = str(voice.call("get_status_text")) if voice != null and voice.has_method("get_status_text") else "PROXIMITY VOICE: UNAVAILABLE"
	if _voice_mic_button != null:
		_voice_mic_button.text = "MIC: " + ("ON" if voice_input_enabled else "OFF")
	if _voice_output_button != null:
		_voice_output_button.text = "VOICE OUTPUT: " + ("ON" if voice_output_enabled else "OFF")
	for slot_var: Variant in _voice_slot_buttons.keys():
		var slot := int(slot_var)
		var button := _voice_slot_buttons[slot] as Button
		var muted := bool(voice.call("is_slot_muted", slot)) if voice != null and voice.has_method("is_slot_muted") else false
		button.text = "P%d VOICE: %s" % [slot, "MUTED" if muted else "AUDIBLE"]

func _network_toggle_ready() -> void:
	var network: Node = _network_manager_node()
	if network == null or not network.has_method("set_local_ready"):
		return
	var current_ready: bool = bool(network.call("is_local_ready")) if network.has_method("is_local_ready") else false
	if bool(network.call("set_local_ready", not current_ready)):
		print("XZOGOT_NETWORK_UI_READY ", not current_ready)

func _lan_share_addresses(port: int) -> PackedStringArray:
	var result := PackedStringArray()
	for address: String in IP.get_local_addresses():
		if address.contains(":"):
			continue
		if address.begins_with("127.") or address.begins_with("169.254."):
			continue
		if address == "0.0.0.0":
			continue
		result.append("%s:%d" % [address, port])
	return result

func _refresh_network_status() -> void:
	if _network_status == null:
		return
	var network: Node = _network_manager_node()
	if network == null or not network.has_method("get_status_text"):
		_network_status.text = "NETWORK MANAGER UNAVAILABLE"
		if _network_error != null:
			_network_error.text = _network_last_error
		return

	_network_status.text = str(network.call("get_status_text"))
	_refresh_found_matches(network)
	if _network_public != null:
		var directory_ready: bool = (
			network.has_method("is_public_directory_configured")
			and bool(network.call("is_public_directory_configured"))
		)
		var upnp_status: String = (
			str(network.call("get_upnp_status"))
			if network.has_method("get_upnp_status")
			else "unavailable"
		)
		var endpoint: String = (
			str(network.call("get_public_endpoint"))
			if network.has_method("get_public_endpoint")
			else ""
		)
		var relay_ready: bool = (
			network.has_method("is_public_relay_configured")
			and bool(network.call("is_public_relay_configured"))
		)
		if not endpoint.is_empty():
			_network_public.text = "INTERNET PUBLIC: %s  •  DIRECTORY: %s  •  RELAY: %s" % [
				endpoint,
				"READY" if directory_ready else "NOT CONFIGURED",
				"READY" if relay_ready else "OFF",
			]
		else:
			_network_public.text = "INTERNET PUBLIC: %s  •  DIRECTORY: %s  •  RELAY: %s" % [
				upnp_status.to_upper(),
				"READY" if directory_ready else "NOT CONFIGURED",
				"READY" if relay_ready else "OFF",
			]
	var mode: String = str(network.call("get_mode")) if network.has_method("get_mode") else "offline"
	var ids: PackedInt32Array = (
		network.call("get_roster_ids") as PackedInt32Array
		if network.has_method("get_roster_ids")
		else PackedInt32Array()
	)
	var max_players: int = int(network.call("get_max_players")) if network.has_method("get_max_players") else 4
	var local_peer: int = int(network.call("get_local_peer_id")) if network.has_method("get_local_peer_id") else 1

	if _network_roster != null:
		var roster_parts := PackedStringArray()
		for id: int in ids:
			var label: String = "P%d" % id
			if id == 1:
				label += " HOST"
			if id == local_peer:
				label += " YOU"
			roster_parts.append(label)
		if roster_parts.is_empty():
			roster_parts.append("LOCAL")
		_network_roster.text = "ROSTER %d/%d  •  %s" % [
			ids.size(),
			max_players,
			"  |  ".join(roster_parts),
		]

	if _network_match != null:
		var phase: String = str(network.call("get_matchmaking_phase")) if network.has_method("get_matchmaking_phase") else "idle"
		var match_text: String = str(network.call("get_matchmaking_status_text")) if network.has_method("get_matchmaking_status_text") else ""
		_network_match.text = match_text
		_network_match.visible = not match_text.is_empty()
		if _network_ready != null:
			var relay_client: bool = mode == "client" and str(network.call("get_transport")) == "websocket"
			var can_ready: bool = relay_client and (phase == "found" or phase == "starting")
			_network_ready.visible = can_ready
			_network_ready.disabled = phase == "started"
			var local_ready: bool = bool(network.call("is_local_ready")) if network.has_method("is_local_ready") else false
			_network_ready.text = "UNREADY" if local_ready else "READY"

	_refresh_voice_controls()

	if _network_share != null:
		_network_share.text = ""
		if mode == "host":
			var port: int = int(network.call("get_session_port")) if network.has_method("get_session_port") else 7777
			var addresses: PackedStringArray = _lan_share_addresses(port)
			if not addresses.is_empty():
				_network_share.text = "SHARE LAN: " + "  •  ".join(addresses)

	if _network_error != null:
		_network_error.text = _network_last_error

func _process(_delta: float) -> void:
	if visible and _current_page == "network":
		_refresh_network_status()

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
		var tag_text: String = "CATALOG"
		if not tags.is_empty():
			tag_text = "/".join(PackedStringArray(tags))
		var asset_status: String = WeaponAssetRegistry.lab_status_text(id)
		var status := "%s | %s" % [tag_text, asset_status]
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
	_page_network.get_parent().visible = page == "network"
	_page_dev.get_parent().visible = page == "dev"
	if page == "network":
		_refresh_network_status()
	if page == "dev":
		_refresh_dev_labels()

func _refresh_labels() -> void:
	if _rows.is_empty():
		return
	(_rows["ads_mode"] as Button).text = "ADS MODE: " + ("TAP / TOGGLE" if ads_toggle_mode else "HOLD")
	(_rows["sprint_zone"] as Button).text = "SPRINT ACTIVATION HEIGHT: %.2f" % mobile_sprint_zone
	(_rows["gyro_mode"] as Button).text = "GYROSCOPE: " + ("OFF" if gyro_mode == 0 else "ADS ONLY")
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
	var network: Node = _network_manager_node()
	var online: bool = (
		network != null
		and network.has_method("is_network_session")
		and bool(network.call("is_network_session"))
	)
	get_tree().paused = not online
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	print("XZOGOT_PAUSE_MENU OPEN online=", online, " world_paused=", get_tree().paused)

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
		"mobile_sprint_zone": return mobile_sprint_zone
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
		"voice_input_enabled": return voice_input_enabled
		"voice_output_enabled": return voice_output_enabled
	return null

func _cycle_ads_mode() -> void:
	ads_toggle_mode = not ads_toggle_mode
	_commit()

func _cycle_sprint_zone() -> void:
	mobile_sprint_zone = _cycle_value(mobile_sprint_zone, 0.05, 1.10, 1.85)
	_commit()

func _cycle_gyro_mode() -> void:
	gyro_mode = 0 if gyro_mode == 2 else 2
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
