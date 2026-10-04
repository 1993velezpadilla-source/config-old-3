extends SceneTree

const PORT := 18782
const TIMEOUT_MS := 22000

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("WS_4P_SERVER: " + message)
	quit(code)

func _wait(seconds: float) -> void:
	await create_timer(seconds).timeout

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame

	var network: Node = scene.get_node_or_null("NetworkManager")
	var rounds: Node = scene.get_node_or_null("RoundManager")
	var powerups: Node = scene.get_node_or_null("PowerUpManager")
	var local_player: Node = scene.get_node_or_null("Player")
	if network == null or rounds == null or powerups == null or local_player == null:
		_fail(3, "runtime missing")
		return

	rounds.set("auto_start", false)
	var err: Error = network.call("host_websocket_dedicated", PORT) as Error
	if err != OK:
		_fail(4, "websocket host failed " + str(err))
		return
	if local_player.is_in_group("player"):
		_fail(5, "dedicated local player still counted")
		return
	if str(network.call("get_transport")) != "websocket" or not bool(network.call("is_dedicated_server")):
		_fail(6, "dedicated transport state wrong")
		return
	print("XZOGOT_WS_4P_SERVER_LISTENING ", PORT)
	print("XZOGOT_WS_DEDICATED_ZERO_HUMANS_GREEN")

	var deadline := Time.get_ticks_msec() + TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		var ids: PackedInt32Array = network.call("get_roster_ids") as PackedInt32Array
		var proxies: Array[Node] = get_nodes_in_group("network_remote_player")
		var players: Array[Node] = get_nodes_in_group("player")
		if ids.size() == 4 and proxies.size() == 4 and players.size() == 4:
			if ids.has(1):
				_fail(7, "authority peer leaked into human roster " + str(ids))
				return
			var total_4p: int = int(rounds.call("zombies_for_round", 12, 4))
			rounds.call("set_dev_no_zombies", true)
			rounds.call("apply_network_round_state", 12, total_4p, 11, 0, 0.0)
			powerups.call("apply_network_effect_state", 18.0, 9.0)
			print("XZOGOT_WS_4P_SERVER_ROSTER_GREEN ", ids)
			print("XZOGOT_WS_4P_SERVER_HUMAN_SLOTS_GREEN 4")
			print("XZOGOT_WS_4P_SERVER_STATE_GREEN")
			await _wait(3.0)
			if int(network.call("get_connected_player_count")) != 4:
				_fail(8, "roster unstable")
				return
			print("XZOGOT_WS_4P_SERVER_STABLE_GREEN")
			await _wait(3.0)
			network.call("leave_game")
			scene.queue_free()
			await process_frame
			print("XZOGOT_WS_4P_SERVER_GREEN")
			quit(0)
			return
		await _wait(0.05)

	_fail(9, "timeout roster=%d proxies=%d players=%d" % [
		int(network.call("get_connected_player_count")),
		get_nodes_in_group("network_remote_player").size(),
		get_nodes_in_group("player").size(),
	])
