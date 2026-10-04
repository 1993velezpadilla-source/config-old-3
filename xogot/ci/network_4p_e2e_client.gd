extends SceneTree

const PORT := 18780
const TIMEOUT_MS := 20000

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NETWORK_4P_CLIENT: " + message)
	quit(code)

func _wait(seconds: float) -> void:
	await create_timer(seconds).timeout

func _tag() -> String:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	return args[0] if not args.is_empty() else "client"

func _run() -> void:
	var tag: String = _tag()
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
	var door: Node = scene.get_node_or_null("RearDoor")
	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if network == null or rounds == null or powerups == null or door == null or barricades.is_empty():
		_fail(3, "runtime nodes missing " + tag)
		return

	var err: Error = network.call("join_game", "127.0.0.1", PORT) as Error
	if err != OK:
		_fail(4, "join failed " + tag + " err=" + str(err))
		return
	print("XZOGOT_4P_E2E_CLIENT_JOINING ", tag)

	var deadline: int = Time.get_ticks_msec() + TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		var connected: bool = (
			str(network.call("get_mode")) == "client"
			and int(network.call("get_connected_player_count")) == 4
		)
		var proxies: Array[Node] = get_nodes_in_group("network_remote_player")
		var round_ok: bool = int(rounds.call("get_round")) == 12
		var effects: Dictionary = powerups.call("get_active_effects") as Dictionary
		var effects_ok: bool = effects.has("double_points") and effects.has("insta_kill")
		var door_ok: bool = bool(door.call("was_used"))
		var power_ok: bool = bool(get_meta("power_on", false))
		var barricade_ok: bool = int(barricades[0].call("get_boards")) == 4

		if connected and proxies.size() == 3 and round_ok and effects_ok and door_ok and power_ok and barricade_ok:
			var ids: PackedInt32Array = network.call("get_roster_ids") as PackedInt32Array
			if ids.size() != 4 or not ids.has(1):
				_fail(5, "roster IDs invalid " + tag + " " + str(ids))
				return
			print("XZOGOT_4P_E2E_CLIENT_ROSTER_GREEN ", tag, " ", ids)
			print("XZOGOT_4P_E2E_CLIENT_PROXIES_GREEN ", tag)
			print("XZOGOT_4P_E2E_CLIENT_ROUND_GREEN ", tag)
			print("XZOGOT_4P_E2E_CLIENT_WORLD_GREEN ", tag)
			print("XZOGOT_4P_E2E_CLIENT_EFFECTS_GREEN ", tag)
			# Remain online so the host can verify a stable four-player window.
			await _wait(7.0)
			if str(network.call("get_mode")) != "client":
				_fail(6, "lost session during stability window " + tag)
				return
			print("XZOGOT_4P_E2E_CLIENT_STABLE_GREEN ", tag)
			print("XZOGOT_4P_E2E_CLIENT_GREEN ", tag)
			network.call("leave_game")
			scene.queue_free()
			await process_frame
			quit(0)
			return
		await _wait(0.05)

	_fail(
		7,
		"timeout %s mode=%s roster=%d proxies=%d round=%d door=%s power=%s boards=%d" % [
			tag,
			str(network.call("get_mode")),
			int(network.call("get_connected_player_count")),
			get_nodes_in_group("network_remote_player").size(),
			int(rounds.call("get_round")),
			str(bool(door.call("was_used"))),
			str(bool(get_meta("power_on", false))),
			int(barricades[0].call("get_boards")),
		]
	)
