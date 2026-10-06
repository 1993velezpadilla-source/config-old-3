extends Node3D
class_name NuketownSourceAudioRuntime

const DATA_PATH := "res://data/nuketown_source_audio.json"

var _source_actor_root: Node3D
var _data: Dictionary = {}
var _source_audio_root: String = ""
var _ambient_runtime_count: int = 0
var _source_stream_count: int = 0
var _fallback_stream_count: int = 0
var _missing_stream_count: int = 0
var _join_player: AudioStreamPlayer
var _network_manager: Node
var _known_peer_ids: Dictionary = {}
var _source_identities: Dictionary = {}
var _join_schedule_serial: int = 0

func configure(source_actor_root: Node3D) -> bool:
	_source_actor_root = source_actor_root
	_data = _read_json(DATA_PATH)
	if _data.is_empty() or int(_data.get("schemaVersion", 0)) != 1:
		push_error("XZOGOT_NUKETOWN_AUDIO_RUNTIME_DATA_MISSING")
		return false
	_source_audio_root = str(_data.get("sourceAudioRoot", ""))
	add_to_group("nuketown_source_audio_runtime")
	_build_join_player()
	_build_ambient_players()
	_bind_network_join_signal()
	set_meta("ambient_runtime_count", _ambient_runtime_count)
	set_meta("source_stream_count", _source_stream_count)
	set_meta("fallback_stream_count", _fallback_stream_count)
	set_meta("missing_stream_count", _missing_stream_count)
	set_meta("join_sound_count", (_data.get("joinSounds", {}) as Dictionary).size())
	set_meta("source_audio_policy", str(_data.get("sourcePolicy", "")))
	print(
		"XZOGOT_NUKETOWN_AUDIO_RUNTIME_READY ambient=", _ambient_runtime_count,
		" source=", _source_stream_count,
		" fallback=", _fallback_stream_count,
		" missing=", _missing_stream_count,
		" joins=", (_data.get("joinSounds", {}) as Dictionary).size()
	)
	return _ambient_runtime_count == 4

func _read_json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _source_wave_path(wave_name: String) -> String:
	if wave_name.is_empty() or _source_audio_root.is_empty():
		return ""
	return _source_audio_root.path_join(wave_name + ".wav")

func _load_stream(path: String) -> AudioStream:
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	return load(path) as AudioStream

func _find_marker(actor_name: String) -> Marker3D:
	if _source_actor_root == null:
		return null
	for node: Node in _source_actor_root.get_children():
		if not (node is Marker3D):
			continue
		var source_object := str(node.get_meta("source_object_path", ""))
		if source_object.ends_with("." + actor_name) or source_object.ends_with(actor_name):
			return node as Marker3D
	return null

func _set_loop(stream: AudioStream, enabled: bool) -> void:
	if not enabled or stream == null:
		return
	if stream is AudioStreamWAV:
		(stream as AudioStreamWAV).loop_mode = AudioStreamWAV.LOOP_FORWARD
	elif stream is AudioStreamOggVorbis:
		(stream as AudioStreamOggVorbis).loop = true

