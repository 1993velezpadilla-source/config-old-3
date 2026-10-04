extends SceneTree

const DIRECTORY_URL := "http://127.0.0.1:18790"
const GAME_PORT := 18791

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("PUBLIC_MATCH_PROBE: " + message)
	quit(code)

func _wait_until(check: Callable, seconds: float = 6.0) -> bool:
	var deadline: int = Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if bool(check.call()):
			return true
		await process_frame
		await create_timer(0.03).timeout
	return bool(check.call())

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
	var upnp: Node = scene.get_node_or_null("NetworkUPNP")
	var directory: Node = scene.get_node_or_null("PublicMatchDirectory")
	if network == null or upnp == null or directory == null:
		_fail(3, "network/upnp/directory runtime missing")
		return

	directory.call("configure_base_url", DIRECTORY_URL)
	if not bool(directory.call("is_configured")):
		_fail(4, "directory URL was not accepted")
		return
	if not bool(network.call("is_public_directory_configured")):
		_fail(5, "network manager does not see configured directory")
		return
	print("XZOGOT_PUBLIC_DIRECTORY_CONFIG_PROBE_GREEN")

	# A public host must remain alive even on CI where there is no UPnP gateway.
	var host_err: int = int(network.call("host_game", GAME_PORT, false))
	if host_err != OK:
		_fail(6, "public host failed before reachability: " + str(host_err))
		return
	if not bool(network.call("is_host")):
		_fail(7, "network did not enter host mode")
		return

	# Let the real threaded UPNP attempt resolve or time out. Failure is expected
	# on many CI/router environments and must never take down ENet.
	await _wait_until(func() -> bool: return not bool(upnp.call("is_busy")), 5.0)
	if not bool(network.call("is_host")):
		_fail(8, "UPnP failure took host offline")
		return
	print("XZOGOT_UPNP_FAILSAFE_HOST_GREEN status=", str(upnp.call("get_status")))

	# Deterministic probe mapping; this emits the same success signal used by a
	# real router mapping and therefore exercises automatic directory register.
	if not bool(upnp.call("debug_set_mapping_for_probe", "203.0.113.10", GAME_PORT)):
		_fail(9, "probe mapping setup failed")
		return
	if not await _wait_until(func() -> bool: return bool(directory.call("is_registered")), 5.0):
		_fail(10, "public host did not register after reachable mapping")
		return
	if str(network.call("get_public_endpoint")) != "203.0.113.10:%d" % GAME_PORT:
		_fail(11, "public endpoint wrong: " + str(network.call("get_public_endpoint")))
		return
	print("XZOGOT_PUBLIC_DIRECTORY_REGISTER_GREEN")

	if not bool(network.call("find_public_matches")):
		_fail(12, "internet find request did not start")
		return
	if not await _wait_until(func() -> bool:
		return (network.call("get_public_matches") as Array).size() == 1
	, 5.0):
		_fail(13, "registered public session was not returned")
		return
	var matches: Array = network.call("get_public_matches") as Array
	var match: Dictionary = matches[0] as Dictionary
	if (
		str(match.get("ip", "")) != "203.0.113.10"
		or int(match.get("port", 0)) != GAME_PORT
		or int(match.get("max_players", 0)) != 4
		or int(match.get("protocol", 0)) != 1
	):
		_fail(14, "directory match payload wrong: " + str(match))
		return
	print("XZOGOT_PUBLIC_FIND_MATCH_GREEN")

	var best: Dictionary = directory.call("get_best_match") as Dictionary
	if best.is_empty() or int(best.get("port", 0)) != GAME_PORT:
		_fail(15, "best public match selection failed")
		return
	print("XZOGOT_PUBLIC_BEST_MATCH_GREEN")

	if not bool(directory.call("unregister_public_host")):
		_fail(16, "public unregister request did not start")
		return
	if not await _wait_until(func() -> bool: return not bool(directory.call("is_registered")), 5.0):
		_fail(17, "public unregister did not complete")
		return
	if not bool(directory.call("find_public_matches")):
		_fail(18, "post-delete list request failed")
		return
	if not await _wait_until(func() -> bool:
		return (network.call("get_public_matches") as Array).is_empty()
	, 5.0):
		_fail(19, "deleted session still listed")
		return
	print("XZOGOT_PUBLIC_DIRECTORY_UNREGISTER_GREEN")

	network.call("leave_game")
	if bool(upnp.call("has_mapping")):
		_fail(20, "leave did not clear public mapping state")
		return

	# Private host is never allowed to register globally.
	var private_err: int = int(network.call("host_game", GAME_PORT + 1, true))
	if private_err != OK:
		_fail(21, "private host failed")
		return
	upnp.call("debug_set_mapping_for_probe", "203.0.113.11", GAME_PORT + 1)
	await process_frame
	if bool(directory.call("register_public_host")):
		_fail(22, "private host started public registration")
		return
	if bool(directory.call("is_registered")):
		_fail(23, "private host became directory-visible")
		return
	print("XZOGOT_PUBLIC_PRIVATE_ISOLATION_GREEN")
	network.call("leave_game")

	print("XZOGOT_PUBLIC_MATCHMAKING_CLIENT_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)
