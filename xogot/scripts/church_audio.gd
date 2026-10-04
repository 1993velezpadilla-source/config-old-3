extends Node
class_name XzChurchAudio

const HORROR_BED := "res://assets/audio/church/ambience/horror_bed.ogg"
const RAIN := "res://assets/audio/church/ambience/rain.ogg"
const BELL := "res://assets/audio/church/world/church_bell.ogg"

var _bed: AudioStreamPlayer
var _rain: AudioStreamPlayer
var _bell: AudioStreamPlayer3D
var _round_stinger: AudioStreamPlayer
var _round_cue_count: int = 0
var _last_round_cue: String = ""

func _loop_ogg(stream: AudioStream) -> void:
	if stream is AudioStreamOggVorbis:
		(stream as AudioStreamOggVorbis).loop = true

func _load_stream(path: String) -> AudioStream:
	if not ResourceLoader.exists(path):
		return null
	return load(path) as AudioStream

func _ready() -> void:
	add_to_group("church_audio_runtime")

	_bed = AudioStreamPlayer.new()
	_bed.name = "HorrorBed"
	_bed.volume_db = -22.0
	_bed.stream = _load_stream(HORROR_BED)
	if _bed.stream != null:
		_loop_ogg(_bed.stream)
		add_child(_bed)
		_bed.play()
	else:
		add_child(_bed)

	_rain = AudioStreamPlayer.new()
	_rain.name = "RainBed"
	_rain.volume_db = -28.0
	_rain.stream = _load_stream(RAIN)
	if _rain.stream != null:
		_loop_ogg(_rain.stream)
		add_child(_rain)
		_rain.play()
	else:
		add_child(_rain)

	_bell = AudioStreamPlayer3D.new()
	_bell.name = "BellAudio"
	_bell.position = Vector3(-25.0, 10.2, 9.0) * 0.78
	_bell.max_distance = 75.0
	_bell.unit_size = 9.0
	_bell.volume_db = -4.0
	_bell.stream = _load_stream(BELL)
	add_child(_bell)

	_round_stinger = AudioStreamPlayer.new()
	_round_stinger.name = "RoundStinger"
	_round_stinger.stream = _load_stream(BELL)
	_round_stinger.volume_db = -12.0
	add_child(_round_stinger)

	var scene_root: Node = get_parent().get_parent() if get_parent() != null else null
	var rounds: Node = scene_root.get_node_or_null("RoundManager") if scene_root != null else null
	if rounds != null:
		if rounds.has_signal("round_started"):
			rounds.connect("round_started", Callable(self, "_on_round_started"))
		if rounds.has_signal("round_cleared"):
			rounds.connect("round_cleared", Callable(self, "_on_round_cleared"))

	print(
		"XZOGOT_CHURCH_AUDIO_READY bed=", _bed.stream != null,
		" rain=", _rain.stream != null,
		" bell=", _bell.stream != null
	)
	print("XZOGOT_ROUND_AUDIO_READY ", _round_stinger.stream != null)

func _play_round_cue(kind: String, pitch: float, volume_db: float) -> bool:
	if _round_stinger == null or _round_stinger.stream == null:
		return false
	_round_stinger.stop()
	_round_stinger.pitch_scale = pitch
	_round_stinger.volume_db = volume_db
	_round_stinger.play()
	_round_cue_count += 1
	_last_round_cue = kind
	print("XZOGOT_ROUND_AUDIO_CUE ", kind, " pitch=", pitch)
	return true

func _on_round_started(round_number: int, _total_zombies: int) -> void:
	var pitch: float = minf(1.08 + float(maxi(0, round_number - 1)) * 0.006, 1.20)
	_play_round_cue("round_start", pitch, -11.0)

func _on_round_cleared(_round_number: int) -> void:
	_play_round_cue("round_clear", 0.72, -9.0)

func get_round_cue_count() -> int:
	return _round_cue_count

func get_last_round_cue() -> String:
	return _last_round_cue

func ring_bell() -> bool:
	if _bell == null or _bell.stream == null:
		return false
	_bell.play()
	print("XZOGOT_CHURCH_BELL_RING")
	return true

func set_ambience_enabled(enabled: bool) -> void:
	if _bed != null:
		_bed.stream_paused = not enabled
	if _rain != null:
		_rain.stream_paused = not enabled

func get_loaded_channel_count() -> int:
	var total := 0
	if _bed != null and _bed.stream != null:
		total += 1
	if _rain != null and _rain.stream != null:
		total += 1
	if _bell != null and _bell.stream != null:
		total += 1
	return total
