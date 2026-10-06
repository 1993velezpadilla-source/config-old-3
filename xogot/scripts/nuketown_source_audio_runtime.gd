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
