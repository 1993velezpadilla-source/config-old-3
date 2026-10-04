extends SceneTree

const PORT := 18779
const TIMEOUT_MS := 15000

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NETWORK_E2E_CLIENT: " + message)
	quit(code)

func _wait_seconds(seconds: float) -> void:
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
	var door: Node = scene.get_node_or_null("RearDoor")
	var power: Node = scene.get_node_or_null("PowerSwitch")
	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if (
		network == null or rounds == null or powerups == null
		or door == null or power == null or barricades.is_empty()
	):
		_fail(3, "client runtime nodes missing")
		return

	var err: Error = network.call("join_game", "127.0.0.1", PORT) as Error
	if err != OK:
		_fail(4, "join_game failed: " + str(err))
		return
	print("XZOGOT_E2E_CLIENT_JOINING")

	var deadline: int = Time.get_ticks_msec() + TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		var connected: bool = (
			str(network.call("get_mode")) == "client"
			and int(network.call("get_connected_player_count")) >= 2
		)
		var round_ok: bool = int(rounds.call("get_round")) == 9
		var effects: Dictionary = powerups.call("get_active_effects") as Dictionary
		var effects_ok: bool = effects.has("double_points")
		var pickup_ok: bool = int(powerups.call("get_network_pickup_count")) >= 1
		var door_ok: bool = bool(door.call("was_used"))
		var power_ok: bool = bool(get_meta("power_on", false))
		var barricade_ok: bool = int(barricades[0].call("get_boards")) == 3
		var zombie_ok: bool = int(network.call("get_network_zombie_count")) >= 1

		if (
			connected and round_ok and effects_ok and pickup_ok
			and door_ok and power_ok and barricade_ok and zombie_ok
		):
			print("XZOGOT_E2E_CLIENT_ROSTER_GREEN")
			print("XZOGOT_E2E_CLIENT_ROUND_GREEN")
			print("XZOGOT_E2E_CLIENT_POWERUP_GREEN")
			print("XZOGOT_E2E_CLIENT_WORLD_GREEN")
			print("XZOGOT_E2E_CLIENT_ZOMBIE_GREEN")
			print("XZOGOT_E2E_CLIENT_GREEN")
			network.call("leave_game")
			scene.queue_free()
			await process_frame
			quit(0)
			return
		await _wait_seconds(0.05)

	_fail(
		5,
		"late join timeout mode=%s players=%d round=%d pickups=%d zombies=%d door=%s power=%s boards=%d" % [
			str(network.call("get_mode")),
			int(network.call("get_connected_player_count")),
			int(rounds.call("get_round")),
			int(powerups.call("get_network_pickup_count")),
			int(network.call("get_network_zombie_count")),
			str(bool(door.call("was_used"))),
			str(bool(get_meta("power_on", false))),
			int(barricades[0].call("get_boards")),
		]
	)
