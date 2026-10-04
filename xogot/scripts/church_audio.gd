extends Node
class_name XzChurchAudio

const HORROR_BED := "res://assets/audio/church/ambience/horror_bed.ogg"
const RAIN := "res://assets/audio/church/ambience/rain.ogg"
const BELL := "res://assets/audio/church/world/church_bell.ogg"

var _bed: AudioStreamPlayer
var _rain: AudioStreamPlayer
var _bell: AudioStreamPlayer3D

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

	print(
		"XZOGOT_CHURCH_AUDIO_READY bed=", _bed.stream != null,
		" rain=", _rain.stream != null,
		" bell=", _bell.stream != null
	)

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
