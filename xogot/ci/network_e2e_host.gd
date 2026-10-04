extends SceneTree

const PORT := 18779
const TIMEOUT_MS := 18000

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NETWORK_E2E_HOST: " + message)
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
	var player: Node = scene.get_node_or_null("Player")
	var door: Node = scene.get_node_or_null("RearDoor")
	var power: Node = scene.get_node_or_null("PowerSwitch")
	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if (
		network == null or rounds == null or powerups == null or player == null
		or door == null or power == null or barricades.is_empty()
	):
		_fail(3, "host runtime nodes missing")
		return

	rounds.set("auto_start", false)
	var err: Error = network.call("host_game", PORT, true) as Error
	if err != OK:
		_fail(4, "host_game failed: " + str(err))
		return

	# Freeze the production round simulator but expose a real authoritative
	# mid-game state for a client that has not connected yet.
	rounds.call("set_dev_no_zombies", true)
	var round_total: int = int(rounds.call("zombies_for_round", 9, 2))
	rounds.call("apply_network_round_state", 9, round_total, 6, 0, 0.0)
	powerups.call("apply_network_effect_state", 25.0, 0.0)
	var drop: Node3D = powerups.call(
		"spawn_powerup",
		"carpenter",
		Vector3(2.0, 0.5, 2.0)
	) as Node3D
	if drop == null:
		_fail(5, "host drop setup failed")
		return

	if not bool(door.call("dev_force_open")):
		_fail(6, "host door setup failed")
		return
	if not bool(power.call("interact", player)):
		_fail(7, "host power setup failed")
		return

	var window: Node = barricades[0]
	window.call("zombie_damage", 126.0)
	if int(window.call("get_boards")) != 3:
		_fail(8, "host barricade setup wrong")
		return

	var anchors: Array[Node] = get_nodes_in_group("zombie_spawn_anchor")
	if anchors.is_empty():
		_fail(9, "host direct zombie anchor missing")
		return
	var zombie := CharacterBody3D.new()
	zombie.name = "E2E_HostZombie"
	zombie.set_script(load("res://scripts/zombie_dummy.gd") as Script)
	zombie.set("health", float(rounds.call("zombie_health_for_round", 9)))
	zombie.call("configure_direct", player as Node3D, anchors[0])
	scene.add_child(zombie)
	zombie.global_position = (anchors[0] as Node3D).global_position
	if int(window.call("get_boards")) != 3:
		_fail(10, "direct zombie mutated barricade during setup")
		return

	print("XZOGOT_E2E_HOST_LISTENING port=", PORT)
	print("XZOGOT_E2E_HOST_PREJOIN_STATE_GREEN")

	var deadline: int = Time.get_ticks_msec() + TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		if int(network.call("get_connected_player_count")) >= 2:
			print("XZOGOT_E2E_HOST_CLIENT_CONNECTED")
			# Keep the host alive long enough for reliable late-join state plus
			# several unreliable session/zombie snapshots.
			await _wait_seconds(8.0)
			print("XZOGOT_E2E_HOST_GREEN")
			network.call("leave_game")
			scene.queue_free()
			await process_frame
			quit(0)
			return
		await _wait_seconds(0.05)

	_fail(11, "client never joined")
