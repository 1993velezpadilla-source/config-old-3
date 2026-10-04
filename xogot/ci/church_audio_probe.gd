extends SceneTree

const AUDIO_PATHS: Array[String] = [
	"res://assets/audio/church/ambience/horror_bed.ogg",
	"res://assets/audio/church/ambience/rain.ogg",
	"res://assets/audio/church/world/church_bell.ogg",
	"res://assets/audio/church/world/door_open.ogg",
	"res://assets/audio/church/world/machine_loop.ogg",
	"res://assets/audio/church/world/machine_use.ogg",
	"res://assets/audio/church/world/mystery_open.ogg",
	"res://assets/audio/church/world/power_switch.ogg",
	"res://assets/audio/church/world/wood_break_01.ogg",
	"res://assets/audio/church/world/wood_break_02.ogg",
	"res://assets/audio/church/world/wood_repair.ogg",
	"res://assets/audio/church/zombie/attack_01.ogg",
	"res://assets/audio/church/zombie/attack_02.ogg",
	"res://assets/audio/church/zombie/death_01.ogg",
	"res://assets/audio/church/zombie/death_02.ogg",
	"res://assets/audio/church/zombie/moan_01.ogg",
	"res://assets/audio/church/zombie/moan_02.ogg",
	"res://assets/audio/church/zombie/moan_03.ogg",
]

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("CHURCH_AUDIO_PROBE: " + message)
	quit(code)

func _run() -> void:
	for path: String in AUDIO_PATHS:
		if not ResourceLoader.exists(path):
			_fail(2, "missing audio asset: " + path)
			return
		var stream := load(path) as AudioStream
		if stream == null:
			_fail(3, "invalid AudioStream: " + path)
			return

	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(4, "main scene missing")
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame

	var audio_nodes: Array[Node] = get_nodes_in_group("church_audio_runtime")
	if audio_nodes.size() != 1:
		_fail(5, "expected one church audio runtime")
		return
	var audio: Node = audio_nodes[0]
	if int(audio.call("get_loaded_channel_count")) != 3:
		_fail(6, "ambience/bell channel load mismatch")
		return

	var bell_nodes: Array[Node] = get_nodes_in_group("bell_interaction")
	if bell_nodes.size() != 1:
		_fail(7, "expected one BellRope")
		return
	var bell: Node = bell_nodes[0]
	if not bool(bell.call("interact", scene.get_node("Player"))):
		_fail(8, "BellRope interaction failed")
		return
	if str(bell.call("get_last_result")) != "BELL_RUNG":
		_fail(9, "BellRope result marker wrong")
		return

	if not bool(audio.call("ring_bell")):
		_fail(10, "direct church bell playback failed")
		return

	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if barricades.is_empty():
		_fail(11, "barricades missing")
		return
	var board: Node = barricades[0]
	if not bool(board.call("zombie_damage", 60.0)):
		_fail(12, "wood break path failed")
		return
	if not bool(board.call("interact", scene.get_node("Player"))):
		_fail(13, "wood repair path failed")
		return

	print("XZOGOT_CHURCH_AUDIO_ASSETS_GREEN ", AUDIO_PATHS.size())
	print("XZOGOT_CHURCH_AMBIENCE_GREEN 3")
	print("XZOGOT_BELL_INTERACTION_AUDIO_GREEN")
	print("XZOGOT_WOOD_AUDIO_PATH_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