func _build_ambient_players() -> void:
	var actors: Dictionary = _data.get("ambientActors", {})
	for actor_var: Variant in actors.keys():
		var actor_name := str(actor_var)
		var config: Dictionary = actors[actor_name]
		var marker := _find_marker(actor_name)
		if marker == null:
			push_warning("XZOGOT_NUKETOWN_AUDIO_MARKER_MISSING " + actor_name)
			_missing_stream_count += 1
			continue

		var player := AudioStreamPlayer3D.new()
		player.name = actor_name + "_Audio"
		add_child(player)
		player.global_transform = marker.global_transform
		player.unit_size = maxf(1.0, float(config.get("attenuationShapeExtentCm", 100.0)) * 0.01)
		var max_cm := float(config.get("attenuationShapeExtentCm", 1200.0)) + float(config.get("falloffDistanceCm", 1800.0))
		player.max_distance = maxf(8.0, max_cm * 0.01)
		player.volume_db = linear_to_db(maxf(0.001, float(config.get("volumeMultiplier", 1.0))))
		player.add_to_group("nuketown_source_ambient_runtime")
		player.set_meta("source_actor_name", actor_name)
		player.set_meta("source_cue", str(config.get("cue", "")))

		var source_waves: Array[String] = []
		for wave_var: Variant in config.get("waves", []):
			source_waves.append(str(wave_var))
		player.set_meta("source_wave_pool", source_waves.duplicate())
		player.set_meta("source_wave_pool_count", source_waves.size())

		var stream: AudioStream = null
		var selected_wave := ""
		for wave_name: String in source_waves:
			var source_path := _source_wave_path(wave_name)
			stream = _load_stream(source_path)
			if stream != null:
				selected_wave = wave_name
				_source_stream_count += 1
				player.set_meta("source_audio_active", true)
				player.set_meta("source_audio_path", source_path)
				break

		if stream == null:
			var fallback := str(config.get("fallback", ""))
			stream = _load_stream(fallback)
			if stream != null:
				_fallback_stream_count += 1
				player.set_meta("source_audio_active", false)
				player.set_meta("fallback_audio_path", fallback)
			else:
				_missing_stream_count += 1
				player.set_meta("source_audio_active", false)
				player.set_meta("audio_missing", true)

		if stream != null:
			player.stream = stream
			_set_loop(stream, bool(config.get("loop", false)) and source_waves.size() <= 1)
			player.autoplay = false
			player.play()
			player.set_meta("selected_source_wave", selected_wave)

		_ambient_runtime_count += 1

func _build_join_player() -> void:
	_join_player = AudioStreamPlayer.new()
	_join_player.name = "SourceJoinSoundPlayer"
	add_child(_join_player)
	_join_player.add_to_group("nuketown_source_join_audio_runtime")

func _bind_network_join_signal() -> void:
	_network_manager = get_parent().get_node_or_null("NetworkManager") if get_parent() != null else null
	if _network_manager == null:
		set_meta("join_network_bound", false)
		return
	if _network_manager.has_method("get_roster_ids"):
		var current: PackedInt32Array = _network_manager.call("get_roster_ids") as PackedInt32Array
		for peer_id: int in current:
			_known_peer_ids[peer_id] = true
	if _network_manager.has_signal("roster_changed"):
		var callback := Callable(self, "_on_network_roster_changed")
		if not _network_manager.is_connected("roster_changed", callback):
			_network_manager.connect("roster_changed", callback)
			set_meta("join_network_bound", true)

func _on_network_roster_changed(peer_ids: PackedInt32Array) -> void:
	var current: Dictionary = {}
	for peer_id: int in peer_ids:
		current[peer_id] = true
		if _known_peer_ids.has(peer_id):
			continue
		var identity: Dictionary = _source_identities.get(peer_id, {})
		var steam_id := str(identity.get("steam_id", ""))
		var shack_name := str(identity.get("shack_name", ""))
		var is_shack := bool(identity.get("is_shack", false))
		notify_source_player_join(peer_id, steam_id, shack_name, is_shack)
	_known_peer_ids = current

func set_source_identity(
	peer_id: int,
	steam_id: String,
	shack_name: String,
	is_shack: bool
) -> void:
	_source_identities[peer_id] = {
		"steam_id": steam_id,
		"shack_name": shack_name,
		"is_shack": is_shack,
	}
	set_meta("source_identity_hook_ready", true)

