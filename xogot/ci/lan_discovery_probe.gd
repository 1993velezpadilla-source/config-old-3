extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("LAN_DISCOVERY_PROBE: " + message)
	quit(code)

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
	var discovery: Node = scene.get_node_or_null("NetworkDiscovery")
	if network == null or discovery == null:
		_fail(3, "network/discovery runtime missing")
		return

	const DISCOVERY_PORT := 18781
	const GAME_PORT := 18782
	var find_err: int = int(discovery.call("start_discovery", DISCOVERY_PORT))
	if find_err != OK:
		_fail(4, "discovery bind failed: " + str(find_err))
		return
	var ad_err: int = int(discovery.call(
		"start_advertising",
		GAME_PORT,
		"XZ TEST MATCH",
		"CHURCH",
		DISCOVERY_PORT
	))
	if ad_err != OK:
		_fail(5, "advertising setup failed: " + str(ad_err))
		return
	if not bool(discovery.call("debug_send_beacon_to", "127.0.0.1", DISCOVERY_PORT)):
		_fail(6, "debug loopback beacon send failed")
		return

	var found: bool = false
	for _i in range(120):
		await process_frame
		var sessions: Array = discovery.call("get_discovered_sessions") as Array
		for session_var: Variant in sessions:
			var session := session_var as Dictionary
			if (
				int(session.get("port", 0)) == GAME_PORT
				and int(session.get("max_players", 0)) == 4
				and int(session.get("players", 0)) == 1
				and str(session.get("name", "")) == "XZ TEST MATCH"
			):
				found = true
				break
		if found:
			break
	if not found:
		_fail(7, "loopback LAN beacon was not discovered")
		return
	print("XZOGOT_LAN_BEACON_DISCOVERY_GREEN")

	var best: Dictionary = discovery.call("get_best_session") as Dictionary
	if best.is_empty() or int(best.get("port", 0)) != GAME_PORT:
		_fail(8, "best session selection failed")
		return
	print("XZOGOT_LAN_FIND_MATCH_GREEN")

	discovery.call("stop_discovery")
	discovery.call("stop_advertising")

	# Private hosts must never appear on LAN discovery.
	var private_err: int = int(network.call("host_game", 18783, true))
	if private_err != OK:
		_fail(9, "private host failed: " + str(private_err))
		return
	if bool(discovery.call("is_advertising")):
		_fail(10, "private host advertised itself")
		return
	if not bool(network.call("is_private_session")):
		_fail(11, "private session flag wrong")
		return
	print("XZOGOT_LAN_PRIVATE_HIDDEN_GREEN")
	network.call("leave_game")

	# Public/LAN means discoverable on the local network, not fake global internet.
	var public_err: int = int(network.call("host_game", 18784, false))
	if public_err != OK:
		_fail(12, "public LAN host failed: " + str(public_err))
		return
	if not bool(discovery.call("is_advertising")):
		_fail(13, "public LAN host did not advertise")
		return
	if bool(network.call("is_private_session")):
		_fail(14, "public LAN privacy flag wrong")
		return
	print("XZOGOT_LAN_PUBLIC_ADVERTISE_GREEN")
	network.call("leave_game")
	if bool(discovery.call("is_advertising")):
		_fail(15, "leave_game did not stop LAN advertising")
		return
	print("XZOGOT_LAN_LEAVE_STOPS_ADVERTISE_GREEN")
	print("XZOGOT_LAN_DISCOVERY_SYSTEM_GREEN")

	scene.queue_free()
	await process_frame
	quit(0)
