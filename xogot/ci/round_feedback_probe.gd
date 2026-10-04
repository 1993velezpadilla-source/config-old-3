extends SceneTree

var _last_signal_count: int = 0
var _last_signal_round: int = 0
var _last_signal_zombie: Node = null

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("ROUND_FEEDBACK_PROBE: " + message)
	quit(code)

func _on_last_zombie(round_number: int, zombie: Node) -> void:
	_last_signal_count += 1
	_last_signal_round = round_number
	_last_signal_zombie = zombie

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return

	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame

	var rounds: Node = scene.get_node_or_null("RoundManager")
	if rounds == null:
		_fail(3, "RoundManager missing")
		return
	rounds.set("auto_start", false)
	if not rounds.has_signal("last_zombie_started"):
		_fail(4, "last-zombie signal missing")
		return
	rounds.connect("last_zombie_started", Callable(self, "_on_last_zombie"))

	var audio_nodes: Array[Node] = get_nodes_in_group("church_audio_runtime")
	if audio_nodes.size() != 1:
		_fail(5, "church audio runtime missing")
		return
	var audio: Node = audio_nodes[0]
	if not audio.has_method("get_round_cue_count"):
		_fail(6, "round audio API missing")
		return

	var cues_before: int = int(audio.call("get_round_cue_count"))
	rounds.call("start_next_round")
	if int(rounds.call("get_round")) != 1:
		_fail(7, "round 1 did not start")
		return
	if int(audio.call("get_round_cue_count")) != cues_before + 1:
		_fail(8, "round-start cue did not fire")
		return
	if str(audio.call("get_last_round_cue")) != "round_start":
		_fail(9, "round-start cue marker wrong")
		return
	print("XZOGOT_ROUND_START_FEEDBACK_GREEN")

	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if barricades.is_empty():
		_fail(10, "barricades missing")
		return

	# Force the final queued spawn of the round. This keeps the production
	# path intact while making the probe deterministic.
	rounds.set("_remaining_to_spawn", 1)
	rounds.set("_alive", 0)
	var zombie: Node = rounds.call("spawn_from_barricade", barricades[0]) as Node
	if zombie == null:
		_fail(11, "could not spawn final zombie")
		return
	if not bool(rounds.call("is_last_zombie")):
		_fail(12, "manager did not enter last-zombie state")
		return
	if _last_signal_count != 1 or _last_signal_round != 1 or _last_signal_zombie != zombie:
		_fail(13, "last-zombie signal contract wrong")
		return
	if not bool(zombie.get_meta("last_zombie", false)):
		_fail(14, "last zombie metadata missing")
		return
	if float(zombie.get("_moan_timer")) > 0.26:
		_fail(15, "last-zombie voice was not armed quickly")
		return
	print("XZOGOT_LAST_ZOMBIE_FEEDBACK_GREEN")

	# Re-checking state must not spam the one-shot signal.
	rounds.call("_refresh_last_zombie_state")
	if _last_signal_count != 1:
		_fail(16, "last-zombie signal repeated")
		return

	zombie.call("powerup_kill")
	await process_frame
	if int(rounds.call("get_alive")) != 0:
		_fail(17, "last zombie death did not clear alive count")
		return
	if not bool(rounds.call("is_between_rounds")):
		_fail(18, "round did not enter intermission")
		return
	if float(rounds.call("get_round_break_remaining")) <= 0.0:
		_fail(19, "intermission timer missing")
		return
	if int(audio.call("get_round_cue_count")) != cues_before + 2:
		_fail(20, "round-clear cue did not fire")
		return
	if str(audio.call("get_last_round_cue")) != "round_clear":
		_fail(21, "round-clear cue marker wrong")
		return
	print("XZOGOT_ROUND_CLEAR_FEEDBACK_GREEN")
	print("XZOGOT_ROUND_TRANSITION_FLOW_GREEN")

	scene.queue_free()
	await process_frame
	quit(0)