func join_source_decision(
	source_class: String,
	steam_id: String,
	shack_name: String,
	is_shack: bool
) -> bool:
	var joins: Dictionary = _data.get("joinSounds", {})
	if not joins.has(source_class):
		return false
	var config: Dictionary = joins[source_class]
	if str(config.get("trigger", "")) != "OnPlayerJoinedServer":
		return false
	if not bool(config.get("whitelistRequired", false)):
		return true
	if is_shack:
		var shack_names: Array = config.get("shackNames", [])
		return shack_names.has(shack_name)
	var steam_ids: Array = config.get("steamIDs", [])
	return steam_ids.has(steam_id)

func get_join_delay(source_class: String) -> float:
	var joins: Dictionary = _data.get("joinSounds", {})
	var config: Dictionary = joins.get(source_class, {})
	return float(config.get("delaySeconds", -1.0))

func notify_source_player_join(
	peer_id: int,
	steam_id: String = "",
	shack_name: String = "",
	is_shack: bool = false
) -> int:
	var scheduled := 0
	var joins: Dictionary = _data.get("joinSounds", {})
	for source_var: Variant in joins.keys():
		var source_class := str(source_var)
		if not join_source_decision(source_class, steam_id, shack_name, is_shack):
			continue
		var delay := get_join_delay(source_class)
		_schedule_join_sound(source_class, peer_id, maxf(0.0, delay))
		scheduled += 1
	set_meta("last_join_peer_id", peer_id)
	set_meta("last_join_route_count", scheduled)
	print(
		"XZOGOT_NUKETOWN_SOURCE_JOIN peer=", peer_id,
		" routes=", scheduled,
		" identity=", "shack" if is_shack else ("steam" if not steam_id.is_empty() else "xogot_only")
	)
	return scheduled

func _schedule_join_sound(source_class: String, peer_id: int, delay: float) -> void:
	_join_schedule_serial += 1
	var serial := _join_schedule_serial
	set_meta("last_join_schedule_class", source_class)
	set_meta("last_join_schedule_delay", delay)
	if delay > 0.0:
		await get_tree().create_timer(delay).timeout
	if not is_inside_tree():
		return
	var played := play_join_sound(source_class)
	print(
		"XZOGOT_NUKETOWN_JOIN_ROUTE_FIRE class=", source_class,
		" peer=", peer_id,
		" serial=", serial,
		" played=", played
	)

func get_join_route_count() -> int:
	return (_data.get("joinSounds", {}) as Dictionary).size()

func play_join_sound(source_class: String) -> bool:
	var joins: Dictionary = _data.get("joinSounds", {})
	if not joins.has(source_class):
		return false
	var config: Dictionary = joins[source_class]
	var stream: AudioStream = null
	var wave := str(config.get("wave", ""))
	if not wave.is_empty():
		var source_path := _source_wave_path(wave)
		stream = _load_stream(source_path)
		if stream != null:
			_join_player.set_meta("source_audio_active", true)
			_join_player.set_meta("source_audio_path", source_path)
	if stream == null:
		var fallback := str(config.get("fallback", ""))
		stream = _load_stream(fallback)
		_join_player.set_meta("source_audio_active", false)
		_join_player.set_meta("fallback_audio_path", fallback)
	if stream == null:
		return false
	_join_player.stream = stream
	_join_player.play()
	_join_player.set_meta("source_class", source_class)
	_join_player.set_meta("source_reference", str(config.get("source", "")))
	print("XZOGOT_NUKETOWN_JOIN_SOUND ", source_class, " source=", bool(_join_player.get_meta("source_audio_active", false)))
	return true

func mystery_source_path() -> String:
	var mystery: Dictionary = _data.get("mysteryBox", {})
	return _source_wave_path(str(mystery.get("wave", "")))

func mystery_fallback_path() -> String:
	var mystery: Dictionary = _data.get("mysteryBox", {})
	return str(mystery.get("fallback", ""))

func get_ambient_runtime_count() -> int:
	return _ambient_runtime_count

func get_source_stream_count() -> int:
	return _source_stream_count

func get_fallback_stream_count() -> int:
	return _fallback_stream_count

func get_missing_stream_count() -> int:
	return _missing_stream_count
