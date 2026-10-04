extends SceneTree

const URL := "ws://127.0.0.1:18782"
const TIMEOUT_MS := 20000

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("WS_4P_CLIENT: " + message)
	quit(code)

func _wait(seconds: float) -> void:
	await create_timer(seconds).timeout

func _tag() -> String:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	return args[0] if not args.is_empty() else "client"

func _run() -> void:
	var tag := _tag()
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing " + tag)
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame

	var network: Node = scene.get_node_or_null("NetworkManager")
	var rounds: Node = scene.get_node_or_null("RoundManager")
	var powerups: Node = scene.get_node_or_null("PowerUpManager")
	if network == null or rounds == null or powerups == null:
		_fail(3, "runtime missing " + tag)
		return

	var err: Error = network.call("join_websocket_game", URL) as Error
	if err != OK:
		_fail(4, "join failed " + tag + " " + str(err))
		return
	print("XZOGOT_WS_4P_CLIENT_JOINING ", tag)

	var deadline := Time.get_ticks_msec() + TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		var connected := str(network.call("get_mode")) == "client"
		var ids: PackedInt32Array = network.call("get_roster_ids") as PackedInt32Array
		var proxies: Array[Node] = get_nodes_in_group("network_remote_player")
		var effects: Dictionary = powerups.call("get_active_effects") as Dictionary
		var synced := int(rounds.call("get_round")) == 12 and effects.has("double_points") and effects.has("insta_kill")
		if connected and ids.size() == 4 and proxies.size() == 3 and synced:
			if ids.has(1):
				_fail(5, "dedicated authority leaked into client roster " + tag + " " + str(ids))
				return
			if str(network.call("get_transport")) != "websocket":
				_fail(6, "transport not websocket " + tag)
				return
			print("XZOGOT_WS_4P_CLIENT_ROSTER_GREEN ", tag, " ", ids)
			print("XZOGOT_WS_4P_CLIENT_PROXIES_GREEN ", tag)
			print("XZOGOT_WS_4P_CLIENT_STATE_GREEN ", tag)
			await _wait(4.0)
			if str(network.call("get_mode")) != "client":
				_fail(7, "lost relay session " + tag)
				return
			print("XZOGOT_WS_4P_CLIENT_STABLE_GREEN ", tag)
			network.call("leave_game")
			scene.queue_free()
			await process_frame
			print("XZOGOT_WS_4P_CLIENT_GREEN ", tag)
			quit(0)
			return
		await _wait(0.05)

	_fail(8, "timeout %s mode=%s roster=%d proxies=%d round=%d" % [
		tag,
		str(network.call("get_mode")),
		int(network.call("get_connected_player_count")),
		get_nodes_in_group("network_remote_player").size(),
		int(rounds.call("get_round")),
	])
