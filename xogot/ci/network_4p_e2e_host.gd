extends SceneTree

const PORT := 18780
const TIMEOUT_MS := 22000

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NETWORK_4P_HOST: " + message)
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
	var player: Node = scene.get_node_or_null("Player")
	var door: Node = scene.get_node_or_null("RearDoor")
	var power: Node = scene.get_node_or_null("PowerSwitch")
	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if (
		network == null or rounds == null or powerups == null or player == null
		or door == null or power == null or barricades.is_empty()
	):
		_fail(3, "runtime nodes missing")
		return

	rounds.set("auto_start", false)
	var err: Error = network.call("host_game", PORT, true) as Error
	if err != OK:
		_fail(4, "host_game failed: " + str(err))
		return

	# Deterministic 4-player mid-game state for all three clients.
	rounds.call("set_dev_no_zombies", true)
	var total_4p: int = int(rounds.call("zombies_for_round", 12, 4))
	rounds.call("apply_network_round_state", 12, total_4p, 11, 0, 0.0)
	powerups.call("apply_network_effect_state", 18.0, 9.0)
	if not bool(door.call("dev_force_open")):
		_fail(5, "door setup failed")
		return
	if not bool(power.call("interact", player)):
		_fail(6, "power setup failed")
		return
	var window: Node = barricades[0]
	window.call("zombie_damage", 84.0)
	if int(window.call("get_boards")) != 4:
		_fail(7, "barricade setup wrong")
		return

	print("XZOGOT_4P_E2E_HOST_LISTENING port=", PORT)
	print("XZOGOT_4P_E2E_HOST_PREJOIN_GREEN round_total=", total_4p)

	var deadline: int = Time.get_ticks_msec() + TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		var roster_count: int = int(network.call("get_connected_player_count"))
		var proxies: Array[Node] = get_nodes_in_group("network_remote_player")
		if roster_count == 4 and proxies.size() == 3:
			var ids: PackedInt32Array = network.call("get_roster_ids") as PackedInt32Array
			if ids.size() != 4 or not ids.has(1):
				_fail(8, "host roster IDs invalid: " + str(ids))
				return
			print("XZOGOT_4P_E2E_HOST_ROSTER_GREEN ", ids)
			print("XZOGOT_4P_E2E_HOST_PROXIES_GREEN 3")
			# Let reliable late-join + several unreliable snapshots settle.
			await _wait(6.0)
			if int(network.call("get_connected_player_count")) != 4:
				_fail(9, "client disconnected before stability window")
				return
			print("XZOGOT_4P_E2E_HOST_STABLE_GREEN")
			print("XZOGOT_4P_E2E_HOST_GREEN")
			network.call("leave_game")
			scene.queue_free()
			await process_frame
			quit(0)
			return
		await _wait(0.05)

	_fail(
		10,
		"timeout roster=%d proxies=%d" % [
			int(network.call("get_connected_player_count")),
			get_nodes_in_group("network_remote_player").size(),
		]
	)
